from app.ingestion.ingest_documents import ingest_documents

docs, chunks = ingest_documents()

print(f"Documents Loaded: {docs}")
print(f"Chunks Created: {chunks}")