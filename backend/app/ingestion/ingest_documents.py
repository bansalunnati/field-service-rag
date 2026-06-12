from collections import defaultdict
from typing import Optional
from langchain.schema import Document

from app.ingestion.document_loader import load_documents, _detect_pipeline
from app.ingestion.chunking import split_documents
from app.ingestion.vector_store import create_vector_store


def ingest_documents(
    data_path: str = "data/policies",
    pipeline: Optional[str] = None,
) -> tuple:
    """
    Drop-in replacement for your original ingest_documents().
    Still returns (total_docs, total_chunks) so nothing breaks.
    Now auto-routes each file to the correct pipeline collection.
    """
    all_docs = load_documents(data_path=data_path, pipeline=pipeline)

    if not all_docs:
        print("No documents found.")
        return 0, 0

    # Group documents by their detected pipeline
    grouped = defaultdict(list)
    for doc in all_docs:
        p = doc.metadata.get("pipeline", "general")
        grouped[p].append(doc)

    total_chunks = 0
    for p, docs in grouped.items():
        print(f"\nPipeline '{p}': {len(docs)} pages")
        chunks = split_documents(docs, pipeline=p)
        create_vector_store(chunks, pipeline=p)
        total_chunks += len(chunks)

    print(f"\nDone: {len(all_docs)} pages → {total_chunks} chunks")
    return len(all_docs), total_chunks


def ingest_single_file(file_path: str, pipeline: Optional[str] = None) -> dict:
    """
    NEW — ingest one uploaded file.
    Called by the FastAPI /api/ingest/upload endpoint.
    """
    import os
    from app.ingestion.document_loader import (
        _load_pdf, _load_docx, _load_txt, _load_csv
    )

    ext = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)
    detected_pipeline = pipeline or _detect_pipeline(filename)

    loader_map = {
        ".pdf":  _load_pdf,
        ".docx": _load_docx,
        ".txt":  _load_txt,
        ".md":   _load_txt,
        ".csv":  _load_csv,
    }
    loader_fn = loader_map.get(ext)
    if not loader_fn:
        raise ValueError(f"Unsupported file type: {ext}")

    docs = loader_fn(file_path)
    for doc in docs:
        doc.metadata["source"] = filename
        doc.metadata["pipeline"] = detected_pipeline

    chunks = split_documents(docs, pipeline=detected_pipeline)
    create_vector_store(chunks, pipeline=detected_pipeline)

    return {
        "filename": filename,
        "pipeline": detected_pipeline,
        "pages": len(docs),
        "chunks": len(chunks),
    }
