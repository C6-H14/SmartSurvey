from core.synthesis import build_synthesis_prompt, render_survey_tex_with_llm, validate_latex_syntax, SECTION_TEMPLATES


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
    assert "\\section{Abstract and Introduction}" in prompt
    assert "\\section{Technical Taxonomy}" in prompt
    assert "\\section{Systematic Review and Deep Critique}" in prompt
    assert "\\section{Academic Comparison Matrix}" in prompt
    assert "\\section{Research Gaps and Future Work}" in prompt
    assert "\\section{Conclusion}" in prompt
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
            r"\section{Abstract and Introduction}This is a test review."
            r"\section{Technical Taxonomy}Categories here."
            r"\section{Systematic Review and Deep Critique}Critique with evidence."
            r"\section{Academic Comparison Matrix}\begin{description}"
            r"\item[\textbf{1. Paper A (2024)：}] \hfill \\"
            r"\textbf{技术方法：}vision \\"
            r"\textbf{关键优势：}fast \\"
            r"\textbf{核心局限：}lighting"
            r"\end{description}"
            r"\section{Research Gaps and Future Work}Future directions."
            r"\section{Conclusion}Summary."
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
    assert r"\section{Abstract and Introduction}" in result
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
                r"\section{Abstract and Introduction}Test abstract content.",
                r"\section{Technical Taxonomy}Test taxonomy.",
                r"\section{Systematic Review and Deep Critique}Test critique.",
                r"\section{Academic Comparison Matrix}Test matrix.",
                r"\section{Research Gaps and Future Work}Test gaps.",
                r"\section{Conclusion}Test conclusion.",
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
    assert r"\section{Abstract and Introduction}" in result
    assert r"\section{Conclusion}" in result
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
            return r"\section{Abstract and Introduction}Test content."

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
    assert r"\section{Abstract and Introduction}" in result
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
    assert len(heavy) == 2  # Chapter 1 and Chapter 5
    assert len(light) == 4
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
    """evidence_page= residuals must be stripped from final output."""
    from core.synthesis import _strip_evidence_page_leaks

    # evidence_page= leak patterns
    dirty = (
        r"\section{Test}Some text (evidence_page=2) more text "
        r"(evidence_page=5) and (evidence_page=42) end."
    )
    clean = _strip_evidence_page_leaks(dirty)
    assert "(evidence_page=" not in clean
    assert "Some text  more text  and  end." == clean or "Some text  more text  and  end." in clean


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

