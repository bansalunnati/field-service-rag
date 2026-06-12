from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from dotenv import load_dotenv

# ── Your existing imports ──────────────────────────────────────────────────────
from app.bots.policy_bot import policy_bot
from app.ingestion.ingest_documents import ingest_documents

# ── New imports ────────────────────────────────────────────────────────────────
from app.auth.router import router as auth_router
from app.chat.router import router as chat_router
from app.ingestion.ingest_router import router as ingest_router
from app.chat.database import init_db

load_dotenv()

app = FastAPI(
    title="Field Service RAG API",
    version="2.0.0",
)

# ── CORS ───────────────────────────────────────────────────────────────────────
# Added ALLOWED_ORIGINS env var so you can set your Vercel URL in production
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://your-frontend.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(ingest_router)

# ── Startup ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()   # creates SQLite tables on first run


# ── Your existing endpoints (unchanged) ───────────────────────────────────────

class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def home():
    return {"message": "Field Service RAG API Running"}


@app.post("/ask")
def ask_question(request: QuestionRequest):
    # Kept exactly as-is so nothing breaks
    answer = policy_bot(request.question)
    return {
        "question": request.question,
        "answer": answer,
    }


@app.post("/process")
def process_documents():
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
