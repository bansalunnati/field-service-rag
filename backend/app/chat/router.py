"""
chat/router.py
Endpoints:
  POST   /api/chat/sessions                    create session
  GET    /api/chat/sessions                    list user sessions
  DELETE /api/chat/sessions/{id}               delete session
  GET    /api/chat/sessions/{id}/messages      get messages with citations
  POST   /api/chat/sessions/{id}/query         ask a question, get answer + citations
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from app.auth.auth_service import get_current_user, require_permission, TokenData
from app.chat.database import get_db
from app.chat.history_service import (
    create_session, get_sessions, get_session, delete_session,
    append_message, get_messages, build_context_window,
)
from app.retrieval.rag_pipeline import ask_question_with_citations

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ── Request / Response schemas ────────────────────────────────────────────────

class SessionCreate(BaseModel):
    pipeline: str = "policy"
    title:    str = "New chat"


class QueryRequest(BaseModel):
    question: str
    pipeline: Optional[str] = None   # overrides session pipeline if provided


# ── Session endpoints ─────────────────────────────────────────────────────────

@router.post("/sessions", status_code=201)
async def new_session(
    body: SessionCreate,
    db:   Session  = Depends(get_db),
    user: TokenData = Depends(require_permission("query")),
):
    s = create_session(db, user.user_id, body.pipeline, body.title)
    return {"id": s.id, "title": s.title, "pipeline": s.pipeline, "updated_at": str(s.updated_at)}


@router.get("/sessions")
async def list_sessions(
    db:   Session   = Depends(get_db),
    user: TokenData = Depends(require_permission("query")),
):
    sessions = get_sessions(db, user.user_id)
    return [
        {"id": s.id, "title": s.title, "pipeline": s.pipeline, "updated_at": str(s.updated_at)}
        for s in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def remove_session(
    session_id: str,
    db:   Session   = Depends(get_db),
    user: TokenData = Depends(require_permission("view_history")),
):
    if not delete_session(db, session_id, user.user_id):
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/sessions/{session_id}/messages")
async def session_messages(
    session_id: str,
    db:   Session   = Depends(get_db),
    user: TokenData = Depends(require_permission("view_history")),
):
    if not get_session(db, session_id, user.user_id):
        raise HTTPException(status_code=404, detail="Session not found")
    msgs = get_messages(db, session_id)
    return [
        {
            "id":         m.id,
            "role":       m.role,
            "content":    m.content,
            "citations":  m.citations,
            "created_at": str(m.created_at),
        }
        for m in msgs
    ]


# ── Query endpoint ────────────────────────────────────────────────────────────

@router.post("/sessions/{session_id}/query")
async def query(
    session_id: str,
    body: QueryRequest,
    db:   Session   = Depends(get_db),
    user: TokenData = Depends(require_permission("query")),
):
    session = get_session(db, session_id, user.user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    pipeline = body.pipeline or session.pipeline
    history  = build_context_window(db, session_id)

    # Save user message
    append_message(db, session_id, "user", body.question)

    # Run RAG — uses your existing rag_pipeline.py
    result = ask_question_with_citations(
        question=body.question,
        pipeline=pipeline,
        history=history,
    )

    # Save assistant message with citations
    msg = append_message(
        db, session_id, "assistant",
        result["answer"],
        citations=result["citations"],
    )

    return {
        "answer":     result["answer"],
        "citations":  result["citations"],
        "session_id": session_id,
        "message_id": msg.id,
    }
