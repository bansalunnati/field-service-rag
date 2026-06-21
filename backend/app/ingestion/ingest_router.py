"""
ingestion/ingest_router.py  — NEW file, add to app/ingestion/
FastAPI router for document uploads.
POST /api/ingest/upload  — accepts PDF, DOCX, TXT, CSV, MD
"""

import os
import tempfile
import shutil
import uuid

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi.responses import StreamingResponse
from app.chat.models import UploadedFile, GroupFileAccess, UserGroup, Group
from app.auth.auth_service import get_current_user   # in addition to require_permission 

from app.chat.database import get_db
from app.chat.models import UploadedFile
from app.auth.auth_service import require_permission, TokenData
from app.ingestion.ingest_documents import ingest_single_file
from app.retrieval.retriever import invalidate_bm25_cache

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
    pages:           int
    chunks_created:  int
    message:         str
    ocr_used:        bool = False
    ocr_confidence:  float | None = None


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

    permanent_path = None
    ocr_used = False
    ocr_confidence = None

    # Pre-generate the file ID so it can be stamped on ChromaDB chunks at ingestion time.
    # This enables per-file retrieval filtering for employee access control.
    new_file_id = str(uuid.uuid4())
    try:
        # ── OCR step (images and scanned PDFs) ────────────────────────────────
        # For image files: run OCR to extract text, then write it to a .txt temp
        # file so the normal ingestion pipeline can handle it.
        # For PDFs with no text layer: same approach — OCR each page first.
        ingest_path = tmp_path  # default: ingest the original file

        if suffix in IMAGE_EXTENSIONS:
            # It's an image — always OCR it
            try:
                from app.ingestion.ocr_service import extract_text_from_image
                ocr_text, ocr_confidence = extract_text_from_image(tmp_path)
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"OCR failed for image '{file.filename}': {exc}. "
                           "Ensure Tesseract is installed on the server (apt-get install -y tesseract-ocr).",
                )
            if not ocr_text.strip():
                raise HTTPException(
                    status_code=422,
                    detail=f"OCR could not find any readable text in '{file.filename}'. "
                           "Try a sharper, well-lit, higher-resolution photo with the text "
                           "facing the camera squarely.",
                )
            ocr_used = True
            # Write extracted text to a temp .txt file for ingestion
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as txt_tmp:
                txt_tmp.write(ocr_text)
                ingest_path = txt_tmp.name

        elif suffix == ".pdf":
            # Check if the PDF is scanned (no text layer)
            try:
                from app.ingestion.ocr_service import is_scanned_pdf, extract_text_from_scanned_pdf
                if is_scanned_pdf(tmp_path):
                    ocr_text, ocr_confidence = extract_text_from_scanned_pdf(tmp_path)
                    if not ocr_text.strip():
                        raise HTTPException(
                            status_code=422,
                            detail=f"OCR could not find any readable text in '{file.filename}'. "
                                   "Try a clearer scan or a higher-resolution photo.",
                        )
                    ocr_used = True
                    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as txt_tmp:
                        txt_tmp.write(ocr_text)
                        ingest_path = txt_tmp.name
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"OCR failed for scanned PDF '{file.filename}': {exc}. "
                           "Ensure Tesseract and poppler-utils are installed on the server.",
                )

        try:
            result = ingest_single_file(ingest_path, pipeline=pipeline, file_id=new_file_id)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Ingestion failed: {exc}")
        finally:
            # Clean up the OCR temp .txt file if we created one
            if ingest_path != tmp_path and os.path.exists(ingest_path):
                os.unlink(ingest_path)

        invalidate_bm25_cache(result["pipeline"])

        stored_name = f"{new_file_id}{suffix}"
        permanent_path = os.path.join(UPLOADS_DIR, stored_name)
        shutil.copyfile(tmp_path, permanent_path)

        try:
            uploaded_file = UploadedFile(
                id=new_file_id,
                filename=file.filename,
                original_name=file.filename,
                file_type=suffix.replace(".", ""),
                pipeline=result["pipeline"],
                chunk_count=result["chunks"],
                ocr_used=ocr_used,
                ocr_confidence=ocr_confidence,
                uploaded_by=user.user_id,
                file_path=permanent_path,
            )
            db.add(uploaded_file)
            db.commit()
            db.refresh(uploaded_file)
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    finally:
        os.unlink(tmp_path)

    return IngestResponse(
        filename=file.filename,
        pipeline=result["pipeline"],
        pages=result["pages"],
        chunks_created=result["chunks"],
        message=f"Ingested {result['chunks']} chunks into '{result['pipeline']}' pipeline",
        ocr_used=ocr_used,
        ocr_confidence=ocr_confidence,
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
        }
        for file in files
    ]


@router.delete("/files/{file_id}", status_code=204)
async def delete_uploaded_file(
    file_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """Delete a file record and its stored copy on disk (admin only)."""
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    # Remove from disk if present
    if file.file_path and os.path.exists(file.file_path):
        try:
            os.remove(file.file_path)
        except OSError:
            pass
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
 
    if not file.file_path or not os.path.exists(file.file_path):
        raise HTTPException(status_code=404, detail="File is no longer available")
 
    media_type = MEDIA_TYPES.get(file.file_type, "application/octet-stream")
 
    def _stream():
        with open(file.file_path, "rb") as f:
            yield from f
 
    return StreamingResponse(
        _stream(),
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