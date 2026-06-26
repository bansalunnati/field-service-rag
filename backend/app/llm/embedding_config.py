import os
from dotenv import load_dotenv

load_dotenv()

_AZURE_KEY = os.getenv("AZURE_OPENAI_API_KEY", "").strip()


def get_embedding_model():
    """
    Returns a LangChain-compatible AzureOpenAIEmbeddings instance.
    Requires AZURE_OPENAI_API_KEY to be set.
    """
    if not _AZURE_KEY:
        raise RuntimeError(
            "AZURE_OPENAI_API_KEY is not set — required to generate embeddings."
        )

    from langchain_openai import AzureOpenAIEmbeddings
    return AzureOpenAIEmbeddings(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=_AZURE_KEY,
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
    )
