from core.evidence import validate_evidence
from core.models import AcademicMatrixRow, GeneratedArtifacts, ParsedPaper
from core.templates import render_bibtex, render_markdown_preview, render_matrix_table_tex, render_survey_tex


def filter_rows_by_evidence(
    rows: list[AcademicMatrixRow],
    papers: list[ParsedPaper],
) -> tuple[list[AcademicMatrixRow], list[str]]:
    page_texts: dict[int, str] = {}
    for paper in papers:
        page_texts.update(paper.page_text_by_number())

    accepted: list[AcademicMatrixRow] = []
    blocked: list[str] = []
    for row in rows:
        result = validate_evidence(row.evidence_page, row.evidence_quote, page_texts)
        if result.accepted:
            accepted.append(row)
        else:
            blocked.append(result.message)
    return accepted, blocked


def generate_artifacts(
    topic: str,
    rows: list[AcademicMatrixRow],
    blocked_warnings: list[str],
) -> GeneratedArtifacts:
    return GeneratedArtifacts(
        markdown_preview=render_markdown_preview(topic, rows, blocked_warnings),
        survey_tex=render_survey_tex(topic, rows),
        matrix_table_tex=render_matrix_table_tex(rows),
        references_bib=render_bibtex(rows),
    )
