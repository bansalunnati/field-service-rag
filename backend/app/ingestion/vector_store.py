"""
ingestion/vector_store.py

Creates and loads named vector collections, one per pipeline, backed by
pgvector in the same Postgres database used for app metadata (UploadedFile
rows, etc.) — so embeddings and metadata always stay consistent.

Pipeline → Collection mapping (updated in Phase 1):
  equipment    → "equipment_assets"
  safety       → "safety_compliance"
  field_reports → "field_reports_docs"
"""

from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.documents import Document
from app.llm.embedding_config import get_embedding_model
from app.chat.database import DATABASE_URL
from typing import List

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
        The PGVector store instance.
    """
    collection_name = get_collection_name(pipeline)

    vector_store = PGVector.from_documents(
        documents=chunks,
        embedding=get_embedding_model(),
        collection_name=collection_name,
        connection_string=DATABASE_URL,
        use_jsonb=True,
    )

    print(f"  Stored {len(chunks)} chunks → collection: '{collection_name}' (pgvector)")
    return vector_store


def get_vector_store(pipeline: str = "field_reports"):
    """
    Loads an existing collection for querying.

    Args:
        pipeline : One of 'equipment', 'safety', 'field_reports'.

    Returns:
        PGVector store ready for similarity search.
    """
    collection_name = get_collection_name(pipeline)

    return PGVector(
        embedding_function=get_embedding_model(),
        collection_name=collection_name,
        connection_string=DATABASE_URL,
        use_jsonb=True,
    )


def get_all_documents(pipeline: str = "field_reports") -> List[Document]:
    """
    Returns every document currently stored in a pipeline's collection.

    Used by the BM25 index builder, which otherwise has no portable way to
    dump an entire collection.
    """
    vector_store = get_vector_store(pipeline)

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


def delete_documents_by_file_id(file_id: str, pipeline: str) -> int:
    """
    Removes every chunk tagged with this file_id from its pipeline's collection.

    Called when an admin deletes an UploadedFile — without this, the original
    file disappears from the file manager but its embedded chunks keep being
    retrieved and quoted in chat answers forever.

    Returns the number of chunks removed.
    """
    vector_store = get_vector_store(pipeline)

    with vector_store._make_session() as session:
        collection = vector_store.get_collection(session)
        if not collection:
            return 0
        rows = (
            session.query(vector_store.EmbeddingStore)
            .filter(vector_store.EmbeddingStore.collection_id == collection.uuid)
            .filter(vector_store.EmbeddingStore.cmetadata["file_id"].astext == file_id)
            .all()
        )
        count = len(rows)
        for row in rows:
            session.delete(row)
        session.commit()
        return count


def list_collection_names() -> List[str]:
    """Lists every collection name currently stored, for the admin /collections endpoint."""
    from sqlalchemy import create_engine, text
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        try:
            rows = conn.execute(text("SELECT name FROM langchain_pg_collection")).fetchall()
        except Exception:
            return []
        return [r[0] for r in rows]
