"""
ingestion/ingest_documents.py

Batch ingestion (entire directory) and single-file ingestion.
Auto-routes each file to the correct pipeline collection.

Pipeline keys (updated in Phase 1):
  equipment    → equipment_assets   ChromaDB collection
  safety       → safety_compliance  ChromaDB collection
  field_reports → field_reports_docs ChromaDB collection
"""

import os
from collections import defaultdict
from typing import Optional

from langchain_core.documents import Document
from app.ingestion.document_loader import load_documents, _detect_pipeline
from app.ingestion.chunking import split_documents
from app.ingestion.vector_store import create_vector_store


def ingest_documents(
    data_path: str = "data/policies",
    pipeline: Optional[str] = None,
) -> tuple:
    """
    Ingests all supported files from a directory into ChromaDB.

    Groups files by detected pipeline and sends each group to the correct
    collection. Returns (total_pages, total_chunks) for the /process endpoint.

    Args:
        data_path : Path to the directory containing seed documents.
        pipeline  : Override auto-detection and force all files into this pipeline.

    Returns:
        (total_pages: int, total_chunks: int)
    """
    all_docs = load_documents(data_path=data_path, pipeline=pipeline)

    if not all_docs:
        print("No documents found. Check the data_path and file types.")
        return 0, 0

    # Group documents by their detected pipeline key.
    grouped: dict = defaultdict(list)
    for doc in all_docs:
        p = doc.metadata.get("pipeline", "field_reports")
        grouped[p].append(doc)

    total_chunks = 0
    for p, docs in grouped.items():
        print(f"\nPipeline '{p}': {len(docs)} pages")
        chunks = split_documents(docs, pipeline=p)
        create_vector_store(chunks, pipeline=p)
        total_chunks += len(chunks)

    print(f"\nIngestion complete: {len(all_docs)} pages → {total_chunks} chunks")
    return len(all_docs), total_chunks


def ingest_single_file(file_path: str, pipeline: Optional[str] = None, file_id: Optional[str] = None) -> dict:
    """
    Ingests a single uploaded file into the correct ChromaDB collection.

    Called by the FastAPI /api/ingest/upload endpoint after the file
    has been saved to a temp path.

    OCR support will be wired here in Phase 5 — the function signature
    will not change, only the internal loading logic will be extended.

    Args:
        file_path : Absolute path to the uploaded file (temp file).
        pipeline  : Override auto-detection with an explicit pipeline key.

    Returns:
        {
            "filename":  str,   # Original filename (no temp path).
            "pipeline":  str,   # Pipeline the file was ingested into.
            "pages":     int,   # Number of pages/sections loaded.
            "chunks":    int,   # Number of chunks stored in ChromaDB.
        }

    Raises:
        ValueError if the file extension is not supported.
    """
    from app.ingestion.document_loader import (
        _load_pdf, _load_docx, _load_txt, _load_csv
    )

    ext      = os.path.splitext(file_path)[1].lower()
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
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported types: {', '.join(sorted(loader_map.keys()))}"
        )

    docs = loader_fn(file_path)

    for doc in docs:
        doc.metadata["source"]   = filename
        doc.metadata["pipeline"] = detected_pipeline
        if file_id:
            doc.metadata["file_id"] = file_id

    chunks = split_documents(docs, pipeline=detected_pipeline)
    # Propagate file_id onto every chunk (split_documents copies metadata)
    if file_id:
        for chunk in chunks:
            chunk.metadata["file_id"] = file_id
    create_vector_store(chunks, pipeline=detected_pipeline)

    return {
        "filename": filename,
        "pipeline": detected_pipeline,
        "pages":    len(docs),
        "chunks":   len(chunks),
    }
