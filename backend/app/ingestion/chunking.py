"""
ingestion/chunking.py

Splits documents into chunks using the correct strategy per pipeline.

Pipeline keys (updated in Phase 1):
  equipment    → large chunks (1500 tokens) to keep specs/part numbers together
  safety       → small sentence-level chunks (350 tokens) for precise retrieval
  field_reports → parent-child chunking (1800 parent / 400 child)
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from typing import List


def split_documents(documents: List[Document], pipeline: str = "field_reports") -> List[Document]:
    """
    Routes documents to the correct chunking strategy based on pipeline.

    Args:
        documents : LangChain Document objects loaded from any file type.
        pipeline  : One of 'equipment', 'safety', 'field_reports'.

    Returns:
        List of chunked Document objects, each stamped with pipeline metadata.
    """
    strategy_map = {
        "equipment":     _split_equipment,
        "safety":        _split_safety,
        "field_reports": _split_field_reports,
    }

    fn = strategy_map.get(pipeline.lower(), _split_field_reports)
    return fn(documents)


# ── Pipeline: Equipment & Assets ──────────────────────────────────────────────
# Larger chunks so part numbers, torque specs, and procedures stay together.

def _split_equipment(documents: List[Document]) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    for i, chunk in enumerate(chunks):
        chunk.metadata["pipeline"]    = "equipment"
        chunk.metadata["chunk_index"] = i
    return chunks


# ── Pipeline: Safety & Compliance ─────────────────────────────────────────────
# Small sentence-level chunks for precise policy and regulation retrieval.

def _split_safety(documents: List[Document]) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=350,
        chunk_overlap=50,
        separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    for i, chunk in enumerate(chunks):
        chunk.metadata["pipeline"]    = "safety"
        chunk.metadata["chunk_index"] = i
        first_line = chunk.page_content.split("\n")[0].strip()
        if len(first_line) < 80:
            chunk.metadata["section_hint"] = first_line
    return chunks


# ── Pipeline: Field Reports ───────────────────────────────────────────────────
# Parent-child: large parents stored for context, small children indexed for search.

def _split_field_reports(documents: List[Document]) -> List[Document]:
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1800,
        chunk_overlap=100,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    all_chunks = []
    parent_chunks = parent_splitter.split_documents(documents)

    for p_idx, parent in enumerate(parent_chunks):
        parent_id = f"parent_{p_idx}"
        parent.metadata["pipeline"]    = "field_reports"
        parent.metadata["chunk_type"]  = "parent"
        parent.metadata["parent_id"]   = parent_id
        parent.metadata["chunk_index"] = p_idx
        all_chunks.append(parent)

        children = child_splitter.create_documents(
            texts=[parent.page_content],
            metadatas=[{
                **parent.metadata,
                "chunk_type": "child",
                "parent_id":  parent_id,
            }]
        )
        all_chunks.extend(children)

    return all_chunks
