# Phase 7 Design: LaTeX Compilation Hardening & Academic Layout Polish

**Date:** 2026-07-09
**Branch:** feat/phase-7
**Status:** Draft

---

## Overview

Phase 7 hardens LaTeX compilation against LLM-generated syntax errors, standardizes the preamble assembly across all synthesis paths, polishes the rendered PDF layout, and enforces structured formatting in LLM prompts.

---

## 1. Bug 1: CJK Bracket Corruption Detection

### 1.1 Problem

LLMs occasionally hallucinate Chinese right-angle quotation marks (`》`) or other CJK closing brackets (`】`, `」`) in place of the LaTeX closing brace `}`. A LaTeX snippet like `\subsection{核心贡献与技术谱系》` causes the compiler to fail because the `》` is not recognized as a closing brace.

### 1.2 Solution

Enhance `validate_latex_syntax()` in `core/synthesis.py` to detect CJK bracket corruption:

- In the existing curly-brace balance scanner (Check 3), when an unmatched opening `{` is found, scan the surrounding context for CJK closing characters (`》`, `】`, `」`).
- If found, report a specific error: `"Line N: Detected CJK character '》' near position P — possibly replacing '}'. Fix all CJK brackets."`
- The existing `}` escape-skipping logic (`\{` and `\}`) is already correct.

### 1.3 File Changes

| File | Change |
|------|--------|
| `core/synthesis.py` | Enhance `validate_latex_syntax()` brace check with CJK detection |
| `tests/test_synthesis.py` | Add `test_cjk_bracket_detected()` test |

### 1.4 Acceptance Criteria

- `\subsection{核心贡献与技术谱系》` → error: `"CJK character '》' detected"`
- `\subsection{核心贡献与技术谱系}` → no error (valid LaTeX)
- Existing `{}` balance tests continue to pass

---

## 2. Table Centering Fix

### 2.1 Problem

In `render_matrix_table_tex()`, `\noindent` is concatenated with `\begin{tabularx}` on the same line (`\noindent\begin{tabularx}{...}`), causing the `\noindent` to be parsed as part of the tabularx preamble and breaking the `\centering` effect.

### 2.2 Solution

Split `\noindent` onto its own line before `\begin{tabularx}`:

```python
r"\noindent",
r"\begin{tabularx}{\textwidth}{" + f"{ragged}{ragged}{ragged}{ragged}" + "}",
```

### 2.3 File Changes

| File | Change |
|------|--------|
| `core/templates.py` | Split `\noindent\begin{tabularx}` into two lines |
| `tests/test_templates.py` | Update test to match new format |

### 2.4 Acceptance Criteria

- Generated LaTeX has `\noindent` and `\begin{tabularx}` on separate lines.
- Table renders centered in PDF output.

---

## 3. Unified Preamble Architecture (SSOT)

### 3.1 Problem

The single-pass synthesis path (`render_survey_tex_with_llm`) lets the LLM generate the preamble, while the multi-stage path (`render_survey_tex_multi_stage`) uses a hardcoded preamble. This creates two risks:
1. LLM may hallucinate preamble packages or syntax errors.
2. Layout settings (geometry, margin) differ between paths.

### 3.2 Solution

Strip preamble generation from the LLM in ALL paths. The new flow:

```
ALL synthesis paths:
  1. LLM generates ONLY section content, starting from \section{Abstract and Introduction}
  2. Python code wraps the result with _build_preamble() + \end{document}
```

#### 3.2.1 `_build_preamble()` Upgrade

```python
def _build_preamble() -> str:
    return (
        "% !TEX program = xelatex\n"
        "% !TEX root = survey_draft.tex\n"
        r"\documentclass{ctexart}" + "\n"
        r"\usepackage[paper=a4paper, margin=1.8cm]{geometry}" + "\n"
        r"\usepackage{booktabs}" + "\n"
        r"\usepackage{tabularx}" + "\n"
        r"\usepackage{amsmath}" + "\n"
        r"\usepackage[backend=biber,style=gb7714-2015]{biblatex}" + "\n"
        r"\addbibresource{references.bib}" + "\n"
        r"\begin{document}" + "\n"
    )
```

#### 3.2.2 `build_synthesis_prompt()` Update

Add to REQUIREMENTS:
```
11. CRITICAL: Start your output DIRECTLY from \section{Abstract and Introduction}.
    Do NOT output \documentclass, any preamble commands, \begin{document}, or \end{document}.
    These are injected by the system automatically.
```

#### 3.2.3 `render_survey_tex_with_llm()` Update

Wrap the LLM output with the hardcoded preamble:
```python
def render_survey_tex_with_llm(...):
    prompt = build_synthesis_prompt(...)
    raw = extraction_fn(prompt)
    # Strip any preamble the LLM may have output anyway
    for marker in [r"\documentclass", r"\begin{document}"]:
        if marker in raw:
            raw = raw.split(marker)[-1]
            raw = raw.lstrip()
    # Wrap with hardcoded preamble
    return _build_preamble() + raw + "\n\n" + r"\end{document}" + "\n"
```

### 3.3 File Changes

| File | Change |
|------|--------|
| `core/synthesis.py` | Upgrade `_build_preamble()`; update `build_synthesis_prompt()`; refactor `render_survey_tex_with_llm()` to wrap with preamble |
| `tests/test_synthesis.py` | Update `ValidLaTeXExtractor` mock to not include preamble; add preamble wrap test |

### 3.4 Acceptance Criteria

- Single-pass output starts with `\documentclass{ctexart}` + geometry + packages + `\begin{document}`.
- Multi-stage output uses the same preamble.
- LLM output never contains `\documentclass`, `\begin{document}`, or `\end{document}`.
- All `validate_latex_syntax` checks pass.

---

## 4. Itemize Environment Constraint

### 4.1 Problem

LLM-generated technical taxonomies and consensus challenges are often written as long, dense paragraphs instead of structured lists.

### 4.2 Solution

Add to both `build_synthesis_prompt()` and `_build_section_prompt()`:

```
CRITICAL: When listing technical categories, consensus challenges, or research gaps,
you MUST use the \begin{itemize} LaTeX environment. Each category must be a separate \item.
Do NOT stack multiple categories in one long sentence paragraph.
```

### 4.3 File Changes

| File | Change |
|------|--------|
| `core/synthesis.py` | Add itemize constraint to `build_synthesis_prompt()` and `_build_section_prompt()` |
| `tests/test_synthesis.py` | Add test for itemize constraint in prompt |

---

## 5. Bold Leading Term Colon Constraint

### 5.1 Problem

When using `\textbf{...}` for bold leading terms, the LLM often omits punctuation after the closing brace, creating run-on text.

### 5.2 Solution

Add to both `build_synthesis_prompt()` and `_build_section_prompt()`:

```
CRITICAL: When using \textbf{...} for a bold leading term, you MUST immediately follow
the closing brace with a Chinese colon ：. 
Example: \textbf{第一类：}[explanation] — NOT \textbf{第一类}[explanation]
```

### 5.3 File Changes

| File | Change |
|------|--------|
| `core/synthesis.py` | Add colon constraint to `build_synthesis_prompt()` and `_build_section_prompt()` |
| `tests/test_synthesis.py` | Add test for colon constraint in prompt |

---

## Self-Review Checklist

- [x] **Placeholder scan:** No TBD/TODO.
- [x] **Internal consistency:** Preamble unification ensures both paths produce identical output structure.
- [x] **Scope check:** 5 independent items, each well-scoped.
- [x] **Ambiguity check:** CJK detection only triggers on brace mismatch; itemize applies to all sections; colon is specifically `：` not `:`.