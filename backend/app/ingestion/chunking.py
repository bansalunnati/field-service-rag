from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from typing import List


def split_documents(documents: List[Document], pipeline: str = "general") -> List[Document]:
    """
    Drop-in replacement for your original split_documents(documents).
    Now accepts an optional pipeline arg to apply the right strategy.
    """
    strategy_map = {
        "technical":  _split_technical,
        "policy":     _split_policy,
        "compliance": _split_policy,
        "general":    _split_general,
        "faq":        _split_general,
    }
    fn = strategy_map.get(pipeline.lower(), _split_general)
    return fn(documents)


# Pipeline 1 — Technical manuals
# Larger chunks so part numbers and specs stay together
def _split_technical(documents: List[Document]) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    for i, chunk in enumerate(chunks):
        chunk.metadata["pipeline"] = "technical"
        chunk.metadata["chunk_index"] = i
    return chunks


# Pipeline 2 — Policy / compliance
# Small sentence-level chunks for precise retrieval
def _split_policy(documents: List[Document]) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=350,
        chunk_overlap=50,
        separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    for i, chunk in enumerate(chunks):
        chunk.metadata["pipeline"] = "policy"
        chunk.metadata["chunk_index"] = i
        first_line = chunk.page_content.split("\n")[0].strip()
        if len(first_line) < 80:
            chunk.metadata["section_hint"] = first_line
    return chunks


# Pipeline 3 — General / FAQs
# Parent-child: large parents stored for context, small children indexed
def _split_general(documents: List[Document]) -> List[Document]:
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
        parent.metadata["pipeline"] = "general"
        parent.metadata["chunk_type"] = "parent"
        parent.metadata["parent_id"] = parent_id
        parent.metadata["chunk_index"] = p_idx
        all_chunks.append(parent)

        children = child_splitter.create_documents(
            texts=[parent.page_content],
            metadatas=[{
                **parent.metadata,
                "chunk_type": "child",
                "parent_id": parent_id,
            }]
        )
        all_chunks.extend(children)

    return all_chunks
