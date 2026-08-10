"""End-to-end closed-loop smoke tests for the LLM synthesis chain.

These tests mock the real LLM at the `core.agent.get_llm_agent` / `agent.invoke`
seam — exactly where `main.py`'s `run_app()` wires in `create_extraction_fn` —
then drive the full UI->core chain:

    create_extraction_fn(on_retry=...)   -> get_llm_agent() is mocked
        -> generate_llm_artifacts(...)   -> dispatches to a render function
            -> render_survey_tex_with_llm(...)        (single-pass, <=8000 chars)
            -> render_survey_tex_multi_stage(...)     (multi-stage, >8000 chars)

They also verify that `on_retry` (the Streamlit warning hook) threads from the UI
layer all the way into the core retry, and that `create_extraction_fn` tolerates
extra keyword arguments (backward/forward compatibility against signature drift).
"""
import openai
from unittest.mock import Mock, patch

from core.agent import create_extraction_fn
from core.models import AcademicMatrixRow
from core.pipeline import generate_llm_artifacts
from core.synthesis import render_survey_tex_with_llm


VALID_LATEX = (
    r"\section{Abstract and Introduction}Intro text."
    r"\section{Technical Taxonomy}Taxonomy text."
    r"\section{Systematic Review and Deep Critique}Critique text."
    r"\section{Academic Comparison Matrix}\begin{description}"
    r"\item[\textbf{1. Paper A (2024)：}] \hfill \\"
    r"\textbf{技术方法：}method \\"
    r"\textbf{关键优势：}fast \\"
    r"\textbf{核心局限：}limit"
    r"\end{description}"
    r"\section{Research Gaps and Future Work}Gaps text."
    r"\section{Conclusion}Done."
)


def _make_row() -> AcademicMatrixRow:
    return AcademicMatrixRow(
        title="Paper A", authors="Alice", year="2024", venue="ICRA",
        research_problem="detection", method="vision", innovation="new",
        limitation="lighting", evidence_page=1, evidence_quote="limitation",
        confidence=0.8, trigger_reason="stated",
    )


class _MockedLLM:
    """Wraps a Mock agent.fake-response seam used to stand in for 'real LLM'."""

    def __init__(self, content: str = VALID_LATEX):
        self.agent = Mock()
        msg = Mock()
        msg.content = content
        self.agent.invoke.return_value = msg

    def patch(self):
        # main.py calls create_extraction_fn -> get_llm_agent(); mock that seam.
        # Returns the active patcher so it can be used as a context manager,
        # e.g. ``with mocked.patch():``.
        return patch("core.agent.get_llm_agent", return_value=self.agent)


def test_e2e_single_pass_full_chain_with_on_retry():
    """UI->core chain (<=8000 chars) runs and threads on_retry into the retry hook."""
    mocked = _MockedLLM()
    retry_messages: list[str] = []

    def on_retry(attempt, max_retries, wait, message, error):
        retry_messages.append(message)

    with mocked.patch(), patch("core.agent.time.sleep"):
        extraction_fn = create_extraction_fn(on_retry=on_retry)
        artifacts = generate_llm_artifacts(
            "anomaly detection", [_make_row()], extraction_fn, [],
            word_count_target=1000,
            progress_callback=lambda *_: None,
            on_retry=on_retry,
        )

    # The mocked LLM never fails, so no retry fires — but the full chain completed.
    assert artifacts.survey_tex
    assert r"\documentclass{ctexart}" in artifacts.survey_tex
    assert r"\end{document}" in artifacts.survey_tex
    assert retry_messages == []
    # Agent invoked in the single-pass path.
    mocked.agent.invoke.assert_called()


def test_e2e_multi_stage_full_chain():
    """UI->core chain with >8000 chars dispatches to the multi-stage renderer."""
    mocked = _MockedLLM()
    with mocked.patch(), patch("core.agent.time.sleep"):
        extraction_fn = create_extraction_fn(on_retry=None)
        artifacts = generate_llm_artifacts(
            "anomaly detection", [_make_row()], extraction_fn, [],
            word_count_target=9000,
            progress_callback=lambda *_: None,
            on_retry=None,
        )
    assert artifacts.survey_tex
    assert r"\documentclass{ctexart}" in artifacts.survey_tex
    assert r"\end{document}" in artifacts.survey_tex
    # Multi-stage calls the LLM 6 times (once per section).
    assert len(mocked.agent.invoke.call_args_list) >= 6


def test_e2e_transient_gateway_error_invokes_on_retry_warning():
    """A transient InternalServerError triggers the on_retry warning hook in chain."""
    from unittest.mock import Mock as _Mock
    agent = _Mock()
    msg = _Mock()
    msg.content = VALID_LATEX

    def invoke_that_fails_once(messages):
        if invoke_that_fails_once.calls == 0:
            invoke_that_fails_once.calls += 1
            req = __import__("httpx").Request("POST", "http://x/v1")
            resp = __import__("httpx").Response(500, request=req)
            raise openai.InternalServerError(
                "upstream connect error", response=resp, body=None)
        # Subsequent calls succeed: return a fake AIMessage with .content.
        return msg

    invoke_that_fails_once.calls = 0
    agent.invoke.side_effect = invoke_that_fails_once
    retry_messages: list[str] = []
    with patch("core.agent.get_llm_agent", return_value=agent), patch("core.agent.time.sleep"):
        extraction_fn = create_extraction_fn(
            on_retry=lambda a, m, w, msg, e: retry_messages.append(msg)
        )
        artifacts = generate_llm_artifacts(
            "anomaly detection", [_make_row()], extraction_fn, [],
            word_count_target=1000,
            on_retry=lambda a, m, w, msg, e: retry_messages.append(msg),
        )
    assert retry_messages, "expected at least one on_retry warning"
    assert any("API 网关抖动" in m for m in retry_messages)


def test_e2e_render_survey_tex_with_llm_direct():
    """render_survey_tex_with_llm is directly callable with a mocked extraction_fn."""
    calls = {"n": 0}

    def mocked_extraction_fn(prompt: str) -> str:
        calls["n"] += 1
        return VALID_LATEX

    with patch("core.agent.time.sleep"):
        result = render_survey_tex_with_llm(
            "anomaly detection", [_make_row()], mocked_extraction_fn,
            word_count_target=1000,
            on_retry=lambda *_: None,
        )
    assert calls["n"] >= 1
    assert r"\documentclass{ctexart}" in result


def test_create_extraction_fn_tolerates_extra_kwargs():
    """Backward/forward compat: unknown kwargs must not raise TypeError."""
    from core.agent import get_llm_agent

    # Only reason we patch get_llm_agent: create_extraction_fn builds a real agent.
    with patch("core.agent.get_llm_agent") as mock_get:
        mock_get.return_value = Mock()
        extraction_fn = create_extraction_fn(
            on_retry=None,
            unsupported_legacy_option="yes",  # must NOT raise
            future_flag=True,                  # must NOT raise
        )
    assert callable(extraction_fn)

# ---- New `agent=` DI seam + full run_app-style chain ----

def test_create_extraction_fn_accepts_injected_agent():
    """The new ``agent=`` dependency-injection seam must work end to end."""
    mocked = _MockedLLM()  # .agent has invoke() -> fake AIMessage
    with patch("core.agent.time.sleep"):
        extraction_fn = create_extraction_fn(agent=mocked.agent, on_retry=None)
        artifacts = generate_llm_artifacts(
            "anomaly detection", [_make_row()], extraction_fn, [],
            word_count_target=1000,
            on_retry=None,
        )
    assert artifacts.survey_tex
    assert r"\documentclass{ctexart}" in artifacts.survey_tex
    mocked.agent.invoke.assert_called()


def test_full_run_app_chain_with_on_retry_and_agent():
    """Mimics main.run_app(): agent + on_retry at create, on_retry at artifacts."""
    mocked = _MockedLLM()
    warned: list[str] = []

    def hook(attempt, max_retries, wait, message, error):
        warned.append(message)

    with patch("core.agent.time.sleep"):
        extraction_fn = create_extraction_fn(agent=mocked.agent, on_retry=hook)
        artifacts = generate_llm_artifacts(
            "robotics review", [_make_row()], extraction_fn, [],
            word_count_target=1000,
            progress_callback=lambda *_: None,
            on_retry=hook,
        )
    assert artifacts.survey_tex
    # every retrieval went through invoke; no transient error -> no warnings
    assert warned == []
    assert mocked.agent.invoke.call_count >= 1


def test_e2e_transient_api_timeout_invokes_on_retry_and_recovers():
    """A transient APITimeoutError triggers the on_retry hook and recovers in chain."""
    from unittest.mock import Mock as _Mock

    agent = _Mock()
    msg = _Mock()
    msg.content = VALID_LATEX

    def invoke_that_times_out_once(messages):
        if invoke_that_times_out_once.calls == 0:
            invoke_that_times_out_once.calls += 1
            req = __import__("httpx").Request("POST", "http://x/v1")
            raise openai.APITimeoutError(request=req)
        # Subsequent calls succeed.
        return msg

    invoke_that_times_out_once.calls = 0
    agent.invoke.side_effect = invoke_that_times_out_once
    retry_messages: list[str] = []
    with patch("core.agent.get_llm_agent", return_value=agent), patch("core.agent.time.sleep"):
        extraction_fn = create_extraction_fn(
            on_retry=lambda a, m, w, msg, e: retry_messages.append(msg)
        )
        artifacts = generate_llm_artifacts(
            "anomaly detection", [_make_row()], extraction_fn, [],
            word_count_target=1000,
            on_retry=lambda a, m, w, msg, e: retry_messages.append(msg),
        )
    assert artifacts.survey_tex
    assert retry_messages, "expected at least one on_retry warning for timeout"
    assert any("重试" in m for m in retry_messages)


def test_main_api_node_presets_and_timeout_guidance():
    """Sidebar presets cover the common nodes + custom, and a friendly timeout hint exists."""
    import main as client

    names = set(client.API_NODE_PRESETS.keys())
    assert {"默认中转网关", "DeepSeek 官方", "硅基流动 SiliconFlow", "自定义 Base URL"} <= names
    assert client.API_NODE_PRESETS["默认中转网关"]["base"] == "https://njusehub.info/v1"
    assert client.API_NODE_PRESETS["DeepSeek 官方"]["base"] == "https://api.deepseek.com/v1"
    assert client.API_NODE_PRESETS["硅基流动 SiliconFlow"]["base"] == "https://api.siliconflow.cn/v1"
    assert client.API_NODE_PRESETS["DeepSeek 官方"]["model"] == "deepseek-chat"
    assert "切换 API 节点" in client.APITIMEOUT_ERROR_MESSAGE
    assert "DeepSeek 官方" in client.APITIMEOUT_ERROR_MESSAGE
    assert "SiliconFlow" in client.APITIMEOUT_ERROR_MESSAGE
