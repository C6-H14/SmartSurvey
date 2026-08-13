import openai
from unittest.mock import patch

from core.synthesis import (
    build_synthesis_prompt,
    render_survey_tex_with_llm,
    render_survey_tex_multi_stage,
    validate_latex_syntax,
    SECTION_TEMPLATES,
    SECTION_NAMES,
)


def test_synthesis_prompt_has_math_constraint():
    """Synthesis prompt must require LaTeX math formulas."""
    from core.models import AcademicMatrixRow
    row = AcademicMatrixRow(
        title="A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    prompt = build_synthesis_prompt("test topic", [row])
    assert "formula" in prompt.lower() or "公式" in prompt or "equation" in prompt.lower()
    assert "$" in prompt or "\\(" in prompt


def test_build_preamble_contains_magic_comments():
    """Preamble must include xelatex magic comments."""
    from core.synthesis import _build_preamble
    preamble = _build_preamble()

    assert "% !TEX program = xelatex" in preamble
    assert "% !TEX root = survey_draft.tex" in preamble
    assert r"\documentclass{ctexart}" in preamble
    assert r"\begin{document}" in preamble


def test_build_preamble_does_not_include_end_document():
    """Preamble should NOT include \end{document}."""
    from core.synthesis import _build_preamble
    preamble = _build_preamble()

    assert r"\end{document}" not in preamble


def test_build_synthesis_prompt_accepts_word_count_target():
    """Word count target must appear in the generated prompt."""
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    prompt = build_synthesis_prompt("topic", [row], word_count_target=2000)
    assert "2000" in prompt
    assert "chinese characters" in prompt.lower() or "字" in prompt


def test_build_synthesis_prompt_contains_topic_and_rows():
    from core.models import AcademicMatrixRow
    row = AcademicMatrixRow(
        title="Paper A", authors="Alice", year="2024", venue="ICRA",
        research_problem="detection", method="vision", innovation="new",
        limitation="lighting", evidence_page=2, evidence_quote="limitation",
        confidence=0.8, trigger_reason="stated",
        domain_fields={"sensor": "camera"},
    )
    prompt = build_synthesis_prompt("anomaly detection", [row])

    assert "anomaly detection" in prompt
    assert "Paper A" in prompt
    assert "ctexart" in prompt
    assert "\\section{摘要与引言}" in prompt
    assert "\\section{技术分类体系}" in prompt
    assert "\\section{系统评述与深度批判}" in prompt
    assert "\\section{学术对比矩阵}" in prompt
    assert "\\section{研究缺口与未来工作}" in prompt
    assert "\\section{结论}" in prompt
    assert "Return ONLY valid LaTeX" in prompt or "Return only" in prompt.lower()


def test_tabularx_is_valid_latex_environment():
    """tabularx environment must not trigger false positive."""
    source = r"\begin{tabularx}{\textwidth}{XXXX} a & b \\ \end{tabularx}"
    errors = validate_latex_syntax(source)
    assert errors == []


class ValidLaTeXExtractor:
    """Mock extractor that returns valid LaTeX section content (no preamble)."""
    def __init__(self):
        self.call_count = 0

    def __call__(self, prompt: str) -> str:
        self.call_count += 1
        return (
            r"\section{摘要与引言}This is a test review."
            r"\section{技术分类体系}Categories here."
            r"\section{系统评述与深度批判}Critique with evidence."
            r"\section{学术对比矩阵}\begin{description}"
            r"\item[\textbf{1. Paper A (2024)：}] \hfill \\"
            r"\textbf{技术方法：}vision \\"
            r"\textbf{关键优势：}fast \\"
            r"\textbf{核心局限：}lighting"
            r"\end{description}"
            r"\section{研究缺口与未来工作}Future directions."
            r"\section{结论}Summary."
        )


class InvalidLaTeXExtractor:
    """Mock extractor that returns LaTeX with syntax errors (no preamble)."""
    def __init__(self):
        self.call_count = 0

    def __call__(self, prompt: str) -> str:
        self.call_count += 1
        if self.call_count == 1:
            return (
                r"\section{Test}Unclosed formula $x + y"
            )
        return (
            r"\section{Test}Closed formula $x + y$"
        )


def test_render_survey_tex_with_llm_valid():
    """Valid LaTeX passes through static validation (xelatex compilation may or may not succeed)."""
    extractor = ValidLaTeXExtractor()
    result = render_survey_tex_with_llm(
        topic="test topic",
        rows=[],
        extraction_fn=extractor,
    )
    # Result must be valid LaTeX regardless of retries
    assert r"\documentclass{ctexart}" in result
    assert r"\section{摘要与引言}" in result
    # At minimum, the LLM was called once
    assert extractor.call_count >= 1


def test_render_survey_tex_with_llm_self_healing():
    """Invalid LaTeX triggers one self-healing retry."""
    extractor = InvalidLaTeXExtractor()
    result = render_survey_tex_with_llm(
        topic="test topic",
        rows=[],
        extraction_fn=extractor,
    )
    # Must have called twice (initial + 1 retry)
    assert extractor.call_count == 2
    # Result should be the fixed version
    assert r"$x + y$" in result


def test_valid_latex_returns_empty_errors():
    source = r"""\documentclass{ctexart}
\usepackage{booktabs}
\begin{document}
\section{Introduction}
This is a test.
\end{document}"""
    errors = validate_latex_syntax(source)
    assert errors == []


def test_unclosed_inline_math_detected():
    source = r"\section{Test} The formula $x + y = z$ is valid."
    errors = validate_latex_syntax(source)
    assert errors == []  # closed $...$ is valid

    broken = r"\section{Test} The formula $x + y = z is broken."
    errors = validate_latex_syntax(broken)
    assert any("$" in e for e in errors)


def test_unclosed_display_math_detected():
    broken = r"\section{Test} Display math $$ x + y"
    errors = validate_latex_syntax(broken)
    assert any("$$" in e or "$" in e for e in errors)


def test_mismatched_begin_end_detected():
    source = r"\begin{table}\begin{tabular}{ll}\end{tabular}\end{figure}"
    errors = validate_latex_syntax(source)
    assert any("figure" in e.lower() or "table" in e.lower() for e in errors)


def test_unclosed_environment_detected():
    source = r"\begin{table}\begin{tabular}{ll}\end{tabular}"
    errors = validate_latex_syntax(source)
    assert len(errors) > 0  # table has no \end{table}


def test_unbalanced_braces_detected():
    source = r"\textbf{Hello world"
    errors = validate_latex_syntax(source)
    assert any("brace" in e.lower() or "{" in e for e in errors)


def test_escaped_dollar_does_not_trigger_false_positive():
    source = r"\section{Test} Price is \$10.00 and \$20.00"
    errors = validate_latex_syntax(source)
    assert errors == []


def test_escaped_brace_does_not_trigger_false_positive():
    source = r"\section{Test} Function call: foo\{bar\} baz"
    errors = validate_latex_syntax(source)
    assert errors == []


def test_build_synthesis_prompt_has_separator_constraint():
    """Prompt must instruct LLM to use \noindent\textbf{摘要：} and \noindent\textbf{引言：}."""
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    prompt = build_synthesis_prompt("topic", [row])

    assert r"\noindent\textbf{摘要：}" in prompt or "摘要：" in prompt
    assert r"\noindent\textbf{引言：}" in prompt or "引言：" in prompt
    assert "CRITICAL" in prompt


def test_render_survey_tex_multi_stage_returns_valid_latex():
    """Multi-stage synthesis must produce valid LaTeX with all 6 sections."""
    from core.synthesis import render_survey_tex_multi_stage, validate_latex_syntax
    from core.models import AcademicMatrixRow

    class SequentialExtractor:
        def __init__(self):
            self.call_count = 0
            self.sections = [
                r"\section{摘要与引言}Test abstract content.",
                r"\section{技术分类体系}Test taxonomy.",
                r"\section{系统评述与深度批判}Test critique.",
                r"\section{学术对比矩阵}Test matrix.",
                r"\section{研究缺口与未来工作}Test gaps.",
                r"\section{结论}Test conclusion.",
            ]
        def __call__(self, prompt: str) -> str:
            result = self.sections[self.call_count]
            self.call_count += 1
            return result

    row = AcademicMatrixRow(
        title="A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    extractor = SequentialExtractor()
    result = render_survey_tex_multi_stage(
        topic="test topic",
        rows=[row],
        extraction_fn=extractor,
        word_count_target=10000,
    )

    # Must have preamble + 6 sections + \end{document}
    assert r"\documentclass{ctexart}" in result
    assert r"\section{摘要与引言}" in result
    assert r"\section{结论}" in result
    assert r"\end{document}" in result
    # Must have called LLM exactly 6 times
    assert extractor.call_count == 6
    # Must pass LaTeX validation
    errors = validate_latex_syntax(result)
    assert errors == []


def test_cjk_bracket_detected():
    """CJK right-angle bracket replacing } must be detected."""
    from core.synthesis import validate_latex_syntax

    # 》 replacing } — a real LLM hallucination found in production
    broken = r"\subsection{核心贡献与技术谱系》"
    errors = validate_latex_syntax(broken)
    assert any("》" in e or "CJK" in e for e in errors)

    # Valid LaTeX with CJK content should NOT trigger false positive
    valid = r"\subsection{核心贡献与技术谱系}"
    errors2 = validate_latex_syntax(valid)
    assert errors2 == []

    # Closing brace with CJK after it is fine
    valid2 = r"\subsection{摘要：}本文围绕"
    errors3 = validate_latex_syntax(valid2)
    assert errors3 == []


def test_build_synthesis_prompt_has_itemize_constraint():
    """Prompt must require itemize for lists."""
    from core.synthesis import build_synthesis_prompt
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    prompt = build_synthesis_prompt("topic", [row])

    assert "begin{itemize}" in prompt
    assert "item" in prompt


def test_build_synthesis_prompt_has_colon_constraint():
    """Prompt must require Chinese colon after \\textbf{...}."""
    from core.synthesis import build_synthesis_prompt
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    prompt = build_synthesis_prompt("topic", [row])

    assert "：\"" in prompt or "：" in prompt
    assert "textbf" in prompt


def test_render_survey_tex_with_llm_has_preamble_wrap():
    """Single-pass synthesis must wrap output with hardcoded preamble."""
    from core.synthesis import render_survey_tex_with_llm

    class ContentOnlyExtractor:
        def __call__(self, prompt: str) -> str:
            # LLM output starts directly with \section (no preamble)
            return r"\section{摘要与引言}Test content."

    result = render_survey_tex_with_llm(
        topic="test",
        rows=[],
        extraction_fn=ContentOnlyExtractor(),
    )

    # Must have hardcoded preamble
    assert r"\documentclass{ctexart}" in result
    assert r"\usepackage[paper=a4paper, margin=1.8cm]{geometry}" in result
    assert r"\usepackage{amsmath}" in result
    # Must have the LLM content
    assert r"\section{摘要与引言}" in result
    # Must have \end{document}
    assert r"\end{document}" in result


# === Dimension A: Topic Neutrality ===

def test_prompt_no_domain_hardcoding():
    """Prompt must not contain domain-specific terms for any topic."""
    from core.models import AcademicMatrixRow
    row = AcademicMatrixRow(
        title="A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    for test_topic in ["medical lesion segmentation", "algebraic geometry"]:
        prompt = build_synthesis_prompt(test_topic, [row])
        assert "robot" not in prompt.lower()
        assert "industrial" not in prompt.lower()
        assert "机械臂" not in prompt
        assert test_topic in prompt


# === Dimension B: SECTION_TEMPLATES Integrity ===

def test_section_templates_integrity():
    """SECTION_TEMPLATES must have exactly 6 entries with valid structure."""
    from core.synthesis import SECTION_TEMPLATES
    assert len(SECTION_TEMPLATES) == 6
    for t in SECTION_TEMPLATES:
        assert "name" in t
        assert "weight" in t
        assert "guidance" in t
        assert "{topic}" in t["guidance"]
        assert t["weight"] in ("heavy", "light")
    heavy = [t for t in SECTION_TEMPLATES if t["weight"] == "heavy"]
    light = [t for t in SECTION_TEMPLATES if t["weight"] == "light"]
    assert len(heavy) == 3  # Chapter 1, Chapter 3 (promoted), and Chapter 5
    assert len(light) == 3
    # heavy guidance must be longer than the shortest light guidance
    min_light_len = min(len(t["guidance"]) for t in light)
    for h in heavy:
        assert len(h["guidance"]) > min_light_len, f"{h['name']} heavy guidance too short"


def test_section_templates_names_match_section_names():
    """SECTION_TEMPLATES names must match SECTION_NAMES in order."""
    from core.synthesis import SECTION_TEMPLATES, SECTION_NAMES
    assert len(SECTION_TEMPLATES) == len(SECTION_NAMES)
    for tmpl, name in zip(SECTION_TEMPLATES, SECTION_NAMES):
        assert tmpl["name"] == name, f"{tmpl['name']} != {name}"


# === Dimension C: Two-Path Consistency ===

def test_both_paths_use_same_section_guidance():
    """Section 0 guidance must appear in both build_synthesis_prompt and _build_section_prompt(0)."""
    from core.synthesis import build_synthesis_prompt, _build_section_prompt
    from core.models import AcademicMatrixRow
    row = AcademicMatrixRow(
        title="A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    topic = "test topic"
    full = build_synthesis_prompt(topic, [row])
    sectional = _build_section_prompt(0, topic, [row], 3000)
    # Both must reference the core guidance indicator for section 0
    assert "研究背景" in full
    assert "研究背景" in sectional


# === Dimension D: CJK Precision ===

def test_cjk_bracket_detection_error_precision():
    """Error message must include precise locating hints in Chinese."""
    from core.synthesis import validate_latex_syntax
    broken = r"\subsection{核心贡献与技术谱系》"
    errors = validate_latex_syntax(broken)
    assert any("检测到中文符号" in e or "CJK" in e for e in errors)
    assert any("输入法冲突" in e or "替换了" in e or "possibly replacing" in e for e in errors)


def test_evidence_page_leak_stripped():
    """evidence_page= residuals must be stripped from final output — all bracket variants."""
    from core.synthesis import _strip_evidence_page_leaks

    # Round brackets
    dirty = (
        r"\section{Test}Some text (evidence_page=2) more text "
        r"(evidence_page=5) and (evidence_page=42) end."
    )
    clean = _strip_evidence_page_leaks(dirty)
    assert "evidence_page" not in clean

    # Full-width parentheses （ ）— common LLM hallucination
    assert "evidence_page" not in _strip_evidence_page_leaks(
        r"该方法存在局限性（evidence_page=17）。"
    )

    # Square brackets [ ]
    assert "evidence_page" not in _strip_evidence_page_leaks(
        r"该方法存在局限性[evidence_page = 3]。"
    )

    # CJK corner brackets 【 】
    assert "evidence_page" not in _strip_evidence_page_leaks(
        r"该方法存在局限性【evidence_page=21】。"
    )

    # Mixed whitespace tolerance
    assert "evidence_page" not in _strip_evidence_page_leaks(
        r"text ( evidence_page = 7 ) more text"
    )


def test_prompt_forbids_evidence_page():
    """build_synthesis_prompt must forbid evidence_page= in output."""
    from core.models import AcademicMatrixRow
    row = AcademicMatrixRow(
        title="A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    prompt = build_synthesis_prompt("test topic", [row])
    assert "evidence_page" not in prompt or "禁止" in prompt or "严禁" in prompt or "CRITICAL" in prompt
    assert "标准引用" in prompt or "[1]" in prompt or "citation" in prompt.lower()


# ===== Phase 9: Physical XeLaTeX compiler self-healing =====

def test_parse_xelatex_log_extracts_error_lines():
    """_parse_xelatex_log must extract lines starting with ! from .log content."""
    from core.synthesis import _parse_xelatex_log

    log_content = (
        "This is a log file\n"
        "! Undefined control sequence.\n"
        "l.12 \\mathbb\n"
        "The control sequence at the end of the top line\n"
        "! Missing $ inserted.\n"
        "l.25 some text\n"
        "Some more context\n"
    )
    errors = _parse_xelatex_log(log_content)
    assert len(errors) == 2
    assert "Undefined control sequence" in errors[0] or "! Undefined control sequence" in errors[0]
    assert "Missing $ inserted" in errors[1] or "! Missing $ inserted" in errors[1]


def test_parse_xelatex_log_returns_empty_for_clean_log():
    """_parse_xelatex_log must return empty list when no ! lines exist."""
    from core.synthesis import _parse_xelatex_log

    log_content = (
        "This is a clean log file\n"
        "Output written on survey_draft.pdf (1 page).\n"
        "Transcript written on survey_draft.log.\n"
    )
    errors = _parse_xelatex_log(log_content)
    assert errors == []


def test_parse_xelatex_log_deduplicates():
    """_parse_xelatex_log must deduplicate repeated error lines."""
    from core.synthesis import _parse_xelatex_log

    log_content = (
        "! Undefined control sequence.\n"
        "l.12 \\mathbb\n"
        "! Undefined control sequence.\n"
        "l.20 \\mathbb{R}\n"
    )
    errors = _parse_xelatex_log(log_content)
    assert len(errors) == 1  # deduplicated
    assert "Undefined control sequence" in errors[0]


def test_parse_xelatex_log_limits_to_five():
    """_parse_xelatex_log must return at most 5 error lines."""
    from core.synthesis import _parse_xelatex_log

    log_content = "\n".join(f"! Error number {i}.\n" for i in range(10))
    errors = _parse_xelatex_log(log_content)
    assert len(errors) <= 5


def test_compile_with_xelatex_importable():
    """compile_with_xelatex must be importable from core.synthesis."""
    from core.synthesis import compile_with_xelatex
    assert callable(compile_with_xelatex)


# ---- Bibliography auto-injection ----

def test_inject_bibliography_adds_before_end_document():
    """_inject_bibliography must insert thebibliography before \end{document}."""
    from core.synthesis import _inject_bibliography

    source = r"\section{结论}Done." + "\n" + r"\end{document}" + "\n"
    result = _inject_bibliography(source)

    assert r"\begin{thebibliography}{99}" in result
    assert r"\bibitem{bergmann2022}" in result
    assert r"\bibitem{costanzino2023}" in result
    assert r"\bibitem{iodice2025}" in result
    assert r"\bibitem{soudani2026}" in result
    assert r"\end{thebibliography}" in result
    assert r"\end{document}" in result
    assert result.index(r"\begin{thebibliography}") < result.index(r"\end{document}")


def test_inject_bibliography_idempotent():
    """_inject_bibliography must NOT double-inject if already present."""
    from core.synthesis import _inject_bibliography

    source = (
        r"\section{结论}Done." + "\n"
        + r"\begin{thebibliography}{99}" + "\n"
        + r"\bibitem{test}Test." + "\n"
        + r"\end{thebibliography}" + "\n"
        + r"\end{document}" + "\n"
    )
    result = _inject_bibliography(source)

    assert result.count(r"\begin{thebibliography}") == 1


def test_inject_bibliography_skips_if_printbibliography():
    """_inject_bibliography must skip if \printbibliography is present."""
    from core.synthesis import _inject_bibliography

    source = (
        r"\section{结论}Done." + "\n"
        + r"\printbibliography" + "\n"
        + r"\end{document}" + "\n"
    )
    result = _inject_bibliography(source)

    assert r"\begin{thebibliography}" not in result


def test_synthesis_output_contains_bibliography():
    """Single-pass synthesis output must include auto-injected bibliography."""
    from core.synthesis import render_survey_tex_with_llm

    class BibTestExtractor:
        def __call__(self, prompt: str) -> str:
            return r"\title{测试综述}" + "\n" + r"\section{结论}Done."

    result = render_survey_tex_with_llm(
        topic="test", rows=[], extraction_fn=BibTestExtractor(),
    )
    assert r"\begin{thebibliography}{99}" in result
    assert r"\bibitem{bergmann2022}" in result
    assert r"\end{thebibliography}" in result


# ---- Math operator cleaning ----

def test_clean_math_operators_replaces_or_with_lor():
    """_clean_math_operators must replace italic 'or' with \\lor inside math mode."""
    from core.synthesis import _clean_math_operators

    # Inline math
    assert r"\lor" in _clean_math_operators(r"$x > 0 \text{ or } y < 0$")
    assert r"$x > 0 \text{ \lor } y < 0$" in _clean_math_operators(r"$x > 0 \text{ or } y < 0$")

    # Display math
    assert r"\lor" in _clean_math_operators(r"$$a \text{ or } b$$")

    # Whole-word only: "for" and "work" must NOT be changed
    result = _clean_math_operators(r"$for each x, work or factor$")
    assert "for" in result
    assert "work" in result
    assert r"\lor" in result  # but isolated "or" IS replaced
    assert "factor" in result


def test_clean_math_operators_preserves_non_math_or():
    """_clean_math_operators must NOT replace 'or' outside math mode."""
    from core.synthesis import _clean_math_operators

    text = r"This or that sentence in English. $x = a \lor b$ formula."
    result = _clean_math_operators(text)
    assert "This or that" in result  # unchanged — outside math
    assert r"\lor" in result  # already present, preserved


# ---- Gateway-transient retry at synthesis LLM-call sites ----

def _make_internal_server_error():
    import httpx
    req = httpx.Request("POST", "http://example.com/v1/chat/completions")
    resp = httpx.Response(500, request=req)
    return openai.InternalServerError(
        "Internal Server Error: upstream connect error", response=resp, body=None
    )


class FlakyGatewayExtractor:
    """Raises InternalServerError for the first N calls, then returns valid LaTeX."""

    def __init__(self, fail_calls: int):
        self.fail_calls = fail_calls
        self.call_count = 0
        self.warnings: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.call_count += 1
        if self.call_count <= self.fail_calls:
            raise _make_internal_server_error()
        return (
            r"\title{测试综述标题}" + "\n"
            r"\section{摘要与引言}Gateway recovered." + "\n"
            r"\section{结论}Done."
        )


def _capture_warning(on_retry_holder: list):
    def hook(attempt, max_retries, wait, message, error):
        on_retry_holder.append((attempt, max_retries, wait, message))
    return hook


def test_render_survey_recovers_from_gateway_error():
    """Single-pass synthesis must retry transient gateway errors and recover."""
    extractor = FlakyGatewayExtractor(fail_calls=2)
    holder = []
    with patch("core.agent.time.sleep"):
        result = render_survey_tex_with_llm(
            topic="t", rows=[], extraction_fn=extractor,
            on_retry=_capture_warning(holder),
        )
    assert extractor.call_count == 3  # initial + 2 retries
    assert r"\documentclass{ctexart}" in result
    assert "recovered" in result
    # warning hook was invoked with the friendly message
    assert len(holder) == 2
    assert "API 网关抖动" in holder[0][3]


def test_render_survey_multi_stage_recovers_from_gateway_error():
    """Multi-stage synthesis must retry transient gateway errors and recover."""
    extractor = FlakyGatewayExtractor(fail_calls=1)
    holder = []
    with patch("core.agent.time.sleep"):
        result = render_survey_tex_multi_stage(
            topic="t", rows=[], extraction_fn=extractor,
            on_retry=_capture_warning(holder),
        )
    # 6 sections; the first call fails once then recovers
    assert extractor.call_count == 7  # 6 sections + 1 retry on first section
    assert r"\end{document}" in result
    assert len(holder) == 1
    assert "重试" in holder[0][3]


# ---- Absurd page number cleaning ----

def test_strip_absurd_page_numbers_corrects_large_numbers():
    """Pages >= 1000 must be corrected to sensible values."""
    from core.synthesis import _strip_absurd_page_numbers

    # LLM hallucination: page 17241 → 结论部分
    text = r"如文献[3]所述（第17241页），该方法存在局限。"
    result = _strip_absurd_page_numbers(text)
    assert "17241" not in result
    assert "结论部分" in result or "17" in result

    # Four-digit number like 1234 → corrected
    text2 = r"第 1234 页的实验中。"
    result2 = _strip_absurd_page_numbers(text2)
    assert "1234" not in result2

    # Normal page numbers (1-99) must be preserved
    text3 = r"第 17 页的实验中。"
    result3 = _strip_absurd_page_numbers(text3)
    assert "第 17 页" in result3


# ---- Table label injection ----

def test_inject_table_label_adds_label_before_tabularx():
    """_inject_table_label must inject \label{tab:comparison} before tabularx."""
    from core.synthesis import _inject_table_label

    source = (
        r"\section{学术对比矩阵}"
        r"\begin{tabularx}{\textwidth}{l c c c X}"
        r"\toprule"
        r"文献 & 方法 & 指标 & 局限 \\"
        r"\bottomrule"
        r"\end{tabularx}"
    )
    result = _inject_table_label(source)
    assert r"\label{tab:comparison}" in result

    # Label must appear before \begin{tabularx}
    label_pos = result.index(r"\label{tab:comparison}")
    tabularx_pos = result.index(r"\begin{tabularx}")
    assert label_pos < tabularx_pos


def test_inject_table_label_idempotent():
    """_inject_table_label must not double-inject if label already exists."""
    from core.synthesis import _inject_table_label

    source = (
        r"\section{学术对比矩阵}"
        r"\label{tab:comparison}"
        r"\begin{tabularx}{\textwidth}{l c c c X}"
        r"\end{tabularx}"
    )
    result = _inject_table_label(source)
    assert result.count(r"\label{tab:comparison}") == 1


# ---- Bibliography citation key correctness ----


def test_standard_bibliography_has_correct_keys():
    """Bibliographic keys must match the required specification exactly."""
    from core.synthesis import _STANDARD_BIBLIOGRAPHY

    # [1] bergmann2022: Bergmann P, et al. (CVPR 2022) - 逻辑异常
    assert r"\bibitem{bergmann2022}" in _STANDARD_BIBLIOGRAPHY
    assert "CVPR" in _STANDARD_BIBLIOGRAPHY
    assert "2022" in _STANDARD_BIBLIOGRAPHY

    # [2] costanzino2023: Costanzino A, et al. (VISAPP 2023) - 跨模态特征映射
    assert r"\bibitem{costanzino2023}" in _STANDARD_BIBLIOGRAPHY
    assert "VISAPP" in _STANDARD_BIBLIOGRAPHY
    assert "2023" in _STANDARD_BIBLIOGRAPHY

    # [3] soudani2026: YOLOv8 (NOT YOLOv11!)
    assert r"\bibitem{soudani2026}" in _STANDARD_BIBLIOGRAPHY
    assert "YOLOv8" in _STANDARD_BIBLIOGRAPHY
    assert "YOLOv11" not in _STANDARD_BIBLIOGRAPHY

    # [4] iodice2025: last entry
    assert r"\bibitem{iodice2025}" in _STANDARD_BIBLIOGRAPHY


def test_standard_bibliography_unity():
    """All four required papers must be present in the standard bibliography."""
    from core.synthesis import _STANDARD_BIBLIOGRAPHY

    keys = ["bergmann2022", "costanzino2023", "soudani2026", "iodice2025"]
    for key in keys:
        assert f"\\bibitem{{{key}}}" in _STANDARD_BIBLIOGRAPHY, f"Missing: {key}"
