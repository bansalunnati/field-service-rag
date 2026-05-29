from app.llm.embedding_config import embedding_model

text = "Safety helmets are mandatory during maintenance."

embedding = embedding_model.embed_query(text)

print("\nEmbedding Length:\n")
print(len(embedding))