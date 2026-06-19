import os
from dotenv import load_dotenv

load_dotenv()

_AZURE_KEY = os.getenv("AZURE_OPENAI_API_KEY", "").strip()


def get_embedding_model():
    """
    Returns a LangChain-compatible embedding model.

    - If AZURE_OPENAI_API_KEY is set: use AzureOpenAIEmbeddings (production).
    - Otherwise: fall back to ChromaDB's built-in local model (onnxruntime,
      no extra packages needed) so local dev works without Azure credentials.
    """
    if _AZURE_KEY:
        from langchain_openai import AzureOpenAIEmbeddings
        return AzureOpenAIEmbeddings(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=_AZURE_KEY,
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        )

    # Local dev fallback — wraps chromadb's DefaultEmbeddingFunction
    # (ships with chromadb, uses onnxruntime under the hood, no API key needed)
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as _CEF

    class _LocalEmbeddings:
        """Thin LangChain-compatible wrapper around chromadb's built-in model."""

        def __init__(self):
            self._fn = _CEF()

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return self._fn(texts)

        def embed_query(self, text: str) -> list[float]:
            return self._fn([text])[0]

    return _LocalEmbeddings()
