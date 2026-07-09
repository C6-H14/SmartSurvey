import os
from unittest.mock import patch

from core.agent import get_llm_agent, create_extraction_fn
from core.credentials import CredentialStore, DEFAULT_API_BASE, DEFAULT_MODEL_NAME
from tests.test_credentials import FakeKeyring


def test_agent_uses_keyring_credentials():
    """Keyring values take priority over environment variables."""
    store = CredentialStore(keyring_backend=FakeKeyring())
    store.save_all(
        api_key="sk-keyring",
        api_base="https://keyring.url/v1",
        model_name="keyring-model",
    )

    os.environ["OPENAI_API_KEY"] = "sk-env"
    os.environ["OPENAI_API_BASE"] = "https://env.url/v1"
    os.environ["LLM_MODEL_NAME"] = "env-model"
    try:
        with patch("core.agent.ChatOpenAI") as mock_chat:
            get_llm_agent(credential_store=store)
            mock_chat.assert_called_once_with(
                model="keyring-model",
                openai_api_key="sk-keyring",
                openai_api_base="https://keyring.url/v1",
                temperature=0.2,
                max_retries=2,
                timeout=180.0,
            )
    finally:
        del os.environ["OPENAI_API_KEY"]
        del os.environ["OPENAI_API_BASE"]
        del os.environ["LLM_MODEL_NAME"]


def test_agent_falls_back_to_env_vars():
    """Empty keyring uses environment variables."""
    store = CredentialStore(keyring_backend=FakeKeyring())

    os.environ["OPENAI_API_KEY"] = "sk-env"
    os.environ["OPENAI_API_BASE"] = "https://env.url/v1"
    os.environ["LLM_MODEL_NAME"] = "env-model"
    try:
        with patch("core.agent.ChatOpenAI") as mock_chat:
            get_llm_agent(credential_store=store)
            mock_chat.assert_called_once_with(
                model="env-model",
                openai_api_key="sk-env",
                openai_api_base="https://env.url/v1",
                temperature=0.2,
                max_retries=2,
                timeout=180.0,
            )
    finally:
        del os.environ["OPENAI_API_KEY"]
        del os.environ["OPENAI_API_BASE"]
        del os.environ["LLM_MODEL_NAME"]


def test_agent_falls_back_to_defaults():
    """Nothing configured uses hardcoded defaults."""
    store = CredentialStore(keyring_backend=FakeKeyring())

    with patch("core.agent.ChatOpenAI") as mock_chat:
        get_llm_agent(credential_store=store)
        mock_chat.assert_called_once_with(
            model=DEFAULT_MODEL_NAME,
            openai_api_key="",
            openai_api_base=DEFAULT_API_BASE,
            temperature=0.2,
            max_retries=2,
            timeout=180.0,
        )


def test_agent_injects_credentials_to_chatopenai():
    """ChatOpenAI receives correct parameters."""
    store = CredentialStore(keyring_backend=FakeKeyring())
    store.save_all(
        api_key="sk-agent",
        api_base="https://agent.url/v1",
        model_name="agent-model",
    )

    with patch("core.agent.ChatOpenAI") as mock_chat:
        get_llm_agent(credential_store=store)
        mock_chat.assert_called_once_with(
            model="agent-model",
            openai_api_key="sk-agent",
            openai_api_base="https://agent.url/v1",
            temperature=0.2,
            max_retries=2,
            timeout=180.0,
        )