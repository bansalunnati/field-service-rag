"""
ingestion/vector_store.py

Creates and loads named ChromaDB collections, one per pipeline.

Pipeline → Collection mapping (updated in Phase 1):
  equipment    → "equipment_assets"
  safety       → "safety_compliance"
  field_reports → "field_reports_docs"
"""

import os
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from app.llm.embedding_config import get_embedding_model
from typing import List

CHROMA_BASE_DIR = os.getenv("CHROMA_BASE_DIR", "chroma_db")

# One named Chroma collection per pipeline.
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
    Returns the ChromaDB collection name for a given pipeline key.
    Falls back to the field_reports collection for unknown pipelines.
    """
    return COLLECTIONS.get(pipeline.lower(), _DEFAULT_COLLECTION)


def create_vector_store(chunks: List[Document], pipeline: str = "field_reports") -> Chroma:
    """
    Ingests a list of chunks into the correct ChromaDB collection.

    Args:
        chunks   : Chunked LangChain Documents (already metadata-stamped).
        pipeline : One of 'equipment', 'safety', 'field_reports'.

    Returns:
        The Chroma vector store instance.
    """
    collection_name = get_collection_name(pipeline)

    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=get_embedding_model(),
        persist_directory=CHROMA_BASE_DIR,
        collection_name=collection_name,
    )

    print(f"  Stored {len(chunks)} chunks → collection: '{collection_name}'")
    return vector_store


def get_vector_store(pipeline: str = "field_reports") -> Chroma:
    """
    Loads an existing ChromaDB collection for querying.

    Args:
        pipeline : One of 'equipment', 'safety', 'field_reports'.

    Returns:
        Chroma vector store ready for similarity search.
    """
    collection_name = get_collection_name(pipeline)

    return Chroma(
        persist_directory=CHROMA_BASE_DIR,
        embedding_function=get_embedding_model(),
        collection_name=collection_name,
    )
