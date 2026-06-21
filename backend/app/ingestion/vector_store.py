"""
ingestion/vector_store.py

Creates and loads named vector collections, one per pipeline.

Backend selection:
  - If DATABASE_URL is PostgreSQL (Render production), vectors are stored in
    that same Postgres database via pgvector. Metadata (UploadedFile rows)
    and embeddings then live in one transactional store, so they can never
    drift apart the way they did with disk-backed Chroma on an ephemeral
    container filesystem.
  - Otherwise (local dev on SQLite), falls back to a local Chroma directory
    for convenience — no Postgres/pgvector setup needed to develop locally.

Pipeline → Collection mapping (updated in Phase 1):
  equipment    → "equipment_assets"
  safety       → "safety_compliance"
  field_reports → "field_reports_docs"
"""

import os
from langchain_community.vectorstores import Chroma
from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.documents import Document
from app.llm.embedding_config import get_embedding_model
from app.chat.database import DATABASE_URL
from typing import List

CHROMA_BASE_DIR = os.getenv("CHROMA_BASE_DIR", "chroma_db")

# Explicit override available via VECTOR_STORE=chroma|pgvector; defaults to
# pgvector whenever a real Postgres DATABASE_URL is configured.
_VECTOR_STORE_OVERRIDE = os.getenv("VECTOR_STORE", "").strip().lower()
if _VECTOR_STORE_OVERRIDE in ("chroma", "pgvector"):
    USE_PGVECTOR = _VECTOR_STORE_OVERRIDE == "pgvector"
else:
    USE_PGVECTOR = DATABASE_URL.startswith("postgresql")

# One named collection per pipeline.
# Add new pipelines here — nowhere else needs to change.
COLLECTIONS = {
    "equipment":     "equipment_assets",
    "safety":        "safety_compliance",
    "field_reports": "field_reports_docs",
}

# Default collection used when an unrecognised pipeline is passed.
_DEFAULT_COLLECTION = "field_reports_docs"


def get_collection_name(pipeline: str) -> str:
    """
    Returns the vector collection name for a given pipeline key.
    Falls back to the field_reports collection for unknown pipelines.
    """
    return COLLECTIONS.get(pipeline.lower(), _DEFAULT_COLLECTION)


def create_vector_store(chunks: List[Document], pipeline: str = "field_reports"):
    """
    Ingests a list of chunks into the correct collection.

    Args:
        chunks   : Chunked LangChain Documents (already metadata-stamped).
        pipeline : One of 'equipment', 'safety', 'field_reports'.

    Returns:
        The vector store instance (PGVector or Chroma).
    """
    collection_name = get_collection_name(pipeline)

    if USE_PGVECTOR:
        vector_store = PGVector.from_documents(
            documents=chunks,
            embedding=get_embedding_model(),
            collection_name=collection_name,
            connection_string=DATABASE_URL,
            use_jsonb=True,
        )
    else:
        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=get_embedding_model(),
            persist_directory=CHROMA_BASE_DIR,
            collection_name=collection_name,
        )

    print(f"  Stored {len(chunks)} chunks → collection: '{collection_name}' ({'pgvector' if USE_PGVECTOR else 'chroma'})")
    return vector_store


def get_vector_store(pipeline: str = "field_reports"):
    """
    Loads an existing collection for querying.

    Args:
        pipeline : One of 'equipment', 'safety', 'field_reports'.

    Returns:
        Vector store ready for similarity search (PGVector or Chroma).
    """
    collection_name = get_collection_name(pipeline)

    if USE_PGVECTOR:
        return PGVector(
            embedding_function=get_embedding_model(),
            collection_name=collection_name,
            connection_string=DATABASE_URL,
            use_jsonb=True,
        )

    return Chroma(
        persist_directory=CHROMA_BASE_DIR,
        embedding_function=get_embedding_model(),
        collection_name=collection_name,
    )


def get_all_documents(pipeline: str = "field_reports") -> List[Document]:
    """
    Returns every document currently stored in a pipeline's collection.

    Backend-agnostic helper used by the BM25 index builder, which otherwise
    has no portable way to dump an entire collection.
    """
    vector_store = get_vector_store(pipeline)

    if USE_PGVECTOR:
        with vector_store._make_session() as session:
            collection = vector_store.get_collection(session)
            if not collection:
                return []
            rows = (
                session.query(vector_store.EmbeddingStore)
                .filter(vector_store.EmbeddingStore.collection_id == collection.uuid)
                .all()
            )
            return [Document(page_content=r.document, metadata=r.cmetadata or {}) for r in rows]

    result = vector_store._collection.get(include=["documents", "metadatas"])
    raw_docs = result.get("documents", [])
    metas = result.get("metadatas", []) or [{}] * len(raw_docs)
    return [Document(page_content=t, metadata=m) for t, m in zip(raw_docs, metas)]


def list_collection_names() -> List[str]:
    """Lists every collection name currently stored, for the admin /collections endpoint."""
    if USE_PGVECTOR:
        from sqlalchemy import create_engine, text
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            try:
                rows = conn.execute(text("SELECT name FROM langchain_pg_collection")).fetchall()
            except Exception:
                return []
            return [r[0] for r in rows]

    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_BASE_DIR)
    return [c.name for c in client.list_collections()]
