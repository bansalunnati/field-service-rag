from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import os
import shutil

from app.bots.policy_bot import policy_bot
from app.ingestion.ingest_documents import ingest_documents

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def home():
    return {"message": "Field Service RAG API Running"}


@app.post("/ask")
def ask_question(request: QuestionRequest):

    answer = policy_bot(request.question)

    return {
        "question": request.question,
        "answer": answer
    }


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):

    save_dir = "data/policies"

    os.makedirs(save_dir, exist_ok=True)

    file_path = os.path.join(
        save_dir,
        file.filename
    )

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": f"{file.filename} uploaded successfully"
    }


@app.post("/process")
def process_documents():

    docs, chunks = ingest_documents()

    return {
        "pages": docs,
        "chunks": chunks,
        "message": "Documents processed successfully"
    }