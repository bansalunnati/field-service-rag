"""
pipelines/field_reports_pipeline.py

Handles queries against Field Investigation Reports.

Uses parent-child retrieval: searches small child chunks for precision,
then expands to larger parent chunks to preserve full context.

Renamed from: general_pipeline.py  (Phase 1)
"""

from app.retrieval.retriever import retrieve_with_parent_expansion
from app.retrieval.rag_pipeline import ask_question_with_citations
from typing import List, Dict, Any


def run(question: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Parent-child retrieval suited for field investigation reports and general documents.

    If no relevant documents are found, returns a clear, actionable message
    rather than a hallucinated answer.

    Args:
        question : The user's query.
        history  : Recent conversation turns for multi-turn memory.

    Returns:
        dict with keys 'answer' (str) and 'citations' (list).
    """
    docs = retrieve_with_parent_expansion(question, pipeline="field_reports", top_k=5)

    if not docs:
        return {
            "answer": (
                "No matching field reports or documents were found for your query. "
                "Reports submitted by your team will appear here once they have been approved. "
                "If you expected to find a specific report, check its status under My Reports "
                "or contact your administrator."
            ),
            "citations": [],
        }

    return ask_question_with_citations(
        question=question,
        pipeline="field_reports",
        history=history,
    )
