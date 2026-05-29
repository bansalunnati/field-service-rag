from app.retrieval.rag_pipeline import ask_question

question = "What inspections should be performed before using PPE?"

answer = ask_question(question)

print("\nQuestion:\n")
print(question)

print("\nAnswer:\n")
print(answer)