from langchain_core.documents import Document
from app.ingestion.vector_store import get_vector_store, get_all_documents
from typing import List, Optional

try:
    from rank_bm25 import BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:
    _BM25_AVAILABLE = False

# In-memory BM25 cache per pipeline
_bm25_cache: dict = {}


def _file_filter(allowed_file_ids: Optional[List[str]], extra: Optional[dict] = None) -> Optional[dict]:
    """
    Builds a ChromaDB `where` filter that restricts results to allowed files.
    - None → no filter (admin sees everything).
    - [] → empty list means no files are accessible; callers should short-circuit before this.
    - extra → merged with $and when both conditions are needed.
    """
    if allowed_file_ids is None:
        return extra  # admin: no restriction

    file_clause = {"file_id": {"$in": allowed_file_ids}} if allowed_file_ids else {"file_id": "__no_match__"}

    if extra is None:
        return file_clause
    return {"$and": [file_clause, extra]}


def get_retriever(pipeline: str = "policy", allowed_file_ids: Optional[List[str]] = None):
    vector_store = get_vector_store(pipeline)
    search_kwargs: dict = {"k": 6}
    f = _file_filter(allowed_file_ids)
    if f:
        search_kwargs["filter"] = f
    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs=search_kwargs,
    )


def retrieve_with_hybrid(
    question: str,
    pipeline: str = "general",
    top_k: int = 6,
    allowed_file_ids: Optional[List[str]] = None,
) -> List[Document]:
    vector_store = get_vector_store(pipeline)
    f = _file_filter(allowed_file_ids)
    dense_docs = vector_store.similarity_search(question, k=top_k, filter=f)

    if _BM25_AVAILABLE:
        bm25_docs = _bm25_retrieve(question, pipeline, top_k, allowed_file_ids)
        return _reciprocal_rank_fusion([dense_docs, bm25_docs], top_n=top_k)

    return dense_docs


def retrieve_with_parent_expansion(
    question: str,
    pipeline: str = "general",
    top_k: int = 5,
    allowed_file_ids: Optional[List[str]] = None,
) -> List[Document]:
    vector_store = get_vector_store(pipeline)

    child_filter = _file_filter(allowed_file_ids, extra={"chunk_type": "child"})
    child_docs = vector_store.similarity_search(question, k=top_k * 2, filter=child_filter)

    if not child_docs:
        fallback_filter = _file_filter(allowed_file_ids)
        return vector_store.similarity_search(question, k=top_k, filter=fallback_filter)

    seen_parents = set()
    parent_docs = []

    for child in child_docs:
        parent_id = child.metadata.get("parent_id")
        if not parent_id or parent_id in seen_parents:
            continue
        seen_parents.add(parent_id)

        parent_filter = _file_filter(
            allowed_file_ids,
            extra={"$and": [{"parent_id": parent_id}, {"chunk_type": "parent"}]},
        )
        parents = vector_store.similarity_search(question, k=1, filter=parent_filter)
        parent_docs.append(parents[0] if parents else child)

        if len(parent_docs) >= top_k:
            break

    return parent_docs


def invalidate_bm25_cache(pipeline: Optional[str] = None):
    if pipeline:
        _bm25_cache.pop(pipeline, None)
    else:
        _bm25_cache.clear()


# ── BM25 internals ────────────────────────────────────────────────────────────

def _bm25_retrieve(
    question: str,
    pipeline: str,
    top_k: int,
    allowed_file_ids: Optional[List[str]] = None,
) -> List[Document]:
    if pipeline not in _bm25_cache:
        _rebuild_bm25_index(pipeline)
    bm25, docs = _bm25_cache.get(pipeline, (None, []))
    if not bm25:
        return []

    # Apply file-level filter on the BM25 corpus
    if allowed_file_ids is not None:
        id_set = set(allowed_file_ids)
        docs_filtered = [d for d in docs if d.metadata.get("file_id") in id_set]
        if not docs_filtered:
            return []
        tokenized = [d.page_content.lower().split() for d in docs_filtered]
        from rank_bm25 import BM25Okapi
        bm25_filtered = BM25Okapi(tokenized)
        scores = bm25_filtered.get_scores(question.lower().split())
        ranked = sorted(zip(scores, docs_filtered), key=lambda x: x[0], reverse=True)
    else:
        scores = bm25.get_scores(question.lower().split())
        ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)

    return [doc for _, doc in ranked[:top_k]]


def _rebuild_bm25_index(pipeline: str):
    try:
        docs = get_all_documents(pipeline)
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
