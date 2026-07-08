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

- [ ] **Step 1: Write failing test for tabularx preamble**

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

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_templates.py::test_render_matrix_table_uses_tabularx -v`

Expected: FAIL — `tabularx` not found in output.

- [ ] **Step 3: Update `render_matrix_table_tex` in `core/templates.py`**

Replace `\begin{tabular}{llll}` with `\begin{tabularx}{\textwidth}{XXXX}` and close with `\end{tabularx}`.

- [ ] **Step 4: Update `render_survey_tex` preamble**

Add `\usepackage{tabularx}` to the LaTeX preamble.

- [ ] **Step 5: Update `build_synthesis_prompt` in `core/synthesis.py`**

Add `\usepackage{tabularx}` to the required packages in the synthesis prompt.

- [ ] **Step 6: Update `validate_latex_syntax` to accept `tabularx`**

Add `tabularx` to the recognized environment list in `validate_latex_syntax`. The current regex `r'\\(begin|end)\{(\w+)\}'` already matches any environment name, so `tabularx` should work. Add a test to confirm.

- [ ] **Step 7: Write test for tabularx compatibility in validator**

```python
def test_tabularx_is_valid_latex_environment():
    """tabularx environment must not trigger false positive."""
    from core.synthesis import validate_latex_syntax

    source = r"\begin{tabularx}{\textwidth}{XXXX} a & b \\ \end{tabularx}"
    errors = validate_latex_syntax(source)
    assert errors == []
```

- [ ] **Step 8: Run both new tests**

Run: `python -m pytest tests/test_templates.py::test_render_matrix_table_uses_tabularx tests/test_synthesis.py::test_tabularx_is_valid_latex_environment -v`

Expected: Both PASS.

- [ ] **Step 9: Commit**

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

- [ ] **Step 1: Write failing test for word count in prompt**

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

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_synthesis.py::test_build_synthesis_prompt_accepts_word_count_target -v`

Expected: FAIL with `TypeError` — unexpected keyword argument `word_count_target`.

- [ ] **Step 3: Update `build_synthesis_prompt` signature**

Add `word_count_target: int = 3000` parameter. Replace the hardcoded `"3000-5000 Chinese characters"` in the prompt with the dynamic value.

- [ ] **Step 4: Update `render_survey_tex_with_llm` signature**

Add `word_count_target: int = 3000` parameter. Pass it to `build_synthesis_prompt`.

- [ ] **Step 5: Update `generate_llm_artifacts` signature**

Add `word_count_target: int = 3000` parameter. Pass it to `render_survey_tex_with_llm`.

- [ ] **Step 6: Run word count test to verify it passes**

Run: `python -m pytest tests/test_synthesis.py::test_build_synthesis_prompt_accepts_word_count_target -v`

Expected: PASS.

- [ ] **Step 7: Add Streamlit slider to `main.py`**

Add before the extraction button:
```python
word_count_target = st.slider(
    "Target word count for manuscript",
    min_value=1000, max_value=10000, value=3000, step=500,
    help="Controls how many Chinese characters the LLM synthesis should target.",
)
```

Pass `word_count_target` to `generate_llm_artifacts`.

- [ ] **Step 8: Run full test suite**

Run: `python -m pytest tests -v --ignore=tests/test_agent.py`

Expected: All tests pass.

- [ ] **Step 9: Commit**

```bash
git add core/synthesis.py core/pipeline.py main.py tests/test_synthesis.py
git commit -m "feat: add word count slider for llm synthesis (Task 21) [Subagent: Sonnet] [Manual: None]"
```

---

## Phase 4: Future Work (Backlog)

