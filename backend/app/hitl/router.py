from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.auth_service import get_current_user, TokenData
from app.chat.database import get_db
from app.chat.models import HITLReview, FieldReport

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