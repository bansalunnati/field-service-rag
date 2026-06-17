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

from typing import Optional

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
from app.chat.models import FileAccess, UserGroup
from app.retrieval.rag_pipeline import ask_question_with_citations


router = APIRouter(
    prefix="/api/chat",
    tags=["chat"],
)


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

def check_pipeline_access(
    user: TokenData,
    pipeline: str,
    db: Session,
) -> None:
    """
    Verify that the user can access the requested pipeline.
    """

    # Admins have unrestricted access
    if user.role == "admin":
        return

    memberships = (
        db.query(UserGroup)
        .filter(UserGroup.user_id == user.user_id)
        .all()
    )

    if not memberships:
        raise HTTPException(
            status_code=403,
            detail="This document category is not available to your team.",
        )

    group_ids = [membership.group_id for membership in memberships]

    access = (
        db.query(FileAccess)
        .filter(
            FileAccess.group_id.in_(group_ids),
            FileAccess.pipeline == pipeline,
        )
        .first()
    )

    if not access:
        raise HTTPException(
            status_code=403,
            detail="This document category is not available to your team.",
        )


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

    pipeline = body.pipeline or session.pipeline

    # Verify access before running retrieval
    check_pipeline_access(
        user=user,
        pipeline=pipeline,
        db=db,
    )

    history = build_context_window(
        db,
        session_id,
    )

    # Store user message
    append_message(
        db,
        session_id,
        "user",
        body.question,
    )

    # Run RAG pipeline
    result = ask_question_with_citations(
        question=body.question,
        pipeline=pipeline,
        history=history,
    )

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