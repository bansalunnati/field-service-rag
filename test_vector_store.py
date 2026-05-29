from backened.app.ingestion.document_loader import load_documents
from backened.app.ingestion.chunking import split_documents
from backened.app.ingestion.vector_store import create_vector_store

print("\nLoading documents...")
documents = load_documents()

print(f"\nLoaded {len(documents)} pages")

print("\nCreating chunks...")
chunks = split_documents(documents)

print(f"Created {len(chunks)} chunks")

print("\nCreating vector database...")
vector_store = create_vector_store(chunks)

print("\nVector database created successfully!")