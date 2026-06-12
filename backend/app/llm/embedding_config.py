import os
from dotenv import load_dotenv
from langchain_openai import AzureOpenAIEmbeddings

# Load environment variables
load_dotenv()

# Initialize Embedding Model
def get_embedding_model():
    return AzureOpenAIEmbeddings(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    )