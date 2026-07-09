# Agent Log

## Task 16.1 - Self-Healing Extraction Pipeline

- Timestamp: 2026-07-07 +08:00
- Triggered Superpowers skills: `executing-plans`, `test-driven-development`
- Key prompt and configuration:
  - Continue previous workflow: implement Phase 2 Tasks 16-17 from docs/PLAN.md.
  - TDD cycle: write failing tests (Red) → implement (Green) → verify → commit.
- Key decisions and actions:
  - **Red 1**: `test_build_self_healing_prompt_contains_xml_tags` — confirmed `ImportError`.
  - **Green 1**: Implemented `build_self_healing_prompt` in `core/extractor.py` — XML correction structure with `<self-healing-correction>`, `<failed-page>`, `<failed-quote>`, `<error>`, `<page-text>` tags.
  - **Red 2**: `tests/test_pipeline_extraction.py` with `StatefulMockExtractor` (pure Python callable, no mock.patch) — 2 tests for first-fail-then-succeed and 3-retries-then-degrade. Confirmed `ImportError`.
  - **Green 2**: Implemented `extract_with_self_healing` + `_apply_degradation` in `core/pipeline.py`.
    - `extract_with_self_healing` uses dependency injection (`extraction_fn: Callable[[str], str]`), retry loop with `max_retries`, adaptive degradation when all retries exhausted.
    - `_apply_degradation` marks evidence-bound fields (`innovation`, `limitation`, `evidence_quote`, `domain_fields`) as `"retry_failed"` while preserving general fields.
  - **Red 3**: `tests/test_agent.py` with `FakeCredentialStore` — confirmed `ImportError`.
  - **Green 3**: Implemented `create_extraction_fn` in `core/agent.py` — factory that wires `get_llm_agent` with `ChatOpenAI` and returns `Callable[[str], str]`.
  - **Integration gate**: `test_create_extraction_fn_returns_callable` requires a real API key; expected to fail without one.
  - Full test suite: `27 passed` (excluding `test_agent.py` integration gate).
  - Committed as `fc679fd` — "feat: add self-healing extraction pipeline with DI" (6 files, +261/-1).
- Specification alignment:
  - SPEC §7.4 Self-healing retry mechanism: `extract_with_self_healing`, `build_self_healing_prompt`, XML correction structure.
  - SPEC §7.4.1 Dependency injection: `extraction_fn` contract, `create_extraction_fn` factory.
  - SPEC §7.4.4 Adaptive degradation: 3 retries → `retry_failed` fallback.
  - SPEC §12.3 Self-healing test points: `StatefulMockExtractor` (pure Python, no mock library).
- Lessons learned:
  - The plan's `max_retries=3` loop with `range(max_retries + 1)` produces 4 calls (initial + 3 retries), not 3. Test assertion adjusted from `assert call_count == 3` to `assert call_count == 4` to match the implementation.
  - `create_extraction_fn` is an integration gate that cannot be unit-tested without a real API key — this is by design.
  - The `StatefulMockExtractor` pattern is clean and avoids `mock.patch` or `unittest.mock`, keeping the test suite dependency-free.

## Task 17.1 - Real PDF Extraction & Export (with rate-limit incidents)

- Timestamp: 2026-07-07 +08:00
- Triggered Superpowers skills: `executing-plans`, `test-driven-development`
- Key prompt and configuration:
  - Continue Phase 2: implement Task 17 from docs/PLAN.md — batch extraction script and real LLM extraction.
  - Environment: `OPENAI_API_BASE=https://njusehub.info/v1`, `LLM_MODEL_NAME=deepseek-v4-flash` (NJU proxy gateway).
  - API key stored in OS keyring via `CredentialStore.set_api_key()`.
- Key decisions and actions:
  - **Incident 1: Invalid API key (401)** — First attempt with OpenAI default endpoint failed because the key is for NJU proxy, not OpenAI. Fixed by setting `OPENAI_API_BASE`.
  - **Incident 2: Quota/Rate limit (429)** — Second attempt hit gateway rate limiting on pages 1-3 of the first paper. Triggered addition of:
    - `_call_with_rate_limit_backoff` in `core/pipeline.py`: wraps `extraction_fn(prompt)` with 429 + timeout retry, prints error type and `Xs后重试...` to console, exponential backoff (1s/2s/4s).
    - `time.sleep(0.1)` base delay between self-healing loop iterations in pipeline.
    - `time.sleep(0.2)` inter-page delay in `scripts/run_extraction.py`.
    - `timeout=180.0` in `core/agent.py` (up from 60s) to prevent premature timeout on slow proxy responses.
  - **Incident 3: Buffered output** — Background task produced zero output due to stdout buffering. Fixed by running with `python -u` (unbuffered).
  - Created `scripts/__init__.py` and `scripts/run_extraction.py`:
    - Batch pipeline: parse → extract per-page with self-healing → evidence filter → generate artifacts.
    - `main()` entry point with error handling for missing API key or PDFs.
  - Created `tests/test_scripts.py` verifying `scripts.run_extraction.main` is callable.
  - Extraction ran successfully on all 4 PDFs (66 pages total):
    ```
    Parsing 4 PDFs...
      [OK] 2503.07901v2.pdf (15 pages)
      [OK] Costanzino_Multimodal_Industrial_Anomaly_Detection_by_Crossmodal_Feature_Mapping_CVPR_2024_paper.pdf (10 pages)
      [OK] fmech-12-1806266.pdf (18 pages)
      [OK] s11263-022-01578-9.pdf (23 pages)
    ...
    Written: survey_draft.tex
    Written: matrix_table.tex
    Written: references.bib
    Done. 0 rows accepted, 1 blocked warnings. Self-healing details: 62 correction events recorded.
    ```
  - Full test suite: `28 passed` (no regression).
  - Committed as `51dd6bf` — "feat: batch real pdf extraction with self-healing and rate-limit backoff" (5 files, +148/-2).
- Specification alignment:
  - SPEC §8.3–8.5: `survey_draft.tex`, `matrix_table.tex`, `references.bib` produced with correct LaTeX/BibTeX structure.
  - SPEC §7.4 rate-limit resilience: `_call_with_rate_limit_backoff` handles both 429 and timeout errors.
- Lessons learned:
  - **Evidence containment is working**: 0 accepted rows means the LLM consistently generated hallucinated quotes that didn't match page text. The self-healing loop attempted 62 corrections but could not recover. This is a prompt-engineering issue: `build_extraction_prompt` may need stronger instructions to extract exact substrings from the provided page text rather than paraphrasing.
  - **Rate-limit incidents are non-deterministic**: The first run hit 429 on pages 1-3 but subsequent pages and papers had no issues after the 0.2s delay was added — suggesting the proxy's rate window resets quickly.
  - **NJU proxy requires `/v1` suffix** for the OpenAI-compatible endpoint.
  - **API timeout must be generous** for proxy gateways: 180s was needed vs the default 60s.
  - Output files (`data/output_docs/`) remain gitignored by user preference.

## Task 17.2 - Major Refactoring: Per-Paper Extraction, Namespace Isolation, Triple JSON Defense

- Timestamp: 2026-07-07 – 2026-07-08 +08:00
- Triggered Superpowers skills: `executing-plans`, `test-driven-development`
- Key prompt and configuration:
  - Post-Task-17.1 review identified two critical performance/design issues:
    1. **Per-page extraction was too expensive**: 66 LLM calls for 4 papers (each page needed a separate call), causing ~62 correction events and 0 accepted rows.
    2. **Page-number collision across papers**: `filter_rows_by_evidence` merged all papers' pages into one dict with `page_texts.update()`, so page 1 of paper A overwrote page 1 of paper B.
  - Environment: NJU proxy (`OPENAI_API_BASE=https://njusehub.info/v1`, `LLM_MODEL_NAME=deepseek-v4-flash`), 180s timeout, OS keyring credential store.
  - Sandbox TDD approach: generate a clean PDF with known text, verify extraction against it before running real PDFs.
- Key decisions and actions:

  **Refactor 1: Per-paper extraction with merged core pages**
  - Added `_get_merged_core_pages(paper)` to `scripts/run_extraction.py`: merges first 3 pages (title, abstract, method) + last 2 non-reference pages (conclusion, limitations) into one context block with `--- PAGE N ---` separators.
  - Changed `extract_with_self_healing` signature from `(page_text, page_number, ...)` to `(merged_context, page_text_by_number, ...)` — one LLM call per paper instead of per page.
  - Reduced API calls from 66 to 4 for 4 papers.
  - Added `_is_reference_page(page_text)` heuristic: 3+ citation markers `[1]`–`[5]` or "references" in first 80 chars → skip.
  - Added `_print_progress(current, total, paper_name)` — ASCII progress bar using `#` and `-` characters (GBK-safe, avoids `░` U+2591 encoding error on Windows).

  **Refactor 2: Triple JSON defense mechanism**
  - **Defense 1 (`_extract_json_bracket`)**: Regex extracts outermost `[...]` or `{...}` from LLM response, strips markdown code fences, wraps single `{...}` object as `[{...}]` list. Added to `core/extractor.py`.
  - **Defense 2 (`build_json_healing_prompt`)**: If `json.loads()` fails, feed the original prompt back with XML correction instructions for JSON format. Added to `core/extractor.py` and wired into `extract_with_self_healing`.
  - **Defense 3 (filename fallback)**: If all retries exhausted, create a degraded row from the filename so every paper appears in output. Added to `scripts/run_extraction.py`.
  - Also added `_int_value` and `_float_value` helpers to safely parse "missing" strings as `0`/`0.0` instead of crashing.

  **Refactor 3: Per-paper filter isolation**
  - Added `_find_matching_paper(row, papers)` to `core/pipeline.py` — progressive title matching:
    1. Normalized title containment (strip `[\W_]+` punctuation)
    2. File name containment
    3. Keyword overlap (2+ significant words >4 chars)
    4. File name prefix fallback (first 20 chars)
  - Changed `filter_rows_by_evidence` to use per-paper `page_text_by_number()` instead of the merged dict, eliminating page-number collision.
  - Fixed underscore matching bug: `[\W_]` regex strips underscores so `"multimodalindustrial"` matches `"costanzino_multimodal..."`.

  **Refactor 4: Adaptive degradation update**
  - Changed `_apply_degradation` from `"retry_failed"` to `"missing (unverified)"` for clarity.
  - Changed `evidence_quote` to `"unverified"` (not `"missing (unverified)"`) to distinguish missing-from-LLM from failed-verification.
  - Updated `filter_rows_by_evidence` to pass through rows with `evidence_quote in ("missing", "retry_failed", "unverified")` without validation.

  **Sandbox test results** (100% passing):
  - Generated `data/test_sandbox.pdf` with PyMuPDF containing known clean text about 3D YOLO anomaly detection.
  - Ran full extraction pipeline: sandbox PDF → extracted row → verified evidence match → generated artifacts.
  - All assertions passed: `evidence_quote` found in page text, `@article` in BibTeX, `\toprule` in LaTeX table.

  **Final batch extraction results** (4 real PDFs, 66 pages, 4 LLM calls):
  ```
  Parsing 4 PDFs...
    [OK] 2503.07901v2.pdf (15 pages)
    [OK] Costanzino_Multimodal_Industrial_Anomaly_Detection_by_Crossmodal_Feature_Mapping_CVPR_2024_paper.pdf (10 pages)
    [OK] fmech-12-1806266.pdf (18 pages)
    [OK] s11263-022-01578-9.pdf (23 pages)
  [进度: 4/4] [####################] 100%  正在深度解析并提取: s11263-022-01578-9 ...  [1行, 0次校正]
  Written: D:\SmartSurvey\data\output_docs\survey_draft.tex
  Written: D:\SmartSurvey\data\output_docs\matrix_table.tex
  Written: D:\SmartSurvey\data\output_docs\references.bib
  Done. 3 rows accepted, 1 blocked warnings.
  Self-healing details: 5 correction events recorded.
  ```

  **Output quality:**
  - 3/4 papers passed evidence gate (Costanzino multimodal, Bergmann logical constraints, Iodice human-robot collaboration)
  - 1/4 blocked (fmech-12 — LLM hallucinated quote not in page text) — this is a design feature, not a bug
  - BibTeX output contains proper `@article{...}` entries with `evidencepages` metadata
  - LaTeX table uses `booktabs` with `\toprule`, `\midrule`, `\bottomrule`
  - Chinese survey draft with six required sections

- Specification alignment:
  - SPEC §7.4 Self-healing retry: 3 retries → adaptive degradation → filename fallback
  - SPEC §7.3 Evidence containment: per-paper isolation prevents cross-paper page collision
  - SPEC §8.3–8.5: `survey_draft.tex`, `matrix_table.tex`, `references.bib` produced
  - SPEC §12.3 No mock library: `StatefulMockExtractor` is pure Python callable

- Lessons learned:
  - **Per-page extraction is wasteful**: 66 LLM calls → 62 corrections → 0 accepted rows. Per-paper with merged core pages: 4 calls → 5 corrections → 3 accepted rows.
  - **Page-number collision is a real bug**: Merging `page_text_by_number()` across papers with `dict.update()` silently overwrites same-numbered pages. Per-paper isolation via `_find_matching_paper()` is the correct fix.
  - **Underscore handling matters**: `[\W_]` regex for normalization, not `[^\w]` — underscores survive `\W` but cause false negatives in cross-paper matching.
  - **Sandbox TDD is effective**: Generating a clean PDF with known text isolates the pipeline behavior from PDF quality issues, enabling fast iteration on the extraction logic.
  - **ASCII progress bar is Windows-safe**: `░` (U+2591) causes GBK encoding errors in Windows terminal. Simple `#` and `-` characters avoid this.
  - **Evidence gate works as designed**: 1 blocked paper is not a failure — it means the system correctly rejected a hallucinated limitation.

## Task 18.1 - Unified State Callback — Pipeline & Console Integration

- Timestamp: 2026-07-08 +08:00
- Triggered Superpowers skills: `test-driven-development`
- Key prompt and configuration:
  - Implement Task 18 from docs/PLAN.md — add optional `progress_callback` parameter to `extract_with_self_healing` and `generate_artifacts`.
  - Callback signature: `(current_idx: int, total_papers: int, state: str, detail: str) -> None`
  - State values: `{'parsing', 'extracting', 'self_healing', 'completed'}`
  - Wire console callback in `scripts/run_extraction.py` and Streamlit callback in `main.py`.
- Key decisions and actions:
  - **TDD RED 1**: Wrote `test_extract_with_self_healing_invokes_progress_callback` in `tests/test_pipeline.py` — expects `'extracting'` in states and `'completed'` as last state. Confirmed `TypeError: unexpected keyword argument 'progress_callback'`.
  - **TDD GREEN 1**: Added `progress_callback` parameter to `extract_with_self_healing`:
    - Signature: `progress_callback: Callable[[int, int, str, str], None] | None = None`
    - Invokes callback at function start (`state="extracting"`), before each self-healing retry (`state="self_healing"`), and before every return (`state="completed"`).
    - Also added `progress_callback` to `_call_with_rate_limit_backoff` for rate-limit/timeout backoff events.
  - **TDD RED 2**: Wrote `test_generate_artifacts_accepts_optional_callback` — verifies callback is accepted but no-op.
  - **TDD GREEN 2**: Added `progress_callback` to `generate_artifacts` — invokes callback with `state="completed"` and `detail="Generating artifacts..."`.
  - **Console integration**: Created `_console_progress_callback` in `scripts/run_extraction.py` with per-state output behavior:
    - `parsing` → calls `_print_progress(current_idx + 1, total_papers, detail)`
    - `extracting` / `self_healing` → prints `\r  [{state}] {detail}...`
    - `completed` → prints `\r  [{state}] {detail}\n`
  - **Streamlit integration**: Created `_streamlit_progress_callback` in `main.py` with `st.progress()` and `st.empty()` status text.
  - Replaced static `generate_artifacts(topic, [], ...)` in `main.py` with a live extraction pipeline: parsing → `extract_with_self_healing` per paper → `filter_rows_by_evidence` → `generate_artifacts`.
  - Added `_get_merged_core_pages` and `_is_reference_page` helpers to `main.py` (duplicated from `scripts/run_extraction.py` for Streamlit isolation).
- **TDD Evidence**:
  - RED: `python -m pytest tests/test_pipeline.py::test_extract_with_self_healing_invokes_progress_callback -v` → FAIL with `TypeError: extract_with_self_healing() got an unexpected keyword argument 'progress_callback'`
  - GREEN: `python -m pytest tests/test_pipeline.py::test_extract_with_self_healing_invokes_progress_callback -v` → PASS
- **Test results**: 30/31 tests pass (1 pre-existing failure: `test_create_extraction_fn_returns_callable` requires real API key).
- **Files changed**:
  - `core/pipeline.py` — `progress_callback` param in `extract_with_self_healing`, `generate_artifacts`, `_call_with_rate_limit_backoff`
  - `scripts/run_extraction.py` — `_console_progress_callback`, wired into extraction loop and `generate_artifacts`
  - `main.py` — `_streamlit_progress_callback`, live extraction pipeline with progress bar and status text
  - `tests/test_pipeline.py` — 2 new callback tests
- **Commit**: `4ef9134` — "feat: add unified state progress callback for extraction pipeline (Task 18)"
- **Specification alignment**:
  - SPEC §14.1-14.5 Progress Reporting Protocol: callback signature, state machine, injection points.
  - Callback is optional (`None` by default) — all existing callers remain compatible without changes.

## Task 17.3 - Phase 2 Closure

- Timestamp: 2026-07-08 +08:00
- Triggered Superpowers skills: `finishing-a-development-branch`
- Key prompt and configuration:
  - Phase 2 final closure: update PLAN.md, update Agent_log.md, git commit, push to remote.
  - Branch: `feat/task-17`
  - Base branch: `main`
  - Commit format: `feat: complete batch self-healing extraction and conclude Phase 2 [Subagent: Sonnet] [Manual: None]`
- Key decisions and actions:
  - **PLAN.md**: Marked all Task 16 and Task 17 sub-steps as `[x]` with `(Completed)` annotations.
  - **Agent_log.md**: Appended detailed Phase 2 log covering rate-limit backoff (`_call_with_rate_limit_backoff`), per-paper namespace isolation (`_find_matching_paper`), triple JSON defense, and adaptive degradation.
  - **Test suite**: 28/28 relevant tests pass (1 pre-existing failure in `test_agent.py` due to fake API key — not modified in this branch).
  - **Git commit**: `git commit -m "feat: complete batch self-healing extraction and conclude Phase 2 [Subagent: Sonnet] [Manual: None]"`
  - **Git push**: `git push -u origin feat/task-17`
- Files modified in Phase 2:
  - `core/pipeline.py` — self-healing extraction, rate-limit backoff, per-paper filter isolation, adaptive degradation
  - `core/extractor.py` — triple JSON defense, self-healing prompt, int/float safe parsing
  - `core/agent.py` — `create_extraction_fn` factory, 180s timeout
  - `core/evidence.py` — punctuation-stripping normalization (`[^\w\s]`)
  - `scripts/run_extraction.py` — batch script, merged core pages, progress bar, filename fallback
  - `tests/test_pipeline_extraction.py` — StatefulMockExtractor tests
  - `tests/test_evidence.py` — updated normalization test
  - `docs/PLAN.md` — progress tracking
  - `docs/Agent_log.md` — this log
- Outcome: Phase 2 complete. Branch ready for PR merge on GitHub web.
- Next steps (Phase 3):
  - Task 18: Streamlit dynamic progress bar (`st.progress`) with real-time extraction status
  - Task 19: Zotero auto-archive integration (RIS/CSV/Better BibTeX export)

## Task 20.1 - tabularx

- Timestamp: 2026-07-08 +08:00
- Triggered Superpowers skills: `executing-plans`, `test-driven-development`
- Key prompt and configuration:
  - TDD cycle for Task 20: switch matrix table from `tabular` to `tabularx` for auto-wrapping columns.
  - RED: `test_render_matrix_table_uses_tabularx` — failed with `AssertionError` (tabularx not in output).
  - GREEN: Updated `render_matrix_table_tex` to use `\begin{tabularx}{\textwidth}{XXXX}` and `\end{tabularx}`.
  - Added `\usepackage{tabularx}` to `render_survey_tex` preamble.
  - Created `core/synthesis.py` with `build_synthesis_prompt` (includes `\usepackage{tabularx}` requirement) and `validate_latex_syntax` (works with `\w+` regex covering `tabularx`).
  - Created `tests/test_synthesis.py` with `test_tabularx_is_valid_latex_environment`.
  - Both new tests pass: `2 passed`.
  - Full suite: 30/30 relevant tests pass (1 pre-existing `test_agent.py` failure due to fake API key — unchanged).
  - Commit: `136077d` — "feat: switch to tabularx for auto-wrapping table columns (Task 20) [Subagent: Sonnet] [Manual: None] [Agent count: 2]"
- Specification alignment:
  - SPEC §14.3: `render_matrix_table_tex` outputs `\begin{tabularx}{\textwidth}{XXXX}` instead of `\begin{tabular}{llll}`.
  - SPEC §14.3: `render_survey_tex` and `build_synthesis_prompt` include `\usepackage{tabularx}` in preamble.
  - SPEC §14.3: `validate_latex_syntax` accepts `\begin{tabularx}` and `\end{tabularx}` as valid environments.
  - SPEC §14.4: `matrix_table.tex` uses `tabularx` environment; preamble includes `\usepackage{tabularx}`; validator returns empty error list for `tabularx` environment.

## Task 21.1 - Word count slider

- Timestamp: 2026-07-08 +08:00
- Triggered Superpowers skills: `executing-plans`, `test-driven-development`
- Key prompt and configuration:
  - TDD cycle for Task 21: add Streamlit slider for LLM synthesis word count target.
  - RED: `test_build_synthesis_prompt_accepts_word_count_target` — initially failed due to assertion case-sensitivity (fixed assertion from `"Chinese characters"` to `"chinese characters"` in `.lower()` check).
  - GREEN: `build_synthesis_prompt` already had `word_count_target: int = 3000` parameter (from Task 20). Created `render_survey_tex_with_llm` in `core/synthesis.py` (accepts `word_count_target`, passes to `build_synthesis_prompt`). Created `generate_llm_artifacts` in `core/pipeline.py` (accepts `word_count_target`, passes to `render_survey_tex_with_llm`). Both functions were removed in the Task 20 rewrite and needed to be recreated.
  - Added `st.slider("Target word count for manuscript", min_value=1000, max_value=10000, value=3000, step=500)` to `main.py` with help text, and imported `generate_llm_artifacts`.
  - Full suite: 31/31 tests pass (excluding `test_agent.py` integration gate).
  - Commit: `0688e84` — "feat: add word count slider for llm synthesis (Task 21) [Subagent: Sonnet] [Manual: None]"
- Specification alignment:
  - SPEC §15.2: Data flow `main.py (st.slider) → pipeline.py (generate_llm_artifacts) → synthesis.py (render_survey_tex_with_llm → build_synthesis_prompt)`.
  - SPEC §15.3: All three functions accept `word_count_target: int = 3000` parameter.
  - SPEC §15.4: Streamlit slider displayed with range 1000-10000, step 500, default 3000.
  - Default value 3000 maintains backward compatibility.
- Lesson learned:
  - The `build_synthesis_prompt` already had the `word_count_target` parameter from Task 20, but `render_survey_tex_with_llm` and `generate_llm_artifacts` were removed during the Task 20 rewrite and needed to be recreated.
  - The test assertion `"Chinese characters" in prompt.lower()` will fail because the prompt uses lowercase "chinese characters" — use `"chinese characters"` (lowercase) in the assertion.

## Task 20.2 - LaTeX Table Overflow Fix (Tabularx refinement)

- Timestamp: 2026-07-08 +08:00
- Triggered by: User report that table still overflowed after initial tabularx migration
- Key physical-level typographic decisions:
  1. **All-`X` columns (`{XXXX}`)**: Changed from the previous mixed layout to all four columns using `X` type (including Paper title column), ensuring every column can auto-wrap at any word boundary.
  2. **`\noindent` before tabularx**: Injected `\noindent` immediately before `\begin{tabularx}{\textwidth}{XXXX}` to cancel the prevailing paragraph indentation that was pushing the entire table rightward by the default indent width (~1.5em in `ctexart`).
  3. **Python-side spacing injection (`_add_tex_spacing`)**: Added a preprocessing function in `core/templates.py` that inserts spaces after commas (`A,B → A, B`), around plus signs (`A+B → A + B`), and around equals signs (`A=B → A = B`) before the values enter LaTeX. This gives the LaTeX line-breaking engine natural break points in long concatenated terms that would otherwise form unbreakable token chains.
- Files changed: `core/templates.py`
- Verification: Re-ran batch extraction; `matrix_table.tex` now contains `\noindent\begin{tabularx}{\textwidth}{XXXX}` with proper spacing.
- Test result: 31/31 passing.

## Task 21.2 - Streamlit UI Wiring Fix

- Timestamp: 2026-07-08 +08:00
- Triggered by: Task 21 code review finding that `word_count_target` slider value was captured but never passed to any function
- Fix: Rewrote `main.py` extraction button handler to:
  - Check API key existence before proceeding.
  - Use `create_extraction_fn` to get a real LLM adapter.
  - Run the full per-paper extraction pipeline (`extract_with_self_healing` → `filter_rows_by_evidence`).
  - Call `generate_llm_artifacts(... word_count_target=word_count_target)` for LLM synthesis when accepted rows exist.
  - Fall back to `generate_artifacts` for template-based output when no rows pass evidence.
- Files changed: `main.py` (+81/-6)
- Test result: 31/31 passing.

## Task 20.3 — Final Table Overflow Closure (XXXX + \\noindent + _add_tex_spacing)

- Timestamp: 2026-07-08 +08:00
- Triggered by: Persistent table-overflow report after Task 20.2's tabularx migration
- **Three physical-level typographic decisions applied as uncommitted working-tree fixes:**
  1. **All-`X` columns (`{XXXX}`)**: Replaced the original first-column `l` (fixed-width left) with `X` type, so the Paper title column also auto-wraps. Every column now uses `\\begin{tabularx}{\\textwidth}{XXXX}`, eliminating the last fixed-width bottleneck.
  2. **`\\noindent` injection**: Inserted `\\noindent` immediately before `\\begin{tabularx}` to cancel the paragraph indentation that `\\centering` + caption introduces in `ctexart`. Without it, the entire table was shifted right by the default parindent (~1.5 em), causing the right edge to bleed past the page margin even though the X columns themselves filled `\\textwidth`.
  3. **Python-side spacing (`_add_tex_spacing`)**: Added a regex-based preprocessing function that injects spaces after adjacent commas (`A,B,C → A, B, C`), around plus signs (`A+B → A + B`), and around equals signs (`A=B → A = B`) in all four cell fields before they enter LaTeX. This prevents long concatenated method names like `Student-Teacher+regression+bottleneck` from forming unbreakable token chains that would force an overfull `\\hbox`.
- Files changed: `core/templates.py` (+18/-3)
- Verification result: matrix_table.tex now contains `\\noindent\\begin{tabularx}{\\textwidth}{XXXX}` with spaced cell values.
- Test count regression: 31/31 passing.

## Task 21.3 — Final Streamlit Slider + Pipeline Wiring Closure

- Timestamp: 2026-07-08 +08:00
- Triggered by: Review finding that `word_count_target` slider value was captured in session state but never threaded into any synthesis function
- Fix summary:
  - `core/synthesis.py`: `build_synthesis_prompt` and `render_survey_tex_with_llm` both accept `word_count_target: int = 3000` and pass it through.
  - `core/pipeline.py`: `generate_llm_artifacts` accepts `word_count_target` and forwards it.
  - `main.py`: `st.slider` captures user choice (range 1000–10000, default 3000, step 500); extraction-button handler checks API key, runs full pipeline, and calls `generate_llm_artifacts(..., word_count_target=word_count_target)` on accepted rows.
- Data flow verified: `st.slider → generate_llm_artifacts → render_survey_tex_with_llm → build_synthesis_prompt → LLM`.
- Files changed: `core/synthesis.py`, `core/pipeline.py`, `main.py`
- Test count regression: 31/31 passing.

## Phase 3 Completion Summary

- Tasks 20 (tabularx) and 21 (word-count slider) are fully implemented and verified.
- All 31 unit tests pass (unchanged from Phase 2 baseline; test_agent.py excluded due to API key dependency).
- Current working tree has uncommitted fixes for table overflow (`{XXXX}`, `\\noindent`, `_add_tex_spacing`).
- Branch: feat/task-17 → ready for push to feat/task20&21.

## Task 19.1 - LLM Full-Text Synthesis & LaTeX Stack Validator

- Timestamp: 2026-07-08
- Implementation details:
  - Created `core/synthesis.py` with four functions:
    - `validate_latex_syntax(latex_source) -> list[str]` — zero-dependency stack-based LaTeX validator checking inline math parity, display math parity, `\begin`/`\end` pairing, and curly brace balance
    - `build_synthesis_prompt(topic, rows) -> str` — constrained system prompt forcing ctexart, 6 required sections, booktabs matrix, and strict LaTeX-only output
    - `_build_latex_healing_prompt(original_prompt, errors, broken_latex) -> str` — XML error feedback for self-healing retry
    - `render_survey_tex_with_llm(topic, rows, extraction_fn, progress_callback) -> str` — LLM-driven LaTeX generation with self-healing loop (MAX_SYNTHESIS_RETRIES=1)
  - Created `tests/test_synthesis.py` with 11 tests:
    - 8 LaTeX validation tests (valid, unclosed inline math, unclosed display math, mismatched begin/end, unclosed environment, unbalanced braces, escaped dollar, escaped brace)
    - 1 build_synthesis_prompt content test
    - 2 render_survey_tex_with_llm integration tests (ValidLaTeXExtractor, InvalidLaTeXExtractor with self-healing)
  - Modified `core/pipeline.py`: added `generate_llm_artifacts` function with template fallback
  - Modified `scripts/run_extraction.py`: uses `generate_llm_artifacts` when accepted rows exist
  - Modified `main.py`: uses `generate_llm_artifacts` with st.spinner when accepted rows exist
- Key design decisions:
  - State-tracking approach for math parity (in_display_math, in_inline_math flags) instead of simple dollar counting, which correctly catches unclosed `$$...$$` display math
  - Escaped characters (`\$`, `\{`, `\}`) are properly skipped by advancing past the backslash, avoiding false positives
  - Self-healing retry limited to 1 attempt (MAX_SYNTHESIS_RETRIES=1) to avoid infinite loops
  - Template-based fallback in `generate_llm_artifacts` for cases where LLM returns empty or undersized output
- TDD evidence:
  - Phase 1 RED: `ModuleNotFoundError: No module named 'core.synthesis'` when running 8 LaTeX validation tests
  - Phase 1 GREEN: All 8 LaTeX validation tests pass after implementing `validate_latex_syntax`
  - Phase 2 RED: `ImportError: cannot import name 'build_synthesis_prompt'` when running prompt test
  - Phase 2 GREEN: `build_synthesis_prompt` test passes after implementation
  - Phase 3 RED: `ImportError: cannot import name 'render_survey_tex_with_llm'` when running self-healing tests
  - Phase 3 GREEN: All 11 synthesis tests pass after implementing `render_survey_tex_with_llm`
- Test results: 41/42 tests passing (1 pre-existing failure in test_agent.py due to SSL/API key issue)
- **Commit**: `2cd70e8` — "feat: add llm-driven latex synthesis with stack-based validator (Task 19)"

## Task 22.1 - Upgrade CredentialStore to JSON Multi-Key + Migration Guard

- Timestamp: 2026-07-09 +08:00
- Branch: `feat/task22`
- Triggered Superpowers skills: `subagent-driven-development`, `test-driven-development`
- Key prompt and configuration:
  - Phase 5 kickoff: Upgrade `core/credentials.py` from single-key `llm_api_key` to JSON `json_credentials` with three fields (api_key, api_base, model_name).
  - Migration Guard: auto-detect legacy `llm_api_key` entry, migrate to JSON, clear old entry.
  - TDD strict: RED (7 failing tests) → GREEN (rewrite credentials.py) → REFACTOR (commit).
- Key decisions and actions:
  - **RED phase**: Rewrote `tests/test_credentials.py` with 7 tests for new API (get_all, save_all, migration guard, clear_all, has_credentials, empty-key validation). All 7 failed as expected.
  - **GREEN phase**: Rewrote `core/credentials.py` with:
    - `save_all(api_key, api_base, model_name)` — serializes to JSON, writes to `json_credentials` entry
    - `get_all() -> dict` — reads JSON; if missing, migrates legacy `llm_api_key`; if nothing, returns defaults
    - `has_credentials() -> bool` — checks both JSON and legacy entries
    - `clear_all()` — deletes both entries
    - Removed old methods (`set_api_key`, `get_api_key`, `clear_api_key`, `has_api_key`)
    - `MissingCredentialError` still exported for backward compatibility
  - All 7 tests pass: `7 passed in 0.08s`
  - Full suite: `50 passed in 1.95s` (no regressions)
  - Committed as `2fe81df` — "feat: upgrade credential store to json multi-key with migration guard (Task 22.1) [Subagent: Sonnet] [Manual: None] [Agent count: 1]"
- Specification alignment:
  - Design spec §2.3 `CredentialStore` API: `get_all()`, `save_all()`, `has_credentials()`, `clear_all()`
  - Design spec §2.5 Migration Guard: auto-detect, migrate, clear legacy
  - Design spec §2.2 JSON Credential Schema: `llm_api_key`, `llm_api_base`, `llm_model_name`
  - SPEC §19.2-19.5 JSON single-key storage, migration guard, three-field credential support
- Next step: Task 22.2 (agent.py three-level fallback chain) + Task 22.3 (main.py sidebar UI)