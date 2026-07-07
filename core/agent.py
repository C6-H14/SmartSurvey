import os

from langchain_openai import ChatOpenAI

from core.credentials import CredentialStore


def get_llm_agent(temperature: float = 0.2, credential_store: CredentialStore | None = None) -> ChatOpenAI:
    store = credential_store or CredentialStore()
    api_key = store.get_api_key()
    api_base = os.getenv("OPENAI_API_BASE")
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o")

    return ChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base=api_base,
        temperature=temperature,
        max_retries=2,
        timeout=60.0,
    )
