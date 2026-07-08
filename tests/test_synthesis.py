from core.synthesis import build_synthesis_prompt, validate_latex_syntax


def test_build_synthesis_prompt_accepts_word_count_target():
    """Word count target must appear in the generated prompt."""
    from core.synthesis import build_synthesis_prompt
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    prompt = build_synthesis_prompt("topic", [row], word_count_target=2000)
    assert "2000" in prompt
    assert "chinese characters" in prompt.lower() or "字" in prompt


def test_tabularx_is_valid_latex_environment():
    """tabularx environment must not trigger false positive."""
    source = r"\begin{tabularx}{\textwidth}{XXXX} a & b \\ \end{tabularx}"
    errors = validate_latex_syntax(source)
    assert errors == []