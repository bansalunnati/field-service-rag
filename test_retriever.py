from app.retrieval.retriever import get_retriever

retriever = get_retriever()

query = "What personal protective equipment is required?"

results = retriever.invoke(query)

print("\nRetrieved Chunks:\n")

for i, doc in enumerate(results, start=1):

    print(f"\n----- Chunk {i} -----\n")

    print(doc.page_content[:1000])