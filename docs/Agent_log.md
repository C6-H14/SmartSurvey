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
