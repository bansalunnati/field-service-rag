from app.llm.llm_config import llm

response = llm.invoke("What is a field inspection report?")

print("\nAI Response:\n")
print(response.content)