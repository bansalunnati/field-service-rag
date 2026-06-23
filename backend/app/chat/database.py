"""
chat/database.py
SQLAlchemy engine + session factory.
Uses SQLite locally, PostgreSQL in production via DATABASE_URL env var.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./field_service_rag.db")

# Render (and Heroku) emit "postgres://" but SQLAlchemy 2.x requires "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs check_same_thread=False; PostgreSQL doesn't
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine       = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base         = declarative_base()


def init_db():
    """Create all tables. Called once at FastAPI startup."""
    from app.chat import models  # noqa — registers models with Base
    Base.metadata.create_all(bind=engine)

    # Each migration is independently best-effort: a stuck lock or transient
    # DB error here should never prevent the app from starting and binding
    # its port — that turns a 5-second DDL hiccup into a full deploy timeout.
    for migration in (_migrate_query_log_fk, _migrate_uploaded_files_status, _migrate_field_reports_task_id):
        try:
            migration()
        except Exception as exc:
            print(f"Startup migration {migration.__name__} failed (non-fatal): {exc}")


def _migrate_query_log_fk():
    """
    query_logs.session_id originally had no ON DELETE rule, so Postgres
    rejected deleting a ChatSession the moment any query had been logged
    against it (every session with messages). create_all() never alters
    existing constraints, so repair it here on every startup — idempotent,
    no-op once the constraint is already correct.
    """
    if not DATABASE_URL.startswith("postgresql"):
        return
    from sqlalchemy import text
    with engine.begin() as conn:
        # If another connection (e.g. a previous deploy's lingering worker)
        # holds a lock on this table, fail fast after a few seconds instead
        # of hanging the whole startup — and therefore the whole deploy —
        # indefinitely.
        conn.execute(text("SET lock_timeout = '5s'"))
        conn.execute(text("""
            DO $$
            DECLARE
                fk_name text;
            BEGIN
                SELECT tc.constraint_name INTO fk_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = 'query_logs'
                  AND tc.constraint_type = 'FOREIGN KEY'
                  AND kcu.column_name = 'session_id';

                IF fk_name IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE query_logs DROP CONSTRAINT %I', fk_name);
                END IF;

                ALTER TABLE query_logs
                    ADD CONSTRAINT query_logs_session_id_fkey
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL;
            END $$;
        """))


def _migrate_uploaded_files_status():
    """
    Adds the status/error_message columns used for background OCR processing
    to an already-deployed uploaded_files table. create_all() only creates
    tables that don't exist yet, so new columns on an existing table need
    this — idempotent via IF NOT EXISTS, safe to run every startup.
    """
    if not DATABASE_URL.startswith("postgresql"):
        return
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("SET lock_timeout = '5s'"))
        conn.execute(text(
            "ALTER TABLE uploaded_files ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'ready'"
        ))
        conn.execute(text(
            "ALTER TABLE uploaded_files ADD COLUMN IF NOT EXISTS error_message TEXT"
        ))


def _migrate_field_reports_task_id():
    """
    Adds field_reports.task_id — lets an employee declare which assigned
    WorkflowTask a submitted report is evidence for, instead of leaving the
    reviewer to guess from file content alone. create_all() only creates
    tables that don't exist yet, so this column needs adding by hand on an
    already-deployed field_reports table.
    """
    from sqlalchemy import text
    with engine.begin() as conn:
        if DATABASE_URL.startswith("postgresql"):
            conn.execute(text("SET lock_timeout = '5s'"))
            conn.execute(text(
                "ALTER TABLE field_reports ADD COLUMN IF NOT EXISTS task_id VARCHAR REFERENCES workflow_tasks(id)"
            ))
        else:
            # SQLite has no "ADD COLUMN IF NOT EXISTS" — check first.
            cols = [row[1] for row in conn.execute(text("PRAGMA table_info(field_reports)"))]
            if "task_id" not in cols:
                conn.execute(text("ALTER TABLE field_reports ADD COLUMN task_id VARCHAR"))


def get_db():
    """FastAPI dependency — yields a DB session, closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
