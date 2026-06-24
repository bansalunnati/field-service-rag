"""
tasks/router.py
Workflow task assignment and tracking.

Endpoints:
  POST   /api/tasks                       Create + assign a task (admin only)
  GET    /api/tasks                       List tasks (admin: all, employee: assigned to them)
  GET    /api/tasks/{task_id}             Get a single task
  PATCH  /api/tasks/{task_id}/status      Update task status (assignee or admin)
  PATCH  /api/tasks/{task_id}             Edit task fields (admin only)
  DELETE /api/tasks/{task_id}             Delete a task (admin only)

Notifications:
  - Creating a task notifies the assignee ("task_assigned").
  - Changing status notifies the admin who created it / all admins ("task_updated"),
    specifically flagging completion so admins know whether a task was completed or not.
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.auth_service import get_current_user, TokenData
from app.chat.database import get_db
from app.chat.models import WorkflowTask, FieldReport, User, Notification

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

VALID_STATUSES = {"open", "in_progress", "pending_review", "done"}
VALID_PRIORITIES = {"low", "medium", "high"}


# ── Auth helpers ───────────────────────────────────────────────────────────────
def require_admin(user: TokenData = Depends(get_current_user)) -> TokenData:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ── Schemas ──────────────────────────────────────────────────────────────────
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    assigned_to: Optional[str] = None     # user_id or email of the employee (None = unassigned)
    report_id: Optional[str] = None       # link to a FieldReport if relevant
    priority: str = "medium"
    due_date: Optional[datetime] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[datetime] = None


class TaskStatusUpdate(BaseModel):
    status: str   # "open" | "in_progress" | "done"


# ── Helpers ──────────────────────────────────────────────────────────────────
def _serialize(task: WorkflowTask) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "report_id": task.report_id,
        "assigned_to": task.assigned_to,
        "assigned_to_email": task.assigned_to_user.email if task.assigned_to_user else None,
        "status": task.status,
        "priority": task.priority,
        "due_date": task.due_date,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def _get_admin_ids(db: Session) -> List[str]:
    """Returns user_ids of all admins, used to fan out task-update notifications."""
    return [u.id for u in db.query(User).filter(User.role == "admin").all()]


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.post("", status_code=201)
async def create_task(
    body: TaskCreate,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """Admin creates a task and assigns it to an employee."""
    if body.priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"priority must be one of {sorted(VALID_PRIORITIES)}")

    assignee = None
    resolved_assigned_to = None
    if body.assigned_to:
        # Accept either user_id or email
        assignee = (
            db.query(User).filter(User.id == body.assigned_to).first()
            or db.query(User).filter(User.email == body.assigned_to).first()
        )
        if not assignee:
            raise HTTPException(status_code=404, detail="Assigned user not found")
        resolved_assigned_to = assignee.id

    if body.report_id:
        report = db.query(FieldReport).filter(FieldReport.id == body.report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Linked report not found")

    task = WorkflowTask(
        title=body.title,
        description=body.description or "",
        assigned_to=resolved_assigned_to,
        report_id=body.report_id,
        priority=body.priority,
        due_date=body.due_date,
        status="open",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Notify the assignee if one was set
    if resolved_assigned_to:
        db.add(Notification(
            user_id=resolved_assigned_to,
            notification_type="task_assigned",
            message=f"You were assigned a new task: '{task.title}'",
            ref_type="workflow_task",
            ref_id=task.id,
        ))
        db.commit()

    return _serialize(task)


@router.get("")
async def list_tasks(
    db: Session = Depends(get_db),
    user: TokenData = Depends(get_current_user),
):
    """
    Admins see all tasks. Employees see only tasks assigned to them.
    """
    query = db.query(WorkflowTask)
    if user.role != "admin":
        query = query.filter(WorkflowTask.assigned_to == user.user_id)
    tasks = query.order_by(WorkflowTask.created_at.desc()).all()
    return [_serialize(t) for t in tasks]


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(get_current_user),
):
    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if user.role != "admin" and task.assigned_to != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return _serialize(task)


@router.patch("/{task_id}/status")
async def update_task_status(
    task_id: str,
    body: TaskStatusUpdate,
    db: Session = Depends(get_db),
    user: TokenData = Depends(get_current_user),
):
    """
    The assignee (or an admin) updates task status.
    Notifies all admins so they know whether the task was completed or not.

    An employee marking "done" only moves the task to "pending_review" —
    self-reported completion isn't reflected as done on the admin side
    until an admin confirms it. Only an admin can set status to "done"
    directly.
    """
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(VALID_STATUSES)}")

    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if user.role != "admin" and task.assigned_to != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    new_status = body.status
    if user.role != "admin" and new_status == "done":
        new_status = "pending_review"

    previous_status = task.status
    task.status = new_status
    task.updated_at = datetime.utcnow()
    db.commit()

    # Notify admins of the status change, calling out completion explicitly.
    if previous_status != new_status:
        assignee = db.query(User).filter(User.id == task.assigned_to).first()
        assignee_label = assignee.email if assignee else "An employee"
        if new_status == "pending_review":
            message = f"{assignee_label} marked task '{task.title}' done — awaiting your confirmation."
        elif new_status == "done":
            message = f"Task '{task.title}' confirmed complete."
        else:
            message = f"{assignee_label} updated task '{task.title}' to '{new_status}'."
        for admin_id in _get_admin_ids(db):
            db.add(Notification(
                user_id=admin_id,
                notification_type="task_updated",
                message=message,
                ref_type="workflow_task",
                ref_id=task.id,
            ))
        db.commit()

    return _serialize(task)


@router.patch("/{task_id}")
async def update_task(
    task_id: str,
    body: TaskUpdate,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    """Admin edits task fields (reassign, change priority/due date, etc.)."""
    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if body.priority is not None and body.priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"priority must be one of {sorted(VALID_PRIORITIES)}")

    reassigned = False
    if body.assigned_to is not None and body.assigned_to != task.assigned_to:
        new_assignee = db.query(User).filter(User.id == body.assigned_to).first()
        if not new_assignee:
            raise HTTPException(status_code=404, detail="Assigned user not found")
        task.assigned_to = body.assigned_to
        reassigned = True

    if body.title is not None:
        task.title = body.title
    if body.description is not None:
        task.description = body.description
    if body.priority is not None:
        task.priority = body.priority
    if body.due_date is not None:
        task.due_date = body.due_date

    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)

    if reassigned:
        db.add(Notification(
            user_id=task.assigned_to,
            notification_type="task_assigned",
            message=f"You were assigned task: '{task.title}'",
            ref_type="workflow_task",
            ref_id=task.id,
        ))
        db.commit()

    return _serialize(task)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_admin),
):
    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()