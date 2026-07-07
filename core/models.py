from dataclasses import dataclass, field
from typing import Any


DEFAULT_SECTIONS = {
    "abstract": "missing",
    "introduction": "missing",
    "conclusion": "missing",
    "references": "missing",
}


@dataclass(frozen=True)
class PageSlice:
    page_number: int
    text: str


@dataclass
class ParsedPaper:
    file_name: str
    pages: list[PageSlice]
    title: str = "missing"
    sections: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SECTIONS))
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    def page_text_by_number(self) -> dict[int, str]:
        return {page.page_number: page.text for page in self.pages}


@dataclass(frozen=True)
class AcademicMatrixRow:
    title: str
    authors: str
    year: str
    venue: str
    research_problem: str
    method: str
    innovation: str
    limitation: str
    evidence_page: int
    evidence_quote: str
    confidence: float
    trigger_reason: str
    domain_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceValidationResult:
    accepted: bool
    message: str
    normalized_quote: str


@dataclass(frozen=True)
class GeneratedArtifacts:
    markdown_preview: str
    survey_tex: str
    matrix_table_tex: str
    references_bib: str