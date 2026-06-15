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
from sqlalchemy.orm import Session

from app.chat.database import get_db
from app.chat.models import UploadedFile
from app.auth.auth_service import require_permission, TokenData
from app.ingestion.ingest_documents import ingest_single_file
from app.retrieval.retriever import invalidate_bm25_cache

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".md"}
MAX_FILE_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
VALID_PIPELINES = {
    "equipment",
    "safety",
    "field_reports"
}

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
    db:       Session         = Depends(get_db),
    user:     TokenData      = Depends(require_permission("upload")),
):
    suffix = Path(file.filename).suffix.lower()
    if pipeline and pipeline not in VALID_PIPELINES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid pipeline '{pipeline}'. "
                f"Valid options: {sorted(VALID_PIPELINES)}"
            ),
        )
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

        uploaded_file = UploadedFile(
            filename=file.filename,
            original_name=file.filename,
            file_type=suffix.replace(".", ""),
            pipeline=result["pipeline"],
            chunk_count=result["chunks"],
            uploaded_by=user.user_id,
        )

        db.add(uploaded_file)
        db.commit()

    finally:
        os.unlink(tmp_path)

    return IngestResponse(
        filename=file.filename,
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

@router.get("/files")
async def list_uploaded_files(
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_permission("upload")),
):
    files = (
        db.query(UploadedFile)
        .order_by(UploadedFile.uploaded_at.desc())
        .all()
    )

    return [
        {
            "id": file.id,
            "filename": file.filename,
            "original_name": file.original_name,
            "file_type": file.file_type,
            "pipeline": file.pipeline,
            "chunk_count": file.chunk_count,
            "uploaded_by": file.uploaded_by,
            "uploaded_at": file.uploaded_at,
        }
        for file in files
    ]