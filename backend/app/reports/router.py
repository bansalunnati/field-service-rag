"""
reports/router.py

Employee report submission and admin review queue.

Endpoints:
  POST  /api/reports/submit           Employee submits a filled report (file upload)
  GET   /api/reports/my               Employee views their own submissions + status
  GET   /api/reports/all              Admin views all submissions
  PATCH /api/reports/{id}/hitl        Admin approves or rejects a needs_hitl report
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.auth_service import TokenData, get_current_user
from app.chat.database import get_db
from app.chat.models import FieldReport, HITLReview, Notification, User
from app.reports.reviewer import run_agentic_review
from app.chat.models import FieldReport, HITLReview, Notification, User

router = APIRouter(prefix="/api/reports", tags=["reports"])

REPORTS_DIR = os.getenv("REPORTS_DIR", "data/submitted_reports")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"} | IMAGE_EXTENSIONS
os.makedirs(REPORTS_DIR, exist_ok=True)

MEDIA_TYPES = {
    "pdf":  "application/pdf",
    "txt":  "text/plain",
    "md":   "text/markdown",
    "png":  "image/png",
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

def _notify_admins_new_report(db: Session, report: FieldReport, submitter_email: str):
    """Notifies every admin that a new report has been submitted and needs eventual review."""
    admin_ids = [u.id for u in db.query(User).filter(User.role == "admin").all()]
    for admin_id in admin_ids:
        db.add(Notification(
            user_id=admin_id,
            notification_type="new_report",
            message=f"{submitter_email} submitted a new report: '{report.title}'",
            ref_type="field_report",
            ref_id=report.id,
        ))
    db.commit()
# ── Auth helpers ──────────────────────────────────────────────────────────────

def require_employee(user: TokenData = Depends(get_current_user)) -> TokenData:
    if user.role not in ("user", "admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    return user

def require_admin(user: TokenData = Depends(get_current_user)) -> TokenData:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ── Submit ────────────────────────────────────────────────────────────────────

@router.post("/submit", status_code=202)
async def submit_report(
    background_tasks: BackgroundTasks,
    title:       str        = Form(...),
    report_type: str        = Form(...),   # e.g. "hazmat_inspection", "tower_sop"
    file:        UploadFile = File(...),
    db:          Session    = Depends(get_db),
    user:        TokenData  = Depends(require_employee),
):
    """
    Employee submits a completed inspection report.

    - File is saved to REPORTS_DIR (not ingested into ChromaDB).
    - A FieldReport record is created with status='under_review'.
    - The agentic reviewer is launched immediately as a background task.
    - Returns 202 Accepted — review result arrives via Notifications.
    """
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    contents = await file.read()

    # Save file to disk — keyed by a FieldReport UUID we generate now
    import uuid
    report_id = str(uuid.uuid4())
    safe_name = f"{report_id}{suffix}"
    file_path = os.path.join(REPORTS_DIR, safe_name)
    with open(file_path, "wb") as f:
        f.write(contents)

    # If the uploaded file is an image or a scanned PDF (no text layer), run OCR
    # and save the extracted text as a .txt file alongside the original.
    # The reviewer will use this text file instead of trying to read the image directly.
    review_path = file_path   # default: reviewer reads the original file
    ocr_used = False

    if suffix in IMAGE_EXTENSIONS:
        from app.ingestion.ocr_service import extract_text_from_image
        ocr_text, _ = extract_text_from_image(file_path)
        ocr_used = True
        txt_path = file_path + ".ocr.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(ocr_text)
        review_path = txt_path

    elif suffix == ".pdf":
        from app.ingestion.ocr_service import is_scanned_pdf, extract_text_from_scanned_pdf
        if is_scanned_pdf(file_path):
            ocr_text, _ = extract_text_from_scanned_pdf(file_path)
            ocr_used = True
            txt_path = file_path + ".ocr.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(ocr_text)
            review_path = txt_path

    # Write FieldReport record
    report = FieldReport(
        id=report_id,
        title=title,
        content="",                           # populated by reviewer after extraction
        submitted_by=user.user_id,
        status="under_review",
        metadata_json={
            "report_type": report_type,
            "original_filename": file.filename,
            "file_path": file_path,
            "ocr_used": ocr_used,
        },
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    _notify_admins_new_report(db, report, submitter_email=user.email if hasattr(user, "email") else user.user_id)
    # Fire agentic review — non-blocking, passes the OCR'd text path if applicable
    background_tasks.add_task(run_agentic_review, report_id, review_path, report_type)

    return {
        "report_id": report_id,
        "status":    "under_review",
        "message":   "Report received. AI review has started. You'll be notified of the result.",
    }


# ── Preview submitted file ────────────────────────────────────────────────────

@router.get("/{report_id}/view")
async def view_report_file(
    report_id: str,
    db:   Session   = Depends(get_db),
    user: TokenData  = Depends(require_employee),
):
    """
    Streams the originally submitted report file inline for in-browser preview.
    The submitting employee and any admin can view it; other employees cannot.
    """
    report = db.query(FieldReport).filter(FieldReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if user.role != "admin" and report.submitted_by != user.user_id:
        raise HTTPException(status_code=403, detail="You do not have access to this report")

    meta = report.metadata_json or {}
    file_path = meta.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Report file is no longer available")

    suffix = Path(file_path).suffix.lstrip(".").lower()
    media_type = MEDIA_TYPES.get(suffix, "application/octet-stream")
    original_name = meta.get("original_filename", os.path.basename(file_path))

    def _stream():
        with open(file_path, "rb") as f:
            yield from f

    return StreamingResponse(
        _stream(),
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{original_name}"'},
    )


# ── Employee: view own submissions ────────────────────────────────────────────

@router.get("/my")
async def my_reports(
    db:   Session   = Depends(get_db),
    user: TokenData = Depends(require_employee),
):
    reports = (
        db.query(FieldReport)
        .filter(FieldReport.submitted_by == user.user_id)
        .order_by(FieldReport.submitted_at.desc())
        .all()
    )
    return [_serialize(r) for r in reports]


# ── Admin: view all submissions ───────────────────────────────────────────────

@router.get("/all")
async def all_reports(
    db:   Session   = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    reports = (
        db.query(FieldReport)
        .order_by(FieldReport.submitted_at.desc())
        .all()
    )
    return [_serialize(r, include_submitter=True) for r in reports]


# ── Admin: HITL decision ──────────────────────────────────────────────────────

from pydantic import BaseModel

class HITLDecision(BaseModel):
    decision: str   # "approved" | "rejected"
    notes: Optional[str] = ""

@router.patch("/{report_id}/hitl")
async def hitl_review(
    report_id: str,
    body:      HITLDecision,
    db:        Session   = Depends(get_db),
    user:      TokenData = Depends(require_admin),
):
    """
    Admin makes a manual decision on a report in needs_hitl status.
    Updates both the HITLReview record and the parent FieldReport status.
    Notifies the employee of the outcome.
    """
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")

    report = db.query(FieldReport).filter(FieldReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != "needs_hitl":
        raise HTTPException(
            status_code=400,
            detail=f"Report is not awaiting HITL review (current status: '{report.status}')",
        )

    # Update HITLReview
    hitl = db.query(HITLReview).filter(HITLReview.report_id == report_id).first()
    if hitl:
        hitl.decision    = body.decision
        hitl.notes       = body.notes or ""
        hitl.reviewed_by = user.user_id
        hitl.reviewed_at = datetime.utcnow()

    # Update FieldReport
    report.status     = body.decision   # "approved" or "rejected"
    report.updated_at = datetime.utcnow()
    db.commit()

    # Notify the employee
    db.add(Notification(
        user_id=report.submitted_by,
        notification_type=f"report_{body.decision}",
        message=(
            f"Your report '{report.title}' was manually reviewed and {body.decision} by an admin."
            + (f" Note: {body.notes}" if body.notes else "")
        ),
        ref_type="field_report",
        ref_id=report_id,
    ))
    db.commit()

    return {
        "report_id": report_id,
        "status":    body.decision,
        "message":   f"Report {body.decision} successfully.",
    }


# ── Serializer ────────────────────────────────────────────────────────────────

def _serialize(report: FieldReport, include_submitter: bool = False) -> dict:
    out = {
        "id":           report.id,
        "title":        report.title,
        "report_type":  (report.metadata_json or {}).get("report_type", ""),
        "status":       report.status,
        "submitted_at": str(report.submitted_at),
        "updated_at":   str(report.updated_at),
        "ai_summary":   (report.metadata_json or {}).get("ai_summary", ""),
        "hitl_reason":  (report.metadata_json or {}).get("hitl_reason", ""),
        "ocr_used":     bool((report.metadata_json or {}).get("ocr_used", False)),
        "matched_sources": (report.metadata_json or {}).get("matched_sources", []),
    }
    if include_submitter and report.submitted_by_user:
        out["submitted_by"] = report.submitted_by_user.email
    return out