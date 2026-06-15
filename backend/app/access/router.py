"""
access/router.py

Controls which pipelines a group is allowed to query.

Endpoints:
  GET   /api/access/{group_id}              Get all pipeline access entries for a group
  POST  /api/access/{group_id}/{pipeline}   Grant a pipeline to a group (admin only)
  DELETE /api/access/{group_id}/{pipeline}  Revoke a pipeline from a group (admin only)

Valid pipeline values: equipment | safety | field_reports

How it works:
  - A FileAccess row exists for each (group, pipeline) pair that is granted.
  - If no row exists for a pipeline, the group cannot query it.
  - The chat router checks this table before running any RAG query.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.auth_service import get_current_user, TokenData
from app.chat.database import get_db
from app.chat.models import FileAccess, Group

router = APIRouter(prefix="/api/access", tags=["access"])

# Pipelines the system knows about — used for validation
VALID_PIPELINES = {"equipment", "safety", "field_reports"}


# ── Auth helper ───────────────────────────────────────────────────────────────

def require_admin(user: TokenData = Depends(get_current_user)) -> TokenData:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{group_id}")
async def get_group_access(
    group_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """
    Returns the pipeline access list for a group.
    Shows all 3 pipelines and whether each is granted or not.
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    granted = {
        row.pipeline
        for row in db.query(FileAccess).filter(FileAccess.group_id == group_id).all()
    }

    return {
        "group_id": group_id,
        "group_name": group.name,
        "pipelines": [
            {
                "pipeline": p,
                "granted": p in granted,
            }
            for p in sorted(VALID_PIPELINES)
        ],
    }


@router.post("/{group_id}/{pipeline}", status_code=201)
async def grant_access(
    group_id: str,
    pipeline: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """Grant a group access to a pipeline. Safe to call if already granted."""
    _validate(group_id, pipeline, db)

    existing = (
        db.query(FileAccess)
        .filter(FileAccess.group_id == group_id, FileAccess.pipeline == pipeline)
        .first()
    )
    if existing:
        return {"message": f"Access to '{pipeline}' already granted", "group_id": group_id, "pipeline": pipeline}

    db.add(FileAccess(group_id=group_id, pipeline=pipeline))
    db.commit()

    return {"message": f"Access to '{pipeline}' granted", "group_id": group_id, "pipeline": pipeline}


@router.delete("/{group_id}/{pipeline}", status_code=200)
async def revoke_access(
    group_id: str,
    pipeline: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """Revoke a group's access to a pipeline."""
    _validate(group_id, pipeline, db)

    row = (
        db.query(FileAccess)
        .filter(FileAccess.group_id == group_id, FileAccess.pipeline == pipeline)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"No access entry found for pipeline '{pipeline}'")

    db.delete(row)
    db.commit()

    return {"message": f"Access to '{pipeline}' revoked", "group_id": group_id, "pipeline": pipeline}


# ── Helper ────────────────────────────────────────────────────────────────────

def _validate(group_id: str, pipeline: str, db: Session):
    """Checks group exists and pipeline name is valid. Raises 404/400 if not."""
    if not db.query(Group).filter(Group.id == group_id).first():
        raise HTTPException(status_code=404, detail="Group not found")
    if pipeline not in VALID_PIPELINES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pipeline '{pipeline}'. Valid options: {sorted(VALID_PIPELINES)}",
        )