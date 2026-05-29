from langchain_community.vectorstores import Chroma
from app.llm.embedding_config import embedding_model


def get_retriever():

    vector_store = Chroma(
        persist_directory="chroma_db",
        embedding_function=embedding_model
    )

    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 5}
    )

    return retriever