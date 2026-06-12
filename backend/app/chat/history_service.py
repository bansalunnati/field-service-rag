"""
chat/history_service.py
Create/read/delete sessions and messages.
Builds the conversation window passed to the LLM.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.chat.models import ChatSession, ChatMessage


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(
    db: Session, user_id: str,
    pipeline: str = "policy", title: str = "New chat"
) -> ChatSession:
    session = ChatSession(user_id=user_id, pipeline=pipeline, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_sessions(db: Session, user_id: str) -> List[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )


def get_session(db: Session, session_id: str, user_id: str) -> Optional[ChatSession]:
    return (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
        .first()
    )


def delete_session(db: Session, session_id: str, user_id: str) -> bool:
    session = get_session(db, session_id, user_id)
    if not session:
        return False
    db.delete(session)
    db.commit()
    return True


# ── Messages ──────────────────────────────────────────────────────────────────

def append_message(
    db: Session,
    session_id: str,
    role: str,
    content: str,
    citations: Optional[List[Dict[str, Any]]] = None,
) -> ChatMessage:
    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        citations=citations or [],
    )
    db.add(msg)
    # Bump session updated_at so it appears at top of session list
    db.query(ChatSession).filter(ChatSession.id == session_id).update(
        {"updated_at": msg.created_at}
    )
    db.commit()
    db.refresh(msg)
    return msg


def get_messages(db: Session, session_id: str) -> List[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


def build_context_window(
    db: Session, session_id: str, max_turns: int = 6
) -> List[Dict[str, str]]:
    """
    Returns the last N turns as [{"role": "user"|"assistant", "content": "..."}]
    Passed into ask_question_with_citations() for multi-turn memory.
    """
    messages = get_messages(db, session_id)
    recent = messages[-(max_turns * 2):]
    return [{"role": m.role, "content": m.content} for m in recent]
