"""
ingestion/ingest_router.py  — NEW file, add to app/ingestion/
FastAPI router for document uploads.
POST /api/ingest/upload  — accepts PDF, DOCX, TXT, CSV, MD
"""

import os
import tempfile
import uuid

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi.responses import Response
from app.chat.models import UploadedFile, GroupFileAccess, UserGroup, Group
from app.auth.auth_service import get_current_user   # in addition to require_permission

from app.chat.database import get_db, SessionLocal
from app.chat.models import UploadedFile
from app.auth.auth_service import require_permission, TokenData
from app.ingestion.ingest_documents import ingest_single_file
from app.ingestion.document_loader import _detect_pipeline
from app.ingestion.vector_store import delete_documents_by_file_id
from app.retrieval.retriever import invalidate_bm25_cache
from app.storage import file_storage

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])

# Image extensions that go through OCR before ingestion
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".md"} | IMAGE_EXTENSIONS
MAX_FILE_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
VALID_PIPELINES = {
    "equipment",
    "safety",
    "field_reports"
}
def require_admin(user: TokenData = Depends(get_current_user)) -> TokenData:
    """
    True admin-only gate. NOTE: require_permission("upload") is NOT
    sufficient here — per ROLE_PERMISSIONS, role "user" also has the
    "upload" permission, so a regular employee could grant/revoke file
    access if we reused that check. Access-control decisions must be
    admin-only per spec ("only the admin can decide"), so the new
    grant/revoke/list-access endpoints below use this instead.
    """
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

UPLOADS_DIR = os.getenv("UPLOADS_DIR", "data/uploaded_files")
os.makedirs(UPLOADS_DIR, exist_ok=True)
 
MEDIA_TYPES = {
    "pdf":  "application/pdf",
    "txt":  "text/plain",
    "md":   "text/markdown",
    "csv":  "text/csv",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

class IngestResponse(BaseModel):
    filename:        str
    pipeline:        str
    pages:           int = 0
    chunks_created:  int = 0
    message:         str
    ocr_used:        bool = False
    ocr_confidence:  float | None = None
    status:          str = "ready"   # "ready" | "processing"
    file_id:         str | None = None


def _process_ocr_upload(
    file_id: str,
    local_path: str,
    suffix: str,
    pipeline: Optional[str],
    original_filename: Optional[str] = None,
):
    """
    Runs OCR + ingestion for an image/scanned-PDF upload OUTSIDE the HTTP
    request, as a background task.

    Why: Tesseract OCR on a free-tier/CPU-constrained host can take well
    longer than any reasonable HTTP request timeout. Running it inline used
    to either hang until the platform killed the worker (a bare 502 with no
    useful message) or hit our own client-side timeout and fail outright.
    The UploadedFile row is created with status='processing' before this
    runs, and updated here once OCR + ingestion finish — or marked 'failed'
    with a reason instead of being left stuck.

    `local_path` is always a real filesystem path (a temp file), regardless
    of whether the durable copy lives on local disk or in object storage —
    Tesseract/pdf2image need an actual path, not bytes, so the caller is
    responsible for handing one in and this function deletes it when done.
    """
    db = SessionLocal()
    txt_path = None
    try:
        if suffix in IMAGE_EXTENSIONS:
            from app.ingestion.ocr_service import extract_text_from_image
            ocr_text, ocr_confidence = extract_text_from_image(local_path)
        else:
            from app.ingestion.ocr_service import extract_text_from_scanned_pdf
            ocr_text, ocr_confidence = extract_text_from_scanned_pdf(local_path)

        if not ocr_text.strip():
            raise ValueError(
                "OCR could not find any readable text. Try a sharper, well-lit, "
                "higher-resolution scan/photo with the text facing the camera squarely."
            )

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as txt_tmp:
            txt_tmp.write(ocr_text)
            txt_path = txt_tmp.name

        result = ingest_single_file(
            txt_path, pipeline=pipeline, file_id=file_id, original_filename=original_filename,
        )
        invalidate_bm25_cache(result["pipeline"])

        record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if record:
            record.pipeline = result["pipeline"]
            record.chunk_count = result["chunks"]
            record.ocr_confidence = ocr_confidence
            record.status = "ready"
            record.error_message = None
            db.commit()
    except Exception as exc:
        db.rollback()
        record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if record:
            record.status = "failed"
            record.error_message = str(exc)
            db.commit()
    finally:
        if txt_path and os.path.exists(txt_path):
            os.unlink(txt_path)
        if local_path and os.path.exists(local_path):
            os.unlink(local_path)
        db.close()


@router.post("/upload", response_model=IngestResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
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

    # Pre-generate the file ID so it can be stamped on chunks at ingestion time.
    # This enables per-file retrieval filtering for employee access control.
    new_file_id = str(uuid.uuid4())
    stored_name = f"{new_file_id}{suffix}"

    # A local temp copy is needed regardless of storage backend — Tesseract,
    # pdf2image, pypdf, and python-docx all operate on real filesystem paths.
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    # Determine whether OCR is required up front — images always need it,
    # PDFs only if they have no text layer (a quick pypdf check, not OCR itself).
    needs_ocr = suffix in IMAGE_EXTENSIONS
    if suffix == ".pdf":
        from app.ingestion.ocr_service import is_scanned_pdf
        needs_ocr = is_scanned_pdf(tmp_path)

    # Durable copy — R2 if configured, else local disk under UPLOADS_DIR.
    permanent_ref = file_storage.save_bytes(stored_name, contents, base_dir=UPLOADS_DIR)

    if needs_ocr:
        resolved_pipeline = pipeline or _detect_pipeline(file.filename)
        try:
            uploaded_file = UploadedFile(
                id=new_file_id,
                filename=file.filename,
                original_name=file.filename,
                file_type=suffix.replace(".", ""),
                pipeline=resolved_pipeline,
                chunk_count=0,
                ocr_used=True,
                ocr_confidence=None,
                uploaded_by=user.user_id,
                file_path=permanent_ref,
                status="processing",
            )
            db.add(uploaded_file)
            db.commit()
        except Exception as exc:
            db.rollback()
            file_storage.delete(permanent_ref)
            os.unlink(tmp_path)
            raise HTTPException(status_code=500, detail=f"Database error: {exc}")

        # _process_ocr_upload owns tmp_path from here and deletes it when done.
        background_tasks.add_task(
            _process_ocr_upload,
            file_id=new_file_id,
            local_path=tmp_path,
            suffix=suffix,
            pipeline=pipeline,
            original_filename=file.filename,
        )

        return IngestResponse(
            filename=file.filename,
            pipeline=resolved_pipeline,
            message=(
                f"'{file.filename}' needs OCR — processing in the background. "
                "It'll show its chunk count here once ready; refresh to check."
            ),
            ocr_used=True,
            status="processing",
            file_id=new_file_id,
        )

    # ── No OCR needed — ingest synchronously, same as before ────────────────
    try:
        result = ingest_single_file(
            tmp_path, pipeline=pipeline, file_id=new_file_id, original_filename=file.filename,
        )
    except Exception as exc:
        file_storage.delete(permanent_ref)
        raise HTTPException(status_code=422, detail=f"Ingestion failed: {exc}")
    finally:
        os.unlink(tmp_path)

    invalidate_bm25_cache(result["pipeline"])

    try:
        uploaded_file = UploadedFile(
            id=new_file_id,
            filename=file.filename,
            original_name=file.filename,
            file_type=suffix.replace(".", ""),
            pipeline=result["pipeline"],
            chunk_count=result["chunks"],
            ocr_used=False,
            ocr_confidence=None,
            uploaded_by=user.user_id,
            file_path=permanent_ref,
            status="ready",
        )
        db.add(uploaded_file)
        db.commit()
        db.refresh(uploaded_file)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")

    return IngestResponse(
        filename=file.filename,
        pipeline=result["pipeline"],
        pages=result["pages"],
        chunks_created=result["chunks"],
        message=f"Ingested {result['chunks']} chunks into '{result['pipeline']}' pipeline",
        ocr_used=False,
        status="ready",
        file_id=new_file_id,
    )


@router.get("/collections")
async def list_collections(user: TokenData = Depends(require_permission("upload"))):
    from app.ingestion.vector_store import list_collection_names
    return {"collections": list_collection_names()}

def _visible_file_ids_for_employee(db: Session, user_id: str) -> set:
    """File IDs explicitly granted to any group this user belongs to."""
    group_ids = [
        ug.group_id
        for ug in db.query(UserGroup).filter(UserGroup.user_id == user_id).all()
    ]
    if not group_ids:
        return set()
    rows = (
        db.query(GroupFileAccess)
        .filter(GroupFileAccess.group_id.in_(group_ids))
        .all()
    )
    return {row.file_id for row in rows}
 
 
@router.get("/files")
async def list_uploaded_files(
    db: Session = Depends(get_db),
    user: TokenData = Depends(get_current_user),
):
    """
    Admins see every uploaded file.
    Employees see ONLY files an admin has explicitly granted to one of
    their groups (per-file grant, not pipeline-wide). No download field —
    files are view-only from the client's perspective.
    """
    query = db.query(UploadedFile)
    if user.role != "admin":
        visible_ids = _visible_file_ids_for_employee(db, user.user_id)
        if not visible_ids:
            return []
        query = query.filter(UploadedFile.id.in_(visible_ids))
 
    files = query.order_by(UploadedFile.uploaded_at.desc()).all()
    return [
        {
            "id": file.id,
            "filename": file.filename,
            "original_name": file.original_name,
            "file_type": file.file_type,
            "pipeline": file.pipeline,
            "chunk_count": file.chunk_count,
            "is_active": file.is_active if file.is_active is not None else True,
            "ocr_used": bool(file.ocr_used),
            "ocr_confidence": file.ocr_confidence,
            "uploaded_by": file.uploaded_by,
            "uploaded_at": file.uploaded_at,
            "viewable": bool(file.file_path),
            "status": file.status or "ready",
            "error_message": file.error_message,
        }
        for file in files
    ]


@router.delete("/files/{file_id}", status_code=204)
async def delete_uploaded_file(
    file_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """Delete a file record, its stored copy, and its embedded chunks (admin only)."""
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    file_storage.delete(file.file_path)
    delete_documents_by_file_id(file_id, file.pipeline)
    invalidate_bm25_cache(file.pipeline)
    db.delete(file)
    db.commit()


@router.patch("/files/{file_id}/toggle")
async def toggle_file_active(
    file_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """Toggle a file's active status (admin only)."""
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    file.is_active = not (file.is_active if file.is_active is not None else True)
    db.commit()
    return {"id": file_id, "is_active": file.is_active}


@router.post("/files/{file_id}/retry")
async def retry_failed_upload(
    file_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """Re-runs OCR + ingestion for a file stuck in status='failed', without re-uploading."""
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    if file.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed uploads can be retried")
    if not file.file_path or not file_storage.exists(file.file_path):
        raise HTTPException(status_code=404, detail="Original file is no longer available")

    file.status = "processing"
    file.error_message = None
    db.commit()

    suffix = os.path.splitext(file.file_path)[1].lower()
    local_path = file_storage.download_to_tempfile(file.file_path, suffix=suffix)
    background_tasks.add_task(
        _process_ocr_upload,
        file_id=file_id,
        local_path=local_path,
        suffix=suffix,
        pipeline=file.pipeline,
        original_filename=file.original_name,
    )
    return {"id": file_id, "status": "processing"}


@router.get("/files/{file_id}/view")
async def view_uploaded_file(
    file_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(get_current_user),
):
    """
    Streams the file INLINE for in-browser viewing (PDF preview, text
    render, etc.). This is intentionally the only way to access file
    bytes — there is no download/attachment endpoint anywhere in this
    API. Browsers may still technically allow "save as" from their native
    viewer; per product decision, we are not engineering around that —
    we simply never provide an explicit download affordance.
    """
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
 
    if user.role != "admin":
        visible_ids = _visible_file_ids_for_employee(db, user.user_id)
        if file.id not in visible_ids:
            raise HTTPException(status_code=403, detail="You do not have access to this file")
 
    if not file.file_path or not file_storage.exists(file.file_path):
        raise HTTPException(status_code=404, detail="File is no longer available")

    media_type = MEDIA_TYPES.get(file.file_type, "application/octet-stream")
    data = file_storage.load_bytes(file.file_path)

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{file.original_name}"'},
    )
 
 
@router.get("/files/{file_id}/access")
async def list_file_access(
    file_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),  # admin-only, enforced
):
    """Lists which groups currently have access to this file."""
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
 
    grants = db.query(GroupFileAccess).filter(GroupFileAccess.file_id == file_id).all()
    group_ids = [g.group_id for g in grants]
    groups = db.query(Group).filter(Group.id.in_(group_ids)).all() if group_ids else []
    return [{"group_id": g.id, "group_name": g.name} for g in groups]
 
 
@router.post("/files/{file_id}/access/{group_id}", status_code=201)
async def grant_file_access(
    file_id: str,
    group_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),  # admin-only, enforced
):
    """Admin grants a group permission to see/view this specific file."""
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    member_count = db.query(UserGroup).filter(UserGroup.group_id == group_id).count()
    if member_count == 0:
        raise HTTPException(
            status_code=400,
            detail=f"This group has no members. Please add at least one member before granting access.",
        )

    existing = (
        db.query(GroupFileAccess)
        .filter(GroupFileAccess.file_id == file_id, GroupFileAccess.group_id == group_id)
        .first()
    )
    if existing:
        return {"message": "Already granted"}
 
    db.add(GroupFileAccess(file_id=file_id, group_id=group_id))
    db.commit()
    return {"message": f"Granted '{group.name}' access to '{file.original_name}'"}
 
 
@router.delete("/files/{file_id}/access/{group_id}", status_code=204)
async def revoke_file_access(
    file_id: str,
    group_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),  # admin-only, enforced
):
    """Admin revokes a group's permission to see/view this specific file."""
    grant = (
        db.query(GroupFileAccess)
        .filter(GroupFileAccess.file_id == file_id, GroupFileAccess.group_id == group_id)
        .first()
    )
    if not grant:
        raise HTTPException(status_code=404, detail="Grant not found")
    db.delete(grant)
    db.commit()