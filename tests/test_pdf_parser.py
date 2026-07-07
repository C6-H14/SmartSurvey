from core.pdf_parser import extract_core_sections_from_text, parse_pdf_bytes


def test_extract_core_sections_marks_missing_when_headings_absent():
    sections = extract_core_sections_from_text("This paper has no standard headings.")

    assert sections["abstract"] == "missing"
    assert sections["introduction"] == "missing"
    assert sections["conclusion"] == "missing"
    assert sections["references"] == "missing"


def test_extract_core_sections_finds_standard_headings():
    text = (
        "Abstract\nWe study the problem.\n"
        "Introduction\nThe setting is important.\n"
        "Conclusion\nThe method has limits.\n"
        "References\n[1] Example"
    )

    sections = extract_core_sections_from_text(text)

    assert sections["abstract"] == "We study the problem."
    assert sections["introduction"] == "The setting is important."
    assert sections["conclusion"] == "The method has limits."
    assert sections["references"] == "[1] Example"


def test_parse_invalid_pdf_returns_error_without_raising():
    paper = parse_pdf_bytes(b"not a pdf", "bad.pdf")

    assert paper.file_name == "bad.pdf"
    assert paper.error is not None
    assert paper.pages == []
