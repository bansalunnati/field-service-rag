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
    _migrate_query_log_fk()


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


def get_db():
    """FastAPI dependency — yields a DB session, closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
