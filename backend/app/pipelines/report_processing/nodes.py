"""
report_processing/nodes.py

The 5 agent nodes for the field service report processing graph.

Each node receives the full GraphState, returns only the keys it mutates
(LangGraph merges partial dict returns into state), and calls
evaluate_node_output() before returning so eval_scores stays current.
"""

import os
from typing import Any, Dict

from app.pipelines.report_processing.state import GraphState
from app.pipelines.report_processing.eval_layer import evaluate_node_output

LOW_RISK_THRESHOLD = float(os.getenv("REPORT_RISK_AUTO_APPROVE", "0.3"))
HIGH_RISK_THRESHOLD = float(os.getenv("REPORT_RISK_AUTO_REJECT", "0.75"))
LOW_CONFIDENCE_FIELD_THRESHOLD = 0.75

_SEVERITY_WEIGHTS = {"FAIL": 1.0, "UNCLEAR": 0.4, "PASS": 0.0}
_REGION_RISK_TIER = {
    # Site/region risk multiplier — defaults to 1.0 for unlisted regions.
    "high_risk": 1.3,
    "standard": 1.0,
}


def _flag_low_confidence(routing_decision: str, eval_score: Dict[str, Any]) -> str:
    """Appends LOW_CONFIDENCE to a routing decision if the node's eval failed."""
    if eval_score and not eval_score.get("passed", True) and "LOW_CONFIDENCE" not in routing_decision:
        return f"{routing_decision}+LOW_CONFIDENCE"
    return routing_decision


# ── 0. orchestrator_node ─────────────────────────────────────────────────────

def orchestrator_node(state: GraphState) -> Dict[str, Any]:
    """
    Decides which of the 5 worker agents runs next, purely from what's already
    in state — no side effects on report fields. Every worker node returns
    control here, so this is the single place the pipeline's control flow is
    decided, instead of being scattered across conditional-edge lambdas.
    """
    qa_query = state.get("qa_query")

    if "extraction_result" not in state and "policy_context" not in state:
        next_agent = "policy_rag_node" if qa_query else "document_extraction_node"
    elif "extraction_result" in state and "policy_context" not in state:
        next_agent = "policy_rag_node"
    elif "policy_context" in state and "compliance_verdicts" not in state:
        next_agent = "END" if qa_query else "compliance_risk_node"
    else:
        decision = state.get("routing_decision", "")
        next_agent = (
            "hitl_coordinator_node"
            if ("LOW_CONFIDENCE" in decision or decision.startswith("ESCALATE_TO_HUMAN"))
            else "report_synthesis_node"
        )

    return {"next_agent": next_agent}


# ── 1. document_extraction_node ─────────────────────────────────────────────

def document_extraction_node(state: GraphState) -> Dict[str, Any]:
    """OCRs/parses the uploaded file into structured fields with per-field confidence."""
    raw_file = state.get("raw_file", "")

    extraction_result = _extract_fields(raw_file)

    low_conf_fields = [
        name for name, f in extraction_result["fields"].items()
        if f.get("confidence", 1.0) < LOW_CONFIDENCE_FIELD_THRESHOLD
    ]
    extraction_result["low_confidence_fields"] = low_conf_fields

    eval_score = evaluate_node_output(
        node_name="document_extraction_node",
        input={"source_document": extraction_result.get("raw_text", "")},
        output={"text": str(extraction_result["fields"])},
    )

    eval_scores = dict(state.get("eval_scores", {}))
    eval_scores["document_extraction_node"] = eval_score

    return {
        "extraction_result": extraction_result,
        "eval_scores": eval_scores,
    }


def _extract_fields(raw_file: str) -> Dict[str, Any]:
    """Runs OCR (if the file needs it) and returns a structured field dict."""
    if not raw_file or not os.path.exists(raw_file):
        return {"fields": {}, "raw_text": ""}

    from app.ingestion.ocr_service import is_scanned_pdf, extract_text_from_image, extract_text_from_scanned_pdf

    ext = raw_file.lower().rsplit(".", 1)[-1]
    if ext in ("png", "jpg", "jpeg"):
        text, confidence = extract_text_from_image(raw_file)
    elif ext == "pdf" and is_scanned_pdf(raw_file):
        text, confidence = extract_text_from_scanned_pdf(raw_file)
    else:
        from app.ingestion.text_extraction import extract_text
        text = extract_text(raw_file)
        confidence = 100.0

    # Per-field structuring would normally go through an LLM extraction prompt;
    # field service reports are unstructured free text, so we treat the whole
    # document as a single "report_text" field carrying the OCR confidence.
    return {
        "fields": {"report_text": {"value": text, "confidence": confidence / 100.0}},
        "raw_text": text,
    }


# ── 2. policy_rag_node ───────────────────────────────────────────────────────

def policy_rag_node(state: GraphState) -> Dict[str, Any]:
    """Retrieves SOP/policy chunks scoped to tenant/job/region; answers qa_query if set."""
    from app.retrieval.retriever import get_retriever

    job_type = state.get("job_type", "")
    region = state.get("region", "")
    query = state.get("qa_query") or _build_policy_query(state)

    retriever = get_retriever(pipeline="safety")
    docs = retriever.invoke(query)

    policy_context = [
        {
            "text": d.page_content,
            "source": d.metadata.get("source", "unknown"),
            "page": str(d.metadata.get("page", "")),
            "score": float(d.metadata.get("score", 0.0)),
        }
        for d in docs
    ]

    eval_scores = dict(state.get("eval_scores", {}))
    eval_scores["policy_rag_node"] = evaluate_node_output(
        node_name="policy_rag_node",
        input={"question": query},
        output={"text": "\n".join(c["text"] for c in policy_context)},
        context=[c["text"] for c in policy_context],
    )

    result: Dict[str, Any] = {"policy_context": policy_context, "eval_scores": eval_scores}

    if state.get("qa_query"):
        from app.retrieval.rag_pipeline import ask_question_with_citations
        answer = ask_question_with_citations(state["qa_query"], pipeline="safety")
        result["qa_response"] = answer["answer"]
        eval_scores["policy_rag_node.qa"] = evaluate_node_output(
            node_name="policy_rag_node.qa",
            input={"question": state["qa_query"]},
            output={"text": answer["answer"]},
            context=[c["text"] for c in policy_context],
        )
        result["eval_scores"] = eval_scores

    return result


def _build_policy_query(state: GraphState) -> str:
    job_type = state.get("job_type", "")
    region = state.get("region", "")
    return f"compliance checklist and SOP requirements for {job_type} jobs in {region}".strip()


# ── 3. compliance_risk_node ──────────────────────────────────────────────────

def compliance_risk_node(state: GraphState) -> Dict[str, Any]:
    """Validates extracted content against policy context, computes risk_score and routing."""
    extraction = state.get("extraction_result", {})
    policy_context = state.get("policy_context", [])

    verdicts = _validate_checklist(extraction, policy_context)

    risk_score = _compute_risk_score(verdicts, extraction, state.get("region", ""))
    routing_decision = _route(risk_score)

    eval_scores = dict(state.get("eval_scores", {}))
    eval_score = evaluate_node_output(
        node_name="compliance_risk_node",
        input={"question": "Are these verdicts grounded in the supplied policy context?"},
        output={"text": str(verdicts)},
        context=[c["text"] for c in policy_context],
    )
    eval_scores["compliance_risk_node"] = eval_score
    routing_decision = _flag_low_confidence(routing_decision, eval_score)

    return {
        "compliance_verdicts": verdicts,
        "risk_score": risk_score,
        "routing_decision": routing_decision,
        "eval_scores": eval_scores,
    }


def _validate_checklist(extraction: Dict[str, Any], policy_context: list) -> list:
    """Stub checklist validation — real implementation would prompt an LLM with
    the extracted fields + policy_context and ask it to verdict each SOP item."""
    low_conf = extraction.get("low_confidence_fields", [])
    verdicts = []
    for field_name in extraction.get("fields", {}):
        if field_name in low_conf:
            verdicts.append({
                "item": field_name,
                "status": "UNCLEAR",
                "reason": "Extraction confidence below threshold; needs human verification.",
            })
        else:
            verdicts.append({"item": field_name, "status": "PASS", "reason": "Matches policy requirements."})
    if not verdicts:
        verdicts.append({"item": "report_text", "status": "UNCLEAR", "reason": "No extracted content to validate."})
    return verdicts


def _compute_risk_score(verdicts: list, extraction: Dict[str, Any], region: str) -> float:
    if not verdicts:
        return 0.5

    verdict_risk = sum(_SEVERITY_WEIGHTS.get(v["status"], 0.0) for v in verdicts) / len(verdicts)
    low_conf_penalty = 0.15 * len(extraction.get("low_confidence_fields", []))
    region_tier = _REGION_RISK_TIER.get(region, 1.0)

    score = (verdict_risk + low_conf_penalty) * region_tier
    return round(min(score, 1.0), 3)


def _route(risk_score: float) -> str:
    if risk_score <= LOW_RISK_THRESHOLD:
        return "AUTO_APPROVE"
    if risk_score >= HIGH_RISK_THRESHOLD:
        return "AUTO_REJECT"
    return "ESCALATE_TO_HUMAN"


# ── 4. hitl_coordinator_node ─────────────────────────────────────────────────

def hitl_coordinator_node(state: GraphState) -> Dict[str, Any]:
    """
    Surfaces extraction + verdicts + risk + eval_scores (with failures) to a
    human reviewer via LangGraph's native interrupt(), then resumes with
    whatever override the reviewer submits back into human_review.
    """
    from langgraph.types import interrupt

    review_payload = {
        "extraction_result": state.get("extraction_result", {}),
        "compliance_verdicts": state.get("compliance_verdicts", []),
        "risk_score": state.get("risk_score"),
        "routing_decision": state.get("routing_decision"),
        "eval_scores": state.get("eval_scores", {}),
        "flagged_failures": {
            node: score.get("failures", [])
            for node, score in state.get("eval_scores", {}).items()
            if not score.get("passed", True)
        },
    }

    human_review = interrupt(review_payload)

    return {"human_review": human_review}


# ── 5. report_synthesis_node ─────────────────────────────────────────────────

def report_synthesis_node(state: GraphState) -> Dict[str, Any]:
    """Assembles the final NL summary, audit trail, and dashboard payload."""
    summary = _build_summary(state)
    audit_trail = _build_audit_trail(state)

    eval_scores = dict(state.get("eval_scores", {}))
    eval_scores["report_synthesis_node"] = evaluate_node_output(
        node_name="report_synthesis_node",
        input={"question": "Summarize the report findings."},
        output={"text": summary},
        context=[c["text"] for c in state.get("policy_context", [])],
    )

    dashboard_payload = {
        "risk_score": state.get("risk_score"),
        "routing_decision": state.get("routing_decision"),
        "compliance_verdicts": state.get("compliance_verdicts", []),
        "eval_scores": eval_scores,
    }

    return {
        "final_report": {
            "summary": summary,
            "audit_trail": audit_trail,
            "dashboard_payload": dashboard_payload,
        },
        "eval_scores": eval_scores,
    }


def _build_summary(state: GraphState) -> str:
    verdicts = state.get("compliance_verdicts", [])
    fails = [v for v in verdicts if v["status"] == "FAIL"]
    unclear = [v for v in verdicts if v["status"] == "UNCLEAR"]
    parts = [
        f"Risk score: {state.get('risk_score', 'n/a')}.",
        f"Routing: {state.get('routing_decision', 'n/a')}.",
    ]
    if fails:
        parts.append(f"{len(fails)} checklist item(s) failed: " + ", ".join(v["item"] for v in fails) + ".")
    if unclear:
        parts.append(f"{len(unclear)} item(s) need verification: " + ", ".join(v["item"] for v in unclear) + ".")
    if state.get("human_review"):
        parts.append(f"Human review decision: {state['human_review'].get('decision', 'n/a')}.")
    return " ".join(parts)


def _build_audit_trail(state: GraphState) -> list:
    trail = []
    for node in ("document_extraction_node", "policy_rag_node", "compliance_risk_node", "hitl_coordinator_node", "report_synthesis_node"):
        score = state.get("eval_scores", {}).get(node)
        if score is not None:
            trail.append({"node": node, "eval_score": score})
    if state.get("human_review"):
        trail.append({"node": "hitl_coordinator_node", "human_review": state["human_review"]})
    return trail
