"""
report_processing/graph.py

Wires 1 orchestrator + 5 worker nodes into a LangGraph StateGraph. Every
worker returns control to orchestrator_node, which decides what runs next
purely from state (risk score / LOW_CONFIDENCE eval flags) — that's the
graph's single source of routing truth instead of routing logic scattered
across edge lambdas. A SQLite checkpointer persists HITL interrupts, and
retry policies cover the extraction and RAG nodes.

Graph shape:

    START -> orchestrator
        -> document_extraction -> orchestrator
        -> policy_rag           -> orchestrator
        -> compliance_risk      -> orchestrator
            -> AUTO_APPROVE / AUTO_REJECT (clean)  -> report_synthesis -> END
            -> ESCALATE_TO_HUMAN                   -> hitl_coordinator -> report_synthesis -> END
            -> any *_LOW_CONFIDENCE flag            -> hitl_coordinator -> report_synthesis -> END

    Q&A shortcut: if qa_query is set on the input state, orchestrator sends
    the run straight to policy_rag -> orchestrator -> END, skipping
    document_extraction and compliance_risk entirely.
"""

import os
import sqlite3
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.types import RetryPolicy

from app.pipelines.report_processing.state import GraphState, new_state
from app.pipelines.report_processing.nodes import (
    orchestrator_node,
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


_NEXT_AGENT_DESTINATIONS = {
    "document_extraction_node": "document_extraction_node",
    "policy_rag_node": "policy_rag_node",
    "compliance_risk_node": "compliance_risk_node",
    "hitl_coordinator_node": "hitl_coordinator_node",
    "report_synthesis_node": "report_synthesis_node",
    "END": END,
}


def build_graph():
    graph = StateGraph(GraphState)

    extraction_retry = RetryPolicy(max_attempts=3)
    rag_retry = RetryPolicy(max_attempts=3)

    graph.add_node("orchestrator_node", orchestrator_node)
    graph.add_node("document_extraction_node", document_extraction_node, retry_policy=extraction_retry)
    graph.add_node("policy_rag_node", policy_rag_node, retry_policy=rag_retry)
    graph.add_node("compliance_risk_node", compliance_risk_node)
    graph.add_node("hitl_coordinator_node", hitl_coordinator_node)
    graph.add_node("report_synthesis_node", report_synthesis_node)

    graph.add_edge(START, "orchestrator_node")

    graph.add_conditional_edges(
        "orchestrator_node",
        lambda state: state["next_agent"],
        _NEXT_AGENT_DESTINATIONS,
    )

    graph.add_edge("document_extraction_node", "orchestrator_node")
    graph.add_edge("policy_rag_node", "orchestrator_node")
    graph.add_edge("compliance_risk_node", "orchestrator_node")

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
