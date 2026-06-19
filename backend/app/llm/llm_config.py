import os
from dotenv import load_dotenv

load_dotenv()

_AZURE_KEY = os.getenv("AZURE_OPENAI_API_KEY", "").strip()

if _AZURE_KEY:
    from langchain_openai import AzureChatOpenAI
    llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=_AZURE_KEY,
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        temperature=0,
    )
else:
    # Local dev stub — returns a clear message instead of crashing
    class _NoLLM:
        def invoke(self, prompt: str):
            class _Resp:
                content = (
                    "⚠️ Chat is not available in local dev mode because "
                    "AZURE_OPENAI_API_KEY is not set. "
                    "Add your Azure OpenAI credentials to backend/.env to enable it."
                )
            return _Resp()

    llm = _NoLLM()
