import os
from typing import Callable

from langchain_core.messages import HumanMessage
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
        timeout=180.0,
    )


def create_extraction_fn(credential_store: CredentialStore | None = None) -> Callable[[str], str]:
    """Create an extraction_fn that wires agent.py with real LLM calls.

    Returns a callable matching the ExtractionFn contract:
        (prompt: str) -> str
    The returned string is the raw LLM response content.
    """
    agent = get_llm_agent(credential_store=credential_store)

    def extraction_fn(prompt: str) -> str:
        response = agent.invoke([HumanMessage(content=prompt)])
        return response.content

    return extraction_fn