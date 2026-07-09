from core.synthesis import build_synthesis_prompt, render_survey_tex_with_llm, validate_latex_syntax


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
    """Mock extractor that returns valid LaTeX source."""
    def __init__(self):
        self.call_count = 0

    def __call__(self, prompt: str) -> str:
        self.call_count += 1
        return (
            r"\documentclass{ctexart}\usepackage{booktabs}\begin{document}"
            r"\section{Abstract and Introduction}This is a test review."
            r"\section{Technical Taxonomy}Categories here."
            r"\section{Systematic Review and Deep Critique}Critique with evidence."
            r"\section{Academic Comparison Matrix}\begin{table}\begin{tabular}{lll}\toprule"
            r"Paper & Method & Limitation \\\midrule Paper A & vision & lighting \\\bottomrule"
            r"\end{tabular}\end{table}"
            r"\section{Research Gaps and Future Work}Future directions."
            r"\section{Conclusion}Summary."
            r"\end{document}"
        )


class InvalidLaTeXExtractor:
    """Mock extractor that returns LaTeX with syntax errors."""
    def __init__(self):
        self.call_count = 0

    def __call__(self, prompt: str) -> str:
        self.call_count += 1
        if self.call_count == 1:
            # First call: broken LaTeX
            return (
                r"\documentclass{ctexart}\begin{document}"
                r"\section{Test}Unclosed formula $x + y"
                r"\end{document}"
            )
        # Second call: fixed LaTeX
        return (
            r"\documentclass{ctexart}\begin{document}"
            r"\section{Test}Closed formula $x + y$"
            r"\end{document}"
        )


def test_render_survey_tex_with_llm_valid():
    """Valid LaTeX passes through without self-healing."""
    extractor = ValidLaTeXExtractor()
    result = render_survey_tex_with_llm(
        topic="test topic",
        rows=[],
        extraction_fn=extractor,
    )
    assert extractor.call_count == 1  # no retry needed
    assert r"\documentclass{ctexart}" in result
    assert r"\section{Abstract and Introduction}" in result


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
    assert "MUST" in prompt


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