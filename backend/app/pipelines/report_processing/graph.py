"""
report_processing/graph.py

Wires the 5 nodes into a LangGraph StateGraph with conditional routing on
routing_decision / LOW_CONFIDENCE eval flags, a SQLite checkpointer for
HITL persistence, and retry policies on the extraction and RAG nodes.

Graph shape:

    START -> document_extraction -> policy_rag -> compliance_risk
        -> AUTO_APPROVE / AUTO_REJECT (clean)        -> report_synthesis -> END
        -> ESCALATE_TO_HUMAN                         -> hitl_coordinator -> report_synthesis -> END
        -> any *_LOW_CONFIDENCE flag                 -> hitl_coordinator -> report_synthesis -> END

    Q&A shortcut: if qa_query is set on the input state, document_extraction
    is skipped and the graph goes straight to policy_rag -> END.
"""

import os
import sqlite3
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.types import RetryPolicy

from app.pipelines.report_processing.state import GraphState, new_state
from app.pipelines.report_processing.nodes import (
    document_extraction_node,
    policy_rag_node,
    compliance_risk_node,
    hitl_coordinator_node,
    report_synthesis_node,
)

CHECKPOINT_DB_PATH = os.getenv(
    "REPORT_PIPELINE_CHECKPOINT_DB",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "report_pipeline_checkpoints.sqlite"),
)


def _get_checkpointer():
    """SQLite-backed checkpointer so interrupt()'d HITL state survives process restarts."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    os.makedirs(os.path.dirname(CHECKPOINT_DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
    return SqliteSaver(conn)


def _route_after_extraction(state: GraphState) -> str:
    """Q&A shortcut: skip extraction/compliance entirely if qa_query is set."""
    return "policy_rag_qa_only" if state.get("qa_query") else "policy_rag"


def _route_after_compliance(state: GraphState) -> str:
    decision = state.get("routing_decision", "")
    if "LOW_CONFIDENCE" in decision or decision.startswith("ESCALATE_TO_HUMAN"):
        return "hitl_coordinator"
    return "report_synthesis"


def build_graph():
    graph = StateGraph(GraphState)

    extraction_retry = RetryPolicy(max_attempts=3)
    rag_retry = RetryPolicy(max_attempts=3)

    graph.add_node("document_extraction_node", document_extraction_node, retry_policy=extraction_retry)
    graph.add_node("policy_rag_node", policy_rag_node, retry_policy=rag_retry)
    graph.add_node("compliance_risk_node", compliance_risk_node)
    graph.add_node("hitl_coordinator_node", hitl_coordinator_node)
    graph.add_node("report_synthesis_node", report_synthesis_node)

    graph.add_conditional_edges(
        START,
        lambda state: "qa_shortcut" if state.get("qa_query") else "full_pipeline",
        {"qa_shortcut": "policy_rag_node", "full_pipeline": "document_extraction_node"},
    )

    graph.add_edge("document_extraction_node", "policy_rag_node")

    graph.add_conditional_edges(
        "policy_rag_node",
        lambda state: "qa_end" if state.get("qa_query") else "continue",
        {"qa_end": END, "continue": "compliance_risk_node"},
    )

    graph.add_conditional_edges(
        "compliance_risk_node",
        _route_after_compliance,
        {"hitl_coordinator": "hitl_coordinator_node", "report_synthesis": "report_synthesis_node"},
    )

    graph.add_edge("hitl_coordinator_node", "report_synthesis_node")
    graph.add_edge("report_synthesis_node", END)

    return graph.compile(checkpointer=_get_checkpointer(), interrupt_before=["hitl_coordinator_node"])


_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


# ── Public entrypoints ───────────────────────────────────────────────────────

def run_pipeline(
    file: str,
    tenant_id: str,
    job_type: str = "",
    region: str = "",
    thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Runs the full extraction -> policy_rag -> compliance_risk pipeline.

    If compliance_risk routes to HITL (ESCALATE_TO_HUMAN or a LOW_CONFIDENCE
    eval flag), execution stops at the interrupt and this returns the partial
    state with __interrupt__ populated — call resume_after_human_review()
    with the same thread_id once a reviewer has made a decision.
    """
    graph = get_compiled_graph()
    thread_id = thread_id or f"{tenant_id}:{os.urandom(4).hex()}"
    config = {"configurable": {"thread_id": thread_id}}

    state = new_state(tenant_id=tenant_id, job_type=job_type, region=region, raw_file=file)
    result = graph.invoke(state, config=config)
    result["_thread_id"] = thread_id
    return result


def resume_after_human_review(thread_id: str, human_review: Dict[str, Any]) -> Dict[str, Any]:
    """Resumes a graph paused at hitl_coordinator_node's interrupt() with the reviewer's decision."""
    from langgraph.types import Command

    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(Command(resume=human_review), config=config)
    result["_thread_id"] = thread_id
    return result


def run_qa(query: str, tenant_id: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
    """Q&A shortcut entrypoint: runs only policy_rag_node and returns qa_response."""
    graph = get_compiled_graph()
    thread_id = thread_id or f"{tenant_id}:qa:{os.urandom(4).hex()}"
    config = {"configurable": {"thread_id": thread_id}}

    state = new_state(tenant_id=tenant_id, qa_query=query)
    result = graph.invoke(state, config=config)
    result["_thread_id"] = thread_id
    return result
