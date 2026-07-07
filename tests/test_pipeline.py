from core.models import AcademicMatrixRow, PageSlice, ParsedPaper
from core.pipeline import filter_rows_by_evidence, generate_artifacts


def test_filter_rows_by_evidence_blocks_uncontained_quote():
    paper = ParsedPaper(
        file_name="paper.pdf",
        pages=[PageSlice(page_number=1, text="This page supports a real limitation.")],
    )
    rows = [
        AcademicMatrixRow(
            title="Paper A",
            authors="missing",
            year="2024",
            venue="missing",
            research_problem="missing",
            method="missing",
            innovation="missing",
            limitation="fake",
            evidence_page=1,
            evidence_quote="Not present.",
            confidence=0.5,
            trigger_reason="missing",
        )
    ]

    accepted, blocked = filter_rows_by_evidence(rows, [paper])

    assert accepted == []
    assert blocked == ["发现无事实根据的空气警告，已自动拦截"]


def test_generate_artifacts_returns_all_downloads():
    row = AcademicMatrixRow(
        title="Paper A",
        authors="Alice",
        year="2024",
        venue="ICRA",
        research_problem="problem",
        method="method",
        innovation="innovation",
        limitation="limitation",
        evidence_page=1,
        evidence_quote="Quote",
        confidence=0.8,
        trigger_reason="reason",
    )

    artifacts = generate_artifacts("topic", [row], [])

    assert "Paper A" in artifacts.markdown_preview
    assert "\\begin{table}" in artifacts.matrix_table_tex
    assert "\\documentclass{ctexart}" in artifacts.survey_tex
    assert "@article" in artifacts.references_bib
