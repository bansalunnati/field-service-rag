"""
pipelines/policy_pipeline.py
Handles queries against policy and compliance documents.
Uses standard similarity retrieval — extends your existing policy_bot behaviour.
"""

from app.retrieval.retriever import get_retriever
from app.retrieval.rag_pipeline import ask_question_with_citations
from typing import List, Dict, Any


def run(question: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Simple similarity retrieval, same as your original policy_bot.
    Now adds citations and chat history support.
    """
    return ask_question_with_citations(
        question=question,
        pipeline="policy",
        history=history,
    )
