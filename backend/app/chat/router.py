"""
chat/router.py

Endpoints:
    POST   /api/chat/sessions
    GET    /api/chat/sessions
    DELETE /api/chat/sessions/{session_id}
    GET    /api/chat/sessions/{session_id}/messages
    POST   /api/chat/sessions/{session_id}/query

Phase 5:
    - Chat history support
    - Citations support
    - Group-based pipeline access control

Access Rules:
    - Admins can query all pipelines.
    - Employees can only query pipelines granted to their groups.
"""

import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.auth_service import TokenData, require_permission
from app.chat.database import get_db
from app.chat.history_service import (
    append_message,
    build_context_window,
    create_session,
    delete_session,
    get_messages,
    get_session,
    get_sessions,
)
from app.chat.models import FileAccess, GroupFileAccess, QueryLog, UploadedFile, UserGroup
from app.retrieval.rag_pipeline import ask_question_across_pipelines


router = APIRouter(
    prefix="/api/chat",
    tags=["chat"],
)

ALL_PIPELINES = ["equipment", "safety", "field_reports"]


# ============================================================================
# Request Models
# ============================================================================

class SessionCreate(BaseModel):
    pipeline: str = "safety"
    title: str = "New Chat"


class QueryRequest(BaseModel):
    question: str
    pipeline: Optional[str] = None


# ============================================================================
# Access Control
# ============================================================================

def accessible_pipelines(user: TokenData, db: Session) -> List[str]:
    """
    Returns every pipeline the user may search.

    Admins: everything. Employees: the union of pipelines granted directly
    via Groups > Pipeline Access, plus any pipeline that has at least one
    file explicitly assigned to one of their groups via Assign Files.

    The chat no longer segregates by a single chosen pipeline — it answers
    from everything the user is allowed to see at once.
    """
    if user.role == "admin":
        return list(ALL_PIPELINES)

    group_ids = [
        ug.group_id
        for ug in db.query(UserGroup).filter(UserGroup.user_id == user.user_id).all()
    ]
    if not group_ids:
        return []

    granted = {
        row.pipeline
        for row in db.query(FileAccess).filter(FileAccess.group_id.in_(group_ids)).all()
    }

    file_granted = {
        row.pipeline
        for row in (
            db.query(UploadedFile.pipeline)
            .join(GroupFileAccess, GroupFileAccess.file_id == UploadedFile.id)
            .filter(GroupFileAccess.group_id.in_(group_ids))
            .all()
        )
    }

    return list(granted | file_granted)


# ============================================================================
# Session Endpoints
# ============================================================================

@router.post("/sessions", status_code=201)
async def new_session(
    body: SessionCreate,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_permission("query")),
):
    session = create_session(
        db,
        user.user_id,
        body.pipeline,
        body.title,
    )

    return {
        "id": session.id,
        "title": session.title,
        "pipeline": session.pipeline,
        "updated_at": str(session.updated_at),
    }


@router.get("/sessions")
async def list_sessions(
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_permission("query")),
):
    sessions = get_sessions(db, user.user_id)

    return [
        {
            "id": session.id,
            "title": session.title,
            "pipeline": session.pipeline,
            "updated_at": str(session.updated_at),
        }
        for session in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def remove_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_permission("view_history")),
):
    deleted = delete_session(
        db,
        session_id,
        user.user_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )


@router.get("/sessions/{session_id}/messages")
async def session_messages(
    session_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_permission("view_history")),
):
    session = get_session(
        db,
        session_id,
        user.user_id,
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    messages = get_messages(db, session_id)

    return [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "citations": message.citations,
            "created_at": str(message.created_at),
        }
        for message in messages
    ]


# ============================================================================
# Query Endpoint
# ============================================================================

@router.post("/sessions/{session_id}/query")
async def query(
    session_id: str,
    body: QueryRequest,
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_permission("query")),
):
    session = get_session(
        db,
        session_id,
        user.user_id,
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    history = build_context_window(db, session_id)

    # Always store the user message so session history is never blank
    append_message(db, session_id, "user", body.question)

    # Search across every pipeline the user can access — chat is no longer
    # segregated by a single chosen document category.
    pipelines = accessible_pipelines(user=user, db=db)
    if not pipelines:
        no_access_msg = "This document category is not available to your team."
        append_message(db, session_id, "assistant", no_access_msg, citations=[])
        raise HTTPException(status_code=403, detail=no_access_msg)

    # Resolve which file IDs the employee may retrieve from, per pipeline.
    # Admins map every pipeline to None → no filter (see all chunks).
    allowed_file_ids_by_pipeline: dict = {}
    if user.role == "admin":
        allowed_file_ids_by_pipeline = {p: None for p in pipelines}
    else:
        group_ids = [
            ug.group_id
            for ug in db.query(UserGroup).filter(UserGroup.user_id == user.user_id).all()
        ]
        for p in pipelines:
            grants = (
                db.query(GroupFileAccess)
                .join(UploadedFile, UploadedFile.id == GroupFileAccess.file_id)
                .filter(
                    GroupFileAccess.group_id.in_(group_ids),
                    UploadedFile.pipeline == p,
                )
                .all()
            )
            allowed_file_ids_by_pipeline[p] = [g.file_id for g in grants]

    # Run RAG pipeline with latency tracking
    t0 = time.monotonic()
    error_text = None
    result = {"answer": "", "citations": []}
    try:
        result = ask_question_across_pipelines(
            question=body.question,
            pipelines=pipelines,
            history=history,
            allowed_file_ids_by_pipeline=allowed_file_ids_by_pipeline,
        )
    except Exception as exc:
        error_text = str(exc)
        raise
    finally:
        latency_ms = int((time.monotonic() - t0) * 1000)
        chunk_ids = [c.get("source", "") for c in result.get("citations", [])]
        log = QueryLog(
            session_id=session_id,
            user_id=user.user_id,
            pipeline=",".join(pipelines),
            question=body.question,
            answer=result.get("answer"),
            chunk_ids=chunk_ids,
            latency_ms=latency_ms,
            error=error_text,
        )
        db.add(log)
        db.commit()

    # Store assistant response
    assistant_message = append_message(
        db,
        session_id,
        "assistant",
        result["answer"],
        citations=result["citations"],
    )

    return {
        "answer": result["answer"],
        "citations": result["citations"],
        "session_id": session_id,
        "message_id": assistant_message.id,
    }