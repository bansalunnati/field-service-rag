"""
analytics/router.py

Admin-only observability endpoints.

GET /api/analytics/overview   — totals + pipeline breakdown
GET /api/analytics/queries    — paginated query log
GET /api/analytics/hitl       — HITL throughput metrics
GET /api/analytics/pipelines  — per-pipeline stats
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.auth_service import TokenData, require_permission
from app.chat.database import get_db
from app.chat.models import FieldReport, HITLReview, QueryLog

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _require_admin(user: TokenData = Depends(require_permission("manage_users"))) -> TokenData:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


# ── Overview ────────────────────────────────────────────────────────────────────

@router.get("/overview")
def overview(
    db: Session = Depends(get_db),
    _: TokenData = Depends(_require_admin),
):
    total_queries = db.query(func.count(QueryLog.id)).scalar() or 0

    avg_latency = (
        db.query(func.avg(QueryLog.latency_ms))
        .filter(QueryLog.latency_ms.isnot(None))
        .scalar()
    )

    pipeline_rows = (
        db.query(
            QueryLog.pipeline,
            func.count(QueryLog.id).label("count"),
            func.avg(QueryLog.latency_ms).label("avg_latency"),
        )
        .group_by(QueryLog.pipeline)
        .all()
    )

    hitl_pending = (
        db.query(func.count(HITLReview.id))
        .filter(HITLReview.decision.is_(None))
        .scalar()
        or 0
    )

    return {
        "total_queries": total_queries,
        "avg_latency_ms": round(avg_latency, 1) if avg_latency else 0.0,
        "hitl_pending": hitl_pending,
        "pipeline_breakdown": [
            {
                "pipeline": row.pipeline,
                "count": row.count,
                "avg_latency_ms": round(row.avg_latency, 1) if row.avg_latency else 0.0,
            }
            for row in pipeline_rows
        ],
    }


# ── Query log ───────────────────────────────────────────────────────────────────

@router.get("/queries")
def query_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    pipeline: Optional[str] = None,
    db: Session = Depends(get_db),
    _: TokenData = Depends(_require_admin),
):
    q = db.query(QueryLog).order_by(QueryLog.timestamp.desc())
    if pipeline:
        q = q.filter(QueryLog.pipeline == pipeline)

    total = q.count()
    items = q.offset((page - 1) * limit).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id": log.id,
                "session_id": log.session_id,
                "user_id": log.user_id,
                "pipeline": log.pipeline,
                "question": log.question,
                "answer": (log.answer or "")[:200],
                "latency_ms": log.latency_ms,
                "error": log.error,
                "ground_truth": log.ground_truth,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in items
        ],
    }


# ── HITL metrics ────────────────────────────────────────────────────────────────

@router.get("/hitl")
def hitl_metrics(
    db: Session = Depends(get_db),
    _: TokenData = Depends(_require_admin),
):
    total = db.query(func.count(HITLReview.id)).scalar() or 0
    approved = (
        db.query(func.count(HITLReview.id))
        .filter(HITLReview.decision == "approved")
        .scalar()
        or 0
    )
    rejected = (
        db.query(func.count(HITLReview.id))
        .filter(HITLReview.decision == "rejected")
        .scalar()
        or 0
    )
    pending = (
        db.query(func.count(HITLReview.id))
        .filter(HITLReview.decision.is_(None))
        .scalar()
        or 0
    )

    # Average hours from creation to review (only completed reviews)
    reviewed_rows = (
        db.query(HITLReview.created_at, HITLReview.reviewed_at)
        .filter(HITLReview.reviewed_at.isnot(None))
        .all()
    )
    if reviewed_rows:
        total_hours = sum(
            (r.reviewed_at - r.created_at).total_seconds() / 3600
            for r in reviewed_rows
            if r.reviewed_at and r.created_at
        )
        avg_review_hours = round(total_hours / len(reviewed_rows), 2)
    else:
        avg_review_hours = 0.0

    return {
        "total_reviews": total,
        "approved": approved,
        "rejected": rejected,
        "pending": pending,
        "avg_review_time_hours": avg_review_hours,
    }


# ── Per-pipeline stats ──────────────────────────────────────────────────────────

@router.get("/pipelines")
def pipeline_stats(
    db: Session = Depends(get_db),
    _: TokenData = Depends(_require_admin),
):
    rows = (
        db.query(
            QueryLog.pipeline,
            func.count(QueryLog.id).label("query_count"),
            func.avg(QueryLog.latency_ms).label("avg_latency"),
        )
        .group_by(QueryLog.pipeline)
        .all()
    )

    result = []
    for row in rows:
        error_count = (
            db.query(func.count(QueryLog.id))
            .filter(QueryLog.pipeline == row.pipeline, QueryLog.error.isnot(None))
            .scalar()
            or 0
        )
        result.append(
            {
                "pipeline": row.pipeline,
                "query_count": row.query_count,
                "avg_latency_ms": round(row.avg_latency, 1) if row.avg_latency else 0.0,
                "error_rate": round(error_count / row.query_count, 3) if row.query_count else 0.0,
            }
        )
    return result
