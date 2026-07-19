# SmartSurvey Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build SmartSurvey from the current prototype into a tested AI4SE non-harness application that parses academic PDFs, validates evidence-bound claims, previews a Chinese review, exports LaTeX/BibTeX files, and manages API keys safely.

**Architecture:** Use a small Python/Streamlit application with focused `core/` modules. Keep PDF parsing, evidence validation, schema construction, LLM access, manuscript rendering, credential storage, and UI orchestration separated so each part can be tested independently. Treat LLM calls as adapter boundaries; deterministic unit tests must cover core behavior without a real API key.

**Tech Stack:** Python, Streamlit, PyMuPDF, LangChain OpenAI-compatible chat adapter, pytest, keyring, Docker, GitLab CI.

---

## Scope And Constraints

This plan implements the first complete SmartSurvey vertical slice described in `docs/SPEC.md`.

Keep all Markdown documentation except `README.md` under `docs/`. This plan therefore lives at `docs/PLAN.md`, and future process documents such as `REFLECTION.md` drafts may also be kept under `docs/` until final packaging decisions are made.

Do not write real API keys to source, tests, logs, exported files, Docker images, or CI variables committed to the repository. Existing `.env` support may remain only as an explicitly documented development compatibility source after the keyring path is implemented; it must not be the primary credential model.

## File Structure

Create or modify these files:

- `requirements.txt`: add `pytest`, `keyring`, and any small test/runtime dependencies.
- `core/models.py`: dataclasses for parsed PDFs, page slices, academic matrix rows, validation results, generated artifacts, and errors.
- `core/pdf_parser.py`: PyMuPDF parsing, core section detection, page slice fallback, per-file error capture.
- `core/evidence.py`: quote normalization and containment validation.
- `core/schema.py`: general schema fields and topic-specific domain field generation.
- `core/credentials.py`: keyring-backed API key storage, update, clear, and status helpers.
- `core/agent.py`: LLM adapter that reads credentials through `core.credentials` and never logs keys.
- `core/extractor.py`: deterministic prompt building and JSON parsing boundary for academic matrix extraction.
- `core/templates.py`: Markdown, LaTeX table, manuscript, and BibTeX rendering.
- `core/pipeline.py`: batch orchestration from uploaded PDFs to artifacts.
- `main.py`: Streamlit UI for upload, topic input, credential status, preview, and downloads.
- `tests/`: pytest suite for every core module.
- `.gitignore`: keep secrets, uploaded PDFs, outputs, caches, and build artifacts out of Git.
- `Dockerfile`: container distribution without secrets or user PDFs.
- `.gitlab-ci.yml`: required `unit-test` job.
- `README.md`: project entry point with install, run, testing, Docker, credential, and safety instructions.
- `docs/Agent_log.md`: append task checkpoints during implementation.

## Task 1: Test Infrastructure And Dependency Baseline (Completed: Commit b069c9a)

**Files:**
- Modify: `requirements.txt`
- Create: `tests/test_smoke.py`
- Create: `tests/conftest.py`
- Modify: `.gitignore`

- [x] **Step 1: Write the failing smoke test**

Create `tests/test_smoke.py`:

```python
def test_pytest_is_configured():
    assert True
```

- [x] **Step 2: Add shared test fixtures**

Create `tests/conftest.py`:

```python
import pytest


@pytest.fixture
def sample_page_texts():
    return {
        1: "Abstract This paper studies spatial anomaly detection. Introduction Safety matters.",
        2: "The method uses a vision model. The limitation is lighting sensitivity.",
    }
```

- [x] **Step 3: Run the new smoke test**

Run: `python -m pytest tests/test_smoke.py -v`

Expected before dependency update if pytest is missing: command fails with `No module named pytest`.

- [x] **Step 4: Update dependencies**

Edit `requirements.txt` to contain:

```text
streamlit
langchain
langchain-openai
pymupdf
python-dotenv
pytest
keyring
```

- [x] **Step 5: Harden ignored files**

Edit `.gitignore` to contain:

```text
.venv/
.env
__pycache__/
.pytest_cache/
data/input_pdfs/
data/output_docs/
dist/
build/
*.pyc
*.log
```

- [x] **Step 6: Verify**

Run: `python -m pytest tests/test_smoke.py -v`

Expected: `1 passed`.

- [x] **Step 7: Commit**

```bash
git add requirements.txt .gitignore tests/test_smoke.py tests/conftest.py
git commit -m "test: add pytest baseline"
```

## Task 2: Core Data Models (Completed: Commit 5291fc1)

**Files:**
- Create: `core/models.py`
- Create: `tests/test_models.py`

- [x] **Step 1: Write failing model tests**

Create `tests/test_models.py`:

```python
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
```

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_models.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'core.models'`.

- [x] **Step 3: Implement models**

Create `core/models.py`:

```python
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
```

- [x] **Step 4: Verify**

Run: `python -m pytest tests/test_models.py -v`

Expected: `2 passed`.

- [x] **Step 5: Commit**

```bash
git add core/models.py tests/test_models.py
git commit -m "feat: add core data models"
```

## Task 3: PDF Parser With Core Sections And Page Slices

**Files:**
- Modify: `core/pdf_parser.py`
- Create: `tests/test_pdf_parser.py`

- [x] **Step 1: Write failing parser unit tests**

Create `tests/test_pdf_parser.py`:

```python
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
```

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_pdf_parser.py -v`

Expected: FAIL because parser functions are missing.

- [x] **Step 3: Implement parser**

Replace `core/pdf_parser.py` with:

```python
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
```

- [x] **Step 4: Verify**

Run: `python -m pytest tests/test_pdf_parser.py -v`

Expected: `3 passed`.

- [x] **Step 5: Commit**

```bash
git add core/pdf_parser.py tests/test_pdf_parser.py
git commit -m "feat: parse pdf pages and core sections"
```

## Task 4: Evidence Containment Validation

**Files:**
- Create: `core/evidence.py`
- Create: `tests/test_evidence.py`

- [x] **Step 1: Write failing containment tests**

Create `tests/test_evidence.py`:

```python
from core.evidence import AIR_WARNING_BLOCKED, normalize_for_containment, validate_evidence


def test_normalize_for_containment_collapses_whitespace_and_hyphen_breaks():
    text = "The method is light-\n ing sensitive."

    assert normalize_for_containment(text) == "the method is lighting sensitive."


def test_validate_evidence_accepts_quote_on_page(sample_page_texts):
    result = validate_evidence(
        evidence_page=2,
        evidence_quote="The limitation is lighting sensitivity.",
        page_text_by_number=sample_page_texts,
    )

    assert result.accepted is True


def test_validate_evidence_rejects_missing_quote(sample_page_texts):
    result = validate_evidence(
        evidence_page=2,
        evidence_quote="This sentence is not in the paper.",
        page_text_by_number=sample_page_texts,
    )

    assert result.accepted is False
    assert result.message == AIR_WARNING_BLOCKED
```

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_evidence.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [x] **Step 3: Implement evidence validation**

Create `core/evidence.py`:

```python
import re

from core.models import EvidenceValidationResult


AIR_WARNING_BLOCKED = "发现无事实根据的空气警告，已自动拦截"


def normalize_for_containment(text: str) -> str:
    text = text.replace("-\n", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def validate_evidence(
    evidence_page: int,
    evidence_quote: str,
    page_text_by_number: dict[int, str],
) -> EvidenceValidationResult:
    normalized_quote = normalize_for_containment(evidence_quote)
    normalized_page = normalize_for_containment(page_text_by_number.get(evidence_page, ""))
    accepted = bool(normalized_quote) and normalized_quote in normalized_page
    return EvidenceValidationResult(
        accepted=accepted,
        message="accepted" if accepted else AIR_WARNING_BLOCKED,
        normalized_quote=normalized_quote,
    )
```

- [x] **Step 4: Verify**

Run: `python -m pytest tests/test_evidence.py -v`

Expected: `3 passed`.

- [x] **Step 5: Commit**

```bash
git add core/evidence.py tests/test_evidence.py
git commit -m "feat: validate evidence containment"
```

## Task 5: Two-Layer Academic Schema

**Files:**
- Create: `core/schema.py`
- Create: `tests/test_schema.py`

- [x] **Step 1: Write failing schema tests**

Create `tests/test_schema.py`:

```python
from core.schema import GENERAL_FIELDS, domain_fields_for_topic


def test_general_fields_match_spec():
    assert GENERAL_FIELDS == [
        "title",
        "authors",
        "year",
        "venue",
        "research_problem",
        "method",
        "innovation",
        "limitation",
        "evidence_page",
        "evidence_quote",
        "confidence",
    ]


def test_domain_fields_for_industrial_anomaly_detection():
    fields = domain_fields_for_topic("industrial automation lab spatial anomaly detection")

    assert "sensor" in fields
    assert "accuracy" in fields
    assert "latency" in fields
    assert "decision_mechanism" in fields


def test_domain_fields_for_brauer_manin():
    fields = domain_fields_for_topic("Brauer-Manin obstruction")

    assert fields == ["mathematical_object", "obstruction_type", "theorem_result", "proof_technique"]


def test_domain_fields_for_matrix_multiplication():
    fields = domain_fields_for_topic("matrix multiplication complexity upper bounds")

    assert "complexity_bound" in fields
    assert "tensor_rank_or_border_rank" in fields
```

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_schema.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [x] **Step 3: Implement schema helper**

Create `core/schema.py`:

```python
GENERAL_FIELDS = [
    "title",
    "authors",
    "year",
    "venue",
    "research_problem",
    "method",
    "innovation",
    "limitation",
    "evidence_page",
    "evidence_quote",
    "confidence",
]


def domain_fields_for_topic(topic: str) -> list[str]:
    normalized = topic.lower()
    if "brauer" in normalized or "manin" in normalized:
        return ["mathematical_object", "obstruction_type", "theorem_result", "proof_technique"]
    if "matrix" in normalized and ("multiplication" in normalized or "complexity" in normalized):
        return [
            "complexity_bound",
            "algorithmic_technique",
            "tensor_rank_or_border_rank",
            "theoretical_result",
        ]
    if any(token in normalized for token in ["anomaly", "industrial", "automation", "robot", "workspace"]):
        return ["sensor", "accuracy", "latency", "deployment_scene", "decision_mechanism"]
    return ["domain_object", "key_metric", "method_family", "evaluation_context"]
```

- [x] **Step 4: Verify**

Run: `python -m pytest tests/test_schema.py -v`

Expected: `4 passed`.

- [x] **Step 5: Commit**

```bash
git add core/schema.py tests/test_schema.py
git commit -m "feat: add two-layer academic schema"
```

## Task 6: Keyring Credential Manager

**Files:**
- Create: `core/credentials.py`
- Create: `tests/test_credentials.py`
- Modify: `core/agent.py`

- [x] **Step 1: Write failing credential tests**

Create `tests/test_credentials.py`:

```python
import pytest

from core.credentials import CredentialStore, MissingCredentialError


class FakeKeyring:
    def __init__(self):
        self.values = {}

    def get_password(self, service, username):
        return self.values.get((service, username))

    def set_password(self, service, username, password):
        self.values[(service, username)] = password

    def delete_password(self, service, username):
        self.values.pop((service, username), None)


def test_store_set_get_clear_key():
    store = CredentialStore(keyring_backend=FakeKeyring())

    store.set_api_key("sk-test")

    assert store.has_api_key() is True
    assert store.get_api_key() == "sk-test"

    store.clear_api_key()

    assert store.has_api_key() is False


def test_missing_key_raises_clear_error():
    store = CredentialStore(keyring_backend=FakeKeyring())

    with pytest.raises(MissingCredentialError, match="No SmartSurvey API key"):
        store.get_api_key()
```

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_credentials.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [x] **Step 3: Implement credential store**

Create `core/credentials.py`:

```python
import keyring


SERVICE_NAME = "SmartSurvey"
API_KEY_USER = "llm_api_key"


class MissingCredentialError(RuntimeError):
    pass


class CredentialStore:
    def __init__(self, keyring_backend=None):
        self.keyring = keyring_backend or keyring

    def set_api_key(self, api_key: str) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("API key must not be empty.")
        self.keyring.set_password(SERVICE_NAME, API_KEY_USER, api_key.strip())

    def get_api_key(self) -> str:
        api_key = self.keyring.get_password(SERVICE_NAME, API_KEY_USER)
        if not api_key:
            raise MissingCredentialError("No SmartSurvey API key is stored in the OS keyring.")
        return api_key

    def clear_api_key(self) -> None:
        self.keyring.delete_password(SERVICE_NAME, API_KEY_USER)

    def has_api_key(self) -> bool:
        return bool(self.keyring.get_password(SERVICE_NAME, API_KEY_USER))
```

- [x] **Step 4: Refactor agent to use keyring**

Replace `core/agent.py` with:

```python
import os

from langchain_openai import ChatOpenAI

from core.credentials import CredentialStore


def get_llm_agent(temperature: float = 0.2, credential_store: CredentialStore | None = None) -> ChatOpenAI:
    store = credential_store or CredentialStore()
    api_key = store.get_api_key()
    api_base = os.getenv("OPENAI_API_BASE")
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o")

    return ChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base=api_base,
        temperature=temperature,
        max_retries=2,
        timeout=60.0,
    )
```

- [x] **Step 5: Verify**

Run: `python -m pytest tests/test_credentials.py -v`

Expected: `2 passed`.

- [x] **Step 6: Commit**

```bash
git add core/credentials.py core/agent.py tests/test_credentials.py
git commit -m "feat: store api key with keyring"
```

## Task 7: Academic Matrix Extraction Boundary

**Files:**
- Create: `core/extractor.py`
- Create: `tests/test_extractor.py`

- [x] **Step 1: Write failing extractor tests**

Create `tests/test_extractor.py`:

```python
from core.extractor import build_extraction_prompt, parse_matrix_json


def test_build_extraction_prompt_includes_general_and_domain_fields():
    prompt = build_extraction_prompt(
        topic="industrial anomaly detection",
        domain_fields=["sensor", "accuracy"],
        page_text="Page 1 text",
    )

    assert "evidence_page" in prompt
    assert "evidence_quote" in prompt
    assert "sensor" in prompt
    assert "Return JSON only" in prompt


def test_parse_matrix_json_converts_missing_fields_to_missing():
    rows = parse_matrix_json(
        '[{"title":"Paper A","evidence_page":1,"evidence_quote":"Quote","confidence":0.7}]',
        domain_fields=["sensor"],
    )

    assert rows[0].title == "Paper A"
    assert rows[0].authors == "missing"
    assert rows[0].domain_fields["sensor"] == "missing"
```

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_extractor.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [x] **Step 3: Implement extractor boundary**

Create `core/extractor.py`:

```python
import json
from typing import Any

from core.models import AcademicMatrixRow
from core.schema import GENERAL_FIELDS


def build_extraction_prompt(topic: str, domain_fields: list[str], page_text: str) -> str:
    all_fields = GENERAL_FIELDS + ["trigger_reason"] + domain_fields
    return (
        "You extract a structured academic comparison matrix from PDF text.\n"
        f"Review topic: {topic}\n"
        f"Required fields: {', '.join(all_fields)}\n"
        "Rules:\n"
        "- Use missing for fields not supported by the text.\n"
        "- Every limitation, risk, or research gap must include evidence_page and evidence_quote.\n"
        "- evidence_quote must be 1-3 exact English source sentences from the supplied page text.\n"
        "- Return JSON only: a list of objects.\n\n"
        f"PDF text:\n{page_text}"
    )


def _string_value(data: dict[str, Any], field: str) -> str:
    value = data.get(field, "missing")
    return str(value) if value not in (None, "") else "missing"


def parse_matrix_json(raw_json: str, domain_fields: list[str]) -> list[AcademicMatrixRow]:
    data = json.loads(raw_json)
    if not isinstance(data, list):
        raise ValueError("Matrix JSON must be a list of row objects.")

    rows: list[AcademicMatrixRow] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Each matrix row must be an object.")
        rows.append(
            AcademicMatrixRow(
                title=_string_value(item, "title"),
                authors=_string_value(item, "authors"),
                year=_string_value(item, "year"),
                venue=_string_value(item, "venue"),
                research_problem=_string_value(item, "research_problem"),
                method=_string_value(item, "method"),
                innovation=_string_value(item, "innovation"),
                limitation=_string_value(item, "limitation"),
                evidence_page=int(item.get("evidence_page", 0) or 0),
                evidence_quote=_string_value(item, "evidence_quote"),
                confidence=float(item.get("confidence", 0.0) or 0.0),
                trigger_reason=_string_value(item, "trigger_reason"),
                domain_fields={field: _string_value(item, field) for field in domain_fields},
            )
        )
    return rows
```

- [x] **Step 4: Verify**

Run: `python -m pytest tests/test_extractor.py -v`

Expected: `2 passed`.

- [x] **Step 5: Commit**

```bash
git add core/extractor.py tests/test_extractor.py
git commit -m "feat: add academic extraction boundary"
```

## Task 8: Markdown, LaTeX, And BibTeX Rendering

**Files:**
- Modify: `core/templates.py`
- Create: `tests/test_templates.py`

- [x] **Step 1: Write failing rendering tests**

Create `tests/test_templates.py`:

```python
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
```

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_templates.py -v`

Expected: FAIL because render functions are missing.

- [x] **Step 3: Implement rendering**

Replace `core/templates.py` with:

```python
import re

from core.models import AcademicMatrixRow


REQUIRED_SECTIONS = [
    "Abstract and Introduction",
    "Technical Taxonomy",
    "Systematic Review and Deep Critique",
    "Academic Comparison Matrix",
    "Research Gaps and Future Work",
    "Conclusion",
]


def latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(char, char) for char in value)


def citation_key(row: AcademicMatrixRow) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", row.title.lower()).strip("_") or "paper"
    return f"{base[:32]}_{row.year}"


def render_matrix_table_tex(rows: list[AcademicMatrixRow]) -> str:
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Academic Comparison Matrix}",
        r"\begin{tabular}{llll}",
        r"\toprule",
        r"Paper & Method & Key Metric & Limitation \\",
        r"\midrule",
    ]
    for row in rows:
        metric = next(iter(row.domain_fields.values()), row.innovation)
        lines.append(
            f"{latex_escape(row.title)} & {latex_escape(row.method)} & "
            f"{latex_escape(str(metric))} & {latex_escape(row.limitation)} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    return "\n".join(lines)


def render_survey_tex(topic: str, rows: list[AcademicMatrixRow]) -> str:
    matrix = render_matrix_table_tex(rows)
    paper_list = "、".join(row.title for row in rows) if rows else "missing"
    sections = {
        "Abstract and Introduction": f"本文围绕“{topic}”展开综述，论文集合包括：{paper_list}。",
        "Technical Taxonomy": "本节依据论文方法、研究问题和领域字段建立技术分类。",
        "Systematic Review and Deep Critique": "本节只纳入已经通过页码与原文摘录校验的批判性结论。",
        "Academic Comparison Matrix": matrix,
        "Research Gaps and Future Work": "本节从已验证的局限性中归纳研究缺口和后续方向。",
        "Conclusion": "本文总结结构化矩阵、证据约束和后续研究价值。",
    }
    body = "\n\n".join(f"\\section{{{name}}}\n{content}" for name, content in sections.items())
    return "\\documentclass{ctexart}\n\\usepackage{booktabs}\n\\begin{document}\n" + body + "\n\\end{document}\n"


def render_markdown_preview(
    topic: str,
    rows: list[AcademicMatrixRow],
    blocked_warnings: list[str] | None = None,
) -> str:
    blocked_warnings = blocked_warnings or []
    lines = [f"# SmartSurvey Preview: {topic}", "", "| Paper | Method | Limitation | Evidence |", "| --- | --- | --- | --- |"]
    for row in rows:
        lines.append(
            f"| {row.title} | {row.method} | {row.limitation} | p.{row.evidence_page}: {row.evidence_quote} |"
        )
    if blocked_warnings:
        lines.extend(["", "## Blocked Warnings"])
        lines.extend(f"- {warning}" for warning in blocked_warnings)
    return "\n".join(lines)


def render_bibtex(rows: list[AcademicMatrixRow]) -> str:
    entries = []
    for row in rows:
        entries.append(
            "@article{"
            + citation_key(row)
            + ",\n"
            + f"  title = {{{row.title}}},\n"
            + f"  author = {{{row.authors}}},\n"
            + f"  year = {{{row.year}}},\n"
            + f"  journal = {{{row.venue}}},\n"
            + f"  evidencepages = {{{row.evidence_page}}}\n"
            + "}"
        )
    return "\n\n".join(entries)
```

- [x] **Step 4: Verify**

Run: `python -m pytest tests/test_templates.py -v`

Expected: `4 passed`.

- [x] **Step 5: Commit**

```bash
git add core/templates.py tests/test_templates.py
git commit -m "feat: render smart survey artifacts"
```

## Task 9: Pipeline Orchestration With Evidence Gate

**Files:**
- Create: `core/pipeline.py`
- Create: `tests/test_pipeline.py`

- [x] **Step 1: Write failing pipeline tests**

Create `tests/test_pipeline.py`:

```python
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
```

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_pipeline.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [x] **Step 3: Implement pipeline**

Create `core/pipeline.py`:

```python
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
```

- [x] **Step 4: Verify**

Run: `python -m pytest tests/test_pipeline.py -v`

Expected: `2 passed`.

- [x] **Step 5: Commit**

```bash
git add core/pipeline.py tests/test_pipeline.py
git commit -m "feat: gate pipeline output by evidence"
```

## Task 10: Streamlit UI Vertical Slice

**Files:**
- Modify: `main.py`
- Create: `tests/test_main_import.py`

- [x] **Step 1: Write failing import test**

Create `tests/test_main_import.py`:

```python
import main


def test_main_exposes_app_entrypoint():
    assert callable(main.run_app)
```

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_main_import.py -v`

Expected: FAIL because `run_app` is missing.

- [x] **Step 3: Implement UI entrypoint**

Replace `main.py` with:

```python
import streamlit as st

from core.credentials import CredentialStore
from core.pdf_parser import parse_pdf_bytes
from core.pipeline import generate_artifacts


def run_app() -> None:
    st.set_page_config(page_title="SmartSurvey", layout="wide")
    st.title("SmartSurvey")

    credential_store = CredentialStore()
    with st.sidebar:
        st.header("Credentials")
        st.caption("API Key is stored in the OS keyring. Full keys are never displayed.")
        key_status = "Configured" if credential_store.has_api_key() else "Missing"
        st.write(f"API Key status: {key_status}")
        new_key = st.text_input("Update API Key", type="password")
        if st.button("Save API Key") and new_key:
            credential_store.set_api_key(new_key)
            st.success("API Key saved to OS keyring.")
        if st.button("Clear API Key"):
            credential_store.clear_api_key()
            st.warning("API Key cleared.")

    topic = st.text_input("Review topic", value="industrial automation lab spatial anomaly detection")
    uploaded_files = st.file_uploader("Upload academic PDFs", type=["pdf"], accept_multiple_files=True)

    if uploaded_files:
        parsed = [parse_pdf_bytes(file.getvalue(), file.name) for file in uploaded_files]
        st.subheader("Parsed PDFs")
        for paper in parsed:
            st.write(
                {
                    "file_name": paper.file_name,
                    "pages": len(paper.pages),
                    "abstract": paper.sections["abstract"] != "missing",
                    "error": paper.error,
                }
            )

        if st.button("Generate preview from verified rows"):
            artifacts = generate_artifacts(topic, [], ["Matrix extraction is not connected yet."])
            st.markdown(artifacts.markdown_preview)
            st.download_button("Download survey_draft.tex", artifacts.survey_tex, "survey_draft.tex")
            st.download_button("Download matrix_table.tex", artifacts.matrix_table_tex, "matrix_table.tex")
            st.download_button("Download references.bib", artifacts.references_bib, "references.bib")


if __name__ == "__main__":
    run_app()
```

- [x] **Step 4: Verify import test**

Run: `python -m pytest tests/test_main_import.py -v`

Expected: `1 passed`.

- [x] **Step 5: Manual UI smoke test**

Run: `streamlit run main.py`

Expected: browser UI shows topic input, PDF uploader, credential status, and download buttons after upload.

- [x] **Step 6: Commit**

```bash
git add main.py tests/test_main_import.py
git commit -m "feat: add streamlit smart survey ui"
```

## Task 11: Docker Distribution

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [x] **Step 1: Write Docker ignore file**

Create `.dockerignore`:

```text
.git
.venv
.env
data/input_pdfs
data/output_docs
__pycache__
.pytest_cache
*.pyc
*.log
```

- [x] **Step 2: Write Dockerfile**

Create `Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core ./core
COPY main.py .

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0", "--server.port=8501"]
```

- [x] **Step 3: Build image**

Run: `docker build -t smartsurvey:local .`

Expected: image builds successfully and does not copy `.env`, `.venv`, or `data/input_pdfs`.

- [x] **Step 4: Run container**

Run: `docker run --rm -p 8501:8501 smartsurvey:local`

Expected: Streamlit starts and exposes the app on `http://localhost:8501`.

- [x] **Step 5: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "build: add docker distribution"
```

## Task 12: CI Unit Test Job

**Files:**
- Create: `.gitlab-ci.yml`

- [x] **Step 1: Add required CI job**

Create `.gitlab-ci.yml`:

```yaml
stages:
  - test

unit-test:
  stage: test
  image: python:3.12-slim
  before_script:
    - python -m pip install --upgrade pip
    - pip install -r requirements.txt
  script:
    - python -m pytest tests -v
```

- [x] **Step 2: Validate locally**

Run: `python -m pytest tests -v`

Expected: all tests pass.

- [x] **Step 3: Commit**

```bash
git add .gitlab-ci.yml
git commit -m "ci: add unit test job"
```

## Task 13: README And Documentation Alignment

**Files:**
- Create: `README.md`
- Modify: `docs/Agent_log.md`
- Modify: `docs/切换API说明.md`

- [x] **Step 1: Create README**

Create `README.md` with these sections:

```markdown
# SmartSurvey

SmartSurvey is an AI4SE non-harness application for evidence-bound academic literature review generation.

## Features

- Batch PDF parsing with core section detection and fallback page slices.
- Two-layer academic matrix schema.
- Evidence containment validation before writing limitations or risks.
- Markdown preview and LaTeX/BibTeX exports.
- OS keyring API key storage.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run main.py
```

## Test

```bash
python -m pytest tests -v
```

## Docker

```bash
docker build -t smartsurvey:local .
docker run --rm -p 8501:8501 smartsurvey:local
```

## Credential Safety

SmartSurvey stores the LLM API key in the operating system keyring. The full key is never displayed in the UI, logs, exported files, Docker images, or committed source files.

## Known Limits

The first version does not automatically download papers, reconstruct perfect PDF paragraphs, or guarantee zero-edit LaTeX compilation in every Overleaf template.
```
```

- [x] **Step 2: Update API switching document**

Edit `docs/切换API说明.md` so it states that `.env` is a development compatibility mechanism for base URL and model name only, while API Key storage should use OS keyring. Remove any instruction that says users should put real API keys into `.env` as the preferred path.

- [x] **Step 3: Append implementation checkpoint to Agent log**

Append to `docs/Agent_log.md`:

```markdown
## Task 1.0 - PLAN.md implementation planning

- Timestamp: 2026-07-07 +08:00
- Triggered Superpowers skills: `writing-plans`
- Key decision: all Markdown documents except `README.md` remain under `docs/`; the implementation plan is stored at `docs/PLAN.md`.
- Next step: execute the plan task-by-task with TDD and subagent-driven development.
```

- [x] **Step 4: Verify docs do not contain real key-like values**

Run: `rg "sk-[A-Za-z0-9]" README.md docs`

Expected: no real API key values. Placeholder strings are acceptable only if clearly fake, such as `sk-your-provider-key`.

- [x] **Step 5: Commit**

```bash
git add README.md docs/切换API说明.md docs/Agent_log.md
git commit -m "docs: align readme and credential guidance"
```

## Task 14: Cold-Start Verification Preparation

**Files:**
- Modify: `docs/SPEC_PROCESS.md`

- [x] **Step 1: Add cold-start verification section placeholder with concrete protocol**

Append to `docs/SPEC_PROCESS.md`:

```markdown
## 8. 冷启动验证计划

后续将使用不同类型的智能体，在不提供历史对话的前提下，仅提供 `docs/SPEC.md` 与 `docs/PLAN.md`，要求其选择 1-2 个任务执行。

验证规则：

1. 不补充口头上下文。
2. 遇到不确定之处必须暂停提问，不得猜测。
3. 记录其暂停点、误解点、产出差距。
4. 根据结果修订 `docs/SPEC.md` 或 `docs/PLAN.md`。
```

- [x] **Step 2: Verify plan and spec are present**

Run: `Test-Path .\docs\SPEC.md; Test-Path .\docs\PLAN.md; Test-Path .\docs\SPEC_PROCESS.md`

Expected: three `True` lines.

- [x] **Step 3: Commit**

```bash
git add docs/SPEC_PROCESS.md docs/PLAN.md
git commit -m "docs: prepare cold start verification"
```

## Task 15: Full Verification Gate

**Files:**
- No new files unless previous tasks reveal a defect.

- [x] **Step 1: Run all tests**

Run: `python -m pytest tests -v`

Expected: all tests pass.

- [x] **Step 2: Check secret hygiene**

Run: `git status --short`

Expected: only intentional working tree changes before final commit.

Run: `rg "OPENAI_API_KEY=.*sk-|sk-[A-Za-z0-9]{20,}" . --glob '!/.git/**' --glob '!/.venv/**'`

Expected: no real keys.

- [x] **Step 3: Check documentation placement**

Run: `Get-ChildItem -Path . -File -Filter *.md | Select-Object -ExpandProperty Name`

Expected: `README.md` only, or no root Markdown except `README.md`.

- [x] **Step 4: Manual app check**

Run: `streamlit run main.py`

Expected: app starts, shows credential status, accepts PDF uploads, and exposes artifact downloads without showing a full API key.

- [x] **Step 5: Final commit if needed**

```bash
git add .
git commit -m "chore: verify smartsurvey vertical slice"
```

## Plan Self-Review

Spec coverage:

- PDF batch upload and parsing: Tasks 3, 10.
- Core section detection and fallback page slices: Task 3.
- General and domain schema: Task 5.
- Evidence containment validation and blocking: Tasks 4, 9.
- Markdown preview and LaTeX/BibTeX exports: Tasks 8, 9, 10.
- Keyring credential storage: Task 6.
- Docker distribution: Task 11.
- CI unit-test job: Task 12.
- README and docs alignment: Task 13.
- Cold-start verification preparation: Task 14.

Known implementation risk:

- The first UI vertical slice wires artifact generation before real LLM extraction. This is intentional for TDD and demo stability. After the deterministic core passes, a later plan can add live LLM extraction and retry/error handling around `core/extractor.py`.

No placeholder tasks remain. Any later implementation agent should execute tasks in order and commit after each task.

---

## Phase 2: Real LLM Extraction & Self-Healing Loop

**Goal:** Connect `core/agent.py` with `core/extractor.py` through dependency injection, implement a self-healing retry loop in `core/pipeline.py`, and run extraction on 4 real PDFs to produce `survey_draft.tex` and `references.bib`.

**Architecture:** `pipeline.py` receives `extraction_fn: Callable[[str], str]` via dependency injection, keeping the self-healing state machine (retry count, containment validation, XML feedback construction, adaptive degradation) agnostic to the LLM adapter. `agent.py` provides a `create_extraction_fn()` factory that wires LangChain ChatOpenAI with `build_extraction_prompt()` and `parse_matrix_json()`. Tests use `StatefulMockExtractor` (a pure Python callable with internal call-count state) — no `mock.patch`, no real API key.

**Key DEPENDENCY INJECTION contract:**
```python
# extraction_fn type: Callable[[str], str]
# Takes a complete prompt string, returns raw JSON string from LLM.
# pipeline.py never touches ChatOpenAI, keyring, or HTTP.

def extract_with_self_healing(
    page_text: str,
    page_number: int,
    topic: str,
    domain_fields: list[str],
    extraction_fn: Callable[[str], str],
    max_retries: int = 3,
) -> tuple[list[AcademicMatrixRow], list[str]]:
    ...
```

### Task 16: Self-Healing Extraction Pipeline (Completed)

**Files:**
- Modify: `core/extractor.py` (add `build_self_healing_prompt`)
- Modify: `core/pipeline.py` (add `extract_with_self_healing`)
- Modify: `core/agent.py` (add `create_extraction_fn`)
- Create: `tests/test_pipeline_extraction.py`
- Modify: `tests/test_extractor.py` (add self-healing prompt tests)

- [x] **Step 1: Write failing tests for `build_self_healing_prompt`**

Append to `tests/test_extractor.py`:

```python
from core.extractor import build_extraction_prompt, build_self_healing_prompt, parse_matrix_json


def test_build_self_healing_prompt_contains_xml_tags():
    original = build_extraction_prompt("test topic", ["sensor"], "Page 1 text.")
    corrected = build_self_healing_prompt(
        original_prompt=original,
        failed_page=1,
        failed_quote="Fake quote.",
        page_text="Page 1 text.",
    )

    assert "<self-healing-correction>" in corrected
    assert "<failed-page>1</failed-page>" in corrected
    assert "<failed-quote>Fake quote.</failed-quote>" in corrected
    assert "<page-text>Page 1 text.</page-text>" in corrected
    assert "<error>" in corrected
    assert "</self-healing-correction>" in corrected
    # Original prompt content must be preserved
    assert "test topic" in corrected
    assert "Return JSON only" in corrected
```

- [x] **Step 2: Run the new self-healing prompt tests**

Run: `python -m pytest tests/test_extractor.py::test_build_self_healing_prompt_contains_xml_tags -v`

Expected: FAIL with `ImportError: cannot import name 'build_self_healing_prompt' from 'core.extractor'`.

- [x] **Step 3: Implement `build_self_healing_prompt`**

Append to `core/extractor.py`:

```python
def build_self_healing_prompt(
    original_prompt: str,
    failed_page: int,
    failed_quote: str,
    page_text: str,
) -> str:
    correction = (
        "\n\n<self-healing-correction>\n"
        f"  <failed-page>{failed_page}</failed-page>\n"
        f"  <failed-quote>{failed_quote}</failed-quote>\n"
        "  <error>The evidence_quote was NOT found in the specified page text. "
        "Please re-extract with a quote that literally exists on this page.</error>\n"
        f"  <page-text>{page_text}</page-text>\n"
        "</self-healing-correction>"
    )
    return original_prompt + correction
```

- [x] **Step 4: Verify self-healing prompt test passes**

Run: `python -m pytest tests/test_extractor.py::test_build_self_healing_prompt_contains_xml_tags -v`

Expected: PASS.

- [x] **Step 5: Write failing tests for `extract_with_self_healing` with `StatefulMockExtractor`**

Create `tests/test_pipeline_extraction.py`:

```python
from typing import Any

from core.evidence import AIR_WARNING_BLOCKED
from core.models import AcademicMatrixRow
from core.pipeline import extract_with_self_healing


class StatefulMockExtractor:
    """Pure Python callable with internal call-count state.
    
    First call returns a hallucinated quote that fails containment.
    Second call returns a corrected quote that passes.
    Third and subsequent calls always return corrected quotes.
    """
    def __init__(self):
        self.call_count = 0
        self.prompts_received: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.call_count += 1
        self.prompts_received.append(prompt)
        if self.call_count == 1:
            # Hallucinated quote — NOT in the page text below
            return (
                '[{"title":"Paper A","authors":"Alice","year":"2024",'
                '"venue":"ICRA","research_problem":"detection",'
                '"method":"vision","innovation":"new","limitation":"lighting",'
                '"evidence_page":1,"evidence_quote":"This sentence does not exist on this page.",'
                '"confidence":0.7,"trigger_reason":"stated"}]'
            )
        # Corrected quote — literally present in page_text
        return (
            '[{"title":"Paper A","authors":"Alice","year":"2024",'
            '"venue":"ICRA","research_problem":"detection",'
            '"method":"vision","innovation":"new","limitation":"lighting",'
            '"evidence_page":1,"evidence_quote":"This page supports a real limitation.",'
            '"confidence":0.9,"trigger_reason":"stated"}]'
        )


PAGE_TEXT = "This page supports a real limitation. Other content here."
PAGE_NUMBER = 1


def test_self_healing_retry_succeeds_on_second_attempt():
    """First call fails containment → XML correction prompt built → second call passes."""
    extractor = StatefulMockExtractor()
    domain = ["sensor"]
    rows, warnings = extract_with_self_healing(
        page_text=PAGE_TEXT,
        page_number=PAGE_NUMBER,
        topic="anomaly detection",
        domain_fields=domain,
        extraction_fn=extractor,
        max_retries=3,
    )

    # Must have extracted one row successfully
    assert len(rows) == 1
    assert rows[0].title == "Paper A"
    assert rows[0].evidence_quote == "This page supports a real limitation."
    # No air-warning blocks for the final result
    assert warnings == []
    # Must have called exactly 2 times (1 failed + 1 retry)
    assert extractor.call_count == 2
    # Second prompt must contain the XML correction tag
    assert "<self-healing-correction>" in extractor.prompts_received[1]


def test_self_healing_stops_after_max_retries_with_adaptive_degradation():
    """All 3 attempts fail → adaptive degradation: retain general fields, mark evidence-bound as retry_failed."""
    class AlwaysFailingExtractor:
        def __init__(self):
            self.call_count = 0
        def __call__(self, prompt: str) -> str:
            self.call_count += 1
            return (
                '[{"title":"Paper B","authors":"Bob","year":"2023",'
                '"venue":"CVPR","research_problem":"detection",'
                '"method":"cnn","innovation":"fast","limitation":"fails at night",'
                '"evidence_page":1,"evidence_quote":"This is pure hallucination.",'
                '"confidence":0.6,"trigger_reason":"stated"}]'
            )

    extractor = AlwaysFailingExtractor()
    rows, warnings = extract_with_self_healing(
        page_text=PAGE_TEXT,
        page_number=PAGE_NUMBER,
        topic="anomaly detection",
        domain_fields=["sensor"],
        extraction_fn=extractor,
        max_retries=3,
    )

    # Must have attempted 3 retries
    assert extractor.call_count == 3
    # Adaptive degradation: general fields retained
    assert len(rows) == 1
    assert rows[0].title == "Paper B"
    assert rows[0].authors == "Bob"
    # Evidence-bound fields marked as retry_failed
    assert rows[0].limitation == "retry_failed"
    assert rows[0].evidence_quote == "retry_failed"
    # Domain fields also marked as retry_failed
    assert rows[0].domain_fields["sensor"] == "retry_failed"
    # Must contain air-warning in the warnings list
    assert len(warnings) == 1
    assert AIR_WARNING_BLOCKED in warnings[0]
```

- [x] **Step 6: Run the new self-healing tests**

Run: `python -m pytest tests/test_pipeline_extraction.py -v`

Expected: FAIL with `ImportError: cannot import name 'extract_with_self_healing' from 'core.pipeline'`.

- [x] **Step 7: Implement `extract_with_self_healing` in `core/pipeline.py`**

Append to `core/pipeline.py`:

```python
from typing import Callable

from core.evidence import validate_evidence
from core.extractor import build_extraction_prompt, build_self_healing_prompt, parse_matrix_json
from core.models import AcademicMatrixRow


def extract_with_self_healing(
    page_text: str,
    page_number: int,
    topic: str,
    domain_fields: list[str],
    extraction_fn: Callable[[str], str],
    max_retries: int = 3,
) -> tuple[list[AcademicMatrixRow], list[str]]:
    """Extract academic matrix rows with self-healing retry loop.
    
    Uses dependency injection for the LLM call (extraction_fn).
    Returns (accepted_rows, warnings_list).
    """
    prompt = build_extraction_prompt(topic, domain_fields, page_text)
    warnings: list[str] = []

    for attempt in range(max_retries + 1):  # +1 for the initial attempt
        raw_json = extraction_fn(prompt)
        try:
            rows = parse_matrix_json(raw_json, domain_fields)
        except (ValueError, json.JSONDecodeError):
            warnings.append("JSON parsing failed; skipping self-healing for this row.")
            return [], warnings

        accepted: list[AcademicMatrixRow] = []
        blocked_any = False
        for row in rows:
            result = validate_evidence(
                row.evidence_page,
                row.evidence_quote,
                {page_number: page_text},
            )
            if result.accepted:
                accepted.append(row)
            else:
                blocked_any = True
                # Adaptive degradation: if we've exhausted retries,
                # keep the row but mark evidence-bound fields as retry_failed
                if attempt >= max_retries:
                    degraded = _apply_degradation(row)
                    accepted.append(degraded)
                    if result.message not in warnings:
                        warnings.append(result.message)

        if not blocked_any:
            return accepted, warnings

        # Build XML correction prompt for next attempt
        if attempt < max_retries:
            failed_quote = rows[0].evidence_quote  # use first failing row's quote
            prompt = build_self_healing_prompt(prompt, page_number, failed_quote, page_text)

    return accepted, warnings


def _apply_degradation(row: AcademicMatrixRow) -> AcademicMatrixRow:
    """Mark evidence-bound fields as retry_failed; keep general fields intact."""
    degraded_domain = {k: "retry_failed" for k in row.domain_fields}
    return AcademicMatrixRow(
        title=row.title,
        authors=row.authors,
        year=row.year,
        venue=row.venue,
        research_problem=row.research_problem,
        method=row.method,
        innovation="retry_failed",
        limitation="retry_failed",
        evidence_page=row.evidence_page,
        evidence_quote="retry_failed",
        confidence=row.confidence,
        trigger_reason=row.trigger_reason,
        domain_fields=degraded_domain,
    )
```

Add the `json` import at the top of `core/pipeline.py`:

```python
import json
from typing import Callable
```

- [x] **Step 8: Verify self-healing tests pass**

Run: `python -m pytest tests/test_pipeline_extraction.py -v`

Expected: `2 passed`.

- [x] **Step 9: Write failing tests for `create_extraction_fn` factory**

Create `tests/test_agent.py`:

```python
from core.agent import create_extraction_fn


class FakeCredentialStore:
    def get_api_key(self):
        return "sk-fake-test-key"


def test_create_extraction_fn_returns_callable():
    fn = create_extraction_fn(credential_store=FakeCredentialStore())
    assert callable(fn)
    # The returned function should accept a prompt string and return a string
    result = fn("Return the word test.")
    assert isinstance(result, str)
```

- [x] **Step 10: Run the new agent test**

Run: `python -m pytest tests/test_agent.py -v`

Expected: FAIL with `ImportError: cannot import name 'create_extraction_fn' from 'core.agent'`.

- [x] **Step 11: Implement `create_extraction_fn` in `core/agent.py`**

Replace `core/agent.py` with:

```python
import os
from typing import Callable

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from core.credentials import CredentialStore


def get_llm_agent(temperature: float = 0.2, credential_store: CredentialStore | None = None) -> ChatOpenAI:
    store = credential_store or CredentialStore()
    api_key = store.get_api_key()
    api_base = os.getenv("OPENAI_API_BASE")
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o")

    return ChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base=api_base,
        temperature=temperature,
        max_retries=2,
        timeout=60.0,
    )


def create_extraction_fn(credential_store: CredentialStore | None = None) -> Callable[[str], str]:
    """Create an extraction_fn that wires agent.py with real LLM calls.
    
    Returns a callable matching the ExtractionFn contract:
        (prompt: str) -> str
    The returned string is the raw LLM response content.
    """
    agent = get_llm_agent(credential_store=credential_store)

    def extraction_fn(prompt: str) -> str:
        response = agent.invoke([HumanMessage(content=prompt)])
        return response.content

    return extraction_fn
```

- [x] **Step 12: Verify agent test passes**

Run: `python -m pytest tests/test_agent.py -v`

Expected: The test calls a real LLM endpoint if a key is configured, OR returns a string response. Note: if no real API key is available, the test will fail with a keyring error — this is acceptable because the `create_extraction_fn` test is an integration gate, not a unit test. The core self-healing logic is already unit-tested in Step 8 without any API key.

- [x] **Step 13: Run full test suite**

Run: `python -m pytest tests -v`

Expected: All existing 24 tests plus the new tests pass. The `test_create_extraction_fn_returns_callable` test may be skipped if no API key is configured (it is the only integration-level test).

- [x] **Step 14: Commit**

```bash
git add core/pipeline.py core/extractor.py core/agent.py tests/test_pipeline_extraction.py tests/test_extractor.py tests/test_agent.py
git commit -m "feat: add self-healing extraction pipeline with DI"
```

### Task 17: Real PDF Extraction & Export (Completed)

**Files:**
- Create: `scripts/run_extraction.py`
- Create: `data/output_docs/survey_draft.tex`
- Create: `data/output_docs/references.bib`
- Create: `data/output_docs/matrix_table.tex`
- Modify: `main.py` (wire extraction_fn into UI pipeline)

**Prerequisites:** A real LLM API key must be stored in the OS keyring (via `streamlit run main.py` sidebar or a keyring CLI command). The 4 PDFs are already in `data/input_pdfs/`.

- [x] **Step 1: Write failing test for the extraction script import**

Create `tests/test_scripts.py`:

```python
import scripts.run_extraction


def test_run_extraction_exposes_main_function():
    assert callable(scripts.run_extraction.main)
```

- [x] **Step 2: Run the script test**

Run: `python -m pytest tests/test_scripts.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.run_extraction'`.

- [x] **Step 3: Create the batch extraction script**

Create `scripts/run_extraction.py`:

```python
"""Batch extraction: parse PDFs, run self-healing extraction, export artifacts.

Usage:
    python -m scripts.run_extraction

Requires a valid LLM API key in the OS keyring.
"""

import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.agent import create_extraction_fn
from core.credentials import CredentialStore
from core.pdf_parser import parse_pdf_bytes
from core.pipeline import extract_with_self_healing, generate_artifacts, filter_rows_by_evidence
from core.schema import domain_fields_for_topic


INPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "input_pdfs")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "output_docs")
TOPIC = "industrial automation lab spatial anomaly detection"


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Resolve credentials
    store = CredentialStore()
    if not store.has_api_key():
        print("ERROR: No API key found in OS keyring. Run 'streamlit run main.py' to configure one.")
        sys.exit(1)

    # Create extraction function (real LLM)
    extraction_fn = create_extraction_fn(credential_store=store)

    # Parse all PDFs
    pdf_paths = glob.glob(os.path.join(INPUT_DIR, "*.pdf"))
    if not pdf_paths:
        print(f"No PDFs found in {INPUT_DIR}")
        sys.exit(1)

    print(f"Parsing {len(pdf_paths)} PDFs...")
    papers = []
    for path in pdf_paths:
        with open(path, "rb") as f:
            paper = parse_pdf_bytes(f.read(), os.path.basename(path))
        papers.append(paper)
        status = "OK" if not paper.error else f"ERROR: {paper.error}"
        print(f"  [{status}] {paper.file_name} ({len(paper.pages)} pages)")

    # Extract matrix rows with self-healing for each paper
    domain_fields = domain_fields_for_topic(TOPIC)
    all_rows: list = []
    all_warnings: list = []
    for paper in papers:
        if paper.error:
            continue
        for page in paper.pages:
            print(f"  Extracting from {paper.file_name} page {page.page_number}...")
            rows, warnings = extract_with_self_healing(
                page_text=page.text,
                page_number=page.page_number,
                topic=TOPIC,
                domain_fields=domain_fields,
                extraction_fn=extraction_fn,
                max_retries=3,
            )
            all_rows.extend(rows)
            all_warnings.extend(warnings)

    # Filter by evidence (second pass)
    accepted, blocked = filter_rows_by_evidence(all_rows, papers)

    # Generate artifacts
    artifacts = generate_artifacts(TOPIC, accepted, blocked)

    # Write outputs
    tex_path = os.path.join(OUTPUT_DIR, "survey_draft.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(artifacts.survey_tex)
    print(f"Written: {tex_path}")

    matrix_path = os.path.join(OUTPUT_DIR, "matrix_table.tex")
    with open(matrix_path, "w", encoding="utf-8") as f:
        f.write(artifacts.matrix_table_tex)
    print(f"Written: {matrix_path}")

    bib_path = os.path.join(OUTPUT_DIR, "references.bib")
    with open(bib_path, "w", encoding="utf-8") as f:
        f.write(artifacts.references_bib)
    print(f"Written: {bib_path}")

    # Summary
    total_accepted = len(accepted)
    total_blocked = len(blocked)
    print(f"\nDone. {total_accepted} rows accepted, {total_blocked} blocked warnings.")
    print(f"Self-healing details: {len(all_warnings)} correction events recorded.")


if __name__ == "__main__":
    main()
```

- [x] **Step 4: Verify script import test passes**

Run: `python -m pytest tests/test_scripts.py -v`

Expected: `1 passed`.

- [x] **Step 5: Run the batch extraction (real LLM call)**

This step requires a real API key in the OS keyring.

Run: `python -m scripts.run_extraction`

Expected output:
```
Parsing 4 PDFs...
  [OK] 2503.07901v2.pdf (N pages)
  [OK] Costanzino_...pdf (N pages)
  [OK] fmech-12-1806266.pdf (N pages)
  [OK] s11263-022-01578-9.pdf (N pages)
  Extracting from ... page 1...
  Written: data/output_docs/survey_draft.tex
  Written: data/output_docs/matrix_table.tex
  Written: data/output_docs/references.bib
Done. X rows accepted, Y blocked warnings.
```

- [x] **Step 6: Verify output files**

Run: `python -m pytest tests -v` (ensure no regression)

Manually verify:
- `data/output_docs/survey_draft.tex` contains `\documentclass{ctexart}`, six `\section{...}` headers, and `\end{document}`.
- `data/output_docs/matrix_table.tex` contains `\toprule`, `\midrule`, `\bottomrule`, and paper titles.
- `data/output_docs/references.bib` contains `@article{` entries with `evidencepages` metadata.

- [x] **Step 7: .gitignore decision — keep output_docs excluded**

By default, `.gitignore` excludes `data/output_docs/`. If the output files should be committed as demo artifacts, remove the `data/output_docs/` line from `.gitignore`. Otherwise, keep it excluded.

- [x] **Step 8: Commit**

```bash
git add scripts/run_extraction.py tests/test_scripts.py
git add data/output_docs/  # only if tracking output artifacts
git commit -m "feat: batch real pdf extraction with self-healing"
```

## Phase 2 Self-Review

Spec coverage:

- `SPEC.md` §7.4 Self-healing retry mechanism: Task 16 (extract_with_self_healing, build_self_healing_prompt, XML correction structure).
- `SPEC.md` §7.4.1 Dependency injection: Task 16 (extraction_fn contract, create_extraction_fn factory, pipeline DI).
- `SPEC.md` §7.4.4 Adaptive degradation: Task 16 (_apply_degradation, 3 retries → retry_failed fallback).
- `SPEC.md` §12.3 Self-healing test points: Task 16 (StatefulMockExtractor, first-fail-then-succeed, 3-retries-then-degrade).
- `SPEC.md` §12.3 No mock library: Task 16 (StatefulMockExtractor is a pure Python callable with no mock.patch).
- Real PDF extraction into LaTeX/BibTeX: Task 17 (scripts/run_extraction.py, data/output_docs/).
- `SPEC.md` §8.3 3000-5000 word Chinese manuscript: Task 17 (survey_draft.tex output).
- `SPEC.md` §8.4 booktabs matrix table: Task 17 (matrix_table.tex output).
- `SPEC.md` §8.5 BibTeX with evidence metadata: Task 17 (references.bib output).

Known implementation risk:

- The `create_extraction_fn` test in Step 9-12 calls a real LLM if a key is configured. This is intentional as an integration gate. The unit-test-only guarantee is maintained by the `StatefulMockExtractor` tests in `test_pipeline_extraction.py`, which need no API key.
- The `scripts/run_extraction.py` script calls the LLM per-page per-paper. For 4 papers with ~10 pages each, this is ~40 LLM calls; each self-healing retry adds more. Users should be aware of token consumption.
- The `_apply_degradation` function currently hardcodes `retry_failed` for `innovation`, `limitation`, `evidence_quote`, and all `domain_fields`. If the spec adds more evidence-bound fields later, this function must be updated.

---

## Phase 3: Academic Table Refinement & UX Word-Control (Current)

**Goal:** Optimize LaTeX table output for Overleaf compatibility (Task 20) and add interactive word-count control to the Streamlit synthesis pipeline (Task 21).

**Note:** Tasks 18-19 (progress callback + LLM synthesis) were completed on the `feat/task18&19` branch and are awaiting PR merge. Tasks 20-21 are the current focus.

### Task 20: LaTeX Table Adaptive Column Wrapping

**Files:**
- Modify: `core/templates.py` (add `\usepackage{tabularx}` to preamble, switch `render_matrix_table_tex` to `tabularx`)
- Modify: `core/synthesis.py` (update `build_synthesis_prompt` to use `tabularx`, update `validate_latex_syntax` to accept `\begin{tabularx}`)
- Test: `tests/test_templates.py` (add tabularx test)
- Test: `tests/test_synthesis.py` (add tabularx compatibility test)

**Problem:** The current `matrix_table.tex` uses `\begin{tabular}{llll}` with fixed-width columns. When paper titles or method descriptions exceed the column width, the table overflows the page margin in Overleaf, producing an unreadable overfull `\hbox` warning.

**Solution:** Replace `tabular` with `tabularx` and `X`-type columns that auto-wrap:
- Use `\begin{tabularx}{\textwidth}{XXXX}` for proportional auto-wrapping
- Add `\usepackage{tabularx}` to the LaTeX preamble in `render_survey_tex` and `build_synthesis_prompt`
- Update `validate_latex_syntax` to recognize `\begin{tabularx}` and `\end{tabularx}` as valid environments

- [x] **Step 1: Write failing test for tabularx preamble**

Append to `tests/test_templates.py`:

```python
def test_render_matrix_table_uses_tabularx():
    """Matrix table must use tabularx for auto-wrapping columns."""
    from core.templates import render_matrix_table_tex
    from core.models import AcademicMatrixRow

    row = AcademicMatrixRow(
        title="A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    output = render_matrix_table_tex([row])

    assert "\\begin{tabularx}" in output
    assert "\\end{tabularx}" in output
    assert "\\textwidth" in output
    # Must NOT use old tabular format
    assert "\\begin{tabular}{llll}" not in output
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_templates.py::test_render_matrix_table_uses_tabularx -v`

Expected: FAIL — `tabularx` not found in output.

- [x] **Step 3: Update `render_matrix_table_tex` in `core/templates.py`**

Replace `\begin{tabular}{llll}` with `\begin{tabularx}{\textwidth}{XXXX}` and close with `\end{tabularx}`.

- [x] **Step 4: Update `render_survey_tex` preamble**

Add `\usepackage{tabularx}` to the LaTeX preamble.

- [x] **Step 5: Update `build_synthesis_prompt` in `core/synthesis.py`**

Add `\usepackage{tabularx}` to the required packages in the synthesis prompt.

- [x] **Step 6: Update `validate_latex_syntax` to accept `tabularx`**

Add `tabularx` to the recognized environment list in `validate_latex_syntax`. The current regex `r'\\(begin|end)\{(\w+)\}'` already matches any environment name, so `tabularx` should work. Add a test to confirm.

- [x] **Step 7: Write test for tabularx compatibility in validator**

```python
def test_tabularx_is_valid_latex_environment():
    """tabularx environment must not trigger false positive."""
    from core.synthesis import validate_latex_syntax

    source = r"\begin{tabularx}{\textwidth}{XXXX} a & b \\ \end{tabularx}"
    errors = validate_latex_syntax(source)
    assert errors == []
```

- [x] **Step 8: Run both new tests**

Run: `python -m pytest tests/test_templates.py::test_render_matrix_table_uses_tabularx tests/test_synthesis.py::test_tabularx_is_valid_latex_environment -v`

Expected: Both PASS.

- [x] **Step 9: Commit**

```bash
git add core/templates.py core/synthesis.py tests/test_templates.py tests/test_synthesis.py
git commit -m "feat: switch to tabularx for auto-wrapping table columns (Task 20) [Subagent: Sonnet] [Manual: None]"
```

### Task 21: Streamlit Word-Count Slider for Synthesis

**Files:**
- Modify: `main.py` (add `st.slider` for word count target)
- Modify: `core/pipeline.py` (pass `word_count_target` through `generate_llm_artifacts`)
- Modify: `core/synthesis.py` (accept `word_count_target` in `render_survey_tex_with_llm` and `build_synthesis_prompt`)
- Test: `tests/test_synthesis.py` (add word count prompt test)

**Data flow:**
```
main.py (st.slider) → pipeline.py (generate_llm_artifacts) → synthesis.py (render_survey_tex_with_llm → build_synthesis_prompt)
```

- [x] **Step 1: Write failing test for word count in prompt**

```python
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
    assert "Chinese characters" in prompt.lower() or "字" in prompt
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_synthesis.py::test_build_synthesis_prompt_accepts_word_count_target -v`

Expected: FAIL with `TypeError` — unexpected keyword argument `word_count_target`.

- [x] **Step 3: Update `build_synthesis_prompt` signature**

Add `word_count_target: int = 3000` parameter. Replace the hardcoded `"3000-5000 Chinese characters"` in the prompt with the dynamic value.

- [x] **Step 4: Update `render_survey_tex_with_llm` signature**

Add `word_count_target: int = 3000` parameter. Pass it to `build_synthesis_prompt`.

- [x] **Step 5: Update `generate_llm_artifacts` signature**

Add `word_count_target: int = 3000` parameter. Pass it to `render_survey_tex_with_llm`.

- [x] **Step 6: Run word count test to verify it passes**

Run: `python -m pytest tests/test_synthesis.py::test_build_synthesis_prompt_accepts_word_count_target -v`

Expected: PASS.

- [x] **Step 7: Add Streamlit slider to `main.py`**

Add before the extraction button:
```python
word_count_target = st.slider(
    "Target word count for manuscript",
    min_value=1000, max_value=10000, value=3000, step=500,
    help="Controls how many Chinese characters the LLM synthesis should target.",
)
```

Pass `word_count_target` to `generate_llm_artifacts`.

- [x] **Step 8: Run full test suite**

Run: `python -m pytest tests -v --ignore=tests/test_agent.py`

Expected: All tests pass.

- [x] **Step 9: Commit**

```bash
git add core/synthesis.py core/pipeline.py main.py tests/test_synthesis.py
git commit -m "feat: add word count slider for llm synthesis (Task 21) [Subagent: Sonnet] [Manual: None]"
```

---

## Phase 4: Future Work (Backlog)

**Files:**
- Modify: `core/pipeline.py` (add `progress_callback` param to `extract_with_self_healing`)
- Modify: `scripts/run_extraction.py` (wire callback into per-paper loop)
- Modify: `main.py` (wire Streamlit `st.progress()` + `st.status()` via callback)
- Test: `tests/test_pipeline.py` (add callback test)

**Interfaces:**
- Consumes: `extraction_fn: Callable[[str], str]`, existing `AcademicMatrixRow`, `ParsedPaper`
- Produces: Updated `extract_with_self_healing` signature with optional `progress_callback`

- [x] **Step 1: Write failing test for callback invocation**

Append to `tests/test_pipeline.py`:

```python
def test_extract_with_self_healing_invokes_progress_callback():
    """Verify that progress_callback is called with correct states."""
    from core.pipeline import extract_with_self_healing
    from tests.test_pipeline_extraction import PAGE_TEXT, StatefulMockExtractor
    
    events: list[tuple] = []
    def callback(idx: int, total: int, state: str, detail: str) -> None:
        events.append((idx, total, state, detail))
    
    extractor = StatefulMockExtractor()  # first call fails, second succeeds
    rows, warnings = extract_with_self_healing(
        merged_context=PAGE_TEXT,
        page_text_by_number={1: PAGE_TEXT},
        topic="test",
        domain_fields=["sensor"],
        extraction_fn=extractor,
        progress_callback=callback,
        max_retries=3,
    )
    
    # Must have at least one 'extracting' event
    states = [e[2] for e in events]
    assert "extracting" in states
    # Must have 'completed' as the last state
    assert events[-1][2] == "completed"
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline.py::test_extract_with_self_healing_invokes_progress_callback -v`

Expected: FAIL with `TypeError: extract_with_self_healing() got an unexpected keyword argument 'progress_callback'`.

- [x] **Step 3: Add `progress_callback` parameter to `extract_with_self_healing`**

In `core/pipeline.py`:

1. Add `progress_callback` import at top: `from typing import Callable, Optional`
2. Change signature from:
   ```python
   def extract_with_self_healing(
       merged_context: str,
       page_text_by_number: dict[int, str],
       topic: str,
       domain_fields: list[str],
       extraction_fn: Callable[[str], str],
       max_retries: int = 3,
   ) -> tuple[list[AcademicMatrixRow], list[str]]:
   ```
   to:
   ```python
   def extract_with_self_healing(
       merged_context: str,
       page_text_by_number: dict[int, str],
       topic: str,
       domain_fields: list[str],
       extraction_fn: Callable[[str], str],
       progress_callback: Callable[[int, int, str, str], None] | None = None,
       max_retries: int = 3,
   ) -> tuple[list[AcademicMatrixRow], list[str]]:
   ```
3. At the start of the function, before the retry loop, add:
   ```python
   if progress_callback:
       progress_callback(0, 1, "extracting", "Initial extraction attempt...")
   ```
4. Before each self-healing retry (`if attempt < max_retries:` block), add:
   ```python
   if progress_callback:
       progress_callback(0, 1, "self_healing",
           f"Retry {attempt + 1}/{max_retries}: Evidence quote failed containment, rebuilding prompt...")
   ```
5. Before the return statement, add:
   ```python
   if progress_callback:
       progress_callback(0, 1, "completed",
           f"Accepted {len(accepted)} rows, {len(warnings)} corrections")
   ```
6. Also wrap `_call_with_rate_limit_backoff` call inside the retry loop: if rate-limit or timeout triggers a backoff wait, invoke the callback with `state="self_healing"` and `detail` indicating the wait duration.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pipeline.py::test_extract_with_self_healing_invokes_progress_callback -v`

Expected: PASS.

- [x] **Step 5: Write failing test for callback in `generate_artifacts`**

```python
def test_generate_artifacts_accepts_optional_callback():
    """Callback parameter is accepted but no-op for template-based generation."""
    from core.pipeline import generate_artifacts
    from core.models import AcademicMatrixRow
    
    called = False
    def callback(idx, total, state, detail):
        nonlocal called
        called = True
    
    row = AcademicMatrixRow(
        title="A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    artifacts = generate_artifacts("topic", [row], [], progress_callback=callback)
    assert artifacts is not None
```

- [x] **Step 6: Add `progress_callback` to `generate_artifacts`**

Modify `core/pipeline.py`:

```python
def generate_artifacts(
    topic: str,
    rows: list[AcademicMatrixRow],
    blocked_warnings: list[str],
    progress_callback: Callable[[int, int, str, str], None] | None = None,
) -> GeneratedArtifacts:
    if progress_callback:
        progress_callback(0, 1, "completed", "Generating artifacts...")
    return GeneratedArtifacts(
        markdown_preview=render_markdown_preview(topic, rows, blocked_warnings),
        survey_tex=render_survey_tex(topic, rows),
        matrix_table_tex=render_matrix_table_tex(rows),
        references_bib=render_bibtex(rows),
    )
```

- [x] **Step 7: Update `scripts/run_extraction.py` — wire progress callback**

Modify `scripts/run_extraction.py`:

1. Define a `_console_progress_callback(current_idx, total_papers, state, detail)` function that:
   - On `state == "parsing"`: calls `_print_progress(current_idx + 1, total_papers, detail)` (detail = paper name)
   - On `state == "extracting"`: prints `f"\r  [{state}] {detail}..."`
   - On `state == "self_healing"`: prints `f"\r  [{state}] {detail}..."`
   - On `state == "completed"`: prints `f"\r  [{state}] {detail}\n"` (newline to finish the line)

2. Pass this callback to both `extract_with_self_healing()` and `generate_artifacts()`.

The per-paper loop becomes:
```python
for idx, paper in enumerate(papers, start=1):
    if paper.error:
        continue
    _console_progress_callback(idx - 1, total_papers, "parsing", paper.file_name)
    merged_context, page_text_by_number = _get_merged_core_pages(paper)
    rows, warnings = extract_with_self_healing(
        merged_context=merged_context,
        page_text_by_number=page_text_by_number,
        topic=TOPIC,
        domain_fields=domain_fields,
        extraction_fn=extraction_fn,
        progress_callback=_console_progress_callback,
        max_retries=3,
    )
    ...
```

- [x] **Step 8: Update `main.py` — wire Streamlit progress callback**

Modify `main.py`:

1. In the `if st.button("Generate preview from verified rows"):` block, replace the static `generate_artifacts(topic, [], ...)` call with a live extraction pipeline that uses Streamlit progress widgets.

2. Create a `_streamlit_progress_callback(current_idx, total_papers, state, detail)` function:
   ```python
   def _streamlit_progress_callback(current_idx, total_papers, state, detail):
       progress = (current_idx + 1) / total_papers if total_papers > 0 else 0
       progress_bar.progress(progress)
       status_text.text(f"**{state}**: {detail}")
   ```
   Where `progress_bar = st.progress(0)` and `status_text = st.empty()` are created before the extraction loop.

3. The `st.button("Extract & Generate")` handler should:
   - Call `extract_with_self_healing` for each paper with the Streamlit callback.
   - Call `filter_rows_by_evidence` on all rows.
   - Call `generate_artifacts` with the callback.
   - Display the resulting Markdown preview and download buttons.

- [x] **Step 9: Run full test suite**

Run: `python -m pytest tests -v`

Expected: All existing tests pass (incl. the new callback tests). The `test_agent.py::test_create_extraction_fn_returns_callable` may fail — this is pre-existing and unrelated.

- [x] **Step 10: Commit**

```bash
git add core/pipeline.py scripts/run_extraction.py main.py tests/test_pipeline.py
git commit -m "feat: add unified state progress callback for extraction pipeline (Task 18)"
```

### Task 19: `core/synthesis.py` — LLM Full-Text Synthesis & LaTeX Stack Validator

**Files:**
- Create: `core/synthesis.py` (render_survey_tex_with_llm, build_synthesis_prompt, validate_latex_syntax, _build_latex_healing_prompt)
- Create: `tests/test_synthesis.py`
- Modify: `core/pipeline.py` (wire synthesis into generate_artifacts)
- Modify: `scripts/run_extraction.py` (use synthesis module)
- Modify: `main.py` (wire synthesis into Streamlit UI)

**Interfaces:**
- Consumes: `extraction_fn: Callable[[str], str]`, `AcademicMatrixRow`, `progress_callback`
- Produces: `render_survey_tex_with_llm(topic, rows, extraction_fn, progress_callback) -> str`

- [x] **Step 1: Write failing tests for `validate_latex_syntax`**

Create `tests/test_synthesis.py`:

```python
from core.synthesis import validate_latex_syntax


def test_valid_latex_returns_empty_errors():
    source = r"""\documentclass{ctexart}
\usepackage{booktabs}
\begin{document}
\section{Introduction}
This is a test.
\end{document}"""
    errors = validate_latex_syntax(source)
    assert errors == []


def test_unclosed_inline_math_detected():
    source = r"\section{Test} The formula $x + y = z$ is valid."
    errors = validate_latex_syntax(source)
    assert errors == []  # closed $...$ is valid

    broken = r"\section{Test} The formula $x + y = z is broken."
    errors = validate_latex_syntax(broken)
    assert any("$" in e for e in errors)


def test_unclosed_display_math_detected():
    broken = r"\section{Test} Display math $$ x + y"
    errors = validate_latex_syntax(broken)
    assert any("$$" in e or "$" in e for e in errors)


def test_mismatched_begin_end_detected():
    source = r"\begin{table}\begin{tabular}{ll}\end{tabular}\end{figure}"
    errors = validate_latex_syntax(source)
    assert any("figure" in e.lower() or "table" in e.lower() for e in errors)


def test_unclosed_environment_detected():
    source = r"\begin{table}\begin{tabular}{ll}\end{tabular}"
    errors = validate_latex_syntax(source)
    assert len(errors) > 0  # table has no \end{table}


def test_unbalanced_braces_detected():
    source = r"\textbf{Hello world"
    errors = validate_latex_syntax(source)
    assert any("brace" in e.lower() or "{" in e for e in errors)


def test_escaped_dollar_does_not_trigger_false_positive():
    source = r"\section{Test} Price is \$10.00 and \$20.00"
    errors = validate_latex_syntax(source)
    assert errors == []


def test_escaped_brace_does_not_trigger_false_positive():
    source = r"\section{Test} Function call: foo\{bar\} baz"
    errors = validate_latex_syntax(source)
    assert errors == []
```

- [x] **Step 2: Run the LaTeX validation tests**

Run: `python -m pytest tests/test_synthesis.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'core.synthesis'`.

- [x] **Step 3: Implement `validate_latex_syntax`**

Create `core/synthesis.py` with the stack-based scanner:

```python
import re
from typing import Callable

from core.models import AcademicMatrixRow


def validate_latex_syntax(latex_source: str) -> list[str]:
    """Validate LaTeX syntax with zero-dependency stack scanning.
    
    Checks:
    1. Inline math $...$ parity (ignoring escaped \$)
    2. Display math $$...$$ parity
    3. \\begin{env}/\\end{env} pairing via stack
    4. Curly brace {} balance (ignoring escaped \\{ \\})
    
    Returns list of error messages (empty = valid).
    """
    errors: list[str] = []
    
    # Check 1: Inline math $...$ parity
    dollar_count = 0
    i = 0
    while i < len(latex_source):
        if latex_source[i] == '\\' and i + 1 < len(latex_source):
            i += 2  # skip escaped character
            continue
        if latex_source[i] == '$':
            # Check if it's $$ (display math)
            if i + 1 < len(latex_source) and latex_source[i + 1] == '$':
                dollar_count += 2
                i += 2
            else:
                dollar_count += 1
                i += 1
        else:
            i += 1
    if dollar_count % 2 != 0:
        errors.append(f"Unclosed inline math or display math: odd number of $ symbols ({dollar_count}).")
    
    # Check 2: \begin{env} / \end{env} pairing
    env_stack: list[str] = []
    for match in re.finditer(r'\\(begin|end)\{(\w+)\}', latex_source):
        keyword, env_name = match.group(1), match.group(2)
        if keyword == 'begin':
            env_stack.append(env_name)
        elif keyword == 'end':
            if not env_stack:
                errors.append(f"Extra \\end{{{env_name}}} with no matching \\begin.")
            else:
                opened = env_stack.pop()
                if opened != env_name:
                    errors.append(
                        f"Mismatched environment: \\begin{{{opened}}} closed by \\end{{{env_name}}}."
                    )
    if env_stack:
        for leftover in env_stack:
            errors.append(f"Unclosed environment: \\begin{{{leftover}}} has no matching \\end.")
    
    # Check 3: Curly brace {} balance
    brace_count = 0
    i = 0
    while i < len(latex_source):
        if latex_source[i] == '\\' and i + 1 < len(latex_source):
            i += 2  # skip escaped character
            continue
        if latex_source[i] == '{':
            brace_count += 1
        elif latex_source[i] == '}':
            brace_count -= 1
            if brace_count < 0:
                errors.append("Extra closing brace encountered.")
                brace_count = 0
        i += 1
    if brace_count > 0:
        errors.append(f"Unclosed brace: {brace_count} unmatched opening brace(s).")
    
    return errors
```

- [x] **Step 4: Run LaTeX validation tests to verify they pass**

Run: `python -m pytest tests/test_synthesis.py -v`

Expected: All 8 tests PASS.

- [x] **Step 5: Write failing tests for `build_synthesis_prompt`**

Append to `tests/test_synthesis.py`:

```python
from core.synthesis import build_synthesis_prompt


def test_build_synthesis_prompt_contains_topic_and_rows():
    from core.models import AcademicMatrixRow
    row = AcademicMatrixRow(
        title="Paper A", authors="Alice", year="2024", venue="ICRA",
        research_problem="detection", method="vision", innovation="new",
        limitation="lighting", evidence_page=2, evidence_quote="limitation",
        confidence=0.8, trigger_reason="stated",
        domain_fields={"sensor": "camera"},
    )
    prompt = build_synthesis_prompt("anomaly detection", [row])
    
    assert "anomaly detection" in prompt
    assert "Paper A" in prompt
    assert "ctexart" in prompt
    assert "\\section{Abstract and Introduction}" in prompt
    assert "\\section{Technical Taxonomy}" in prompt
    assert "\\section{Systematic Review and Deep Critique}" in prompt
    assert "\\section{Academic Comparison Matrix}" in prompt
    assert "\\section{Research Gaps and Future Work}" in prompt
    assert "\\section{Conclusion}" in prompt
    assert "Return ONLY valid LaTeX" in prompt or "Return only" in prompt.lower()
```

- [x] **Step 6: Implement `build_synthesis_prompt`**

Append to `core/synthesis.py`:

```python
def build_synthesis_prompt(topic: str, rows: list[AcademicMatrixRow]) -> str:
    """Build a constrained system prompt for LLM-driven LaTeX synthesis.
    
    The prompt forces the LLM to:
    - Use ctexart document class.
    - Include exactly 6 required \\section{...} headers.
    - Embed the booktabs matrix table from provided row data.
    - Return ONLY valid LaTeX source (no markdown fences, no explanations).
    """
    paper_list = "\n".join(
        f"  - {row.title} ({row.authors}, {row.year}, {row.venue})"
        for row in rows
    )
    
    matrix_rows = "\n".join(
        f"    {row.title} & {row.method} & {row.limitation} \\\\"
        for row in rows
    )
    
    return (
        f"You are an academic writing assistant. Generate a Chinese academic survey manuscript in LaTeX.\n\n"
        f"Review topic: {topic}\n\n"
        f"Papers to review ({len(rows)} total):\n{paper_list}\n\n"
        f"Extracted comparison data:\n"
        f"\\begin{{tabular}}{{lll}}\n"
        f"  Paper & Method & Limitation \\\\\n"
        f"  \\midrule\n{matrix_rows}"
        f"\\end{{tabular}}\n\n"
        f"REQUIREMENTS:\n"
        f"1. Use \\documentclass{{ctexart}} and \\usepackage{{booktabs}}.\n"
        f"2. Include EXACTLY these six sections:\n"
        f"   \\section{{Abstract and Introduction}}\n"
        f"   \\section{{Technical Taxonomy}}\n"
        f"   \\section{{Systematic Review and Deep Critique}}\n"
        f"   \\section{{Academic Comparison Matrix}}\n"
        f"   \\section{{Research Gaps and Future Work}}\n"
        f"   \\section{{Conclusion}}\n"
        f"3. The \\section{{Academic Comparison Matrix}} must contain a full booktabs table.\n"
        f"4. Each critique of a paper's limitation must reference its evidence_page.\n"
        f"5. Write body text in Chinese, keep evidence quotes in English.\n"
        f"6. Total length: 3000-5000 Chinese characters.\n"
        f"7. Return ONLY valid LaTeX source. No markdown fences, no explanations.\n"
        f"8. All $, {{, }}, \\begin, \\end must be properly balanced.\n"
    )
```

- [x] **Step 7: Run synthesis prompt tests**

Run: `python -m pytest tests/test_synthesis.py::test_build_synthesis_prompt_contains_topic_and_rows -v`

Expected: PASS.

- [x] **Step 8: Write failing test for `render_survey_tex_with_llm` with `StatefulMockExtractor`**

```python
from core.synthesis import render_survey_tex_with_llm


class ValidLaTeXExtractor:
    """Mock extractor that returns valid LaTeX source."""
    def __init__(self):
        self.call_count = 0
    
    def __call__(self, prompt: str) -> str:
        self.call_count += 1
        return (
            r"\documentclass{ctexart}\usepackage{booktabs}\begin{document}"
            r"\section{Abstract and Introduction}This is a test review."
            r"\section{Technical Taxonomy}Categories here."
            r"\section{Systematic Review and Deep Critique}Critique with evidence."
            r"\section{Academic Comparison Matrix}\begin{table}\begin{tabular}{lll}\toprule"
            r"Paper & Method & Limitation \\\midrule Paper A & vision & lighting \\\bottomrule"
            r"\end{tabular}\end{table}"
            r"\section{Research Gaps and Future Work}Future directions."
            r"\section{Conclusion}Summary."
            r"\end{document}"
        )


class InvalidLaTeXExtractor:
    """Mock extractor that returns LaTeX with syntax errors."""
    def __init__(self):
        self.call_count = 0
    
    def __call__(self, prompt: str) -> str:
        self.call_count += 1
        if self.call_count == 1:
            # First call: broken LaTeX
            return (
                r"\documentclass{ctexart}\begin{document}"
                r"\section{Test}Unclosed formula $x + y"
                r"\end{document}"
            )
        # Second call: fixed LaTeX
        return (
            r"\documentclass{ctexart}\begin{document}"
            r"\section{Test}Closed formula $x + y$"
            r"\end{document}"
        )


def test_render_survey_tex_with_llm_valid():
    """Valid LaTeX passes through without self-healing."""
    extractor = ValidLaTeXExtractor()
    result = render_survey_tex_with_llm(
        topic="test topic",
        rows=[],
        extraction_fn=extractor,
    )
    assert extractor.call_count == 1  # no retry needed
    assert r"\documentclass{ctexart}" in result
    assert r"\section{Abstract and Introduction}" in result


def test_render_survey_tex_with_llm_self_healing():
    """Invalid LaTeX triggers one self-healing retry."""
    extractor = InvalidLaTeXExtractor()
    result = render_survey_tex_with_llm(
        topic="test topic",
        rows=[],
        extraction_fn=extractor,
    )
    # Must have called twice (initial + 1 retry)
    assert extractor.call_count == 2
    # Result should be the fixed version
    assert r"$x + y$" in result
```

- [x] **Step 9: Implement `render_survey_tex_with_llm` and `_build_latex_healing_prompt`**

Append to `core/synthesis.py`:

```python
MAX_SYNTHESIS_RETRIES = 1


def _build_latex_healing_prompt(
    original_prompt: str,
    errors: list[str],
    broken_latex: str,
) -> str:
    """Build XML correction prompt for LaTeX self-healing."""
    error_xml = "\n".join(f"  <error>{e}</error>" for e in errors)
    return (
        original_prompt
        + "\n\n<latex-validation-errors>\n"
        + error_xml
        + "\n</latex-validation-errors>\n"
        + "<self-healing-instruction>\n"
        + "  The LaTeX source above contains syntax errors. "
        + "Fix ALL errors listed above and return ONLY the corrected LaTeX source.\n"
        + "</self-healing-instruction>"
    )


def render_survey_tex_with_llm(
    topic: str,
    rows: list[AcademicMatrixRow],
    extraction_fn: Callable[[str], str],
    progress_callback: Callable[[int, int, str, str], None] | None = None,
) -> str:
    """Generate a full Chinese LaTeX manuscript using LLM-driven synthesis.
    
    Args:
        topic: Review topic string.
        rows: Verified academic matrix rows.
        extraction_fn: LLM callable (prompt → raw response).
        progress_callback: Optional progress callback.
    
    Returns:
        Complete LaTeX manuscript string (may contain syntax errors if
        self-healing retry is exhausted — caller decides how to handle).
    """
    prompt = build_synthesis_prompt(topic, rows)
    
    for attempt in range(MAX_SYNTHESIS_RETRIES + 1):
        if progress_callback:
            state = "extracting" if attempt == 0 else "self_healing"
            detail = "Generating LaTeX manuscript..." if attempt == 0 else f"Retry {attempt}/{MAX_SYNTHESIS_RETRIES}: Fixing LaTeX syntax errors..."
            progress_callback(0, 1, state, detail)
        
        raw = extraction_fn(prompt)
        errors = validate_latex_syntax(raw)
        
        if not errors:
            if progress_callback:
                progress_callback(0, 1, "completed", "LaTeX manuscript generated successfully.")
            return raw
        
        if attempt < MAX_SYNTHESIS_RETRIES:
            prompt = _build_latex_healing_prompt(prompt, errors, raw)
    
    # Fallback: return raw LaTeX even if validation fails
    if progress_callback:
        progress_callback(0, 1, "completed",
            f"LaTeX generated with {len(errors)} unresolved syntax error(s).")
    return raw
```

- [x] **Step 10: Run all synthesis tests**

Run: `python -m pytest tests/test_synthesis.py -v`

Expected: All tests PASS (validation + prompt + self-healing).

- [x] **Step 11: Wire synthesis into `core/pipeline.py`**

Add a new function `generate_llm_artifacts` (or update `generate_artifacts` to optionally use LLM):

```python
def generate_llm_artifacts(
    topic: str,
    rows: list[AcademicMatrixRow],
    extraction_fn: Callable[[str], str],
    blocked_warnings: list[str],
    progress_callback: Callable[[int, int, str, str], None] | None = None,
) -> GeneratedArtifacts:
    """Generate artifacts with LLM-driven LaTeX synthesis instead of template.
    
    Falls back to template-based generation if synthesis produces empty output.
    """
    from core.synthesis import render_survey_tex_with_llm
    
    survey_tex = render_survey_tex_with_llm(
        topic, rows, extraction_fn, progress_callback
    )
    # Fallback: if synthesis produced empty or broken output, use template
    if not survey_tex or len(survey_tex) < 100:
        from core.templates import render_survey_tex
        survey_tex = render_survey_tex(topic, rows)
    
    return GeneratedArtifacts(
        markdown_preview=render_markdown_preview(topic, rows, blocked_warnings),
        survey_tex=survey_tex,
        matrix_table_tex=render_matrix_table_tex(rows),
        references_bib=render_bibtex(rows),
    )
```

- [x] **Step 12: Wire synthesis into `scripts/run_extraction.py`**

Modify `scripts/run_extraction.py`:

```python
# Replace generate_artifacts with generate_llm_artifacts
from core.pipeline import generate_llm_artifacts, ...
```

In the final output section:

```python
# Generate artifacts with LLM synthesis (falls back to template)
if accepted:
    artifacts = generate_llm_artifacts(
        TOPIC, accepted, extraction_fn, blocked,
        progress_callback=_console_progress_callback,
    )
else:
    artifacts = generate_artifacts(TOPIC, accepted, blocked)
```

- [x] **Step 13: Wire synthesis into `main.py` (Streamlit UI)**

Modify `main.py`:

```python
# After extraction completes and evidence filter passes:
if accepted:
    with st.spinner("Generating full-text manuscript with LLM..."):
        artifacts = generate_llm_artifacts(
            topic, accepted, extraction_fn, blocked,
            progress_callback=_streamlit_progress_callback,
        )
else:
    artifacts = generate_artifacts(topic, accepted, blocked)
```

- [x] **Step 14: Run full test suite**

Run: `python -m pytest tests -v`

Expected: All tests pass (including synthesis tests, pipeline tests, callback tests).

- [x] **Step 15: Commit**

```bash
git add core/synthesis.py tests/test_synthesis.py core/pipeline.py scripts/run_extraction.py main.py
git commit -m "feat: add llm-driven latex synthesis with stack-based validator (Task 19)"
```

---

## Phase 3 Self-Review

Spec coverage:

- `SPEC.md` §14.1-14.5 Progress Reporting Protocol: Task 18 (Unified State Callback, callback signature, state machine, injection points).
- `SPEC.md` §15.1-15.6 LLM-Driven Full-Text Synthesis: Task 19 (core/synthesis.py, validate_latex_syntax, build_synthesis_prompt, self-healing loop).
- `SPEC.md` §15.4.2-15.4.5 LaTeX validation rules: Task 19 (inline math parity, display math parity, begin/end stack pairing, brace balance).
- `SPEC.md` §15.5 Self-healing loop: Task 19 (MAX_SYNTHESIS_RETRIES=1, XML error feedback).
- SPEC.md §15.6 Testing strategy: Task 19 (validate_latex_syntax unit tests, build_synthesis_prompt tests, StatefulMockExtractor integration test).

Known implementation notes:

- The `progress_callback` is optional (`None` by default) — all existing callers remain compatible without changes.
- `render_survey_tex_with_llm` has a template-based fallback if the LLM returns empty/broken output.
- LaTeX validation is zero-dependency — no `pdflatex`, no TeX Live, no external CLI calls.
- The stack-based scanner handles escaped `\$`, `\{`, `\}` correctly, avoiding false positives.

**Deferral reason:** Lower priority than table formatting (Task 20) and interactive word control (Task 21). Zotero integration is a convenience feature that does not affect the core survey-generation quality.

---

## Phase 5: Multi-Credential Manager & Bug Fixes (Current)

**Goal:** Upgrade `core/credentials.py` to support three-field JSON credential storage (api_key, api_base, model_name) with automatic migration from the legacy single-key format. Fix 3 blocking academic-quality bugs. Add `agent_run.log` for LLM extraction monitoring.

**Architecture:** OS Keyring entry changes from plain-text `llm_api_key` to JSON `json_credentials` containing three fields. `CredentialStore.get_all()` auto-detects legacy keys and migrates. `agent.py` reads from keyring with a three-level fallback chain (keyring -> env vars -> hardcoded defaults). Bug fixes span `core/extractor.py`, `core/templates.py`, `core/synthesis.py`, `core/pipeline.py`, `scripts/run_extraction.py`.

---

### Task 22.1: Upgrade CredentialStore — JSON Single-Key + Migration Guard

**Files:**
- Modify: `core/credentials.py`
- Modify: `tests/test_credentials.py`

**Interfaces:**
- Consumes: `keyring` library (unchanged dependency)
- Produces: `CredentialStore.get_all() -> dict`, `save_all(api_key, api_base, model_name)`, `has_credentials() -> bool`, `clear_all()`

- [x] **Step 1: Write failing tests for new CredentialStore API**

Rewrite `tests/test_credentials.py` with tests for:
- `test_get_all_with_json_entry`: save_all + get_all returns three fields
- `test_get_all_migrates_legacy_key`: legacy key triggers auto-migration to JSON
- `test_get_all_no_credentials_returns_defaults`: empty keyring returns defaults
- `test_save_all_writes_json`: save_all serializes to JSON
- `test_clear_all_removes_both_entries`: clears both JSON and legacy entries
- `test_has_credentials_detects_json_entry`: has_credentials works
- `test_empty_api_key_raises_on_save`: empty key raises ValueError

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_credentials.py -v`

Expected: FAIL — old CredentialStore methods don't support new API.

- [x] **Step 3: Rewrite `core/credentials.py` with new JSON API + Migration Guard**

Replace `CredentialStore` with:
- `save_all(api_key, api_base, model_name)`: serialize to JSON, write to `json_credentials`
- `get_all() -> dict`: read JSON entry; if missing, check legacy `llm_api_key` and auto-migrate; if nothing, return defaults
- `has_credentials() -> bool`: check JSON or legacy entry
- `clear_all() -> None`: delete both entries
- Remove old `set_api_key()`, `get_api_key()`, `clear_api_key()`, `has_api_key()` methods

- [x] **Step 4: Run credential tests to verify all pass**

Run: `python -m pytest tests/test_credentials.py -v`

Expected: All 7 new tests PASS.

- [x] **Step 5: Commit**

```bash
git add core/credentials.py tests/test_credentials.py
git commit -m "feat: upgrade credential store to json multi-key with migration guard (Task 22.1) [Subagent: Sonnet] [Manual: None] [Agent count: 1]"
```

---

## Phase 8: RAG Leak Cleanup, Math Formula Support & Test De-Hardcoding (Completed)

Phase 8 consists of 3 tasks (evidence_page= leak cleanup, math formula constraints, test de-hardcoding) implemented in `docs/superpowers/plans/2026-07-10-phase8-plan.md`. All committed.

---

## Task 24: BibTeX Author Parsing Hardening (Completed)

**Files:**
- Modify: `core/extractor.py` (add `_normalize_authors` helper, wire into `parse_matrix_json`)
- Create: `tests/test_extractor_author.py` (5 tests for author normalization)

**Problem:** LLM output occasionally returns `authors` as a Python list literal (e.g., `['Paul Bergmann', 'Kilian Batzner']`) or a comma-separated string (e.g., `"Paul Bergmann, Kilian Batzner"`). Both cause `str()` to produce BibTeX-invalid author strings that crash LaTeX compilation.

**Solution:** New `_normalize_authors()` function in `core/extractor.py` that handles three formats:
- Python list (from JSON array): `['A', 'B']` → `'A and B'`
- Comma-separated string: `'A, B'` → `'A and B'`
- Already standard: `'A and B'` → unchanged

- [x] **Step 1 (RED)**: Write 5 failing tests in `tests/test_extractor_author.py`
- [x] **Step 2 (GREEN)**: Implement `_normalize_authors()` in `core/extractor.py` and wire into `parse_matrix_json`
- [x] **Step 3 (Document & Commit)**: Log to `Agent_log2.md`, update PLAN.md, commit

### Task 22.2: Upgrade agent.py — Three-Level Fallback Chain

**Files:**
- Modify: `core/agent.py`
- Modify: `tests/test_agent.py`

**Interfaces:**
- Consumes: `CredentialStore.get_all() -> dict` (from Task 22.1)
- Produces: `get_llm_agent()` with keyring → env var → hardcoded default fallback

**Three-level priority:**
1. Keyring: `store.get_all()` returns dict with `llm_api_key`, `llm_api_base`, `llm_model_name`
2. Environment variables: `OPENAI_API_KEY`, `OPENAI_API_BASE`, `LLM_MODEL_NAME`
3. Hardcoded defaults: `DEFAULT_API_BASE`, `DEFAULT_MODEL_NAME` from `core/credentials.py`

- [x] **Step 1: Write failing tests for three-level fallback**

Write tests in `tests/test_agent.py`:
- `test_agent_uses_keyring_credentials`: keyring values take priority over env vars
- `test_agent_falls_back_to_env_vars`: empty keyring uses env vars
- `test_agent_falls_back_to_defaults`: nothing configured uses hardcoded defaults
- `test_agent_injects_credentials_to_chatopenai`: verify ChatOpenAI receives correct params

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_agent.py -v`

Expected: FAIL — old agent uses `get_api_key()` which no longer exists.

- [x] **Step 3: Rewrite `core/agent.py` with three-level fallback**

Replace `get_llm_agent()`:
- Call `store.get_all()` to get credentials dict
- For each field (api_key, api_base, model_name): keyring value → env var → hardcoded default
- Remove calls to old `get_api_key()` method

- [x] **Step 4: Run agent tests to verify all pass**

Run: `python -m pytest tests/test_agent.py -v`

Expected: All new tests PASS.

- [x] **Step 5: Commit**

```bash
git add core/agent.py tests/test_agent.py
git commit -m "feat: upgrade agent.py with three-level fallback chain (Task 22.2) [Subagent: Sonnet] [Manual: None] [Agent count: 1]"
```

### Task 22.3: Upgrade main.py Sidebar — Three-Field Credential UI

**Files:**
- Modify: `main.py`

**Interfaces:**
- Consumes: `CredentialStore.save_all()`, `get_all()`, `has_credentials()`, `clear_all()`
- Consumes: `DEFAULT_API_BASE`, `DEFAULT_MODEL_NAME` from `core/credentials.py`

- [x] **Step 1: Update `main.py` sidebar**

Replace old single-key credential UI with three-field form:
- Show credential status via `has_credentials()`
- Three text inputs: API Key (password masked), API Base (shows default), Model Name (shows default)
- "Save Credentials" button calls `save_all(api_key, api_base, model_name)`
- "Clear Credentials" button calls `clear_all()`
- Remove calls to old `has_api_key()`, `set_api_key()`, `clear_api_key()`

- [x] **Step 2: Run app syntax check**

Run: `python -c "import ast; ast.parse(open('main.py').read()); print('main.py syntax OK')"`

Expected: syntax OK.

- [x] **Step 3: Run full test suite**

Run: `python -m pytest tests -v --ignore=tests/test_agent.py`

Expected: All credential and pipeline tests PASS.

- [x] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: add three-field credential UI to streamlit sidebar (Task 22.3) [Subagent: Sonnet] [Manual: None] [Agent count: 1]"
```

### Task 22.4: Fix Bug 1 — Hollow Content Fallback

**Files:**
- Modify: `scripts/run_extraction.py`
- Modify: `core/pipeline.py`
- Modify: `core/synthesis.py`

**Symptoms:** Batch-extraction produced `survey_draft.tex` where all sections except the Academic Comparison Matrix contained only hollow placeholder text (e.g., "本节依据论文方法..."), never the LLM-synthesized quality Chinese prose.

**Root cause:** `scripts/run_extraction.py` never called `generate_llm_artifacts` (the LLM-driven synthesis path). Also `has_api_key()` was used instead of `has_credentials()` after Task 22.1 removed the old API.

**Fixes:**
1. `scripts/run_extraction.py`:
   - Replace `store.has_api_key()` → `store.has_credentials()` (line 100)
   - Ensure `extraction_fn` is passed to `generate_llm_artifacts`
2. `core/pipeline.py`:
   - In `generate_llm_artifacts`, add `print("⚠️ LLM synthesis returned empty or invalid, falling back to template.")` when falling back
3. `core/synthesis.py`:
   - In `render_survey_tex_with_llm`, add `print(f"[LLM] Entering synthesis...")` at entry
   - At exit/success, print `print(f"[LLM] Generated {len(raw)} chars: {raw[:200]}")`

- [x] **Step 1: Fix `scripts/run_extraction.py`**
- [x] **Step 2: Fix `core/pipeline.py` with fallback warning**
- [x] **Step 3: Fix `core/synthesis.py` with LLM logging**
- [x] **Step 4: Run full test suite**
- [x] **Step 5: Commit**

### Task 22.5: Fix Bug 2 — Giant English Table

**Files:**
- Modify: `core/extractor.py`
- Modify: `core/synthesis.py`
- Modify: `core/templates.py`

**Symptoms:** Exported `matrix_table.tex` had oversized tables with long English paragraphs in cells, breaking PDF layout. Poor readability.

**Fixes:**
1. `core/extractor.py` — `build_extraction_prompt`: append CRITICAL rule — method/limitation fields MUST be Chinese, ≤20 chars, concise academic summary
2. `core/synthesis.py` — `build_synthesis_prompt`: same CRITICAL rule for table cells
3. `core/templates.py` — `render_matrix_table_tex`:
   - Inject `\footnotesize` before tabularx
   - Inject `\setlength{\tabcolsep}{4pt}`
   - Use `>{\raggedright\arraybackslash}X` for all 4 X columns instead of plain `X`
   - Keep `\noindent` (already present)

- [x] **Step 1: Add prompt constraints in `core/extractor.py`**
- [x] **Step 2: Add prompt constraints in `core/synthesis.py`**
- [x] **Step 3: Add table micro-typography in `core/templates.py`**
- [x] **Step 4: Run full test suite**
- [x] **Step 5: Commit**

### Task 22.6: Fix Bug 3 — Key Metric Missing

**Files:**
- Modify: `core/extractor.py`
- Modify: `core/templates.py`

**Symptoms:** Key Metric column showed all "missing" values instead of actual data.

**Fixes:**
1. `core/extractor.py` — `build_extraction_prompt`: add semantic descriptions for each domain field key (e.g., 'sensor: the type of sensor used')
2. `core/templates.py` — `render_matrix_table_tex`: strengthen metric fallback to filter out "missing"/empty values before falling back to innovation

- [x] **Step 1: Add semantic descriptions in `core/extractor.py`**
- [x] **Step 2: Fix metric fallback in `core/templates.py`**
- [x] **Step 3: Run full test suite**
- [x] **Step 4: Commit**
### Task 22.7: Add `agent_run.log` Logging System

**Files:**
- Modify: `.gitignore`
- Modify: `docs/SPEC.md`
- Create: `docs/superpowers/specs/2026-07-09-phase-5-credentials-bugfix-design.md`
- Move: `docs/Agent_log.md` → `data/logs/Agent_log.md` (full backup archive)
- Move: `docs/Agent_log1.md` → `data/logs/Agent_log1.md` (early task archive)
- Move: `docs/Agent_log2.md` → `data/logs/Agent_log2.md` (current dev log)

**Log Architecture:**

```
data/logs/
├── Agent_log.md        # Complete backup archive (Tasks 1–789, all sessions)
├── Agent_log1.md       # Early task archive (Tasks 0–15)
├── Agent_log2.md       # Current development log (Tasks 16+)
└── agent_run.log       # Runtime LLM extraction log (auto-generated)
```

**Changes:**
1. `.gitignore`: Remove blanket `data/` ignore, replace with `data/input_pdfs/`, `data/output_docs/`
2. Move log files to `data/logs/` with correct naming
3. Update `docs/SPEC.md` with Phase 5 and logging section (§19)
4. Create `docs/superpowers/specs/2026-07-09-phase-5-credentials-bugfix-design.md`

- [x] **Step 1: Move log files and update naming**
- [x] **Step 2: Update `.gitignore`**
- [x] **Step 3: Update `docs/SPEC.md` with Phase 5 section**
- [x] **Step 4: Create design spec document**
- [x] **Step 5: Commit**
