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

load_dotenv()

app = FastAPI(
    title="Field Service RAG API",
    version="2.0.0",
)

# ── CORS ───────────────────────────────────────────────────────────────────────
# ALLOWED_ORIGINS env var lets you set your Vercel URL in production without
# changing code. Falls back to localhost for local dev.
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000",
).split(",")

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
# ── Startup ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()   # creates / migrates SQLite tables on first run

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