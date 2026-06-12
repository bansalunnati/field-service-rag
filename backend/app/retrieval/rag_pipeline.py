import json
import re
from typing import List, Dict, Any, Optional

from app.retrieval.retriever import (
    get_retriever,
    retrieve_with_hybrid,
    retrieve_with_parent_expansion,
)
from app.llm.llm_config import llm


def ask_question(question: str, pipeline: str = "policy") -> str:
    """
    Drop-in replacement for your original ask_question(question).
    Still returns a plain string so policy_bot.py keeps working unchanged.
    Now uses the correct pipeline collection.
    """
    result = ask_question_with_citations(question, pipeline=pipeline)
    return result["answer"]


def ask_question_with_citations(
    question: str,
    pipeline: str = "policy",
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    NEW — full RAG with citations and chat history.
    Called by the FastAPI chat endpoint.
    Returns: {"answer": str, "citations": [...]}
    """
    # Choose retrieval strategy per pipeline
    if pipeline == "technical":
        docs = retrieve_with_hybrid(question, pipeline=pipeline)
    elif pipeline == "general" or pipeline == "faq":
        docs = retrieve_with_parent_expansion(question, pipeline=pipeline)
    else:
        # policy / compliance — use your original retriever (simple similarity)
        retriever = get_retriever(pipeline=pipeline)
        docs = retriever.invoke(question)

    if not docs:
        return {
            "answer": "I could not find that information in the available documents.",
            "citations": [],
        }

    # Build numbered reference block for citations
    ref_block = _build_ref_block(docs)

    # Build conversation history string
    history_str = ""
    if history:
        for turn in history[-6:]:   # last 3 pairs
            role = "User" if turn["role"] == "user" else "Assistant"
            history_str += f"{role}: {turn['content']}\n"

    prompt = f"""You are a field service compliance and policy assistant.

Use ONLY the reference documents below to answer the question.
After every factual claim write the citation in brackets like [REF-1] or [REF-2].
At the end, output a JSON block (fenced ```json ... ```) with this structure:
[
  {{"ref": "REF-1", "source": "filename.pdf", "page": "3", "excerpt": "short quote"}}
]

If no relevant information exists, say exactly:
"I could not find that information in the available documents."

{f"Conversation so far:{chr(10)}{history_str}" if history_str else ""}

REFERENCE DOCUMENTS:
{ref_block}

Question: {question}

Answer:"""

    response = llm.invoke(prompt)
    raw = response.content

    answer, citations = _parse_citations(raw, docs)

    return {"answer": answer, "citations": citations}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_ref_block(docs) -> str:
    lines = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        page   = doc.metadata.get("page", "?")
        lines.append(f"[REF-{i}] Source: {source}, Page {page}\n{doc.page_content}\n")
    return "\n".join(lines)


def _parse_citations(raw: str, docs) -> tuple:
    """Split LLM output into clean answer text + structured citations list."""
    json_match = re.search(r"```json\s*(\[.*?\])\s*```", raw, re.DOTALL)
    citations = []

    if json_match:
        try:
            raw_cites = json.loads(json_match.group(1))
            for cite in raw_cites:
                ref = cite.get("ref", "")
                idx = _ref_to_index(ref)
                doc = docs[idx] if idx is not None and idx < len(docs) else None
                citations.append({
                    "ref":     ref,
                    "source":  doc.metadata.get("source", cite.get("source", "")) if doc else cite.get("source", ""),
                    "page":    doc.metadata.get("page",   cite.get("page",   "")) if doc else cite.get("page", ""),
                    "excerpt": cite.get("excerpt", doc.page_content[:200] if doc else ""),
                })
        except (json.JSONDecodeError, TypeError):
            pass

    clean_answer = re.sub(r"```json.*?```", "", raw, flags=re.DOTALL).strip()
    return clean_answer, citations


def _ref_to_index(ref: str):
    match = re.search(r"REF-(\d+)", ref or "", re.IGNORECASE)
    return int(match.group(1)) - 1 if match else None
