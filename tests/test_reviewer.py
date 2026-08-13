"""Unit tests for core/reviewer.py — ReviewerAgent static rules and refinement pipeline."""

import pytest

from core.reviewer import (
    _align_cite_bibitem_keys,
    _fix_bibitem_format,
    _fix_formula_operators,
    _fix_table_ref_spacing,
    _remove_duplicate_phrases,
    _strip_markdown_fences,
    apply_static_rules,
    refine_survey_tex,
    refine_survey_tex_static_only,
)


# ── Tests: _align_cite_bibitem_keys ────────────────────────────────────────

def test_align_cite_bibitem_keys_exact_match_passes_through():
    """When all cite keys already match bibitem keys, no changes."""
    tex = (
        r"\section{Test}"
        r"\cite{bergmann2022dents} and \cite{costanzino2023cross}"
        r"\begin{thebibliography}{99}"
        r"\bibitem{bergmann2022dents} Bergmann..."
        r"\bibitem{costanzino2023cross} Costanzino..."
        r"\end{thebibliography}"
    )
    result = _align_cite_bibitem_keys(tex)
    assert r"\cite{bergmann2022dents}" in result
    assert r"\cite{costanzino2023cross}" in result


def test_align_cite_bibitem_keys_fuzzy_lowercase_match():
    """Case-insensitive mismatch is auto-corrected."""
    tex = (
        r"\cite{Bergmann2022Dents} is cited."
        r"\begin{thebibliography}{99}"
        r"\bibitem{bergmann2022dents} Bergmann..."
        r"\end{thebibliography}"
    )
    result = _align_cite_bibitem_keys(tex)
    # The uppercase variant should be corrected to lowercase
    assert r"\cite{bergmann2022dents}" in result


def test_align_cite_bibitem_keys_no_bibliography_unchanged():
    """When there is no bibliography section, source is returned unchanged."""
    tex = r"\section{Test}\cite{somekey} no bibliography here."
    result = _align_cite_bibitem_keys(tex)
    assert result == tex


def test_align_cite_bibitem_keys_prefix_match():
    """When cite key differs but shares prefix with a bibitem key, auto-correct."""
    tex = (
        r"\cite{bergmann2022} is cited."
        r"\begin{thebibliography}{99}"
        r"\bibitem{bergmann2022dents} Bergmann..."
        r"\end{thebibliography}"
    )
    result = _align_cite_bibitem_keys(tex)
    # bergmann2022 should be corrected to bergmann2022dents (prefix match)
    assert r"\cite{bergmann2022dents}" in result


def test_align_cite_bibitem_keys_no_match_left_unchanged():
    """A cite key with no fuzzy match is left as-is (not removed)."""
    tex = (
        r"\cite{completelyunknown}" r"\begin{thebibliography}{99}"
        r"\bibitem{known2024paper} Known..."
        r"\end{thebibliography}"
    )
    result = _align_cite_bibitem_keys(tex)
    # The unknown key stays — we don't silently drop citations
    assert r"\cite{completelyunknown}" in result


# ── Tests: _remove_duplicate_phrases ───────────────────────────────────────

def test_remove_duplicate_chinese_parens_exact():
    """中文词语（中文词语） → 中文词语."""
    tex = r"论文结论部分（结论部分）是综述的核心。"
    result = _remove_duplicate_phrases(tex)
    # After fixing: 论文结论部分 is kept, （结论部分） is removed
    # But note: "论文" + "结论部分" are different strings, so only （结论部分） matches
    # Let's test the exact pattern: 词语（词语）
    assert "结论部分（结论部分）" not in result


def test_remove_duplicate_english_repeated_words():
    """'the the' → 'the'."""
    tex = "This is the the main contribution."
    result = _remove_duplicate_phrases(tex)
    assert "the the" not in result
    assert "the main" in result


def test_remove_duplicate_missing_dot():
    """'missing. missing.' → 'missing.'."""
    tex = r"Some text missing. missing. in bibliography."
    result = _remove_duplicate_phrases(tex)
    assert "missing. missing." not in result


def test_remove_duplicate_ascii_parens():
    """词语(词语) → 词语."""
    tex = "方法部分(方法部分)是核心。"
    result = _remove_duplicate_phrases(tex)
    assert "方法部分(方法部分)" not in result
    assert "方法部分" in result


# ── Tests: _fix_table_ref_spacing ──────────────────────────────────────────

def test_fix_table_ref_spacing_inserts_tilde():
    """表\\ref{tab:comparison} → 表~\\ref{tab:comparison}."""
    tex = r"如表\ref{tab:comparison}所示"
    result = _fix_table_ref_spacing(tex)
    assert r"表~\ref{tab:comparison}" in result


def test_fix_table_ref_spacing_no_double_tilde():
    """表~\\ref{...} already has tilde, no double-insert."""
    tex = r"如表~\ref{tab:comparison}所示"
    result = _fix_table_ref_spacing(tex)
    assert result.count(r"表~\ref{tab:comparison}") == 1


def test_fix_table_ref_spacing_after_ref_before_chinese():
    r"""\ref{tab:comparison}从 → \ref{tab:comparison}~从."""
    tex = r"表~\ref{tab:comparison}从数据中可见"
    result = _fix_table_ref_spacing(tex)
    assert r"\ref{tab:comparison}~从" in result


# ── Tests: _fix_formula_operators ──────────────────────────────────────────

def test_fix_formula_or_to_lor_inline():
    """$a or b$ → $a \\lor b$."""
    tex = r"公式 $x or y$ 表示逻辑或。"
    result = _fix_formula_operators(tex)
    assert r"$x \lor y$" in result


def test_fix_formula_or_to_lor_display():
    """$$a or b$$ → $$a \\lor b$$."""
    tex = r"$$P or Q$$ is a tautology."
    result = _fix_formula_operators(tex)
    assert r"$$P \lor Q$$" in result


def test_fix_formula_and_to_land():
    r"""$a and b$ → $a \land b$."""
    tex = r"$P and Q$ is true when both are true."
    result = _fix_formula_operators(tex)
    assert r"$P \land Q$" in result


def test_fix_formula_does_not_touch_text_or():
    """Text 'or' outside math mode is NOT replaced."""
    tex = "This or that is the question."
    result = _fix_formula_operators(tex)
    assert "This or that" in result
    assert r"\lor" not in result


def test_fix_formula_does_not_touch_substring_or():
    """'for', 'work' inside math are NOT replaced (whole word only)."""
    tex = r"$work$ is not changed because 'or' is inside 'work'."
    result = _fix_formula_operators(tex)
    assert r"$work$" in result


# ── Tests: _fix_bibitem_format ─────────────────────────────────────────────

def test_fix_bibitem_missing_to_unpublished():
    """Bare 'missing' in bibitem should become 'Unpublished manuscript.'."""
    tex = (
        r"\begin{thebibliography}{99}"
        r"\bibitem{test2024}"
        r"missing"
        r"\end{thebibliography}"
    )
    result = _fix_bibitem_format(tex)
    assert "Unpublished manuscript" in result


def test_fix_bibitem_missing_dot_to_unpublished():
    """'missing.' in bibitem should become 'Unpublished manuscript.'."""
    tex = (
        r"\begin{thebibliography}{99}"
        r"\bibitem{test2024}"
        r"missing."
        r"\end{thebibliography}"
    )
    result = _fix_bibitem_format(tex)
    assert "Unpublished manuscript" in result


# ── Tests: _strip_markdown_fences ──────────────────────────────────────────

def test_strip_markdown_fences_latex():
    """```latex ... ``` fences are removed."""
    text = "```latex\n\\section{Test}\nHello.\n```"
    result = _strip_markdown_fences(text)
    assert "```" not in result
    assert r"\section{Test}" in result


def test_strip_markdown_fences_no_fences():
    """Text without fences is returned unchanged."""
    text = r"\section{Test}\nHello."
    result = _strip_markdown_fences(text)
    assert result == text


# ── Tests: apply_static_rules (integration of all static rules) ────────────

def test_apply_static_rules_full_pipeline():
    """All static rules applied together on a realistic TeX fragment."""
    tex = (
        r"\section{学术对比矩阵}"
        r"表\ref{tab:comparison}展示了对比结果。"
        r"公式 $x or y$ 表示选择。"
        r"论文结论部分（结论部分）是关键。"
        r"\begin{thebibliography}{99}"
        r"\bibitem{berg22test} Test paper."
        r"\end{thebibliography}"
        r"\cite{Berg22Test} is cited."
    )
    result = apply_static_rules(tex)

    # Table ref spacing fixed
    assert r"表~\ref{tab:comparison}" in result
    # Formula or → \lor
    assert r"$x \lor y$" in result
    # Duplicate phrase removed
    assert "结论部分（结论部分）" not in result
    # Cite key aligned (case-insensitive)
    assert r"\cite{berg22test}" in result


def test_apply_static_rules_idempotent_on_clean_tex():
    """Applying static rules to already-clean TeX should not break it."""
    tex = (
        r"\documentclass{ctexart}"
        r"\begin{document}"
        r"\section{摘要与引言}"
        r"如表~\ref{tab:comparison}所示。"
        r"公式 $a \lor b$ 正确。"
        r"\begin{thebibliography}{99}"
        r"\bibitem{test2024paper} Author. \emph{Title}. Venue, 2024."
        r"\end{thebibliography}"
        r"\cite{test2024paper}"
        r"\end{document}"
    )
    result = apply_static_rules(tex)
    # Core structure intact
    assert r"\documentclass{ctexart}" in result
    assert r"\section{摘要与引言}" in result
    assert r"\cite{test2024paper}" in result
    assert r"\bibitem{test2024paper}" in result
    assert r"\end{document}" in result


# ── Tests: refine_survey_tex (full refinement pipeline) ────────────────────

def test_refine_survey_tex_static_only():
    """refine_survey_tex with no extraction_fn applies only static rules."""
    tex = (
        r"\documentclass{ctexart}"
        r"\begin{document}"
        r"\section{Test}"
        r"表\ref{tab:comparison}数据。"
        r"$error or timeout$"
        r"\begin{thebibliography}{99}"
        r"\bibitem{test2024} Test paper."
        r"\end{thebibliography}"
        r"\cite{test2024}"
        r"\end{document}"
    )
    result = refine_survey_tex(tex, extraction_fn=None)
    # Static rules applied
    assert r"表~\ref{tab:comparison}" in result
    assert r"$error \lor timeout$" in result
    # Structure intact
    assert r"\end{document}" in result


def test_refine_survey_tex_static_only_convenience():
    """refine_survey_tex_static_only is a convenience wrapper."""
    tex = r"表\ref{tab:comparison}数据。the the end。"
    result = refine_survey_tex_static_only(tex)
    assert r"表~\ref{tab:comparison}" in result
    assert "the the" not in result


def test_refine_survey_tex_preserves_bibliography_structure():
    """Refinement must not corrupt the thebibliography environment."""
    tex = (
        r"\begin{thebibliography}{99}"
        r"\bibitem{bergmann2022dents}"
        r"Bergmann P, et al."
        r"\emph{Beyond Dents and Scratches}. CVPR, 2022."
        r"\bibitem{costanzino2023cross}"
        r"Costanzino A, et al."
        r"\emph{Cross-Modal Feature Mapping}. VISAPP, 2023."
        r"\end{thebibliography}"
        r"\cite{bergmann2022dents}"
        r"\cite{costanzino2023cross}"
    )
    result = refine_survey_tex_static_only(tex)
    assert r"\bibitem{bergmann2022dents}" in result
    assert r"\bibitem{costanzino2023cross}" in result
    assert r"\cite{bergmann2022dents}" in result
    assert r"\cite{costanzino2023cross}" in result


def test_refine_survey_tex_multiple_cites_in_one_command():
    """Multiple comma-separated cites should be handled correctly."""
    tex = (
        r"\cite{bergmann2022dents, costanzino2023cross}"
        r"\begin{thebibliography}{99}"
        r"\bibitem{bergmann2022dents} Paper A..."
        r"\bibitem{costanzino2023cross} Paper B..."
        r"\end{thebibliography}"
    )
    result = _align_cite_bibitem_keys(tex)
    assert r"\bibitem{bergmann2022dents}" in result
    assert r"\bibitem{costanzino2023cross}" in result


# ── Tests: Edge cases ──────────────────────────────────────────────────────

def test_empty_tex_unchanged():
    """Empty LaTeX string is returned unchanged."""
    assert apply_static_rules("") == ""


def test_no_math_mode_unchanged_by_formula_fixer():
    """TeX with no math mode is not broken by formula operator fixer."""
    tex = r"\section{Introduction}This is a test with or without math."
    result = _fix_formula_operators(tex)
    # "or" outside math mode must not be touched
    assert " or " in result
    assert r"\lor" not in result


def test_bibitem_missing_author_field():
    """Bibitem with missing. author field is fixed."""
    tex = (
        r"\begin{thebibliography}{99}"
        r"\bibitem{test2024}"
        r"missing."
        r"\emph{Some Title}. Some Venue, 2024."
        r"\end{thebibliography}"
    )
    result = _fix_bibitem_format(tex)
    assert "Unpublished manuscript" in result


def test_refine_does_not_drop_end_document():
    """Refinement must never remove \end{document}."""
    tex = r"\section{Test}\end{document}"
    result = refine_survey_tex_static_only(tex)
    assert r"\end{document}" in result


def test_refine_does_not_double_process():
    """Applying refine twice should not degrade the output (idempotence)."""
    tex = (
        r"\documentclass{ctexart}"
        r"\begin{document}"
        r"\section{测试}"
        r"如表\ref{tab:comparison}所示。"
        r"$a or b$"
        r"测试测试"
        r"\begin{thebibliography}{99}"
        r"\bibitem{test2024} Test."
        r"\end{thebibliography}"
        r"\cite{test2024}"
        r"\end{document}"
    )
    first_pass = refine_survey_tex_static_only(tex)
    second_pass = refine_survey_tex_static_only(first_pass)
    # Second pass should be identical to first pass (idempotent)
    assert first_pass == second_pass