# SmartSurvey Phase 3 Design: Tabularx & Word Count Slider

## Overview

Phase 3 (continued) adds two refinements on top of the existing Task 18-19 foundation:
1. **Task 20**: Replace `tabular` with `tabularx` for auto-wrapping LaTeX table columns.
2. **Task 21**: Add a Streamlit word-count slider that controls LLM synthesis length.

Both tasks are incremental enhancements to existing code — no new modules, no architectural changes.

---

## Task 20: LaTeX Table Adaptive Column Wrapping

### Problem

`matrix_table.tex` uses `\begin{tabular}{llll}` with fixed-width columns. Long paper titles and method descriptions overflow the page margin in Overleaf, producing `overfull \hbox` warnings.

### Solution

Replace `tabular` with `tabularx` and `X`-type auto-wrapping columns:

```latex
% Before (overflows)
\begin{tabular}{llll}
\Paper & Method & Limitation \\

% After (auto-wraps)
\begin{tabularx}{\textwidth}{XXXX}
\Paper & Method & Limitation \\
```

### Files Changed

| File | Change |
|------|--------|
| `core/templates.py:render_matrix_table_tex` | `{tabular}{llll}` → `{tabularx}{\textwidth}{XXXX}`; `\end{tabular}` → `\end{tabularx}` |
| `core/templates.py:render_survey_tex` | Add `\usepackage{tabularx}` to LaTeX preamble |
| `core/synthesis.py:build_synthesis_prompt` | Add `\usepackage{tabularx}` requirement to System Prompt |
| `core/synthesis.py:validate_latex_syntax` | **No change needed** — `\w+` regex already covers `tabularx` |

### Validation Compatibility

The existing `validate_latex_syntax` handles `tabularx` correctly:
- `\begin{tabularx}` matched by `r'\\(begin|end)\{(\w+)\}'` — `tabularx` is all word chars.
- `{\textwidth}{XXXX}` extra parameters: braces are counted by the brace-balance checker, which correctly handles them since they're balanced within the `\begin{tabularx}` line.
- Escaped braces `\{` `\}` are already skipped by the character-pointer lookahead.

---

## Task 21: Streamlit Word-Count Slider

### Data Flow

```
main.py (st.slider, min=1000, max=10000, step=500, value=3000)
  → core/pipeline.py:generate_llm_artifacts(word_count_target=3000)
    → core/synthesis.py:render_survey_tex_with_llm(word_count_target=3000)
      → core/synthesis.py:build_synthesis_prompt(word_count_target=3000)
```

### Parameter Design

- **Option A chosen** (explicit parameter per layer, no Context Object). Reason: YAGNI — only one tunable parameter.
- Default value: `3000` — all existing callers remain compatible.
- The prompt changes from hardcoded `"Total length: 3000-5000 Chinese characters"` to `f"Total length: approximately {word_count_target} Chinese characters"`.

### UI Design

```python
word_count_target = st.slider(
    "Target word count for manuscript",
    min_value=1000, max_value=10000, value=3000, step=500,
    help="Controls how many Chinese characters the LLM synthesis should target.",
)
```

Placed in `main.py` between the topic input and the extraction button.

---

## Testing

### Task 20 Tests

- `test_render_matrix_table_uses_tabularx` — asserts `\begin{tabularx}` in output, `\begin{tabular}{llll}` NOT in output.
- `test_tabularx_is_valid_latex_environment` — asserts `validate_latex_syntax` returns empty for `\begin{tabularx}...\end{tabularx}`.

### Task 21 Tests

- `test_build_synthesis_prompt_accepts_word_count_target` — asserts the prompt string contains the target number.
- Existing `test_render_survey_tex_with_llm_valid` — still passes with default `word_count_target=3000`.

---

## Spec References

- `docs/SPEC.md` §14: LaTeX Table Adaptive Column Wrapping (Task 20)
- `docs/SPEC.md` §15: Streamlit Word-Count Slider (Task 21)

---

## Open Questions (Resolved)

1. ✅ `tabularx` environment compatibility: `\w+` regex already covers it — no `validate_latex_syntax` modification needed.
2. ✅ Parameter passing strategy: Explicit parameter per layer (Option A), not Context Object.
3. ✅ Slider range: 1000-10000, step 500, default 3000.