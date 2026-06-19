"""
chat/models.py

SQLAlchemy ORM models.

EXISTING (Phase 1 — do not change):
  User         — accounts with roles
  ChatSession  — one conversation thread per user
  ChatMessage  — individual turns, stores answer + citations JSON

NEW (Phase 2):
  Group         — teams / departments (e.g. Electrical, Safety)
  UserGroup     — which users belong to which group
  FileAccess    — which groups can access which pipeline
  UploadedFile  — registry of every file ingested into ChromaDB
  FieldReport   — submitted field investigation reports
  HITLReview    — human-in-the-loop review queue for reports
  WorkflowTask  — task assignments generated from approved reports
  Notification  — in-app alerts for reviews, approvals, tasks
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON, Boolean, Integer
from sqlalchemy.orm import relationship
from app.chat.database import Base


def _uuid():
    return str(uuid.uuid4())


# ══════════════════════════════════════════════════════════════════════════════
# EXISTING MODELS — Phase 1 (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    id              = Column(String, primary_key=True, default=_uuid)
    email           = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role            = Column(String, default="user")   # "admin" | "user" | "viewer"
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    # Existing relationships
    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")

    # Phase 2 relationships
    group_memberships = relationship("UserGroup", back_populates="user", cascade="all, delete-orphan")
    uploaded_files    = relationship("UploadedFile", back_populates="uploaded_by_user")
    field_reports     = relationship("FieldReport", back_populates="submitted_by_user")
    hitl_reviews      = relationship("HITLReview", back_populates="reviewed_by_user")
    assigned_tasks    = relationship("WorkflowTask", back_populates="assigned_to_user")
    notifications     = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id         = Column(String, primary_key=True, default=_uuid)
    user_id    = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title      = Column(String, default="New chat")
    pipeline   = Column(String, default="safety")   # "equipment" | "safety" | "field_reports"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user     = relationship("User", back_populates="sessions")
    messages = relationship(
        "ChatMessage", back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id         = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role       = Column(String, nullable=False)    # "user" | "assistant"
    content    = Column(Text, nullable=False)
    citations  = Column(JSON, default=list)        # [{source, page, excerpt, ref}]
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


# ══════════════════════════════════════════════════════════════════════════════
# NEW MODELS — Phase 2
# ══════════════════════════════════════════════════════════════════════════════


class Group(Base):
    """
    A team or department within the organisation.
    e.g. "Electrical", "Safety", "Field Operations"

    Admins create groups and assign users to them.
    Groups are then granted access to specific pipelines via FileAccess.
    """
    __tablename__ = "groups"

    id          = Column(String, primary_key=True, default=_uuid)
    name        = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    created_at  = Column(DateTime, default=datetime.utcnow)

    members       = relationship("UserGroup",   back_populates="group", cascade="all, delete-orphan")
    file_accesses = relationship("FileAccess",  back_populates="group", cascade="all, delete-orphan")
    file_grants   = relationship("GroupFileAccess", back_populates="group", cascade="all, delete-orphan")


class UserGroup(Base):
    """
    Join table: one row per (user, group) pair.
    A user can belong to multiple groups.
    """
    __tablename__ = "user_groups"

    id        = Column(String, primary_key=True, default=_uuid)
    user_id   = Column(String, ForeignKey("users.id"),  nullable=False, index=True)
    group_id  = Column(String, ForeignKey("groups.id"), nullable=False, index=True)
    joined_at = Column(DateTime, default=datetime.utcnow)

    user  = relationship("User",  back_populates="group_memberships")
    group = relationship("Group", back_populates="members")


class FileAccess(Base):
    """
    Controls which pipelines (ChromaDB collections) a group can query.

    pipeline values: "equipment" | "safety" | "field_reports"

    e.g. The "Electrical" group is granted access to "equipment" and "safety".
    When a user in that group sends a chat query, only those pipelines are
    available to them.
    """
    __tablename__ = "file_access"

    id         = Column(String, primary_key=True, default=_uuid)
    group_id   = Column(String, ForeignKey("groups.id"), nullable=False, index=True)
    pipeline   = Column(String, nullable=False)   # "equipment" | "safety" | "field_reports"
    granted_at = Column(DateTime, default=datetime.utcnow)

    group = relationship("Group", back_populates="file_accesses")

class GroupFileAccess(Base):
    """
    Per-individual-file visibility grant for the employee-facing Files UI.
 
    Admin picks exact files a group is allowed to see/open — distinct from
    FileAccess (pipeline-level chat retrieval access, unchanged).
 
    e.g. Even if "Electrical" group has FileAccess to the "equipment"
    pipeline (so chat can retrieve from it), they will only SEE / be able
    to OPEN "motor_spec_v2.pdf" in the Files page if an admin explicitly
    grants it via GroupFileAccess.
    """
    __tablename__ = "group_file_access"
 
    id         = Column(String, primary_key=True, default=_uuid)
    group_id   = Column(String, ForeignKey("groups.id"), nullable=False, index=True)
    file_id    = Column(String, ForeignKey("uploaded_files.id"), nullable=False, index=True)
    granted_at = Column(DateTime, default=datetime.utcnow)
 
    group = relationship("Group", back_populates="file_grants")
    file  = relationship("UploadedFile", back_populates="group_accesses")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"
 
    id            = Column(String, primary_key=True, default=_uuid)
    filename      = Column(String, nullable=False)
    original_name = Column(String, nullable=False)
    file_type     = Column(String, nullable=False)
    pipeline      = Column(String, nullable=False)
    chunk_count   = Column(Integer, default=0)
    ocr_used      = Column(Boolean, default=False)
    is_active     = Column(Boolean, default=True)
    file_path     = Column(String, nullable=True)   # original file on disk, for in-browser viewing only
    uploaded_by   = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    uploaded_at   = Column(DateTime, default=datetime.utcnow)
 
    uploaded_by_user = relationship("User", back_populates="uploaded_files")
    group_accesses    = relationship("GroupFileAccess", back_populates="file", cascade="all, delete-orphan")

class FieldReport(Base):
    """
    A field investigation report submitted by an employee.

    Status lifecycle:  pending → under_review → approved | rejected

    metadata_json holds structured data extracted during LangGraph processing
    (e.g. location, equipment ID, hazard category).
    """
    __tablename__ = "field_reports"

    id            = Column(String, primary_key=True, default=_uuid)
    title         = Column(String, nullable=False)
    content       = Column(Text, nullable=False)
    submitted_by  = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    status        = Column(String, default="pending")  # "pending"|"under_review"|"approved"|"rejected"
    metadata_json = Column(JSON, default=dict)         # structured fields from LangGraph
    submitted_at  = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    file_path    = Column(String, nullable=True)   # path to the uploaded file on disk
    report_type  = Column(String, nullable=True)   # e.g. "hazmat_inspection", "tower_sop"
    
    submitted_by_user = relationship("User",back_populates="field_reports")
    hitl_review       = relationship("HITLReview",   back_populates="report", uselist=False)
    workflow_tasks    = relationship("WorkflowTask", back_populates="report", cascade="all, delete-orphan")


class HITLReview(Base):
    """
    Human-in-the-loop review record — one per FieldReport.

    Created automatically when a report is submitted.
    An admin picks it up, sets decision to "approved" or "rejected",
    and optionally adds notes.
    """
    __tablename__ = "hitl_reviews"

    id          = Column(String, primary_key=True, default=_uuid)
    report_id   = Column(String, ForeignKey("field_reports.id"), unique=True, nullable=False, index=True)
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)  # null until picked up
    decision    = Column(String, nullable=True)   # None | "approved" | "rejected"
    notes       = Column(Text, default="")        # reviewer's comments
    reviewed_at = Column(DateTime, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    report           = relationship("FieldReport", back_populates="hitl_review")
    reviewed_by_user = relationship("User",        back_populates="hitl_reviews")


class WorkflowTask(Base):
    """
    A task generated from an approved FieldReport by LangGraph.

    status:   "open" | "in_progress" | "done"
    priority: "low"  | "medium"      | "high"
    """
    __tablename__ = "workflow_tasks"

    id          = Column(String, primary_key=True, default=_uuid)
    report_id   = Column(String, ForeignKey("field_reports.id"), nullable=True, index=True)
    title       = Column(String, nullable=False)
    description = Column(Text, default="")
    assigned_to = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    status      = Column(String, default="open")     # "open" | "in_progress" | "done"
    priority    = Column(String, default="medium")   # "low" | "medium" | "high"
    due_date    = Column(DateTime, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    report           = relationship("FieldReport", back_populates="workflow_tasks")
    assigned_to_user = relationship("User",        back_populates="assigned_tasks")


class Notification(Base):
    """
    In-app alert sent to a user.

    notification_type values:
      "new_report"      — admin alerted when employee submits a report
      "report_reviewed" — employee alerted when admin makes a decision
      "task_assigned"   — user alerted when a WorkflowTask is assigned to them
      "task_updated"    — user alerted when task status changes

    ref_type + ref_id point to the triggering object so the frontend
    can build a deep link (e.g. ref_type="field_report", ref_id="<uuid>").
    """
    __tablename__ = "notifications"

    id                = Column(String, primary_key=True, default=_uuid)
    user_id           = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    notification_type = Column(String, nullable=False)
    message           = Column(Text, nullable=False)
    is_read           = Column(Boolean, default=False)
    ref_type          = Column(String, nullable=True)  # "field_report"|"workflow_task"|"hitl_review"
    ref_id            = Column(String, nullable=True)  # UUID of the referenced object
    created_at        = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="notifications")


# ══════════════════════════════════════════════════════════════════════════════
# Phase 8 — Observability
# ══════════════════════════════════════════════════════════════════════════════

class QueryLog(Base):
    """
    One row per chat query sent through the RAG pipeline.
    Captures latency, retrieved chunk IDs, and any error for analytics.
    """
    __tablename__ = "query_logs"

    id         = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=True, index=True)
    user_id    = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    pipeline   = Column(String, nullable=False)
    question   = Column(Text, nullable=False)
    answer     = Column(Text, nullable=True)
    chunk_ids  = Column(JSON, default=list)   # citation source IDs
    latency_ms = Column(Integer, nullable=True)
    error      = Column(Text, nullable=True)
    timestamp  = Column(DateTime, default=datetime.utcnow, index=True)
