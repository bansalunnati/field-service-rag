"""
pipelines/equipment_pipeline.py

Handles queries against Equipment & Asset documents.

Uses hybrid BM25 + dense retrieval for high-precision lookup of part numbers,
torque specs, maintenance schedules, and service procedures.

Renamed from: technical_pipeline.py  (Phase 1)
"""

from app.retrieval.retriever import retrieve_with_hybrid
from app.retrieval.rag_pipeline import ask_question_with_citations
from typing import List, Dict, Any


def run(question: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Hybrid retrieval suited for technical specifications and equipment manuals.

    If no relevant documents are found, returns a clear, actionable message
    rather than a hallucinated answer.

    Args:
        question : The user's query.
        history  : Recent conversation turns for multi-turn memory.

    Returns:
        dict with keys 'answer' (str) and 'citations' (list).
    """
    docs = retrieve_with_hybrid(question, pipeline="equipment", top_k=6)

    if not docs:
        return {
            "answer": (
                "No matching equipment or asset documentation was found for your query. "
                "Try rephrasing with a part number, equipment name, or maintenance task, "
                "or contact your administrator if you believe the relevant document has not been uploaded yet."
            ),
            "citations": [],
        }

    return ask_question_with_citations(
        question=question,
        pipeline="equipment",
        history=history,
    )
