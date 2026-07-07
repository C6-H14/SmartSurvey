import re

import fitz

from core.models import DEFAULT_SECTIONS, PageSlice, ParsedPaper


SECTION_ORDER = ["abstract", "introduction", "conclusion", "references"]
SECTION_PATTERNS = {
    "abstract": r"(?im)^\s*abstract\s*$",
    "introduction": r"(?im)^\s*(?:\d+\.?\s*)?introduction\s*$",
    "conclusion": r"(?im)^\s*(?:\d+\.?\s*)?conclusions?\s*$",
    "references": r"(?im)^\s*references\s*$",
}


def clean_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).replace("\r\n", "\n").strip()


def extract_core_sections_from_text(text: str) -> dict[str, str]:
    sections = dict(DEFAULT_SECTIONS)
    matches: list[tuple[str, int, int]] = []

    for name, pattern in SECTION_PATTERNS.items():
        match = re.search(pattern, text)
        if match:
            matches.append((name, match.start(), match.end()))

    matches.sort(key=lambda item: item[1])
    for index, (name, _start, content_start) in enumerate(matches):
        next_start = matches[index + 1][1] if index + 1 < len(matches) else len(text)
        content = clean_text(text[content_start:next_start])
        sections[name] = content if content else "missing"

    return sections


def parse_pdf_bytes(pdf_bytes: bytes, file_name: str) -> ParsedPaper:
    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = [
            PageSlice(page_number=page_index + 1, text=clean_text(page.get_text("text")))
            for page_index, page in enumerate(document)
        ]
        full_text = "\n".join(page.text for page in pages)
        return ParsedPaper(
            file_name=file_name,
            pages=pages,
            sections=extract_core_sections_from_text(full_text),
        )
    except Exception as exc:
        return ParsedPaper(
            file_name=file_name,
            pages=[],
            warnings=["PDF parsing failed; batch processing should continue."],
            error=str(exc),
        )
