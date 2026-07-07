from core.models import AcademicMatrixRow, PageSlice, ParsedPaper


def test_parsed_paper_defaults_missing_sections():
    paper = ParsedPaper(file_name="paper.pdf", pages=[PageSlice(page_number=1, text="hello")])

    assert paper.sections["abstract"] == "missing"
    assert paper.sections["introduction"] == "missing"
    assert paper.sections["conclusion"] == "missing"
    assert paper.sections["references"] == "missing"


def test_academic_matrix_row_requires_evidence_fields():
    row = AcademicMatrixRow(
        title="A",
        authors="B",
        year="2024",
        venue="C",
        research_problem="problem",
        method="method",
        innovation="innovation",
        limitation="limitation",
        evidence_page=2,
        evidence_quote="The limitation is lighting sensitivity.",
        confidence=0.8,
        trigger_reason="The sentence explicitly names a limitation.",
        domain_fields={"sensor": "camera"},
    )

    assert row.evidence_page == 2
    assert row.domain_fields["sensor"] == "camera"