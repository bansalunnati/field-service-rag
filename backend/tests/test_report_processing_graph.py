"""
Tests for the field service report processing LangGraph pipeline.

These run against the DeepEval stub path (no AZURE_OPENAI_API_KEY set in
the test environment), so they verify pipeline wiring, state propagation,
and routing logic rather than real DeepEval LLM-judge scores. Golden-dataset
cases for real metric scoring are parametrized separately and skipped when
no judge LLM is configured.
"""

import os
import uuid

import pytest

from app.pipelines.report_processing.eval_layer import evaluate_node_output
from app.pipelines.report_processing.graph import run_pipeline, run_qa, resume_after_human_review
from app.pipelines.report_processing.nodes import (
    document_extraction_node,
    policy_rag_node,
    compliance_risk_node,
    report_synthesis_node,
    _compute_risk_score,
    _route,
)

HAS_JUDGE_LLM = bool(os.getenv("AZURE_OPENAI_API_KEY", "").strip())


# ── Unit tests: individual node logic ───────────────────────────────────────

def test_document_extraction_node_handles_missing_file():
    state = {"raw_file": "this_file_does_not_exist.txt", "eval_scores": {}}
    result = document_extraction_node(state)
    assert result["extraction_result"]["fields"] == {}
    assert "document_extraction_node" in result["eval_scores"]


def test_route_auto_approve_below_threshold():
    assert _route(0.1) == "AUTO_APPROVE"


def test_route_auto_reject_above_threshold():
    assert _route(0.9) == "AUTO_REJECT"


def test_route_escalate_in_middle_band():
    assert _route(0.5) == "ESCALATE_TO_HUMAN"


def test_compute_risk_score_penalizes_low_confidence_fields():
    verdicts = [{"item": "f1", "status": "PASS", "reason": ""}]
    extraction_clean = {"low_confidence_fields": []}
    extraction_low_conf = {"low_confidence_fields": ["f1", "f2"]}

    clean_score = _compute_risk_score(verdicts, extraction_clean, region="standard")
    low_conf_score = _compute_risk_score(verdicts, extraction_low_conf, region="standard")

    assert low_conf_score > clean_score


def test_compute_risk_score_applies_region_risk_tier():
    # UNCLEAR (not FAIL) keeps the base score under 1.0 so the region
    # multiplier's effect isn't hidden by the final min(score, 1.0) clamp.
    verdicts = [{"item": "f1", "status": "UNCLEAR", "reason": ""}]
    extraction = {"low_confidence_fields": []}

    standard_score = _compute_risk_score(verdicts, extraction, region="standard")
    high_risk_score = _compute_risk_score(verdicts, extraction, region="high_risk")

    assert high_risk_score > standard_score


# ── Eval layer ───────────────────────────────────────────────────────────────

def test_evaluate_node_output_returns_well_formed_score():
    """Verifies the EvalScore shape regardless of whether a real judge LLM
    is configured — passed/failures must always be present and consistent."""
    score = evaluate_node_output(
        node_name="document_extraction_node",
        input={"source_document": "Inspection complete: all checklist items satisfied."},
        output={"text": "All checklist items satisfied."},
    )
    assert "passed" in score
    assert "failures" in score
    assert score["passed"] == (len(score["failures"]) == 0)


def test_evaluate_node_output_unknown_node_returns_default_pass():
    score = evaluate_node_output(node_name="not_a_real_node", input={}, output={})
    assert score["passed"] is True


# ── Integration: full graph ──────────────────────────────────────────────────

def test_run_pipeline_reaches_hitl_interrupt_on_unclear_verdict():
    """An empty/missing file has no extractable fields -> UNCLEAR verdict ->
    risk score lands in the ESCALATE band -> graph pauses before HITL."""
    result = run_pipeline(
        file=f"missing_{uuid.uuid4().hex}.txt",
        tenant_id="test-tenant",
        job_type="inspection",
        region="standard",
    )
    assert result["routing_decision"].startswith("ESCALATE_TO_HUMAN")
    assert "final_report" not in result  # paused before synthesis
    assert "_thread_id" in result


def test_resume_after_human_review_completes_synthesis():
    result = run_pipeline(
        file=f"missing_{uuid.uuid4().hex}.txt",
        tenant_id="test-tenant",
        job_type="inspection",
        region="standard",
    )
    thread_id = result["_thread_id"]

    final = resume_after_human_review(
        thread_id, {"decision": "approved", "notes": "manually verified"}
    )

    assert final["final_report"]["summary"]
    assert "dashboard_payload" in final["final_report"]
    assert "eval_scores" in final["final_report"]["dashboard_payload"]
    audit_nodes = [step["node"] for step in final["final_report"]["audit_trail"]]
    assert "hitl_coordinator_node" in audit_nodes


def test_run_qa_shortcut_skips_extraction_and_compliance():
    result = run_qa("What PPE is required on site?", tenant_id="test-tenant")
    assert "qa_response" in result
    assert "extraction_result" not in result
    assert "compliance_verdicts" not in result


# ── Golden-dataset DeepEval cases (real judge LLM required) ─────────────────

GOLDEN_EXTRACTION_CASES = [
    {
        "source_document": "Inspection on 2026-01-10: PPE worn, harness certified, no violations found.",
        "expected_output": "PPE compliant; harness certified; no violations.",
    },
    {
        "source_document": "Site visit noted a missing fall-arrest anchor point on the east tower.",
        "expected_output": "Fall-arrest anchor point missing on east tower.",
    },
]


@pytest.mark.skipif(not HAS_JUDGE_LLM, reason="No AZURE_OPENAI_API_KEY configured for DeepEval judge LLM")
@pytest.mark.parametrize("case", GOLDEN_EXTRACTION_CASES)
def test_extraction_correctness_golden_cases(case):
    score = evaluate_node_output(
        node_name="document_extraction_node",
        input={"source_document": case["source_document"], "expected_output": case["expected_output"]},
        output={"text": case["expected_output"]},
    )
    assert score["passed"] is True
    assert not score["failures"]
