from core.models import AcademicMatrixRow
from core.templates import render_bibtex, render_markdown_preview, render_matrix_table_tex, render_survey_tex


def sample_rows():
    return [
        AcademicMatrixRow(
            title="Paper A",
            authors="Alice and Bob",
            year="2024",
            venue="ICRA",
            research_problem="Detect workspace anomalies",
            method="Vision model",
            innovation="Evidence-bound review",
            limitation="Lighting sensitivity",
            evidence_page=2,
            evidence_quote="The limitation is lighting sensitivity.",
            confidence=0.9,
            trigger_reason="The paper states the limitation.",
            domain_fields={"sensor": "camera"},
        )
    ]


def test_render_matrix_table_uses_booktabs():
    """Matrix table must use \begin{description} environment (replaces tabularx)."""
    output = render_matrix_table_tex(sample_rows())

    assert "\\begin{description}" in output
    assert "\\end{description}" in output
    assert "Paper A" in output
    # Must NOT contain old tabular or tabularx
    assert "\\begin{tabular}" not in output
    assert "\\begin{tabularx}" not in output


def test_render_survey_has_required_sections():
    output = render_survey_tex("test topic", sample_rows())

    assert "\\documentclass{ctexart}" in output
    assert "\\section{Abstract and Introduction}" in output
    assert "\\section{Conclusion}" in output


def test_render_markdown_preview_contains_evidence():
    output = render_markdown_preview("test topic", sample_rows(), blocked_warnings=["blocked"])

    assert "Paper A" in output
    assert "p.2" in output
    assert "blocked" in output


def test_render_bibtex_contains_page_metadata():
    output = render_bibtex(sample_rows())

    assert "@article{paper_a_2024" in output
    assert "evidencepages = {2}" in output


# ===== Phase 9: Description list (replaces tabularx) =====

def test_render_survey_has_abstract_intro_separator():
    """Section 1 must use \noindent\textbf{摘要：} and \noindent\textbf{引言：}."""
    output = render_survey_tex("test topic", sample_rows())
    assert r"\noindent\textbf{摘要：}" in output
    assert r"\noindent\textbf{引言：}" in output
    assert r"\par\bigskip" in output


def test_render_matrix_table_uses_description():
    """Matrix table must use \begin{description} environment."""
    from core.templates import render_matrix_table_tex
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="Paper A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    output = render_matrix_table_tex([row])

    assert "\\begin{description}" in output
    assert "\\end{description}" in output
    # Must NOT use tabularx or tabular
    assert "\\begin{tabularx}" not in output
    assert "\\begin{tabular}" not in output
    assert "\\toprule" not in output
    assert "\\midrule" not in output
    assert "\\bottomrule" not in output


def test_render_matrix_table_has_item_format():
    """Each paper must be a \item[\textbf{N. Title (Year)：}]."""
    from core.templates import render_matrix_table_tex
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="Paper A", authors="Alice", year="2024", venue="ICRA",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    output = render_matrix_table_tex([row])

    assert r"\item[\textbf{1. Paper A (2024)：}]" in output
    assert r"\hfill \\" in output


def test_render_matrix_table_has_section_headers():
    """Each description item must have 技术方法, 关键优势, 核心局限 headers."""
    from core.templates import render_matrix_table_tex
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="Paper A", authors="B", year="2024", venue="C",
        research_problem="P", method="Vision model", innovation="Fast", limitation="Lighting",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    output = render_matrix_table_tex([row])

    assert r"\textbf{技术方法：}" in output
    assert r"\textbf{关键优势：}" in output
    assert r"\textbf{核心局限：}" in output
    assert "Vision model" in output
    assert "Fast" in output
    assert "Lighting" in output


def test_render_matrix_table_numbers_items_sequentially():
    """Multiple papers must be numbered 1, 2, 3..."""
    from core.templates import render_matrix_table_tex
    from core.models import AcademicMatrixRow

    rows = [
        AcademicMatrixRow(
            title="Paper A", authors="B", year="2024", venue="C",
            research_problem="P", method="M", innovation="I", limitation="L",
            evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
        ),
        AcademicMatrixRow(
            title="Paper B", authors="C", year="2023", venue="D",
            research_problem="P", method="M", innovation="I", limitation="L",
            evidence_page=2, evidence_quote="Q", confidence=0.5, trigger_reason="R",
        ),
    ]
    output = render_matrix_table_tex(rows)

    assert r"\item[\textbf{1. Paper A (2024)：}]" in output
    assert r"\item[\textbf{2. Paper B (2023)：}]" in output


def test_render_survey_tex_no_tabularx_in_preamble():
    """Survey preamble must NOT contain booktabs or tabularx packages."""
    output = render_survey_tex("test topic", sample_rows())
    assert "\\usepackage{booktabs}" not in output
    assert "\\usepackage{tabularx}" not in output
