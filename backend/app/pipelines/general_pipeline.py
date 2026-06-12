"""
pipelines/general_pipeline.py
Handles general queries and FAQs.
Uses parent-child retrieval — fetches small child chunks
for precision, then expands to larger parent chunks for context.
"""

from app.retrieval.retriever import retrieve_with_parent_expansion
from app.retrieval.rag_pipeline import ask_question_with_citations
from typing import List, Dict, Any


def run(question: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Parent-child retrieval suited for general guides and FAQs.
    """
    docs = retrieve_with_parent_expansion(question, pipeline="general", top_k=5)

    if not docs:
        return {
            "answer": "I could not find that information in the available documents.",
            "citations": [],
        }

    return ask_question_with_citations(
        question=question,
        pipeline="general",
        history=history,
    )
