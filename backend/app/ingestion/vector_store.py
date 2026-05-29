from langchain_community.vectorstores import Chroma
from app.llm.embedding_config import embedding_model


def create_vector_store(chunks):

    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        persist_directory="chroma_db"
    )

    return vector_store