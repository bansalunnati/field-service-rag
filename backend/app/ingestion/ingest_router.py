"""
ingestion/ingest_router.py  — NEW file, add to app/ingestion/
FastAPI router for document uploads.
POST /api/ingest/upload  — accepts PDF, DOCX, TXT, CSV, MD
"""

import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from pydantic import BaseModel

from app.auth.auth_service import require_permission, TokenData
from app.ingestion.ingest_documents import ingest_single_file
from app.retrieval.retriever import invalidate_bm25_cache

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".md"}
MAX_FILE_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))


class IngestResponse(BaseModel):
    filename:       str
    pipeline:       str
    pages:          int
    chunks_created: int
    message:        str


@router.post("/upload", response_model=IngestResponse)
async def upload_document(
    file:     UploadFile     = File(...),
    pipeline: Optional[str]  = Form(None),
    user:     TokenData      = Depends(require_permission("upload")),
):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported type '{suffix}'. Allowed: {ALLOWED_EXTENSIONS}",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_FILE_MB}MB limit")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        result = ingest_single_file(tmp_path, pipeline=pipeline)
        invalidate_bm25_cache(result["pipeline"])
    finally:
        os.unlink(tmp_path)

    return IngestResponse(
        filename=result["filename"],
        pipeline=result["pipeline"],
        pages=result["pages"],
        chunks_created=result["chunks"],
        message=f"Ingested {result['chunks']} chunks into '{result['pipeline']}' pipeline",
    )


@router.get("/collections")
async def list_collections(user: TokenData = Depends(require_permission("upload"))):
    from app.ingestion.vector_store import CHROMA_BASE_DIR
    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_BASE_DIR)
    return {"collections": [c.name for c in client.list_collections()]}
