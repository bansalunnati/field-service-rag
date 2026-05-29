from app.ingestion.document_loader import load_documents
from app.ingestion.chunking import split_documents

print("\nLoading documents...\n")

documents = load_documents()

print(f"\nLoaded {len(documents)} pages")

print("\nSplitting into chunks...\n")

chunks = split_documents(documents)

print(f"Total chunks created: {len(chunks)}")

# Show sample chunk
print("\nSample Chunk:\n")

print(chunks[0].page_content)

print("\nChunk Length:\n")

print(len(chunks[0].page_content))