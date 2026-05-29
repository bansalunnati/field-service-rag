from app.ingestion.document_loader import load_documents

print("\nLoading documents...\n")

documents = load_documents()

print(f"\nTotal document pages loaded: {len(documents)}")

# Print sample content
print("\nSample Extracted Text:\n")

print(documents[0].page_content[:1000])