from langchain.schema import Document
from app.ingestion.vector_store import get_vector_store
from typing import List, Optional

try:
    from rank_bm25 import BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:
    _BM25_AVAILABLE = False

# In-memory BM25 cache per pipeline
_bm25_cache: dict = {}


def get_retriever(pipeline: str = "policy"):
    """
    Drop-in replacement for your original get_retriever().
    Defaults to 'policy' so your existing policy_bot.py keeps working.
    Now loads from the correct named collection.
    """
    vector_store = get_vector_store(pipeline)
    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 6},
    )


def retrieve_with_hybrid(
    question: str,
    pipeline: str = "general",
    top_k: int = 6,
) -> List[Document]:
    """
    Hybrid dense + BM25 retrieval fused with Reciprocal Rank Fusion.
    Used by the 3 pipeline modules for richer, more accurate results.
    """
    vector_store = get_vector_store(pipeline)
    dense_docs = vector_store.similarity_search(question, k=top_k)

    if _BM25_AVAILABLE:
        bm25_docs = _bm25_retrieve(question, pipeline, top_k)
        return _reciprocal_rank_fusion([dense_docs, bm25_docs], top_n=top_k)

    return dense_docs


def retrieve_with_parent_expansion(
    question: str,
    pipeline: str = "general",
    top_k: int = 5,
) -> List[Document]:
    """
    Parent-child retrieval for the general pipeline.
    Searches small child chunks, then swaps them for their larger parent.
    """
    vector_store = get_vector_store(pipeline)

    child_docs = vector_store.similarity_search(
        question,
        k=top_k * 2,
        filter={"chunk_type": "child"},
    )

    if not child_docs:
        # Fallback for data ingested before parent-child was added
        return vector_store.similarity_search(question, k=top_k)

    seen_parents = set()
    parent_docs = []

    for child in child_docs:
        parent_id = child.metadata.get("parent_id")
        if not parent_id or parent_id in seen_parents:
            continue
        seen_parents.add(parent_id)

        parents = vector_store.similarity_search(
            question,
            k=1,
            filter={"parent_id": parent_id, "chunk_type": "parent"},
        )
        parent_docs.append(parents[0] if parents else child)

        if len(parent_docs) >= top_k:
            break

    return parent_docs


def invalidate_bm25_cache(pipeline: Optional[str] = None):
    """Call this after ingesting new documents."""
    if pipeline:
        _bm25_cache.pop(pipeline, None)
    else:
        _bm25_cache.clear()


# ── BM25 internals ────────────────────────────────────────────────────────────

def _bm25_retrieve(question: str, pipeline: str, top_k: int) -> List[Document]:
    if pipeline not in _bm25_cache:
        _rebuild_bm25_index(pipeline)
    bm25, docs = _bm25_cache.get(pipeline, (None, []))
    if not bm25:
        return []
    scores = bm25.get_scores(question.lower().split())
    ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
    return [doc for _, doc in ranked[:top_k]]


def _rebuild_bm25_index(pipeline: str):
    try:
        vs = get_vector_store(pipeline)
        result = vs._collection.get(include=["documents", "metadatas"])
        raw_docs = result.get("documents", [])
        metas = result.get("metadatas", []) or [{}] * len(raw_docs)
        docs = [Document(page_content=t, metadata=m) for t, m in zip(raw_docs, metas)]
        tokenized = [d.page_content.lower().split() for d in docs]
        _bm25_cache[pipeline] = (BM25Okapi(tokenized) if tokenized else None, docs)
    except Exception as e:
        print(f"BM25 index build failed for '{pipeline}': {e}")
        _bm25_cache[pipeline] = (None, [])


def _reciprocal_rank_fusion(
    result_lists: List[List[Document]], top_n: int = 6, k: int = 60
) -> List[Document]:
    scores: dict = {}
    doc_map: dict = {}
    for results in result_lists:
        for rank, doc in enumerate(results):
            key = doc.page_content[:128]
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            doc_map[key] = doc
    sorted_keys = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [doc_map[k] for k in sorted_keys[:top_n]]
