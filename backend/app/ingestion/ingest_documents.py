from app.ingestion.document_loader import load_documents
from app.ingestion.chunking import split_documents
from app.ingestion.vector_store import create_vector_store


def ingest_documents():

    documents = load_documents()

    chunks = split_documents(documents)

    create_vector_store(chunks)

    return len(documents), len(chunks)