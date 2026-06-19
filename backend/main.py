from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from dotenv import load_dotenv

# ── Router imports ─────────────────────────────────────────────────────────────
from app.auth.router import router as auth_router
from app.chat.router import router as chat_router
from app.ingestion.ingest_router import router as ingest_router

# Phase 3.4 — new routers
from app.groups.router import router as groups_router
from app.access.router import router as access_router
from app.reports.router import router as reports_router
from app.notifications.router import router as notifications_router
from app.chat.database import init_db
from app.hitl.router import router as hitl_router
from app.tasks.router import router as tasks_router
from app.analytics.router import router as analytics_router
from app.ragas.router import router as ragas_router

load_dotenv()

# ── Lifespan (replaces deprecated @app.on_event("startup")) ────────────────────
def _run_migrations():
    """Add/fix columns that were introduced or changed after initial DB creation."""
    from app.chat.database import engine
    from sqlalchemy import text, inspect

    is_sqlite = engine.dialect.name == "sqlite"

    # ── uploaded_files: add columns added in Phase 5 ───────────────────────────
    # PostgreSQL: ADD COLUMN IF NOT EXISTS is atomic — safe to run every startup.
    # SQLite: no IF NOT EXISTS support, so catch the duplicate-column exception.
    for col, definition in [
        ("ocr_used",      "BOOLEAN DEFAULT FALSE"),
        ("is_active",     "BOOLEAN DEFAULT TRUE"),
        ("file_path",     "VARCHAR"),
        ("original_name", "VARCHAR"),
    ]:
        try:
            with engine.connect() as conn:
                if is_sqlite:
                    conn.execute(text(
                        f"ALTER TABLE uploaded_files ADD COLUMN {col} {definition}"
                    ))
                else:
                    conn.execute(text(
                        f"ALTER TABLE uploaded_files ADD COLUMN IF NOT EXISTS {col} {definition}"
                    ))
                conn.commit()
        except Exception:
            pass  # SQLite: column already exists — safe to ignore

    # ── query_logs: add ground_truth column (Phase 9) ─────────────────────────
    try:
        with engine.connect() as conn:
            if is_sqlite:
                conn.execute(text("ALTER TABLE query_logs ADD COLUMN ground_truth TEXT"))
            else:
                conn.execute(text("ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS ground_truth TEXT"))
            conn.commit()
    except Exception:
        pass

    # ── ragas_scores table (Phase 9) ───────────────────────────────────────────
    try:
        with engine.connect() as conn:
            if is_sqlite:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS ragas_scores (
                        id                 VARCHAR PRIMARY KEY,
                        query_log_id       VARCHAR NOT NULL UNIQUE REFERENCES query_logs(id),
                        faithfulness       VARCHAR,
                        answer_relevancy   VARCHAR,
                        context_precision  VARCHAR,
                        context_recall     VARCHAR,
                        created_at         DATETIME
                    )
                """))
            else:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS ragas_scores (
                        id                 VARCHAR PRIMARY KEY,
                        query_log_id       VARCHAR NOT NULL UNIQUE REFERENCES query_logs(id),
                        faithfulness       VARCHAR,
                        answer_relevancy   VARCHAR,
                        context_precision  VARCHAR,
                        context_recall     VARCHAR,
                        created_at         TIMESTAMP
                    )
                """))
            conn.commit()
    except Exception:
        pass

    # ── workflow_tasks: report_id must be nullable ─────────────────────────────
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            if "workflow_tasks" in inspector.get_table_names():
                cols = {c["name"]: c for c in inspector.get_columns("workflow_tasks")}
                report_id_col = cols.get("report_id", {})
                if report_id_col and not report_id_col.get("nullable", True):
                    if is_sqlite:
                        conn.execute(text("PRAGMA foreign_keys = OFF"))
                        conn.execute(text("""
                            CREATE TABLE IF NOT EXISTS workflow_tasks_new (
                                id          VARCHAR PRIMARY KEY,
                                report_id   VARCHAR,
                                title       VARCHAR NOT NULL,
                                description TEXT    DEFAULT '',
                                assigned_to VARCHAR REFERENCES users(id),
                                status      VARCHAR DEFAULT 'open',
                                priority    VARCHAR DEFAULT 'medium',
                                due_date    DATETIME,
                                created_at  DATETIME,
                                updated_at  DATETIME
                            )
                        """))
                        conn.execute(text(
                            "INSERT OR IGNORE INTO workflow_tasks_new "
                            "SELECT id, report_id, title, description, assigned_to, "
                            "       status, priority, due_date, created_at, updated_at "
                            "FROM workflow_tasks"
                        ))
                        conn.execute(text("DROP TABLE workflow_tasks"))
                        conn.execute(text("ALTER TABLE workflow_tasks_new RENAME TO workflow_tasks"))
                        conn.execute(text("PRAGMA foreign_keys = ON"))
                    else:
                        conn.execute(text(
                            "ALTER TABLE workflow_tasks "
                            "ALTER COLUMN report_id DROP NOT NULL"
                        ))
                    conn.commit()
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _run_migrations()
    yield
    # Shutdown: nothing to clean up yet, but this is where it would go


app = FastAPI(
    title="Field Service RAG API",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
# ALLOWED_ORIGINS env var lets you set your Vercel URL in production without
# changing code. Falls back to localhost for local dev ONLY — make sure
# ALLOWED_ORIGINS is set on Render (or wherever this is deployed), otherwise
# your deployed frontend will be silently blocked by CORS.
#
# Format on Render: a comma-separated list, no spaces, no trailing slashes:
#   ALLOWED_ORIGINS=https://field-service-rag.vercel.app,https://your-custom-domain.com
#
# NEVER set this to "*" — it cannot be combined with allow_credentials=True
# (browsers will reject the response), and it defeats the purpose of CORS.
raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
ALLOWED_ORIGINS = [origin.strip().rstrip("/") for origin in raw_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(ingest_router)

# Phase 3.4 — groups + access control
app.include_router(groups_router)
app.include_router(access_router)
app.include_router(reports_router)
app.include_router(notifications_router)
app.include_router(hitl_router)
app.include_router(tasks_router)
app.include_router(analytics_router)
app.include_router(ragas_router)

# ── Legacy endpoints (unchanged) ───────────────────────────────────────────────
class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def home():
    return {"message": "Field Service RAG API Running"}


@app.post("/ask")
def ask_question(request: QuestionRequest):
    from app.bots.policy_bot import policy_bot
    answer = policy_bot(request.question)
    return {
        "question": request.question,
        "answer": answer,
    }


@app.post("/process")
def process_documents():
    from app.ingestion.ingest_documents import ingest_documents
    docs, chunks = ingest_documents()
    return {
        "pages": docs,
        "chunks": chunks,
        "message": "Documents processed successfully",
    }


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}