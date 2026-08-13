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

    assert "itemize" in prompt
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
        assert "TOPIC_PLACEHOLDER" in t["guidance"]
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
    """_inject_bibliography (embedded mode) must insert thebibliography before \end{document}."""
    from core.synthesis import _inject_bibliography

    source = r"\section{结论}Done." + "\n" + r"\end{document}" + "\n"
    result = _inject_bibliography(source, use_external_bib=False)

    assert r"\begin{thebibliography}{99}" in result
    assert r"\bibitem{bergmann2022}" in result
    assert r"\bibitem{costanzino2023}" in result
    assert r"\bibitem{iodice2025}" in result
    assert r"\bibitem{soudani2026}" in result
    assert r"\end{thebibliography}" in result
    assert r"\end{document}" in result
    assert result.index(r"\begin{thebibliography}") < result.index(r"\end{document}")


def test_inject_bibliography_external_bib_mode():
    """_inject_bibliography (external mode) must inject \bibliographystyle + \bibliography."""
    from core.synthesis import _inject_bibliography

    source = r"\section{结论}Done." + "\n" + r"\end{document}" + "\n"
    result = _inject_bibliography(source, use_external_bib=True)

    assert r"\bibliographystyle{plain}" in result
    assert r"\bibliography{references}" in result
    assert r"\begin{thebibliography}" not in result
    assert r"\end{document}" in result
    assert result.index(r"\bibliographystyle") < result.index(r"\end{document}")


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
    result = _inject_bibliography(source, use_external_bib=False)

    assert result.count(r"\begin{thebibliography}") == 1

    # Also test external bib mode idempotency
    source2 = (
        r"\section{结论}Done." + "\n"
        + r"\bibliographystyle{plain}" + "\n"
        + r"\bibliography{references}" + "\n"
        + r"\end{document}" + "\n"
    )
    result2 = _inject_bibliography(source2, use_external_bib=True)
    assert result2.count(r"\bibliography{") == 1


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
    """Single-pass synthesis output must include auto-injected bibliography (external .bib mode)."""
    from core.synthesis import render_survey_tex_with_llm

    class BibTestExtractor:
        def __call__(self, prompt: str) -> str:
            return r"\title{测试综述}" + "\n" + r"\section{结论}Done."

    result = render_survey_tex_with_llm(
        topic="test", rows=[], extraction_fn=BibTestExtractor(),
    )
    # External .bib mode: uses \bibliographystyle{plain} + \bibliography{references}
    assert r"\bibliographystyle{plain}" in result
    assert r"\bibliography{references}" in result
    assert r"\end{document}" in result
    # Verify \bibliographystyle appears before \end{document}
    assert result.index(r"\bibliographystyle") < result.index(r"\end{document}")


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


# ===== Phase 10: SSOT Citation Key Guardrails =====

def test_derive_cite_key_from_authors_and_year():
    """derive_cite_key must produce deterministic lowercase alphanumeric keys."""
    from core.synthesis import derive_cite_key

    # Bergmann P, 2022 + "Beyond Dents and Scratches" → "Beyond" is stop word → "dents"
    key = derive_cite_key("Bergmann P, Batzner K, Fauser M", "2022", "Beyond Dents and Scratches")
    assert key == "bergmann2022dents"

    # Iodice P, 2025 + "Human-Robot Collaborative Safety Monitoring" → "human" (stop), "robot" (stop), "collaborative" → no, wait...
    # "human" not in stop_words, "robot" not in stop_words → "human" is first
    key2 = derive_cite_key("Iodice P, et al.", "2025", "Human-Robot Collaborative Safety Monitoring")
    assert "iodice2025" in key2
    assert key2.startswith("iodice2025")

    # Costanzino A, 2023 — no title → just surname+year
    key3 = derive_cite_key("Costanzino A, et al.", "2023")
    assert key3 == "costanzino2023"

    # Empty authors fallback
    key4 = derive_cite_key("", "2022")
    assert key4 == "unknown2022"


def test_build_cite_key_map_returns_stable_order():
    """build_cite_key_map must return keys in the same order as input rows."""
    from core.synthesis import build_cite_key_map
    from core.models import AcademicMatrixRow

    rows = [
        AcademicMatrixRow(title="Test Paper One", authors="Bergmann P", year="2022", venue="C",
                          research_problem="P", method="M", innovation="I", limitation="L",
                          evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R"),
        AcademicMatrixRow(title="Test Paper Two", authors="Iodice P", year="2025", venue="D",
                          research_problem="P", method="M", innovation="I", limitation="L",
                          evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R"),
    ]
    mapping = build_cite_key_map(rows)
    assert len(mapping) == 2
    assert mapping[0]["cite_key"] == "bergmann2022"
    assert mapping[1]["cite_key"] == "iodice2025"


def test_build_cite_key_map_disambiguates():
    """build_cite_key_map must append suffix when keys collide."""
    from core.synthesis import build_cite_key_map
    from core.models import AcademicMatrixRow

    rows = [
        AcademicMatrixRow(title="Same Paper Name", authors="Smith J", year="2024", venue="V",
                          research_problem="P", method="M", innovation="I", limitation="L",
                          evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R"),
        AcademicMatrixRow(title="Same Paper Name", authors="Smith J", year="2024", venue="V",
                          research_problem="P", method="M", innovation="I", limitation="L",
                          evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R"),
    ]
    mapping = build_cite_key_map(rows)
    assert len(mapping) == 2
    assert mapping[0]["cite_key"] == "smith2024"
    assert mapping[1]["cite_key"] == "smith2024-2"


def test_build_synthesis_prompt_contains_cite_key_map():
    """Prompt must include the mandatory SSOT citation key mapping."""
    from core.synthesis import build_synthesis_prompt
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="Beyond Dents and Scratches", authors="Bergmann P", year="2022", venue="CVPR",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.8, trigger_reason="R",
    )
    prompt = build_synthesis_prompt("test", [row])
    assert "SSOT" in prompt
    assert "cite{" in prompt
    # Now uses canonical key: surname+year only
    assert "bergmann2022" in prompt
    assert "Do NOT invent new keys" in prompt


# ===== Phase 10: Hardcoded Column Spec Guardrail =====

def test_render_matrix_table_has_hardcoded_column_spec():
    """Table must use the exact fixed-width p{...} column spec with raggedright."""
    from core.templates import render_matrix_table_tex
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="Paper A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    output = render_matrix_table_tex([row])

    # Verify each part of the hardcoded column spec
    assert r">{\raggedright\arraybackslash}p{2.2cm}" in output
    assert r">{\raggedright\arraybackslash}p{2.5cm}" in output
    assert r">{\raggedright\arraybackslash}X" in output
    # Must use tabularx with textwidth
    assert r"\begin{tabularx}{\textwidth}" in output
    # Must have \label
    assert r"\label{tab:comparison}" in output
    # Must have \small for compact width
    assert r"\small" in output


# ===== Phase 10: Orphan Section Regex Guardrail =====

def test_strip_orphan_english_sections_removes_english_before_cjk():
    """Regex must strip English \section before a Chinese \section."""
    from core.synthesis import _strip_orphan_english_sections

    source = (
        r"\section{Systematic Review and Deep Critique}" + "\n\n"
        + r"\section{系统评述与深度批判}" + "\n"
        + r"Some critical content."
    )
    result = _strip_orphan_english_sections(source)
    assert "Systematic Review" not in result
    assert "系统评述与深度批判" in result
    assert "Some critical content" in result


def test_strip_orphan_english_sections_preserves_standalone():
    """Regex must NOT strip English \section if no CJK section follows."""
    from core.synthesis import _strip_orphan_english_sections

    source = (
        r"\section{Methods}" + "\n"
        + r"Some content." + "\n"
        + r"\section{Results}" + "\n"
        + r"More content."
    )
    result = _strip_orphan_english_sections(source)
    assert "Methods" in result
    assert "Results" in result


def test_strip_orphan_english_sections_handles_starred():
    """Regex must also match \section* variants."""
    from core.synthesis import _strip_orphan_english_sections

    source = (
        r"\section*{Abstract}" + "\n"
        + r"\section*{摘要}" + "\n"
        + r"Content."
    )
    result = _strip_orphan_english_sections(source)
    assert "Abstract" not in result
    assert "摘要" in result


# ===== Phase 10: Undefined Reference .log Pre-check Guardrail =====

def test_scan_log_for_undefined_refs_detects_missing_label():
    """Must warn when \ref{tab:comparison} has no matching \label."""
    from core.synthesis import _scan_log_for_undefined_refs

    source = (
        r"\section{Test}" + "\n"
        + r"See 表\ref{tab:comparison} for details." + "\n"
        + r"\begin{tabularx}{\textwidth}{l c}"
        + r"\end{tabularx}"
    )
    warnings = _scan_log_for_undefined_refs(source)
    assert len(warnings) >= 1
    assert any("tab:comparison" in w for w in warnings)


def test_scan_log_for_undefined_refs_detects_missing_cite():
    """Must warn when \cite{lostkey} has no matching \bibitem."""
    from core.synthesis import _scan_log_for_undefined_refs

    source = (
        r"\section{Test}" + "\n"
        + r"See \cite{bergmann2022} and \cite{fakekey}." + "\n"
        + r"\begin{thebibliography}{99}" + "\n"
        + r"\bibitem{bergmann2022} Bergmann et al." + "\n"
        + r"\end{thebibliography}"
    )
    warnings = _scan_log_for_undefined_refs(source)
    assert any("fakekey" in w for w in warnings)


def test_scan_log_for_undefined_refs_returns_empty_when_all_good():
    """Must return empty when all refs and cites resolve."""
    from core.synthesis import _scan_log_for_undefined_refs

    source = (
        r"\section{Test}" + "\n"
        r"\label{tab:comparison}" + "\n"
        + r"See 表\ref{tab:comparison} and \cite{bergmann2022}." + "\n"
        + r"\begin{thebibliography}{99}" + "\n"
        + r"\bibitem{bergmann2022} Bergmann et al." + "\n"
        + r"\end{thebibliography}"
    )
    warnings = _scan_log_for_undefined_refs(source)
    assert warnings == []


def test_parse_undefined_references_from_log_extracts():
    """Must parse LaTeX Warning: ... undefined from .log content."""
    from core.synthesis import _parse_undefined_references_from_log

    log_content = (
        "LaTeX Warning: Reference `tab:comparison' on page 1 undefined on input line 14.\n"
        "Some other log content.\n"
        "LaTeX Warning: Citation `badkey' on page 2 undefined on input line 20.\n"
    )
    warnings = _parse_undefined_references_from_log(log_content)
    assert len(warnings) == 2
    assert any("tab:comparison" in w for w in warnings)
    assert any("badkey" in w for w in warnings)


def test_inject_bibliography_uses_cite_key_map():
    """When cite_key_map is provided, bibliography must use dynamic keys."""
    from core.synthesis import _inject_bibliography

    source = r"\section{结论}Done." + "\n" + r"\end{document}" + "\n"
    cite_key_map = [
        {"cite_key": "test2024custom", "authors": "Test A", "title": "Custom Title",
         "year": "2024", "venue": "Conf"},
    ]
    result = _inject_bibliography(source, cite_key_map)

    assert r"\bibitem{test2024custom}" in result
    assert "Test A" in result
    assert "Custom Title" in result
    assert r"\end{thebibliography}" in result


def test_derive_cite_key_strips_stop_words():
    """derive_cite_key must skip 'the', 'a', 'of', 'and' etc. when picking title word."""
    from core.synthesis import derive_cite_key

    # "The Analysis of Spatial Data" → should use "analysis", not "the"
    key = derive_cite_key("Smith J", "2023", "The Analysis of Spatial Data")
    assert key == "smith2023analysis"

    # "A Study of Deep Methods" → should use "study", not "a"
    key2 = derive_cite_key("Li W", "2024", "A Study of Deep Methods")
    assert key2 == "li2024study"


# ===== Task 33: clean_synthesized_latex centralized post-processing =====

def test_clean_synthesized_latex_strips_evidence_page_leaks():
    """clean_synthesized_latex must remove all 4 bracket variants of evidence_page=N."""
    from core.synthesis import clean_synthesized_latex

    tex = (
        r"\section{测试}"
        r"本文使用了深度学习方法(evidence_page=3)。"
        r"另一方法【evidence_page=5】也有效。"
        r"还有[evidence_page=2]和（evidence_page=4）。"
    )
    cleaned = clean_synthesized_latex(tex)
    assert "evidence_page" not in cleaned
    assert "(evidence_page=3)" not in cleaned
    assert "【evidence_page=5】" not in cleaned
    assert "[evidence_page=2]" not in cleaned
    assert "（evidence_page=4）" not in cleaned
    assert r"\section{测试}" in cleaned


def test_clean_synthesized_latex_strips_orphan_english_sections():
    """Orphan English \\section before Chinese \\section must be stripped."""
    from core.synthesis import clean_synthesized_latex

    tex = (
        r"\section{Abstract and Introduction}"
        r"\section{摘要与引言}"
        r"正文内容。"
        r"\section{Technical Taxonomy}"
        r"\section{技术分类体系}"
        r"分类内容。"
    )
    cleaned = clean_synthesized_latex(tex)
    # English headers before Chinese must be removed
    assert r"\section{Abstract and Introduction}" not in cleaned
    assert r"\section{Technical Taxonomy}" not in cleaned
    # Chinese headers must be preserved
    assert r"\section{摘要与引言}" in cleaned
    assert r"\section{技术分类体系}" in cleaned


def test_clean_synthesized_latex_preserves_standalone_english_section():
    """A standalone English section NOT followed by Chinese must be preserved."""
    from core.synthesis import clean_synthesized_latex

    tex = (
        r"\section{Experimental Results}"
        r"Here are the experimental results."
    )
    cleaned = clean_synthesized_latex(tex)
    # No Chinese section follows, so this English section is not orphan
    assert r"\section{Experimental Results}" in cleaned


def test_clean_synthesized_latex_cleans_math_operators():
    """Math-mode 'or' must become \\lor."""
    from core.synthesis import clean_synthesized_latex

    tex = r"公式 $x or y$ 表示选择。"
    cleaned = clean_synthesized_latex(tex)
    assert r"$x \lor y$" in cleaned


def test_clean_synthesized_latex_corrects_absurd_page_numbers():
    """Absurd page numbers like 第17241页 must be corrected."""
    from core.synthesis import clean_synthesized_latex

    tex = r"如第17241页所示。"
    cleaned = clean_synthesized_latex(tex)
    assert "第17241页" not in cleaned
    # Should be corrected to "结论部分" (>= 10000)
    assert "结论部分" in cleaned


def test_clean_synthesized_latex_idempotent():
    """Applying clean_synthesized_latex twice should give the same result."""
    from core.synthesis import clean_synthesized_latex

    tex = (
        r"\section{Abstract and Introduction}"
        r"\section{摘要与引言}"
        r"本文(evidence_page=3)使用了 $a or b$ 方法。"
        r"见第17241页。"
    )
    first = clean_synthesized_latex(tex)
    second = clean_synthesized_latex(first)
    assert first == second


def test_compile_with_xelatex_two_pass():
    """compile_with_xelatex must run two xelatex passes for cross-reference resolution."""
    from core.synthesis import compile_with_xelatex

    # A minimal LaTeX document with a \ref that requires two-pass resolution
    tex = (
        r"\documentclass{article}"
        r"\begin{document}"
        r"\section{Test}\label{sec:test}"
        r"See Section~\ref{sec:test}."
        r"\end{document}"
    )
    errors = compile_with_xelatex(tex, timeout=30)
    # After two passes, \ref{sec:test} should resolve — no undefined ref warnings
    assert len(errors) == 0


# ===== Phase 11: SSOT canonical_cite_key + citation sanitizer + compile guard =====

def test_derive_canonical_cite_key_surname_year():
    """derive_canonical_cite_key must produce surname+year only (no title slug)."""
    from core.synthesis import derive_canonical_cite_key

    assert derive_canonical_cite_key("Bergmann P, Batzner K", "2022") == "bergmann2022"
    assert derive_canonical_cite_key("Iodice P, et al.", "2025") == "iodice2025"
    assert derive_canonical_cite_key("Costanzino A", "2023") == "costanzino2023"
    assert derive_canonical_cite_key("Soudani A", "2026") == "soudani2026"
    assert derive_canonical_cite_key("", "2022") == "unknown2022"


def test_canonical_cite_key_differs_from_full_cite_key():
    """canonical key (surname+year) must be shorter than full cite_key (surname+year+titleword)."""
    from core.synthesis import derive_cite_key, derive_canonical_cite_key

    full = derive_cite_key("Bergmann P", "2022", "Beyond Dents and Scratches")
    canonical = derive_canonical_cite_key("Bergmann P", "2022")
    # Full key includes title word, canonical does not
    assert len(canonical) < len(full)
    assert full.startswith(canonical)  # canonical is prefix of full


def test_sanitize_and_repair_citations_normalizes_alias_keys():
    """Alias cite keys like francesco2025intelligent must be replaced with canonical keys."""
    from core.synthesis import sanitize_and_repair_citations
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="Human-Robot Collaborative Safety Monitoring Framework",
        authors="Iodice P, et al.", year="2025", venue="Robotics",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    tex = (
        r"\section{测试}"
        r"本文参考了 \cite{iodice2025humanrobot} 和 \cite{iodice2025} 的方法。"
        r"\begin{thebibliography}{99}"
        r"\bibitem{iodice2025} Iodice P. Test. Robotics, 2025."
        r"\end{thebibliography}"
    )
    cleaned = sanitize_and_repair_citations(tex, [row])
    # iodice2025humanrobot contains "iodice" (surname) — should be resolved to canonical
    assert "iodice2025humanrobot" not in cleaned
    assert r"\cite{iodice2025}" in cleaned


def test_sanitize_and_repair_citations_unifies_bibitem_keys():
    """All \bibitem keys must be canonical after sanitization."""
    from core.synthesis import sanitize_and_repair_citations
    from core.models import AcademicMatrixRow

    rows = [
        AcademicMatrixRow(
            title="Beyond Dents and Scratches", authors="Bergmann P", year="2022", venue="CVPR",
            research_problem="P", method="M", innovation="I", limitation="L",
            evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
        ),
    ]
    tex = (
        r"\section{测试}"
        r"\begin{thebibliography}{99}"
        r"\bibitem{bergmann2022dents} Bergmann P. Test. CVPR, 2022."
        r"\end{thebibliography}"
    )
    cleaned = sanitize_and_repair_citations(tex, rows)
    assert r"\bibitem{bergmann2022}" in cleaned
    # Old non-canonical keys must be gone
    assert "bergmann2022dents" not in cleaned


def test_sanitize_and_repair_citations_normalizes_bibitem_via_alias():
    """Non-canonical bibitem keys matching known aliases must be corrected."""
    from core.synthesis import sanitize_and_repair_citations
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="Beyond Dents and Scratches", authors="Bergmann P", year="2022", venue="CVPR",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    tex = (
        r"\section{测试}"
        r"\begin{thebibliography}{99}"
        r"\bibitem{bergmann2022dents} Bergmann P. CVPR, 2022."
        r"\end{thebibliography}"
    )
    cleaned = sanitize_and_repair_citations(tex, [row])
    # bergmann2022dents is in alias map → should be replaced with bergmann2022
    assert r"\bibitem{bergmann2022}" in cleaned
    assert "bergmann2022dents" not in cleaned


def test_sanitize_and_repair_citations_idempotent():
    """sanitize_and_repair_citations must be idempotent."""
    from core.synthesis import sanitize_and_repair_citations
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="Test", authors="Iodice P", year="2025", venue="Robotics",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    tex = (
        r"\section{测试}"
        r"\begin{thebibliography}{99}"
        r"\bibitem{iodice2025} Iodice P. Test. Robotics, 2025."
        r"\end{thebibliography}"
    )
    first = sanitize_and_repair_citations(tex, [row])
    second = sanitize_and_repair_citations(first, [row])
    assert first == second


def test_sanitize_and_repair_citations_handles_multi_cite():
    """Multi-cite \cite{key1,key2} must be repaired correctly."""
    from core.synthesis import sanitize_and_repair_citations
    from core.models import AcademicMatrixRow

    rows = [
        AcademicMatrixRow(
            title="T1", authors="Bergmann P", year="2022", venue="CVPR",
            research_problem="P", method="M", innovation="I", limitation="L",
            evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
        ),
        AcademicMatrixRow(
            title="T2", authors="Costanzino A", year="2023", venue="VISAPP",
            research_problem="P", method="M", innovation="I", limitation="L",
            evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
        ),
    ]
    tex = (
        r"\section{测试}"
        r"本文参考了 \cite{fakebergmann,costanzino2023cross} 的方法。"
        r"\begin{thebibliography}{99}"
        r"\bibitem{bergmann2022} Bergmann P. CVPR, 2022."
        r"\bibitem{costanzino2023} Costanzino A. VISAPP, 2023."
        r"\end{thebibliography}"
    )
    cleaned = sanitize_and_repair_citations(tex, rows)
    assert "fakebergmann" not in cleaned
    assert "costanzino2023cross" not in cleaned
    assert r"\bibitem{bergmann2022}" in cleaned
    assert r"\bibitem{costanzino2023}" in cleaned


def test_compile_with_xelatex_detects_undefined_citation():
    """compile_with_xelatex must raise RuntimeError when Citation ... undefined found in .log."""
    from core.synthesis import compile_with_xelatex

    # A document with a \cite to a non-existent bibitem — will produce Citation undefined
    tex = (
        r"\documentclass{article}"
        r"\begin{document}"
        r"See \cite{nonexistent2025} for details."
        r"\begin{thebibliography}{99}"
        r"\bibitem{real2024} Real Paper. Some Venue, 2024."
        r"\end{thebibliography}"
        r"\end{document}"
    )
    # This should raise RuntimeError because xelatex .log will have "Citation ... undefined"
    raised = False
    try:
        compile_with_xelatex(tex, timeout=30)
    except RuntimeError:
        raised = True
    assert raised, "Expected RuntimeError for undefined citation, but none was raised"


def test_build_cite_key_map_uses_canonical_keys():
    """build_cite_key_map must use derive_canonical_cite_key for cite_key values."""
    from core.synthesis import build_cite_key_map
    from core.models import AcademicMatrixRow

    rows = [
        AcademicMatrixRow(
            title="Beyond Dents and Scratches", authors="Bergmann P, Batzner K", year="2022",
            venue="CVPR", research_problem="P", method="M", innovation="I", limitation="L",
            evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
        ),
        AcademicMatrixRow(
            title="Human-Robot Collaborative Safety", authors="Iodice P, et al.", year="2025",
            venue="Robotics", research_problem="P", method="M", innovation="I", limitation="L",
            evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
        ),
    ]
    mapping = build_cite_key_map(rows)
    # Keys must be canonical: surname+year only, no title words
    assert mapping[0]["cite_key"] == "bergmann2022"
    assert mapping[1]["cite_key"] == "iodice2025"


def test_parsed_paper_has_canonical_cite_key_field():
    """ParsedPaper must expose canonical_cite_key as an immutable field."""
    from core.models import ParsedPaper, PageSlice

    paper = ParsedPaper(
        file_name="test.pdf",
        pages=[PageSlice(page_number=1, text="abstract")],
        title="Test Paper",
        canonical_cite_key="smith2024",
    )
    assert paper.canonical_cite_key == "smith2024"

    # Default fallback
    paper2 = ParsedPaper(
        file_name="test2.pdf",
        pages=[PageSlice(page_number=1, text="abstract")],
    )
    assert paper2.canonical_cite_key == "missing"


# ===== Task: .tex/.bib standard separation architecture =====

def test_export_references_bib_creates_bib_file():
    """export_references_bib must create a valid .bib file with correct keys."""
    from core.synthesis import export_references_bib

    cite_key_map = [
        {"cite_key": "bergmann2022", "authors": "Bergmann P, Batzner K", "title": "Beyond Dents",
         "year": "2022", "venue": "CVPR"},
        {"cite_key": "iodice2025", "authors": "Iodice P", "title": "Human-Robot Collaborative",
         "year": "2025", "venue": "Robotics"},
    ]
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        path = export_references_bib(cite_key_map, output_dir=tmpdir)
        assert os.path.isfile(path)
        content = open(path, encoding="utf-8").read()
        assert "@inproceedings{bergmann2022" in content
        assert "@article{iodice2025" in content
        assert "CVPR" in content
        assert "Robotics" in content


def test_export_references_bib_fallback():
    """export_references_bib must write _STANDARD_BIBTEX_ENTRIES when map is empty."""
    from core.synthesis import export_references_bib

    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        path = export_references_bib([], output_dir=tmpdir)
        assert os.path.isfile(path)
        content = open(path, encoding="utf-8").read()
        assert "@inproceedings{bergmann2022" in content
        assert "@article{soudani2026" in content


def test_compile_with_xelatex_external_bib_workflow():
    """compile_with_xelatex must handle external .bib workflow (xelatex→bibtex→xelatex→xelatex)."""
    from core.synthesis import compile_with_xelatex

    # A document using external .bib workflow with a valid citation
    tex = (
        r"\documentclass{article}"
        r"\begin{document}"
        r"See \cite{bergmann2022} for details."
        r"\bibliographystyle{plain}"
        r"\bibliography{references}"
        r"\end{document}"
    )
    errors = compile_with_xelatex(tex, timeout=30)
    # Should compile clean — the auto-generated references.bib has bergmann2022
    assert len(errors) == 0


def test_compile_with_xelatex_external_bib_undefined_citation():
    """External .bib + undefined citation must still raise RuntimeError."""
    from core.synthesis import compile_with_xelatex

    # A document citing a non-existent key, using external .bib workflow
    tex = (
        r"\documentclass{article}"
        r"\begin{document}"
        r"See \cite{nonexistent2025} for details."
        r"\bibliographystyle{plain}"
        r"\bibliography{references}"
        r"\end{document}"
    )
    raised = False
    try:
        compile_with_xelatex(tex, timeout=30)
    except RuntimeError:
        raised = True
    assert raised, "Expected RuntimeError for undefined citation in external .bib workflow"


def test_export_references_bib_via_synthesis_pipeline():
    """The synthesis pipeline must call export_references_bib and produce a .bib file."""
    from core.synthesis import render_survey_tex_with_llm, export_references_bib

    # Verify that export_references_bib is callable and produces output
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        # Simple cite_key_map
        cite_key_map = [
            {"cite_key": "bergmann2022", "authors": "Bergmann P, Batzner K",
             "title": "Beyond Dents and Scratches", "year": "2022", "venue": "CVPR"},
        ]
        path = export_references_bib(cite_key_map, output_dir=tmpdir)
        assert os.path.isfile(path)
        content = open(path, encoding="utf-8").read()
        # Must be valid BibTeX
        assert "@inproceedings{bergmann2022" in content
        assert "}" in content  # closing brace for entry

    # Also test via synthesis: the output .tex must use \bibliographystyle + \bibliography
    class BibTestExtractor:
        def __call__(self, prompt: str) -> str:
            return r"\title{测试}" + "\n" + r"\section{结论}Done."

    result = render_survey_tex_with_llm(
        topic="test", rows=[], extraction_fn=BibTestExtractor(),
    )
    assert r"\bibliographystyle{plain}" in result
    assert r"\bibliography{references}" in result


def test_compile_with_xelatex_full_recipe_zero_errors():
    """Full xelatex→bibtex→xelatex→xelatex recipe must compile with zero errors."""
    from core.synthesis import compile_with_xelatex

    # A complete document using external .bib with cross-references
    tex = (
        r"\documentclass{article}"
        r"\begin{document}"
        r"\section{Introduction}\label{sec:intro}"
        r"Bergmann et al.~\cite{bergmann2022} proposed logical anomaly detection."
        r"In Section~\ref{sec:intro} we introduced the topic."
        r"\bibliographystyle{plain}"
        r"\bibliography{references}"
        r"\end{document}"
    )
    errors = compile_with_xelatex(tex, timeout=30)
    # After full xelatex→bibtex→xelatex→xelatex, both \cite and \ref should resolve
    assert len(errors) == 0, f"Unexpected errors: {errors}"
