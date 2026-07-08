# SmartSurvey Phase 3 Design: Synthesis UX & Progress Reporting

## Overview

Phase 3 enhances SmartSurvey with two capabilities:
1. **Real-time progress reporting** via a Unified State Callback, enabling the Streamlit UI to show live extraction progress.
2. **LLM-driven full-text synthesis** that upgrades the template-based `render_survey_tex` to a LLM-powered academic manuscript generator, with a lightweight stack-based LaTeX validation self-healing loop.

---

## Task 18: Unified State Callback for Progress Reporting

### Design Decision: Scheme C — Unified State Callback

Chosen over:
- **Scheme A (Stage Callback)**: Too coarse-grained — silent during 429 retry backoff periods.
- **Scheme B (Token Callback)**: Too many event types, high interface coupling.

### Callback Signature

```python
progress_callback: Callable[[int, int, str, str], None]
# Parameters:
#   current_idx: int        — 0-based index of the paper currently being processed
#   total_papers: int       — total number of papers in the batch
#   state: str              — one of {'parsing', 'extracting', 'self_healing', 'completed'}
#   detail: str             — human-readable real-time status string (e.g., "Retry 2/3: Generating XML feedback prompt...")
```

### State Machine

```
parsing  →  extracting  →  self_healing (0..N times)  →  completed
```

- `parsing`: PDF file is being read and page-sliced.
- `extracting`: First LLM extraction call in progress.
- `self_healing`: One or more retry attempts (evidence containment failed, JSON parse failed, or rate-limit retry).
- `completed`: Paper finished (accepted or degraded).

### Design Principles

1. **Decoupling**: `pipeline.py` only broadcasts state via the callback. The caller decides how to render it.
2. **Console mode**: `print(end="\r", flush=True)` for ASCII progress bar.
3. **Streamlit mode**: `st.progress()` + `st.status()` for rich UI updates.
4. **No breaking changes**: The callback is optional (`None` by default) — existing callers that don't pass a callback continue to work.

### Callback Injection Points

- `extract_with_self_healing()` — wrap the LLM call with `extracting` and `self_healing` states.
- `scripts/run_extraction.py` — wrap the per-paper loop with `parsing` and `completed` states.

---

## Task 19: LLM-Driven Full-Text Synthesis

### Architecture Decision: New `core/synthesis.py` Module

Chosen over:
- **Option A**: Adding `extraction_fn` to `core/templates.py` — breaks single-responsibility principle.
- **Option B**: Adding to `core/pipeline.py` — file would become too large.

### Module Interface

```python
def render_survey_tex_with_llm(
    topic: str,
    rows: list[AcademicMatrixRow],
    extraction_fn: Callable[[str], str],
    progress_callback: Callable[[int, int, str, str], None] | None = None,
) -> str:
    """Generate a full LaTeX manuscript using LLM-driven synthesis.

    Args:
        topic: Review topic string.
        rows: Verified academic matrix rows.
        extraction_fn: LLM callable (prompt → raw response).
        progress_callback: Optional progress callback (for UI updates).

    Returns:
        Complete LaTeX manuscript string (survey_draft.tex content).
    """
```

### System Prompt Design

The synthesis prompt is a separate function in `core/synthesis.py`:

```python
def build_synthesis_prompt(topic: str, rows: list[AcademicMatrixRow]) -> str:
    """Build a system prompt that constrains LLM output to valid LaTeX.
    
    Requirements:
    - Output must be valid LaTeX using ctexart document class.
    - Must include exactly 6 required \section{...} headers.
    - Must embed the booktabs matrix table from provided data.
    - All Chinese text must be in the body (not in commands).
    - Return ONLY the LaTeX source — no markdown fences, no explanations.
    """
```

### LaTeX Syntax Validation: Stack-Based Scanner

**Design Principle**: Lightweight, zero-dependency, no external LaTeX compiler.

#### Validation Rules

```python
def validate_latex_syntax(latex_source: str) -> list[str]:
    """Run three lightweight checks on LaTeX source.

    Returns a list of error messages (empty = valid).
    """
```

#### Check 1: Inline Math `$...$` Parity

- Scan character-by-character, ignoring `\$` escapes.
- Track `$` open/close parity.
- Error: `"Unclosed inline math: odd number of $ symbols."`

#### Check 2: Display Math `$$...$$` Parity

- Same character scan, but for `$$` pairs.
- Error: `"Unclosed display math: $$ block not terminated."`

#### Check 3: `\begin{...}` / `\end{...}` Pairing

- Stack-based scanner: push `\begin{env}` → pop on `\end{env}`.
- Error on mismatch: `"Mismatched environment: \\begin{foo} closed by \\end{bar}."`
- Error on unclosed: `"Unclosed environment: \\begin{foo} has no matching \\end{foo}."`

#### Check 4: Curly Braces `{...}` Balance

- Integer counter: `+1` on `{`, `-1` on `}`, ignoring `\{` and `\}` escapes.
- Error on negative: `"Extra closing brace encountered."`
- Error on positive: `"Unclosed brace: {count} unmatched opening braces."`

### Self-Healing Loop

```python
MAX_SYNTHESIS_RETRIES = 1  # Token budget is small

def render_survey_tex_with_llm(...) -> str:
    prompt = build_synthesis_prompt(topic, rows)
    for attempt in range(MAX_SYNTHESIS_RETRIES + 1):
        raw = extraction_fn(prompt)
        errors = validate_latex_syntax(raw)
        if not errors:
            return raw
        # Build XML feedback for LLM to self-correct
        prompt = _build_latex_healing_prompt(prompt, errors, raw)
    # Fallback: return raw LaTeX even if validation fails
    return raw
```

### XML Healing Prompt

```python
def _build_latex_healing_prompt(
    original_prompt: str,
    errors: list[str],
    broken_latex: str,
) -> str:
    correction = (
        "\n\n<latex-validation-errors>\n"
        + "\n".join(f"  <error>{e}</error>" for e in errors)
        + "\n</latex-validation-errors>\n"
        "<self-healing-instruction>\n"
        "  The LaTeX source above contains syntax errors. "
        "Please fix ALL errors listed above and return ONLY the corrected LaTeX source.\n"
        "</self-healing-instruction>"
    )
    return original_prompt + correction
```

### Testing Strategy

1. **Unit tests for `validate_latex_syntax`**:
   - Valid LaTeX → empty error list.
   - Unclosed `$` → one error.
   - Mismatched `\begin{...}` / `\end{...}` → one error.
   - Unbalanced `{...}` → one error.
   - Escaped `\$`, `\{`, `\}` → no false positives.

2. **Unit tests for `build_synthesis_prompt`**:
   - Prompt contains topic, all rows, and output format constraints.

3. **Integration test for `render_survey_tex_with_llm`**:
   - Use `StatefulMockExtractor` (pure Python, no real LLM).
   - Verify that self-healing retry is triggered on LaTeX syntax errors.

---

## File Change Summary

| File | Action | Purpose |
|------|--------|---------|
| `core/synthesis.py` | **Create** | LLM synthesis prompt, LaTeX validation, self-healing loop |
| `core/pipeline.py` | **Modify** | Add `progress_callback` parameter to `extract_with_self_healing` and `generate_artifacts` |
| `core/templates.py` | **No change** | Keep pure rendering; synthesis moves to `core/synthesis.py` |
| `scripts/run_extraction.py` | **Modify** | Wire `progress_callback` into per-paper loop |
| `main.py` | **Modify** | Wire Streamlit `st.progress()` + `st.status()` via callback |
| `tests/test_synthesis.py` | **Create** | Tests for LaTeX validation, synthesis prompt, and self-healing |
| `tests/test_pipeline.py` | **Modify** | Update tests for optional `progress_callback` parameter |

---

## Open Questions (Resolved)

All design decisions for Phase 3 have been confirmed via brainstorming:

1. ✅ **Progress callback**: Scheme C — Unified State Callback with `(current_idx, total_papers, state, detail)`.
2. ✅ **Synthesis module**: New `core/synthesis.py` (not templates.py, not pipeline.py).
3. ✅ **LaTeX validation**: Lightweight stack-based scanner (no pdflatex).
4. ✅ **Self-healing**: Max 1 retry with XML error feedback.
5. ✅ **Zotero integration**: Deferred to Phase 4 (Task 20, optional).