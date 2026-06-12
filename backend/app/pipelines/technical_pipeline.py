"""
pipelines/technical_pipeline.py
Handles queries against technical manuals.
Uses hybrid dense + BM25 retrieval via retrieve_with_hybrid().
"""

from app.retrieval.retriever import retrieve_with_hybrid
from app.retrieval.rag_pipeline import ask_question_with_citations
from typing import List, Dict, Any


def run(question: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Hybrid retrieval (dense + BM25) suited for part numbers,
    equipment specs, and service procedures.
    """
    docs = retrieve_with_hybrid(question, pipeline="technical", top_k=6)

    if not docs:
        return {
            "answer": "I could not find that information in the technical manuals.",
            "citations": [],
        }

    return ask_question_with_citations(
        question=question,
        pipeline="technical",
        history=history,
    )
