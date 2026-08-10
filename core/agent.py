import os
import time
from typing import Callable

import openai
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from core.credentials import CredentialStore, DEFAULT_API_BASE, DEFAULT_MODEL_NAME


def gateway_retry(
    fn: Callable[[], str],
    max_retries: int = 3,
    on_retry: Callable[[int, int, float, str, BaseException], None] | None = None,
) -> str:
    """Call ``fn`` with exponential backoff on transient API-gateway errors.

    Retries only when the call raises ``openai.InternalServerError`` or
    ``openai.APIConnectionError`` (e.g. Envoy upstream connection failures from
    an API relay gateway). Waits 2s / 4s / 8s between attempts.

    Args:
        fn: Zero-arg callable wrapping an LLM request (``agent.invoke`` or an
            ``extraction_fn`` call). Returns the raw response.
        max_retries: Number of additional attempts after the first (default 3).
        on_retry: Optional hook invoked before each retry with
            ``(attempt, max_retries, wait_seconds, friendly_message, error)``.
            When ``None``, a friendly line is printed to the console. Callers may
            pass a hook that surfaces ``st.warning(friendly_message)`` in the UI.

    Returns:
        The successful return value of ``fn``.

    Raises:
        The last ``openai.InternalServerError`` / ``openai.APIConnectionError``
        once ``max_retries`` are exhausted.
    """
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except (openai.InternalServerError, openai.APIConnectionError) as e:
            if attempt >= max_retries:
                raise
            wait = 2 ** (attempt + 1)  # 2, 4, 8 seconds
            message = (
                f"API 网关抖动中，正在尝试第 {attempt + 1}/{max_retries} 次重试"
                f"（{type(e).__name__}），{wait:.0f}s 后重试..."
            )
            if on_retry:
                on_retry(attempt + 1, max_retries, float(wait), message, e)
            else:
                print(f"  [{type(e).__name__}] {message}")
            time.sleep(wait)
    raise RuntimeError("gateway_retry: unreachable")  # pragma: no cover


def invoke_llm_with_retry(
    agent,
    messages,
    on_retry: Callable[[int, int, float, str, BaseException], None] | None = None,
):
    """Invoke ``agent.invoke(messages)`` with the shared gateway-transient retry.

    Thin convenience wrapper so LLM call sites read naturally:
    ``invoke_llm_with_retry(agent, [HumanMessage(content=prompt)], on_retry=...)``.
    """
    return gateway_retry(lambda: agent.invoke(messages), on_retry=on_retry)


def get_llm_agent(temperature: float = 0.2, credential_store: CredentialStore | None = None) -> ChatOpenAI:
    store = credential_store or CredentialStore()
    creds = store.get_all()

    if store.has_credentials():
        api_key = creds["llm_api_key"]
        api_base = creds["llm_api_base"]
        model_name = creds["llm_model_name"]
    else:
        api_key = os.getenv("OPENAI_API_KEY") or ""
        api_base = os.getenv("OPENAI_API_BASE") or DEFAULT_API_BASE
        model_name = os.getenv("LLM_MODEL_NAME") or DEFAULT_MODEL_NAME

    return ChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base=api_base,
        temperature=temperature,
        max_retries=2,
        timeout=180.0,
    )


def create_extraction_fn(
    credential_store: CredentialStore | None = None,
    on_retry: Callable[[int, int, float, str, BaseException], None] | None = None,
    **kwargs: object,
) -> Callable[[str], str]:
    """Create an extraction_fn that wires agent.py with real LLM calls.

    Args:
        credential_store: Optional credential store; falls back to environment.
        on_retry: Optional hook invoked before each gateway-transient retry so the
            UI can surface a friendly warning (e.g. ``st.warning``). When ``None``
            a friendly line is printed to the console.
        **kwargs: Reserved for forward/backward compatibility. Unrecognized keyword
            arguments are silently accepted so an older or newer caller that passes
            an extra kwarg never crashes with ``TypeError``. (This guards against
            signature drift between a deployed instance and this source.)

    Returns:
        A callable matching the ExtractionFn contract:
            (prompt: str) -> str
        The returned string is the raw LLM response content. Transient
        ``openai.InternalServerError`` / ``openai.APIConnectionError`` are retried
        internally with exponential backoff (2s/4s/8s, 3 retries).
    """
    # NOTE: ``kwargs`` is intentionally unused — it exists solely so that a caller
    # passing a now-obsolete/extra keyword argument (e.g. an older UI layer calling
    # ``create_extraction_fn(..., on_retry=...)`` against a newer signature, or a
    # newer caller passing a not-yet-supported option) degrades gracefully instead of
    # raising ``TypeError: unexpected keyword argument`` at runtime.
    _ = kwargs
    agent = get_llm_agent(credential_store=credential_store)

    def extraction_fn(prompt: str) -> str:
        response = invoke_llm_with_retry(
            agent,
            [HumanMessage(content=prompt)],
            on_retry=on_retry,
        )
        return response.content

    return extraction_fn