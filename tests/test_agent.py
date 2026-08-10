import httpx
import openai
import os
from unittest.mock import patch

from core.agent import get_llm_agent, create_extraction_fn, invoke_llm_with_retry
from core.credentials import CredentialStore, DEFAULT_API_BASE, DEFAULT_MODEL_NAME
from tests.test_credentials import FakeKeyring


def _make_internal_server_error() -> openai.InternalServerError:
    """Build a realistic openai.InternalServerError (e.g. Envoy upstream failure)."""
    req = httpx.Request("POST", "http://example.com/v1/chat/completions")
    resp = httpx.Response(500, request=req)
    return openai.InternalServerError(
        "Internal Server Error: upstream connect error", response=resp, body=None
    )


def _make_api_connection_error() -> openai.APIConnectionError:
    req = httpx.Request("POST", "http://example.com/v1/chat/completions")
    return openai.APIConnectionError(message="Connection error: [Errno 111] Connection refused", request=req)


def _make_api_timeout_error() -> openai.APITimeoutError:
    req = httpx.Request("POST", "http://example.com/v1/chat/completions")
    return openai.APITimeoutError(request=req)


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
                timeout=120.0,
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
                timeout=120.0,
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
            timeout=120.0,
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
            timeout=120.0,
        )

# ---- Gateway-transient retry (InternalServerError / APIConnectionError / APITimeoutError) ----

class _FakeAgent:
    """Minimal fake agent whose .invoke can raise transient errors then succeed."""

    def __init__(self, side_effect, success="OK"):
        self.side_effect = list(side_effect)
        self.success = success
        self.call_count = 0
        self.last_messages = None

    def invoke(self, messages):
        self.call_count += 1
        self.last_messages = messages
        if self.side_effect:
            exc = self.side_effect.pop(0)
            if exc is not None:
                raise exc
        return self.success


def test_invoke_llm_with_retry_recovers_from_internal_server_error():
    """Transient InternalServerError must be retried and recover."""
    fake = _FakeAgent(side_effect=[_make_internal_server_error(), _make_internal_server_error(), None])
    retries = []
    with patch("core.agent.time.sleep") as mock_sleep:
        result = invoke_llm_with_retry(
            fake, ["msg"],
            on_retry=lambda attempt, max_retries, wait, message, error: retries.append((attempt, wait, message)),
        )
    assert result == "OK"
    assert fake.call_count == 3  # initial + 2 retries
    assert len(retries) == 2
    # durations are 3s then 6s (exponential)
    assert mock_sleep.call_args_list[0][0][0] == 3
    assert mock_sleep.call_args_list[1][0][0] == 6
    # friendly message present
    assert "API 网关抖动" in retries[0][2] or "重试" in retries[0][2]


def test_invoke_llm_with_retry_recovers_from_api_connection_error():
    """Transient APIConnectionError must be retried and recover."""
    fake = _FakeAgent(side_effect=[_make_api_connection_error(), None])
    with patch("core.agent.time.sleep"):
        result = invoke_llm_with_retry(fake, ["msg"])
    assert result == "OK"
    assert fake.call_count == 2  # initial + 1 retry


def test_invoke_llm_with_retry_recovers_from_api_timeout_error():
    """Transient APITimeoutError must be retried and recover."""
    fake = _FakeAgent(side_effect=[_make_api_timeout_error(), None])
    retries = []
    with patch("core.agent.time.sleep") as mock_sleep:
        result = invoke_llm_with_retry(
            fake, ["msg"],
            on_retry=lambda attempt, max_retries, wait, message, error: retries.append(message),
        )
    assert result == "OK"
    assert fake.call_count == 2  # initial + 1 retry
    assert len(retries) == 1
    assert "重试" in retries[0]
    assert mock_sleep.call_args_list[0][0][0] == 3  # first wait is 3s


def test_invoke_llm_with_retry_raises_api_timeout_after_exhausting_retries():
    """APITimeoutError re-raised after retries are exhausted."""
    fake = _FakeAgent(side_effect=[_make_api_timeout_error()] * 4)
    with patch("core.agent.time.sleep"):
        try:
            invoke_llm_with_retry(fake, ["msg"])
            assert False, "expected APITimeoutError to be raised"
        except openai.APITimeoutError:
            pass
    assert fake.call_count == 4  # initial + 3 retries


def test_invoke_llm_with_retry_raises_after_exhausting_retries():
    """After 3 retries the InternalServerError must be re-raised."""
    fake = _FakeAgent(
        side_effect=[_make_internal_server_error()] * 4  # initial + 3 retries
    )
    retries = []
    with patch("core.agent.time.sleep") as mock_sleep:
        try:
            invoke_llm_with_retry(
                fake, ["msg"],
                on_retry=lambda attempt, m, w, msg, e: retries.append((attempt, w)),
            )
            assert False, "expected InternalServerError to be raised"
        except openai.InternalServerError:
            pass
    assert fake.call_count == 4  # initial + 3 retries
    assert len(retries) == 3
    # durations 3, 6, 12; attempts 1, 2, 3
    sleeps = [c[0][0] for c in mock_sleep.call_args_list]
    assert sleeps == [3, 6, 12]
    assert [a for a, _ in retries] == [1, 2, 3]


def test_invoke_llm_with_retry_does_not_retry_other_errors():
    """Non-transient errors must propagate immediately without retry."""
    fake = _FakeAgent(side_effect=[ValueError("no retry")])
    with patch("core.agent.time.sleep") as mock_sleep:
        try:
            invoke_llm_with_retry(fake, ["msg"])
            assert False, "expected ValueError"
        except ValueError:
            pass
    assert fake.call_count == 1
    mock_sleep.assert_not_called()
