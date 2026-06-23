"""
report_processing/eval_layer.py

DeepEval evaluation layer for the report processing pipeline.

evaluate_node_output() is called at the end of every node. It runs the
metrics relevant to that node's output, writes the result into
state["eval_scores"][node_name], and never raises — a failed metric just
gets recorded so the routing logic can decide to escalate to HITL.

Local dev without an LLM judge configured (no AZURE_OPENAI_API_KEY) falls
back to a stub evaluator that always "passes", mirroring the stub pattern
in app/llm/llm_config.py — this keeps the graph runnable without API keys
while making it obvious (via the stub's metadata) that real scoring isn't
happening.
"""

import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from app.pipelines.report_processing.state import EvalScore

load_dotenv()

_AZURE_KEY = os.getenv("AZURE_OPENAI_API_KEY", "").strip()

# Metric name -> threshold, per the spec table.
THRESHOLDS = {
    "answer_relevancy": 0.8,
    "faithfulness": 0.85,
    "hallucination": 0.1,  # this one is a ceiling, not a floor
    "contextual_precision": 0.75,
    "contextual_recall": 0.75,
    "extraction_correctness": 0.85,
}

# Which metrics apply to which node. Drives which DeepEval metrics run.
NODE_METRICS = {
    "document_extraction_node": ["extraction_correctness", "hallucination"],
    "policy_rag_node": ["contextual_precision", "contextual_recall"],
    "policy_rag_node.qa": ["answer_relevancy", "faithfulness"],
    "compliance_risk_node": ["faithfulness"],
    "report_synthesis_node": ["answer_relevancy", "faithfulness", "hallucination"],
}

_IS_CEILING_METRIC = {"hallucination"}


def _passes(metric: str, score: float) -> bool:
    threshold = THRESHOLDS[metric]
    if metric in _IS_CEILING_METRIC:
        return score <= threshold
    return score >= threshold


def _get_deepeval_model():
    """Builds a DeepEval-compatible model wrapper around the app's configured LLM."""
    from app.llm.llm_config import llm
    from deepeval.models.base_model import DeepEvalBaseLLM

    class _LangChainDeepEvalModel(DeepEvalBaseLLM):
        def load_model(self):
            return llm

        def generate(self, prompt: str) -> str:
            return llm.invoke(prompt).content

        async def a_generate(self, prompt: str) -> str:
            return self.generate(prompt)

        def get_model_name(self) -> str:
            return "app-configured-llm"

    return _LangChainDeepEvalModel()


def _stub_score(metrics: List[str]) -> EvalScore:
    """No LLM judge configured — record a passing stub score, not a real evaluation."""
    return {
        "correctness": 1.0,
        "confidence": 1.0,
        "faithfulness": 1.0,
        "passed": True,
        "failures": [],
        "stub": True,  # marks this as not a real DeepEval run
    }


def evaluate_node_output(
    node_name: str,
    input: Dict[str, Any],
    output: Dict[str, Any],
    context: Optional[List[str]] = None,
    metrics: Optional[List[str]] = None,
) -> EvalScore:
    """
    Scores a node's output with the DeepEval metrics relevant to it.

    Args:
        node_name : key under which the result is stored (e.g. "document_extraction_node",
                    or "policy_rag_node.qa" for the Q&A branch of policy_rag_node).
        input     : the question/source content the output should be judged against
                    (e.g. {"question": ..., "source_document": ...}).
        output    : the actual text/JSON the node produced.
        context   : retrieval context chunks, required for contextual/faithfulness metrics.
        metrics   : override which metrics run; defaults to NODE_METRICS[node_name].

    Returns:
        EvalScore dict — never raises, even if DeepEval itself errors.
    """
    metric_names = metrics if metrics is not None else NODE_METRICS.get(node_name, [])
    if not metric_names:
        return {"correctness": 1.0, "confidence": 1.0, "faithfulness": 1.0, "passed": True, "failures": []}

    if not _AZURE_KEY:
        return _stub_score(metric_names)

    try:
        return _run_deepeval(node_name, input, output, context or [], metric_names)
    except Exception as exc:  # DeepEval/network failure must not crash the pipeline
        return {
            "correctness": 0.0,
            "confidence": 0.0,
            "faithfulness": 0.0,
            "passed": False,
            "failures": [f"eval_error: {exc}"],
        }


def _run_deepeval(
    node_name: str,
    input: Dict[str, Any],
    output: Dict[str, Any],
    context: List[str],
    metric_names: List[str],
) -> EvalScore:
    from deepeval import evaluate
    from deepeval.test_case import LLMTestCase
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        FaithfulnessMetric,
        HallucinationMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        GEval,
    )
    from deepeval.test_case import LLMTestCaseParams

    model = _get_deepeval_model()
    actual_output = output.get("text") or str(output)
    # Hallucination/GEval require non-None context; fall back to the source
    # document itself when no retrieval context was supplied (e.g. extraction node).
    effective_context = context or [input.get("source_document", "") or input.get("question", "")]
    test_case = LLMTestCase(
        input=input.get("question") or input.get("source_document", ""),
        actual_output=actual_output,
        retrieval_context=effective_context,
        context=effective_context,
        expected_output=input.get("expected_output"),
    )

    metric_objs = []
    for name in metric_names:
        if name == "answer_relevancy":
            metric_objs.append(AnswerRelevancyMetric(threshold=THRESHOLDS[name], model=model))
        elif name == "faithfulness":
            metric_objs.append(FaithfulnessMetric(threshold=THRESHOLDS[name], model=model))
        elif name == "hallucination":
            metric_objs.append(HallucinationMetric(threshold=THRESHOLDS[name], model=model))
        elif name == "contextual_precision":
            metric_objs.append(ContextualPrecisionMetric(threshold=THRESHOLDS[name], model=model))
        elif name == "contextual_recall":
            metric_objs.append(ContextualRecallMetric(threshold=THRESHOLDS[name], model=model))
        elif name == "extraction_correctness":
            metric_objs.append(
                GEval(
                    name="ExtractionCorrectness",
                    criteria="Does the actual_output's structured JSON faithfully and accurately "
                    "match the facts present in the input source document, without inventing "
                    "or omitting fields?",
                    evaluation_params=[
                        LLMTestCaseParams.INPUT,
                        LLMTestCaseParams.ACTUAL_OUTPUT,
                    ],
                    threshold=THRESHOLDS[name],
                    model=model,
                )
            )

    failures = []
    scores = {}
    for metric, name in zip(metric_objs, metric_names):
        metric.measure(test_case)
        scores[name] = metric.score
        if not _passes(name, metric.score):
            failures.append(f"{name}={metric.score:.2f}")

    correctness = scores.get("extraction_correctness", scores.get("answer_relevancy", 1.0))
    faithfulness = scores.get("faithfulness", 1.0)
    # Normalize all scores to "higher is better" before combining into one
    # confidence figure — hallucination is a ceiling metric (lower is better).
    normalized = [
        (1.0 - v) if name in _IS_CEILING_METRIC else v
        for name, v in scores.items()
    ]
    confidence = min(normalized) if normalized else 1.0

    return {
        "correctness": correctness,
        "confidence": confidence,
        "faithfulness": faithfulness,
        "passed": len(failures) == 0,
        "failures": failures,
    }
