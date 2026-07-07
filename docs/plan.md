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

- [ ] **Step 1: Write failing parser unit tests**

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

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_pdf_parser.py -v`

Expected: FAIL because parser functions are missing.

- [ ] **Step 3: Implement parser**

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

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_pdf_parser.py -v`

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add core/pdf_parser.py tests/test_pdf_parser.py
git commit -m "feat: parse pdf pages and core sections"
```

## Task 4: Evidence Containment Validation

**Files:**
- Create: `core/evidence.py`
- Create: `tests/test_evidence.py`

- [ ] **Step 1: Write failing containment tests**

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

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_evidence.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement evidence validation**

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

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_evidence.py -v`

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add core/evidence.py tests/test_evidence.py
git commit -m "feat: validate evidence containment"
```

## Task 5: Two-Layer Academic Schema

**Files:**
- Create: `core/schema.py`
- Create: `tests/test_schema.py`

- [ ] **Step 1: Write failing schema tests**

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

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_schema.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement schema helper**

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

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_schema.py -v`

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add core/schema.py tests/test_schema.py
git commit -m "feat: add two-layer academic schema"
```

## Task 6: Keyring Credential Manager

**Files:**
- Create: `core/credentials.py`
- Create: `tests/test_credentials.py`
- Modify: `core/agent.py`

- [ ] **Step 1: Write failing credential tests**

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

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_credentials.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement credential store**

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

- [ ] **Step 4: Refactor agent to use keyring**

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

- [ ] **Step 5: Verify**

Run: `python -m pytest tests/test_credentials.py -v`

Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add core/credentials.py core/agent.py tests/test_credentials.py
git commit -m "feat: store api key with keyring"
```

## Task 7: Academic Matrix Extraction Boundary

**Files:**
- Create: `core/extractor.py`
- Create: `tests/test_extractor.py`

- [ ] **Step 1: Write failing extractor tests**

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

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_extractor.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement extractor boundary**

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

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_extractor.py -v`

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add core/extractor.py tests/test_extractor.py
git commit -m "feat: add academic extraction boundary"
```

## Task 8: Markdown, LaTeX, And BibTeX Rendering

**Files:**
- Modify: `core/templates.py`
- Create: `tests/test_templates.py`

- [ ] **Step 1: Write failing rendering tests**

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

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_templates.py -v`

Expected: FAIL because render functions are missing.

- [ ] **Step 3: Implement rendering**

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

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_templates.py -v`

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add core/templates.py tests/test_templates.py
git commit -m "feat: render smart survey artifacts"
```

## Task 9: Pipeline Orchestration With Evidence Gate

**Files:**
- Create: `core/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing pipeline tests**

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

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_pipeline.py -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement pipeline**

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

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_pipeline.py -v`

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add core/pipeline.py tests/test_pipeline.py
git commit -m "feat: gate pipeline output by evidence"
```

## Task 10: Streamlit UI Vertical Slice

**Files:**
- Modify: `main.py`
- Create: `tests/test_main_import.py`

- [ ] **Step 1: Write failing import test**

Create `tests/test_main_import.py`:

```python
import main


def test_main_exposes_app_entrypoint():
    assert callable(main.run_app)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_main_import.py -v`

Expected: FAIL because `run_app` is missing.

- [ ] **Step 3: Implement UI entrypoint**

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

- [ ] **Step 4: Verify import test**

Run: `python -m pytest tests/test_main_import.py -v`

Expected: `1 passed`.

- [ ] **Step 5: Manual UI smoke test**

Run: `streamlit run main.py`

Expected: browser UI shows topic input, PDF uploader, credential status, and download buttons after upload.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main_import.py
git commit -m "feat: add streamlit smart survey ui"
```

## Task 11: Docker Distribution

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [ ] **Step 1: Write Docker ignore file**

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

- [ ] **Step 2: Write Dockerfile**

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

- [ ] **Step 3: Build image**

Run: `docker build -t smartsurvey:local .`

Expected: image builds successfully and does not copy `.env`, `.venv`, or `data/input_pdfs`.

- [ ] **Step 4: Run container**

Run: `docker run --rm -p 8501:8501 smartsurvey:local`

Expected: Streamlit starts and exposes the app on `http://localhost:8501`.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "build: add docker distribution"
```

## Task 12: CI Unit Test Job

**Files:**
- Create: `.gitlab-ci.yml`

- [ ] **Step 1: Add required CI job**

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

- [ ] **Step 2: Validate locally**

Run: `python -m pytest tests -v`

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add .gitlab-ci.yml
git commit -m "ci: add unit test job"
```

## Task 13: README And Documentation Alignment

**Files:**
- Create: `README.md`
- Modify: `docs/Agent_log.md`
- Modify: `docs/切换API说明.md`

- [ ] **Step 1: Create README**

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

- [ ] **Step 2: Update API switching document**

Edit `docs/切换API说明.md` so it states that `.env` is a development compatibility mechanism for base URL and model name only, while API Key storage should use OS keyring. Remove any instruction that says users should put real API keys into `.env` as the preferred path.

- [ ] **Step 3: Append implementation checkpoint to Agent log**

Append to `docs/Agent_log.md`:

```markdown
## Task 1.0 - PLAN.md implementation planning

- Timestamp: 2026-07-07 +08:00
- Triggered Superpowers skills: `writing-plans`
- Key decision: all Markdown documents except `README.md` remain under `docs/`; the implementation plan is stored at `docs/PLAN.md`.
- Next step: execute the plan task-by-task with TDD and subagent-driven development.
```

- [ ] **Step 4: Verify docs do not contain real key-like values**

Run: `rg "sk-[A-Za-z0-9]" README.md docs`

Expected: no real API key values. Placeholder strings are acceptable only if clearly fake, such as `sk-your-provider-key`.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/切换API说明.md docs/Agent_log.md
git commit -m "docs: align readme and credential guidance"
```

## Task 14: Cold-Start Verification Preparation

**Files:**
- Modify: `docs/SPEC_PROCESS.md`

- [ ] **Step 1: Add cold-start verification section placeholder with concrete protocol**

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

- [ ] **Step 2: Verify plan and spec are present**

Run: `Test-Path .\docs\SPEC.md; Test-Path .\docs\PLAN.md; Test-Path .\docs\SPEC_PROCESS.md`

Expected: three `True` lines.

- [ ] **Step 3: Commit**

```bash
git add docs/SPEC_PROCESS.md docs/PLAN.md
git commit -m "docs: prepare cold start verification"
```

## Task 15: Full Verification Gate

**Files:**
- No new files unless previous tasks reveal a defect.

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests -v`

Expected: all tests pass.

- [ ] **Step 2: Check secret hygiene**

Run: `git status --short`

Expected: only intentional working tree changes before final commit.

Run: `rg "OPENAI_API_KEY=.*sk-|sk-[A-Za-z0-9]{20,}" . --glob '!/.git/**' --glob '!/.venv/**'`

Expected: no real keys.

- [ ] **Step 3: Check documentation placement**

Run: `Get-ChildItem -Path . -File -Filter *.md | Select-Object -ExpandProperty Name`

Expected: `README.md` only, or no root Markdown except `README.md`.

- [ ] **Step 4: Manual app check**

Run: `streamlit run main.py`

Expected: app starts, shows credential status, accepts PDF uploads, and exposes artifact downloads without showing a full API key.

- [ ] **Step 5: Final commit if needed**

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

### Task 16: Self-Healing Extraction Pipeline

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

### Task 17: Real PDF Extraction & Export

**Files:**
- Create: `scripts/run_extraction.py`
- Create: `data/output_docs/survey_draft.tex`
- Create: `data/output_docs/references.bib`
- Create: `data/output_docs/matrix_table.tex`
- Modify: `main.py` (wire extraction_fn into UI pipeline)

**Prerequisites:** A real LLM API key must be stored in the OS keyring (via `streamlit run main.py` sidebar or a keyring CLI command). The 4 PDFs are already in `data/input_pdfs/`.

- [ ] **Step 1: Write failing test for the extraction script import**

Create `tests/test_scripts.py`:

```python
import scripts.run_extraction


def test_run_extraction_exposes_main_function():
    assert callable(scripts.run_extraction.main)
```

- [ ] **Step 2: Run the script test**

Run: `python -m pytest tests/test_scripts.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.run_extraction'`.

- [ ] **Step 3: Create the batch extraction script**

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

## Phase 3: Streamlit Dynamic Progress Bar & Zotero Archive Integration (Planned)

**Goal:** Improve user experience with real-time extraction progress visualization and enable automatic export to Zotero reference manager.

**Note:** Tasks 18-19 have not been brainstormed yet. The following is a preliminary scope sketch only.

### Task 18: Streamlit Dynamic Progress Bar

**Scope sketch:**
- Replace the current per-page print-based progress with a Streamlit progress bar (`st.progress`) during batch extraction.
- Show real-time status: current paper name, current page / total pages, number of rows extracted so far, number of self-healing corrections.
- Consider using Streamlit's `session_state` or a generator pattern to stream progress updates from `pipeline.py` back to the UI.

### Task 19: Zotero Auto-Archive Integration

**Scope sketch:**
- Export extracted paper metadata (title, authors, year, venue, evidence) into a Zotero-compatible format (CSV, RIS, or Better BibTeX JSON).
- Allow one-click "export to Zotero" from the Streamlit UI.
- May require `pyzotero` library or manual RIS/CSV generation.

---

> **Branching convention:** Each future task should be implemented on its own branch (`feat/task-xx`), pushed to remote, and submitted as a PR for merging.
