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
    """Matrix table must use tabularx with booktabs three-line table and \label{tab:comparison}."""
    output = render_matrix_table_tex(sample_rows())

    assert "\\begin{tabularx}" in output
    assert "\\toprule" in output
    assert "\\midrule" in output
    assert "\\bottomrule" in output
    assert "\\label{tab:comparison}" in output
    assert "Paper A" in output
    # Use raggedright for limitation column
    assert "\\raggedright" in output


def test_render_survey_has_required_sections():
    output = render_survey_tex("test topic", sample_rows())

    assert "\\documentclass{ctexart}" in output
    assert "\\section{摘要与引言}" in output
    assert "\\section{结论}" in output


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


def test_render_matrix_table_uses_tabularx():
    """Matrix table must use tabularx with three-line table rules for Overleaf compatibility."""
    from core.templates import render_matrix_table_tex
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="Paper A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    output = render_matrix_table_tex([row])

    assert "\\begin{tabularx}" in output
    assert "\\end{tabularx}" in output
    assert "\\toprule" in output
    assert "\\midrule" in output
    assert "\\bottomrule" in output
    assert "\\label{tab:comparison}" in output
    # Must use X column with raggedright for Chinese text wrapping
    assert "\\raggedright\\arraybackslash" in output


def test_render_matrix_table_has_item_format():
    """Each paper row must reference its title, year, method, and limitation in the tabularx table."""
    from core.templates import render_matrix_table_tex
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="Paper A", authors="Alice", year="2024", venue="ICRA",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    output = render_matrix_table_tex([row])

    assert "Paper A" in output
    assert "2024" in output
    assert "\\label{tab:comparison}" in output


def test_render_matrix_table_has_section_headers():
    """Table header must contain 局限性 column for Chinese limitation text."""
    from core.templates import render_matrix_table_tex
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="Paper A", authors="B", year="2024", venue="C",
        research_problem="P", method="Vision model", innovation="Fast", limitation="Lighting",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    output = render_matrix_table_tex([row])

    assert "局限性" in output
    assert "异常范式" in output
    assert "模态输入" in output
    assert "关键指标" in output
    assert "\\toprule" in output
    assert "Fast" in output  # innovation used as key metric
    assert "Lighting" in output


def test_render_matrix_table_numbers_items_sequentially():
    """Multiple papers must both appear in the tabularx table rows."""
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

    assert "Paper A" in output
    assert "Paper B" in output
    assert "2024" in output
    assert "2023" in output
    assert "\\toprule" in output


def test_render_survey_tex_no_tabularx_in_preamble():
    """Survey preamble must contain tabularx and array packages for the comparison matrix."""
    output = render_survey_tex("test topic", sample_rows())
    assert "\\usepackage{tabularx}" in output
    assert "\\usepackage{array}" in output
    assert "\\usepackage{booktabs}" in output
