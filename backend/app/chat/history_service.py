"""
chat/history_service.py

Creates, reads, and deletes chat sessions and messages.
Builds the conversation window that is passed to the LLM for multi-turn memory.

Default pipeline changed from 'policy' → 'safety' in Phase 1.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.chat.models import ChatSession, ChatMessage


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(
    db: Session,
    user_id: str,
    pipeline: str = "safety",
    title: str = "New conversation",
) -> ChatSession:
    """
    Creates a new chat session for a user.

    Args:
        db       : Active SQLAlchemy session.
        user_id  : ID of the authenticated user.
        pipeline : Default pipeline for this session ('equipment', 'safety', 'field_reports').
        title    : Display title shown in the sidebar.

    Returns:
        The newly created ChatSession ORM object.
    """
    session = ChatSession(user_id=user_id, pipeline=pipeline, title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_sessions(db: Session, user_id: str) -> List[ChatSession]:
    """
    Returns all sessions for a user, ordered most-recently-updated first.
    Used to populate the chat history sidebar.
    """
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )


def get_session(
    db: Session, session_id: str, user_id: str
) -> Optional[ChatSession]:
    """
    Returns a single session, scoped to the requesting user.
    Returns None if the session does not exist or belongs to another user.
    """
    return (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
        .first()
    )


def delete_session(db: Session, session_id: str, user_id: str) -> bool:
    """
    Deletes a session and all its messages (cascade).

    Returns:
        True  if the session was found and deleted.
        False if the session was not found or belongs to another user.
    """
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
    """
    Appends a single message to a session.
    Also bumps the session's updated_at timestamp so it rises to the top
    of the sidebar list.

    Args:
        db         : Active SQLAlchemy session.
        session_id : ID of the parent ChatSession.
        role       : 'user' or 'assistant'.
        content    : Full text of the message.
        citations  : Parsed citation list from the RAG pipeline (optional).

    Returns:
        The newly created ChatMessage ORM object.
    """
    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        citations=citations or [],
    )
    db.add(msg)

    # Bump session so it appears at top of the history sidebar.
    db.query(ChatSession).filter(ChatSession.id == session_id).update(
        {"updated_at": msg.created_at}
    )

    db.commit()
    db.refresh(msg)
    return msg


def get_messages(db: Session, session_id: str) -> List[ChatMessage]:
    """
    Returns all messages in a session in chronological order.
    Used to render the full conversation view.
    """
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


def build_context_window(
    db: Session,
    session_id: str,
    max_turns: int = 6,
) -> List[Dict[str, str]]:
    """
    Returns the last N message turns as a list of role/content dicts.
    Passed into ask_question_with_citations() for multi-turn memory.

    Args:
        db         : Active SQLAlchemy session.
        session_id : ID of the session to read from.
        max_turns  : Maximum number of message pairs (user + assistant) to include.
                     Defaults to 6 (last 3 exchanges).

    Returns:
        [{"role": "user"|"assistant", "content": "..."}, ...]
    """
    messages = get_messages(db, session_id)
    recent   = messages[-(max_turns * 2):]
    return [{"role": m.role, "content": m.content} for m in recent]
