from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.auth_service import get_current_user, TokenData
from app.chat.database import get_db
from app.chat.models import HITLReview, FieldReport
from pydantic import BaseModel
from datetime import datetime
from app.chat.models import Notification

router = APIRouter(
    prefix="/api/hitl",
    tags=["hitl"]
)


def require_admin(
    user: TokenData = Depends(get_current_user)
):
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return user

@router.get("/queue")
async def get_hitl_queue(
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin)
):

class HITLDecision(BaseModel):
    notes: str = ""


@router.patch("/{report_id}/approve")
async def approve_report(
    report_id: str,
    body: HITLDecision,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin)
):
    report = (
        db.query(FieldReport)
        .filter(FieldReport.id == report_id)
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    hitl = (
        db.query(HITLReview)
        .filter(HITLReview.report_id == report_id)
        .first()
    )

    if hitl:
        hitl.decision = "approved"
        hitl.notes = body.notes
        hitl.reviewed_by = user.user_id
        hitl.reviewed_at = datetime.utcnow()

    report.status = "approved"

    db.commit()

    db.add(
        Notification(
            user_id=report.submitted_by,
            notification_type="report_approved",
            message=f"Your report '{report.title}' was approved.",
            ref_type="field_report",
            ref_id=report_id,
        )
    )

    db.commit()

    return {
        "status": "approved",
        "report_id": report_id
    }


@router.patch("/{report_id}/reject")
async def reject_report(
    report_id: str,
    body: HITLDecision,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin)
):
    report = (
        db.query(FieldReport)
        .filter(FieldReport.id == report_id)
        .first()
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )

    hitl = (
        db.query(HITLReview)
        .filter(HITLReview.report_id == report_id)
        .first()
    )

    if hitl:
        hitl.decision = "rejected"
        hitl.notes = body.notes
        hitl.reviewed_by = user.user_id
        hitl.reviewed_at = datetime.utcnow()

    report.status = "rejected"

    db.commit()

    db.add(
        Notification(
            user_id=report.submitted_by,
            notification_type="report_rejected",
            message=f"Your report '{report.title}' was rejected.",
            ref_type="field_report",
            ref_id=report_id,
        )
    )

    db.commit()

    return {
        "status": "rejected",
        "report_id": report_id
    }

    reviews = (
        db.query(HITLReview)
        .filter(HITLReview.decision == None)
        .all()
    )

    results = []

    for review in reviews:
        report = (
            db.query(FieldReport)
            .filter(FieldReport.id == review.report_id)
            .first()
        )

        if report:
            results.append({
                "review_id": review.id,
                "report_id": report.id,
                "title": report.title,
                "status": report.status,
                "submitted_at": report.submitted_at
            })

    return results