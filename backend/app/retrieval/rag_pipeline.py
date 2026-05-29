from app.retrieval.retriever import get_retriever
from app.llm.llm_config import llm


def ask_question(question):

    retriever = get_retriever()

    docs = retriever.invoke(question)

    context = "\n\n".join(
        [doc.page_content for doc in docs]
    )

    prompt = f"""
You are a field service compliance and policy assistant.

Use the provided context to answer the user's question.

If relevant information exists in the context, summarize it clearly.

Only say 'I could not find that information in the policy documents'
if the context contains no relevant information at all.

Context:
{context}

Question:
{question}

Answer:
"""

    response = llm.invoke(prompt)

    return response.content