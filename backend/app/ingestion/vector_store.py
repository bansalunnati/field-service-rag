from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from app.llm.embedding_config import get_embedding_model
from typing import List

CHROMA_BASE_DIR = "chroma_db"

# One named Chroma collection per pipeline
COLLECTIONS = {
    "technical":  "technical_manuals",
    "policy":     "policy_compliance",
    "compliance": "policy_compliance",
    "general":    "general_docs",
    "faq":        "general_docs",
}


def get_collection_name(pipeline: str) -> str:
    return COLLECTIONS.get(pipeline.lower(), "general_docs")


def create_vector_store(chunks: List[Document], pipeline: str = "general") -> Chroma:
    """
    Drop-in replacement for your original create_vector_store(chunks).
    Now routes chunks into a named collection based on pipeline.
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


def get_vector_store(pipeline: str = "general") -> Chroma:
    """Load an existing named collection for querying."""
    collection_name = get_collection_name(pipeline)
    return Chroma(
        persist_directory=CHROMA_BASE_DIR,
        embedding_function=get_embedding_model(),
        collection_name=collection_name,
    )