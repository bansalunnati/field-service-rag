"""
retrieval/rag_pipeline.py

Core RAG logic: retrieves relevant document chunks and generates
a cited answer using Azure OpenAI GPT-4.

Pipeline keys (updated in Phase 1):
  equipment    → hybrid BM25 + dense retrieval
  safety       → standard similarity retrieval
  field_reports → parent-child retrieval with expansion

RAGAs evaluation will be wired here in Phase 9 as a BackgroundTask
after every assistant response is saved to the database.
"""

import json
import re
from typing import List, Dict, Any, Optional

from app.retrieval.retriever import (
    get_retriever,
    retrieve_with_hybrid,
    retrieve_with_parent_expansion,
)
from app.llm.llm_config import llm


# ── Public API ────────────────────────────────────────────────────────────────

def ask_question(question: str, pipeline: str = "safety") -> str:
    """
    Legacy endpoint — returns a plain string answer.
    Kept for backward compatibility with the /ask route in main.py.
    """
    result = ask_question_with_citations(question, pipeline=pipeline)
    return result["answer"]


def _retrieve_docs(question: str, pipeline: str, allowed_file_ids: Optional[List[str]], top_k: Optional[int] = None) -> List:
    """Dispatches to the retrieval strategy configured for a single pipeline."""
    if pipeline == "equipment":
        kwargs = {"top_k": top_k} if top_k else {}
        return retrieve_with_hybrid(question, pipeline=pipeline, allowed_file_ids=allowed_file_ids, **kwargs)
    if pipeline == "field_reports":
        kwargs = {"top_k": top_k} if top_k else {}
        return retrieve_with_parent_expansion(question, pipeline=pipeline, allowed_file_ids=allowed_file_ids, **kwargs)

    retriever = get_retriever(pipeline=pipeline, allowed_file_ids=allowed_file_ids)
    docs = retriever.invoke(question)
    return docs[:top_k] if top_k else docs


def ask_question_with_citations(
    question: str,
    pipeline: str = "safety",
    history: Optional[List[Dict[str, str]]] = None,
    allowed_file_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Full RAG with inline citations and optional multi-turn memory.

    Steps:
      1. Select retrieval strategy for the pipeline.
      2. Retrieve relevant document chunks.
      3. Build a cited prompt and invoke the LLM.
      4. Parse the answer and citation JSON from the LLM response.

    Args:
        question : The user's query string.
        pipeline : One of 'equipment', 'safety', 'field_reports'.
        history  : Recent conversation turns (role + content dicts).

    Returns:
        {
            "answer":    str,            # Answer with inline [REF-N] markers.
            "citations": list[dict],     # [{ref, source, page, excerpt}, ...]
        }
    """
    docs = _retrieve_docs(question, pipeline, allowed_file_ids)

    # ── Guard against empty retrieval ────────────────────────────────────────
    if not docs:
        return {
            "answer": (
                "I could not find that information in the documents available to you. "
                "Try rephrasing your question, or contact your administrator if you believe "
                "the relevant document has not been uploaded yet."
            ),
            "citations": [],
        }

    # ── Step 3: Build prompt ──────────────────────────────────────────────────
    ref_block   = _build_ref_block(docs)
    history_str = _build_history_str(history)

    prompt = f"""You are an AI assistant for a Utilities and Facility Management team.
Your role is to answer questions accurately using ONLY the reference documents provided below.

RULES:
- Cite every factual claim with an inline marker like [REF-1] or [REF-2].
- If information comes from multiple sources, cite all relevant references.
- Never invent, infer, or extrapolate FACTS beyond what the documents state.
- If the user asks you to grade, score, rate, or assess something (e.g. a
  report or attachment) against the documents, you MAY make that judgment —
  compare the content point-by-point against the requirements/criteria stated
  in the reference documents, cite which requirement each point is judged
  against, and explain the reasoning behind the score. This is evaluation
  grounded in the documents, not invented facts, so it is allowed.
- If you cannot find the answer in the documents, say exactly:
  "I could not find that information in the documents available to you."
- After your answer, output a JSON block (fenced ```json ... ```) in this exact structure:
  [
    {{"ref": "REF-1", "source": "filename.pdf", "page": "3", "excerpt": "brief quote from document"}}
  ]

{f"CONVERSATION HISTORY:{chr(10)}{history_str}" if history_str else ""}

REFERENCE DOCUMENTS:
{ref_block}

Question: {question}

Answer:"""

    # ── Step 4: Generate and parse ────────────────────────────────────────────
    response = llm.invoke(prompt)
    answer, citations = _parse_citations(response.content, docs)

    return {"answer": answer, "citations": citations}


def ask_question_across_pipelines(
    question: str,
    pipelines: List[str],
    history: Optional[List[Dict[str, str]]] = None,
    allowed_file_ids_by_pipeline: Optional[Dict[str, Optional[List[str]]]] = None,
    attached_text: Optional[str] = None,
    attached_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified RAG — retrieves from every pipeline the caller can access and
    answers from the merged set, instead of segregating by document category.

    Args:
        question  : The user's query string.
        pipelines : Pipelines to search (e.g. all three for an admin, or
                    only the ones a user's groups have been granted).
        history   : Recent conversation turns (role + content dicts).
        allowed_file_ids_by_pipeline : Per-pipeline file-id allowlist for
                    employees (None per pipeline means admin/no restriction).
        attached_text, attached_filename : An ad-hoc file the employee attached
                    to this turn (e.g. their own rejected report) — not stored
                    in the vector store, just prepended to this prompt's
                    reference block so the model can quote/explain it.

    Returns:
        Same shape as ask_question_with_citations.
    """
    allowed_file_ids_by_pipeline = allowed_file_ids_by_pipeline or {}

    # Pull a few candidates from each pipeline rather than flooding the
    # prompt with one pipeline's results — 4 per pipeline keeps the combined
    # set roughly the same size as a single-pipeline query used to be.
    per_pipeline_k = 4
    docs = []
    for p in pipelines:
        allowed = allowed_file_ids_by_pipeline.get(p)
        docs.extend(_retrieve_docs(question, p, allowed, top_k=per_pipeline_k))

    if not docs and not attached_text:
        return {
            "answer": (
                "I could not find that information in the documents available to you. "
                "Try rephrasing your question, or contact your administrator if you believe "
                "the relevant document has not been uploaded yet."
            ),
            "citations": [],
        }

    ref_block   = _build_ref_block(docs)
    if attached_text:
        # Give the attachment its own [REF-N] like every other source, numbered
        # after the retrieved docs — otherwise the model has nothing but a raw
        # "[UPLOADED FILE: ...]" label to cite it with, and that whole string
        # ends up jammed into the citation's short numeric "ref" badge in the UI.
        attached_ref = f"REF-{len(docs) + 1}"
        attached_block = (
            f"[{attached_ref}] Source: {attached_filename or 'attachment'}, Page —\n{attached_text}\n"
        )
        ref_block = f"{ref_block}\n{attached_block}" if ref_block else attached_block
    history_str = _build_history_str(history)

    prompt = f"""You are an AI assistant for a Utilities and Facility Management team.
Your role is to answer questions accurately using ONLY the reference documents provided below.

RULES:
- Cite every factual claim with an inline marker like [REF-1] or [REF-2].
- If information comes from multiple sources, cite all relevant references.
- Never invent, infer, or extrapolate FACTS beyond what the documents state.
- If the user asks you to grade, score, rate, or assess something (e.g. a
  report or attachment) against the documents, you MAY make that judgment —
  compare the content point-by-point against the requirements/criteria stated
  in the reference documents, cite which requirement each point is judged
  against, and explain the reasoning behind the score. This is evaluation
  grounded in the documents, not invented facts, so it is allowed.
- If you cannot find the answer in the documents, say exactly:
  "I could not find that information in the documents available to you."
- After your answer, output a JSON block (fenced ```json ... ```) in this exact structure:
  [
    {{"ref": "REF-1", "source": "filename.pdf", "page": "3", "excerpt": "brief quote from document"}}
  ]

{f"CONVERSATION HISTORY:{chr(10)}{history_str}" if history_str else ""}

REFERENCE DOCUMENTS:
{ref_block}

Question: {question}

Answer:"""

    response = llm.invoke(prompt)
    answer, citations = _parse_citations(response.content, docs)

    return {"answer": answer, "citations": citations}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_ref_block(docs) -> str:
    """Formats retrieved documents as a numbered reference block for the prompt."""
    lines = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        page   = doc.metadata.get("page", "—")
        lines.append(
            f"[REF-{i}] Source: {source}, Page {page}\n{doc.page_content}\n"
        )
    return "\n".join(lines)


def _build_history_str(history: Optional[List[Dict[str, str]]]) -> str:
    """Formats the last 6 conversation turns (3 pairs) as a string for the prompt."""
    if not history:
        return ""
    lines = []
    for turn in history[-6:]:
        role  = "User" if turn["role"] == "user" else "Assistant"
        lines.append(f"{role}: {turn['content']}")
    return "\n".join(lines)


def _parse_citations(raw: str, docs) -> tuple:
    """
    Splits the LLM response into:
      - clean answer text (inline [REF-N] markers preserved)
      - structured citations list

    The LLM is prompted to append a ```json ... ``` block — this function
    extracts and parses that block, then strips it from the answer text.
    """
    json_match = re.search(r"```json\s*(\[.*?\])\s*```", raw, re.DOTALL)
    citations  = []

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
    """Converts a REF-N marker string to a zero-based list index."""
    match = re.search(r"REF-(\d+)", ref or "", re.IGNORECASE)
    return int(match.group(1)) - 1 if match else None
