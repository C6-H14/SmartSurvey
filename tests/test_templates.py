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
    output = render_matrix_table_tex(sample_rows())

    assert "\\toprule" in output
    assert "\\midrule" in output
    assert "\\bottomrule" in output
    assert "Paper A" in output


def test_render_survey_has_required_sections():
    output = render_survey_tex("industrial anomaly detection", sample_rows())

    assert "\\documentclass{ctexart}" in output
    assert "\\section{Abstract and Introduction}" in output
    assert "\\section{Conclusion}" in output


def test_render_markdown_preview_contains_evidence():
    output = render_markdown_preview("industrial anomaly detection", sample_rows(), blocked_warnings=["blocked"])

    assert "Paper A" in output
    assert "p.2" in output
    assert "blocked" in output


def test_render_bibtex_contains_page_metadata():
    output = render_bibtex(sample_rows())

    assert "@article{paper_a_2024" in output
    assert "evidencepages = {2}" in output
