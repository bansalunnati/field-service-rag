"""
report_processing/state.py

Shared LangGraph state for the field service report processing pipeline.

GraphState is the TypedDict passed between all 5 nodes. ReportStateModel
is a Pydantic model used to validate a GraphState dict at the pipeline's
entry/exit boundaries (run_pipeline / run_qa) — LangGraph nodes themselves
operate on the plain TypedDict since that's what StateGraph expects.
"""

from typing import Any, Dict, List, Literal, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field

RoutingDecision = Literal["AUTO_APPROVE", "ESCALATE_TO_HUMAN", "AUTO_REJECT"]
VerdictStatus = Literal["PASS", "FAIL", "UNCLEAR"]


class ExtractedField(TypedDict, total=False):
    value: Any
    confidence: float  # 0-1 OCR/extraction confidence for this field


class ExtractionResult(TypedDict, total=False):
    fields: Dict[str, ExtractedField]
    raw_text: str
    low_confidence_fields: List[str]


class PolicyChunk(TypedDict, total=False):
    text: str
    source: str
    page: str
    score: float


class ComplianceVerdict(TypedDict):
    item: str
    status: VerdictStatus
    reason: str


class EvalScore(TypedDict, total=False):
    correctness: float
    confidence: float
    faithfulness: float
    passed: bool
    failures: List[str]


class HumanReview(TypedDict, total=False):
    decision: str  # "approved" | "rejected" | "corrected"
    corrected_values: Dict[str, Any]
    notes: str


class FinalReport(TypedDict, total=False):
    summary: str
    audit_trail: List[Dict[str, Any]]
    dashboard_payload: Dict[str, Any]


class GraphState(TypedDict, total=False):
    # ── Inputs ──────────────────────────────────────────────────────────────
    raw_file: str  # path to the uploaded file
    tenant_id: str
    job_type: str
    region: str

    # ── Per-node outputs ────────────────────────────────────────────────────
    extraction_result: ExtractionResult
    policy_context: List[PolicyChunk]
    compliance_verdicts: List[ComplianceVerdict]
    risk_score: float
    routing_decision: str  # RoutingDecision, optionally suffixed "+LOW_CONFIDENCE"
    human_review: HumanReview
    final_report: FinalReport

    # ── Q&A shortcut ────────────────────────────────────────────────────────
    qa_query: str
    qa_response: str

    # ── Evaluation layer ────────────────────────────────────────────────────
    eval_scores: Dict[str, EvalScore]


class ReportStateModel(BaseModel):
    """Pydantic validation wrapper for GraphState at pipeline boundaries."""

    model_config = ConfigDict(extra="allow")

    raw_file: Optional[str] = None
    tenant_id: str
    job_type: Optional[str] = None
    region: Optional[str] = None

    extraction_result: Optional[Dict[str, Any]] = None
    policy_context: List[Dict[str, Any]] = Field(default_factory=list)
    compliance_verdicts: List[Dict[str, Any]] = Field(default_factory=list)
    risk_score: Optional[float] = None
    routing_decision: Optional[str] = None
    human_review: Optional[Dict[str, Any]] = None
    final_report: Optional[Dict[str, Any]] = None

    qa_query: Optional[str] = None
    qa_response: Optional[str] = None

    eval_scores: Dict[str, Any] = Field(default_factory=dict)


def new_state(
    tenant_id: str,
    job_type: str = "",
    region: str = "",
    raw_file: str = "",
    qa_query: str = "",
) -> GraphState:
    """Builds an initial GraphState dict for run_pipeline / run_qa entrypoints."""
    state: GraphState = {
        "tenant_id": tenant_id,
        "job_type": job_type,
        "region": region,
        "raw_file": raw_file,
        "eval_scores": {},
    }
    if qa_query:
        state["qa_query"] = qa_query
    return state
