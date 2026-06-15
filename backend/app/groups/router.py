"""
groups/router.py

Group management — admins create groups, assign employees, and control
which pipelines each group can access.

Endpoints:
  POST   /api/groups                        Create a group (admin only)
  GET    /api/groups                        List all groups (admin only)
  GET    /api/groups/{group_id}             Get group details + members
  DELETE /api/groups/{group_id}             Delete a group (admin only)
  POST   /api/groups/{group_id}/members     Add employee to group (admin only)
  DELETE /api/groups/{group_id}/members/{user_id}  Remove employee (admin only)
  GET    /api/groups/{group_id}/members     List members of a group
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.auth.auth_service import get_current_user, TokenData
from app.chat.database import get_db
from app.chat.models import Group, UserGroup, User

router = APIRouter(prefix="/api/groups", tags=["groups"])


# ── Auth helper ───────────────────────────────────────────────────────────────

def require_admin(user: TokenData = Depends(get_current_user)) -> TokenData:
    """Raises 403 if the caller is not an admin."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ── Request / Response schemas ────────────────────────────────────────────────

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = ""


class AddMemberRequest(BaseModel):
    user_id: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_group(
    body: GroupCreate,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """Create a new group. Name must be unique."""
    if db.query(Group).filter(Group.name == body.name).first():
        raise HTTPException(status_code=400, detail=f"Group '{body.name}' already exists")

    group = Group(name=body.name, description=body.description or "")
    db.add(group)
    db.commit()
    db.refresh(group)

    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "created_at": str(group.created_at),
    }


@router.get("")
async def list_groups(
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """List all groups with their member count."""
    groups = db.query(Group).order_by(Group.created_at.desc()).all()

    return [
        {
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "member_count": len(g.members),
            "created_at": str(g.created_at),
        }
        for g in groups
    ]


@router.get("/{group_id}")
async def get_group(
    group_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """Get a single group with its full member list."""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    members = _get_members(db, group_id)

    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "created_at": str(group.created_at),
        "members": members,
    }


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """Delete a group and all its memberships (cascade)."""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    db.delete(group)
    db.commit()


@router.post("/{group_id}/members", status_code=201)
async def add_member(
    group_id: str,
    body: AddMemberRequest,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """Add an employee to a group. An employee can belong to multiple groups."""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    target_user = db.query(User).filter(User.id == body.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already a member
    existing = (
        db.query(UserGroup)
        .filter(UserGroup.user_id == body.user_id, UserGroup.group_id == group_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"User '{target_user.email}' is already a member of this group",
        )

    membership = UserGroup(user_id=body.user_id, group_id=group_id)
    db.add(membership)
    db.commit()

    return {
        "message": f"'{target_user.email}' added to group '{group.name}'",
        "user_id": body.user_id,
        "group_id": group_id,
    }


@router.delete("/{group_id}/members/{user_id}", status_code=204)
async def remove_member(
    group_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """Remove an employee from a group."""
    membership = (
        db.query(UserGroup)
        .filter(UserGroup.user_id == user_id, UserGroup.group_id == group_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")

    db.delete(membership)
    db.commit()


@router.get("/{group_id}/members")
async def list_members(
    group_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """List all members of a group."""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    return _get_members(db, group_id)


# ── Shared helper ─────────────────────────────────────────────────────────────

def _get_members(db: Session, group_id: str) -> list:
    """Returns a clean list of member dicts for a given group."""
    memberships = (
        db.query(UserGroup)
        .filter(UserGroup.group_id == group_id)
        .all()
    )

    result = []
    for m in memberships:
        u = db.query(User).filter(User.id == m.user_id).first()
        if u:
            result.append({
                "user_id": u.id,
                "email": u.email,
                "role": u.role,
                "joined_at": str(m.joined_at),
            })
    return result