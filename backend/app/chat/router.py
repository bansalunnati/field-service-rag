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

import os
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
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
from app.chat.models import FieldReport, FileAccess, GroupFileAccess, QueryLog, UploadedFile, UserGroup
from app.ingestion.text_extraction import extract_text
from app.retrieval.rag_pipeline import ask_question_across_pipelines
from app.storage import file_storage


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
    attached_text: Optional[str] = None
    attached_filename: Optional[str] = None


ATTACHED_TEXT_LIMIT = 8000


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
# Upload Endpoint
# ============================================================================

@router.post("/sessions/{session_id}/upload")
async def upload_chat_file(
    session_id: str,
    file: Optional[UploadFile] = File(default=None),
    report_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user: TokenData = Depends(require_permission("query")),
):
    """
    Ad-hoc attachment for a single chat turn — extracts text and hands it
    back to the frontend to send alongside the next /query call. Nothing is
    ingested into the shared vector store and nothing is persisted in the DB;
    the bytes are written to object storage / disk only long enough to run
    the same extraction reviewer.py uses, then discarded.

    If `report_id` is given (employee opening "Discuss in Policy Chat" from
    one of their own rejected reports), the employee's own report text and
    the AI reviewer's already-computed verdict/matched templates are
    returned instead of re-extracting the uploaded file.
    """
    session = get_session(db, session_id, user.user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if report_id:
        report = (
            db.query(FieldReport)
            .filter(FieldReport.id == report_id, FieldReport.submitted_by == user.user_id)
            .first()
        )
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        meta = report.metadata_json or {}
        parts = [f"Report title: {report.title}", f"Report status: {report.status}"]
        if meta.get("ai_summary"):
            parts.append(f"AI review summary: {meta['ai_summary']}")
        if meta.get("hitl_reason"):
            parts.append(f"Rejection reason: {meta['hitl_reason']}")
        if meta.get("matched_sources"):
            parts.append(f"Matched template/SOP documents: {', '.join(meta['matched_sources'])}")
        parts.append(f"Report content:\n{report.content}")

        extracted_text = "\n\n".join(parts)[:ATTACHED_TEXT_LIMIT]
        return {"filename": report.title, "extracted_text": extracted_text}

    if not file:
        raise HTTPException(status_code=422, detail="No file provided.")

    suffix = os.path.splitext(file.filename or "")[1].lower()
    key = f"chat_uploads/{session_id}/{uuid.uuid4()}{suffix}"
    data = await file.read()
    ref = file_storage.save_bytes(key, data)

    local_path = file_storage.download_to_tempfile(ref, suffix=suffix)
    try:
        # OCR (images, scanned PDFs) can take up to OCR_TIMEOUT_SECONDS — fine
        # for report submission, which runs it as a BackgroundTask, but this
        # endpoint extracts inline within the request, so it would just time
        # out. Detect the OCR case up front and fail fast with a clear
        # message instead of hanging until the proxy/browser gives up.
        if suffix in {".png", ".jpg", ".jpeg"}:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Image attachments need OCR, which is too slow to run inline "
                    "in chat. Submit it as a Field Report instead — OCR runs in "
                    "the background there."
                ),
            )
        if suffix == ".pdf":
            from app.ingestion.ocr_service import is_scanned_pdf
            if is_scanned_pdf(local_path):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "This looks like a scanned PDF, which needs OCR — too slow "
                        "to run inline in chat. Submit it as a Field Report instead, "
                        "or attach a PDF with selectable text."
                    ),
                )

        text, _ocr_used, _ocr_confidence = extract_text(local_path)
    finally:
        os.unlink(local_path)
        file_storage.delete(ref)

    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from this file.")

    return {"filename": file.filename, "extracted_text": text[:ATTACHED_TEXT_LIMIT]}


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
            attached_text=body.attached_text,
            attached_filename=body.attached_filename,
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