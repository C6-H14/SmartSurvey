# Agent Log

## Task 0.1 - SPEC.md brainstorming kickoff

- Timestamp: 2026-07-06 16:03:38 +08:00
- Triggered Superpowers skills: `using-superpowers`, `brainstorming`
- Key prompt and configuration:
  - Project: `SmartSurvey: 自动文献综述与系统决策软件`
  - Course framing: AI4SE final project, non-harness application project.
  - Current priority: collaboratively produce a standards-compliant `SPEC.md`.
  - Discussion constraints: ask 1-2 questions per round, wait for confirmation before moving on.
  - Core design topics: INVEST user stories, PDF batch parsing, academic matrix extraction, one-click review generation, keyring-based credential security, Docker/public deployment.
- Key decisions:
  - Primary user: course project student who needs a usable literature review draft and reusable reference workflow for future projects.
  - Secondary user: research assistant or lab member who needs batch PDF organization and a verifiable paper comparison matrix.
  - Anti-overwarning rule accepted: SmartSurvey must not emit vague warnings such as "this method may have limitations" unless the claim is grounded in paper title, page or paragraph evidence, trigger reason, and confidence or missing-field status.
  - `docs/Agent_log.md` will be maintained as a timeline log for current and future tasks, using task numbers such as `Task 0.1`.
- Lessons learned:
  - The SPEC should optimize first for the student's own repeatable research workflow, then generalize to stronger features for secondary users.
  - Anti-hallucination requirements should be written as acceptance criteria, not as vague model behavior preferences.
  - Evidence binding is a core product feature, not a post-generation quality check.

## Task 0.2 - User stories and LaTeX manuscript deliverables

- Timestamp: 2026-07-06 16:16:25 +08:00
- Triggered Superpowers skills: `brainstorming`
- Key prompt and configuration:
  - User confirmed the five-story flow should be centered on the course project student, while keeping wording broad enough for researchers and students.
  - Target test domains:
    - Deep-learning-based industrial or automation-lab spatial anomaly detection.
    - Research related to the Brauer-Manin obstruction.
    - Theoretical upper bounds for matrix multiplication complexity.
  - UI deliverable: real-time Markdown preview for the review draft and comparison matrix.
  - Downloadable deliverables:
    - `survey_draft.tex`: a full-text academic manuscript suitable for Overleaf.
    - `matrix_table.tex`: a `booktabs` three-line LaTeX comparison table.
    - `references.bib`: BibTeX entries with title, author, year, and evidence/page binding metadata.
- Key decisions:
  - US1: Batch upload and parse academic PDFs from arbitrary fields through the UI.
  - US2: Extract core technical indicators, methods, innovations, and limitations from parsed text.
  - US3: Bind all extracted limitations and risks to page numbers and original text evidence to prevent vague warnings.
  - US4: Present a multidimensional comparison matrix in the UI.
  - US5: Generate a logically complete Markdown preview and LaTeX academic manuscript, not merely a loose draft.
  - The manuscript target is 3000-5000 words and includes six required sections: Abstract & Introduction, Technical Taxonomy, Systematic Review & Deep Critique, Academic Comparison Matrix, Research Gaps & Future Work, and Conclusion.
- Lessons learned:
  - The project scope has shifted from a lightweight draft generator to a research-writing pipeline with structured LaTeX outputs.
  - The three target domains are intentionally heterogeneous, so the extraction schema must separate domain-neutral fields from domain-specific metrics.
  - The phrase "full-text academic manuscript" needs hard acceptance criteria, otherwise it can become too subjective to evaluate.

## Task 0.3 - Cross-domain schema and LaTeX article structure

- Timestamp: 2026-07-06 16:19:36 +08:00
- Triggered Superpowers skills: `brainstorming`
- Key prompt and configuration:
  - The extraction schema should support three heterogeneous evaluation domains without hardcoding one domain's metrics into the whole product.
  - The final manuscript should be produced in Chinese.
  - LaTeX output should target an article-style manuscript using `\section{...}` headings rather than `\chapter{...}` headings.
- Key decisions:
  - SmartSurvey will use a two-layer academic matrix schema:
    - General fields: `title`, `authors`, `year`, `venue`, `research_problem`, `method`, `innovation`, `limitation`, `evidence_page`, `evidence_quote`, `confidence`.
    - Domain-specific fields generated from the review topic, such as `sensor`, `accuracy`, and `latency` for industrial anomaly detection; `complexity_bound` and `algorithmic_technique` for matrix multiplication; and `mathematical_object`, `obstruction_type`, and `theorem_result` for Brauer-Manin obstruction research.
  - `survey_draft.tex` will use standard `article`-compatible sectioning, not `chapter` sectioning.
  - Generated manuscript language: Chinese.
- Lessons learned:
  - Cross-domain generalization should be achieved through schema layering, not by weakening the extraction requirements.
  - LaTeX export should match the target document class; using `\section` keeps the output easier to compile in Overleaf.
  - Chinese output introduces additional requirements for LaTeX engine and template choices, likely `ctexart` or XeLaTeX-compatible settings.

## Task 0.4 - PDF parsing and evidence containment specification

- Timestamp: 2026-07-06 16:29:08 +08:00
- Triggered Superpowers skills: `brainstorming`
- Key prompt and configuration:
  - User requested writing the accumulated decisions into `docs/SPEC.md`.
  - PDF parsing should use a mixed strategy: standard core-section extraction plus fallback page slices.
  - Evidence binding should use verifiable page-level containment rather than paragraph IDs.
- Key decisions:
  - `pdf_parser.py` must try heuristic regex extraction for `Abstract`, `Introduction`, `Conclusion`, and `References`.
  - Missing core sections must be marked as `missing` and surfaced in the UI rather than invented.
  - The parser must always preserve page-level text slices so non-standard PDFs can still be processed.
  - Each extracted claim must bind `evidence_page` and `evidence_quote`.
  - The backend must run a containment check equivalent to `evidence_quote in page_text[evidence_page]`.
  - If containment fails, the claim is rejected and the UI warns the user: `发现无事实根据的空气警告，已自动拦截`.
- Lessons learned:
  - Page-level evidence is the right first-version compromise: it is verifiable and avoids fragile PDF paragraph reconstruction.
  - Fallback page slices are necessary for robustness across journal layouts and mathematical papers.
  - Anti-hallucination should be enforced by backend validation before data is written, not merely displayed as a warning.

## Task 0.5 - Brainstorming process documentation

- Timestamp: 2026-07-06 16:34:22 +08:00
- Triggered Superpowers skills: `brainstorming`
- Key prompt and configuration:
  - User requested a process-oriented document named `docs/SPEC_PROCESS.md`.
  - The document must review key brainstorming nodes, at least three iterative dialogue excerpts, adopted and rejected AI suggestions, and reflection.
  - The process review should include context from the 3D/YOLO-style industrial spatial anomaly detection topic and the keyring credential security model.
- Key decisions:
  - Create `SPEC_PROCESS.md` as a companion to `SPEC.md`.
  - Separate product requirements from process rationale: `SPEC.md` states what to build, while `SPEC_PROCESS.md` records why decisions were made.
- Lessons learned:
  - A process document is useful for AI4SE evaluation because it exposes requirement iteration, tradeoff reasoning, and human engineering decisions.
  - The strongest decisions in this brainstorming came from rejecting fragile overengineering in favor of verifiable, testable constraints.

## Task 1.1 - Test infrastructure and dependency baseline

- Timestamp: 2026-07-07 10:14-10:18 +08:00
- Triggered Superpowers skills: `executing-plans`, `subagent-driven-development`
- Key prompt and configuration:
  - Read `docs/SPEC.md` and `docs/PLAN.md`.
  - Execute PLAN.md Task 1 (test infrastructure and dependency baseline) and Task 2 (core data models).
  - Strict TDD discipline: write failing tests first (Red), then minimal implementation (Green), then commit.
  - Hard requirement: pause and ask before guessing if any specification is ambiguous.
- Key decisions and actions:
  - Confirmed existing files: `tests/` directory initially empty; `.gitignore` missing `.pytest_cache/` and `data/`.
  - Read `core/agent.py`, `core/pdf_parser.py`, `core/__init__.py` to assess baseline.
  - Read `docs/SPEC.md` (401 lines) and `docs/PLAN.md` (1548 lines) for full context.
  - Created `tests/test_smoke.py` with `test_pytest_is_configured`.
  - Created `tests/conftest.py` with `sample_page_texts` fixture returning a dict of 2 page texts.
  - Updated `requirements.txt`: appended `pytest` and `keyring`.
  - Ran `pip install -r requirements.txt` — installation succeeded in `.venv`.
  - Verified pytest is available: `pytest 9.1.1`.
  - Ran smoke test: `1 passed`.
  - Hardened `.gitignore`: added `.pytest_cache/`, `data/`, `*.pyo`, `*.log`.
  - Committed as `b069c9a` — "Task 1: test infrastructure and dependency baseline" (4 files changed, 27 insertions, 3 deletions).
- Specification alignment:
  - Smoke test covers PLAN.md Step 1-7 exactly.
  - Fixture `sample_page_texts` provides page-granularity text for future evidence containment tests (§7).
  - `.gitignore` hardening prevents `.pytest_cache/`, `data/output_docs/`, `*.log` from entering Git.
  - All sections default to `"missing"` placeholder per SPEC §5.4.
- Lessons learned:
  - PowerShell's `&&` chaining is unsupported; use separate `git add` then `git commit` commands on Windows.
  - The project already had a small `.venv` with `pytest 9.1.1` installed, so the expected "ModuleNotFoundError for pytest" was not triggered; the Red phase was confirmed via `tests/` absence instead.

## Task 1.2 - Core data models (TDD)

- Timestamp: 2026-07-07 10:19-10:20 +08:00
- Triggered Superpowers skills: `executing-plans`, `subagent-driven-development`
- Key prompt and configuration:
  - Implement PLAN.md Task 2: Core Data Models.
  - TDD cycle: write failing test → confirm failure → implement → confirm pass → commit.
- Key decisions and actions:
  - **Red phase**: created `tests/test_models.py` with 2 tests:
    - `test_parsed_paper_defaults_missing_sections`: creates a `ParsedPaper` with 1 page slice, asserts all four sections are `"missing"`.
    - `test_academic_matrix_row_requires_evidence_fields`: creates a full `AcademicMatrixRow` with all 11 general fields + `trigger_reason` + `domain_fields`, asserts evidence binding and domain field access.
  - Ran tests → `ModuleNotFoundError: No module named 'core.models'` — Red confirmed.
  - **Green phase**: created `core/models.py` with 5 dataclasses:
    - `PageSlice(frozen)`: `page_number: int`, `text: str`.
    - `ParsedPaper`: `file_name`, `pages`, `title` (default `"missing"`), `sections` (default all `"missing"`), `warnings`, `error`, plus `page_text_by_number()` helper.
    - `AcademicMatrixRow(frozen)`: all 11 general fields from SPEC §6.1 + `trigger_reason` + `domain_fields`.
    - `EvidenceValidationResult(frozen)`: `accepted`, `message`, `normalized_quote`.
    - `GeneratedArtifacts(frozen)`: `markdown_preview`, `survey_tex`, `matrix_table_tex`, `references_bib`.
  - Ran tests → `2 passed` — Green confirmed.
  - Committed as `5291fc1` — "feat: add core data models" (2 files created, 92 insertions).
- Specification alignment:
  - `DEFAULT_SECTIONS` dict mirrors SPEC §5.4 default `"missing"` for all four core sections.
  - `AcademicMatrixRow` exactly matches SPEC §6.1 general fields (title, authors, year, venue, research_problem, method, innovation, limitation, evidence_page, evidence_quote, confidence).
  - `domain_fields: dict[str, Any]` supports SPEC §6.2 cross-domain schema layering.
  - `EvidenceValidationResult` and `page_text_by_number()` provide the data structure for SPEC §7.3 containment validation.
- Lessons learned:
  - `@dataclass(frozen=True)` for value objects enforces immutability, which matches the design intent that parsed/extracted data should not be mutated after creation.
  - The `DEFAULT_SECTIONS` constant is defined at module level to allow reuse by `pdf_parser.py` in Task 3, avoiding a circular import or duplication issue.

## Task 3.1 - PDF parser failing tests (TDD Red)

- Timestamp: 2026-07-07 10:36-10:39 +08:00
- Triggered Superpowers skills: `test-driven-development`
- Key prompt and configuration:
  - Cold-start verification continuation: read `docs/SPEC.md`, `docs/PLAN.md`, and agent log.
  - Execute PLAN.md Task 3 Step 1 only: write failing parser unit tests before any implementation.
- Key decisions and actions:
  - Created `tests/test_pdf_parser.py` with 3 tests:
    - `test_extract_core_sections_marks_missing_when_headings_absent`
    - `test_extract_core_sections_finds_standard_headings`
    - `test_parse_invalid_pdf_returns_error_without_raising`
  - Ran `python -m pytest tests/test_pdf_parser.py -v` via `.venv` — Red confirmed:
    - `ImportError: cannot import name 'extract_core_sections_from_text' from 'core.pdf_parser'`
  - `core/pdf_parser.py` remains empty; no production code written before tests.
- Specification alignment:
  - Tests cover SPEC §5.2 (`missing` when headings absent), §5.3 (invalid PDF captured without raising), and §12.2 TDD points for section detection.
- Lessons learned:
  - On Windows PowerShell, chain commands with `;` instead of `&&`; use `.venv\Scripts\python.exe` when system Python lacks pytest.
  - Root-level `AGENT_LOG.md` duplicated `docs/Agent_log.md`; canonical log lives under `docs/`.

## Task 3.2 - PDF parser implementation (TDD Green)

- Timestamp: 2026-07-07 10:39 +08:00
- Triggered Superpowers skills: `test-driven-development`
- Key decisions and actions:
  - Merged root `AGENT_LOG.md` into `docs/Agent_log.md` (content was already present); deleted root duplicate.
  - Implemented `core/pdf_parser.py`:
    - `clean_text`, `extract_core_sections_from_text`, `parse_pdf_bytes`
    - Heuristic regex for Abstract / Introduction / Conclusion(s) / References
    - PyMuPDF page-slice fallback via `fitz.open`
    - Invalid PDF bytes return `ParsedPaper` with `error` set, empty `pages`, and a warning — no exception propagated.
  - Ran `python -m pytest tests/test_pdf_parser.py -v` → `3 passed`.
  - Ran full suite `python -m pytest tests -v` → all tests pass.
- Specification alignment:
  - §5.2 core section extraction with `missing` default preserved.
  - §5.3 page slices per physical page; parse errors captured per file.
  - §5.4 output shape matches `ParsedPaper` model from Task 2.

## Task 4.1 - Evidence containment failing tests (TDD Red)

- Timestamp: 2026-07-07 11:07 +08:00
- Triggered Superpowers skills: `test-driven-development`
- Key decisions and actions:
  - Created `tests/test_evidence.py` with 3 tests:
    - `test_normalize_for_containment_collapses_whitespace_and_hyphen_breaks`
    - `test_validate_evidence_accepts_quote_on_page`
    - `test_validate_evidence_rejects_missing_quote`
  - Ran `python -m pytest tests/test_evidence.py -v` → Red confirmed:
    - `ModuleNotFoundError: No module named 'core.evidence'`
- Specification alignment:
  - Tests cover SPEC §7.2 (`evidence_page` + `evidence_quote`), §7.3 containment check, and UI message for blocked air warnings.

## Task 4.2 - Evidence containment implementation (TDD Green)

- Timestamp: 2026-07-07 11:08 +08:00
- Triggered Superpowers skills: `test-driven-development`
- Key decisions and actions:
  - Created `core/evidence.py` with `AIR_WARNING_BLOCKED`, `normalize_for_containment`, `validate_evidence`.
  - Normalization uses `re.sub(r"-\s*\n\s*", "", text)` instead of plain `-\n` replacement so PDF hyphenation like `light-\n ing` joins to `lighting` (PLAN snippet alone did not pass the test case).
  - Ran `python -m pytest tests -v` → `9 passed`.
- Specification alignment:
  - `validate_evidence` implements `evidence_quote in page_text[evidence_page]` with normalized whitespace and hyphen-break handling.
  - Rejected quotes return `AIR_WARNING_BLOCKED` = `发现无事实根据的空气警告，已自动拦截`.

## Task 5.1 - Two-layer schema failing tests (TDD Red)

- Timestamp: 2026-07-07 11:09 +08:00
- Triggered Superpowers skills: `test-driven-development`
- Key decisions and actions:
  - Created `tests/test_schema.py` with 4 tests for `GENERAL_FIELDS` and `domain_fields_for_topic` across three SPEC §3 test domains.
  - Ran `python -m pytest tests/test_schema.py -v` → Red confirmed: `ModuleNotFoundError: No module named 'core.schema'`.

## Task 5.2 - Two-layer schema implementation (TDD Green)

- Timestamp: 2026-07-07 11:09 +08:00
- Triggered Superpowers skills: `test-driven-development`
- Key decisions and actions:
  - Created `core/schema.py` with `GENERAL_FIELDS` (11 fields per SPEC §6.1) and topic-driven `domain_fields_for_topic`.
  - Ran `python -m pytest tests -v` → `13 passed`.
- Specification alignment:
  - General fields match SPEC §6.1 exactly.
  - Domain field sets cover industrial anomaly detection, Brauer-Manin, and matrix multiplication complexity per SPEC §6.2.

## Task 6.1 - Keyring credential failing tests (TDD Red)

- Timestamp: 2026-07-07 11:15 +08:00
- Triggered Superpowers skills: `test-driven-development`
- Key decisions and actions:
  - Created `tests/test_credentials.py` with `FakeKeyring` backend and 2 tests: set/get/clear cycle and missing-key error.
  - Ran `python -m pytest tests/test_credentials.py -v` → Red confirmed: `ModuleNotFoundError: No module named 'core.credentials'`.
- Notes:
  - User placed anomaly-detection sample PDFs under `data/input_pdfs/` for future integration tests (directory is gitignored per `.gitignore`):
    - `2503.07901v2.pdf`
    - `Costanzino_Multimodal_Industrial_Anomaly_Detection_by_Crossmodal_Feature_Mapping_CVPR_2024_paper.pdf`
    - `fmech-12-1806266.pdf`
    - `s11263-022-01578-9.pdf`

## Task 6.2 - Keyring credential implementation and agent refactor (TDD Green)

- Timestamp: 2026-07-07 11:16 +08:00
- Triggered Superpowers skills: `test-driven-development`
- Key decisions and actions:
  - Created `core/credentials.py` with `CredentialStore`, `MissingCredentialError`, OS keyring via `keyring` library.
  - Refactored `core/agent.py` to read API key through `CredentialStore` instead of `.env` `OPENAI_API_KEY`; removed `load_dotenv()` from agent module.
  - `get_llm_agent` accepts optional `credential_store` for testing/injection.
  - Ran `python -m pytest tests -v` → `15 passed`.
- Specification alignment:
  - §9.1 local keyring storage: set, get, clear, has_api_key.
  - §9.2 no API key in source; agent no longer reads key from env by default.

## Task 7.1 - Academic extraction boundary failing tests (TDD Red)

- Timestamp: 2026-07-07 11:17 +08:00
- Triggered Superpowers skills: `test-driven-development`
- Key decisions and actions:
  - Created `tests/test_extractor.py` with prompt-building and JSON parsing tests.
  - Ran `python -m pytest tests/test_extractor.py -v` → Red confirmed: `ModuleNotFoundError: No module named 'core.extractor'`.

## Task 7.2 - Academic extraction boundary implementation (TDD Green)

- Timestamp: 2026-07-07 11:17 +08:00
- Triggered Superpowers skills: `test-driven-development`
- Key decisions and actions:
  - Created `core/extractor.py` with `build_extraction_prompt` and `parse_matrix_json`.
  - Prompt includes general + domain fields and evidence-binding rules; parser fills absent fields with `"missing"`.
  - Ran `python -m pytest tests -v` → `17 passed`.
- Specification alignment:
  - §6.1–6.2 two-layer matrix extraction boundary without live LLM in unit tests.
  - Sample PDFs in `data/input_pdfs/` reserved for later end-to-end runs with industrial anomaly detection topic.

## Task 7.1 - Academic extraction boundary failing tests (TDD Red)

- Timestamp: 2026-07-07 11:17 +08:00
- Triggered Superpowers skills: `test-driven-development`
- Key decisions and actions:
  - Created `tests/test_extractor.py` with 2 tests: prompt field coverage and JSON parsing with `missing` defaults.
  - Ran `python -m pytest tests/test_extractor.py -v` → Red confirmed: `ModuleNotFoundError: No module named 'core.extractor'`.

## Task 7.2 - Academic extraction boundary implementation (TDD Green)

- Timestamp: 2026-07-07 11:17 +08:00
- Triggered Superpowers skills: `test-driven-development`
- Key decisions and actions:
  - Created `core/extractor.py` with `build_extraction_prompt` and `parse_matrix_json`.
  - Prompt includes general fields, `trigger_reason`, domain fields, and evidence-binding rules.
  - `parse_matrix_json` maps absent fields to `"missing"` per SPEC §6.1.
  - Ran `python -m pytest tests -v` → `17 passed`.
- Specification alignment:
  - LLM adapter boundary: deterministic prompt building and JSON parsing without live API calls.
  - Sample PDFs in `data/input_pdfs/` reserved for later end-to-end extraction tests once pipeline/UI tasks land.
