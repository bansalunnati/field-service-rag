"""
pipelines/safety_pipeline.py

Handles queries against Safety & Compliance documents.

Uses standard similarity retrieval suited for SOPs, regulations,
hazardous material procedures, and emergency protocols.

Renamed from: policy_pipeline.py  (Phase 1)
"""

from app.retrieval.rag_pipeline import ask_question_with_citations
from typing import List, Dict, Any


def run(question: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Similarity retrieval for safety policies and compliance documents.

    If no relevant documents are found, returns a clear, actionable message
    rather than a hallucinated answer.

    Args:
        question : The user's query.
        history  : Recent conversation turns for multi-turn memory.

    Returns:
        dict with keys 'answer' (str) and 'citations' (list).
    """
    result = ask_question_with_citations(
        question=question,
        pipeline="safety",
        history=history,
    )

    if not result.get("citations"):
        result.setdefault(
            "answer",
            (
                "No matching safety or compliance documentation was found for your query. "
                "Try rephrasing using regulation names, procedure titles, or hazard categories, "
                "or contact your administrator if the relevant policy document has not been uploaded yet."
            )
        )

    return result
