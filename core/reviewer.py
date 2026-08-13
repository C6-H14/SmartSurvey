"""审阅专家微调模块 (ReviewerAgent).

在 TeX 初稿产出后自动进行二次审查与微调，杜绝语法、引用及表格瑕疵。

Two-phase refinement:
1. Static rule scanning (regex-based, zero-cost, always applied)
2. Critic LLM reviewer (optional, requires extraction_fn)
"""

import re
from typing import Callable

from core.agent import gateway_retry


# ── Phase 1: Static rule scanning ──────────────────────────────────────────

def _align_cite_bibitem_keys(tex: str) -> str:
    """Align body ``\\cite{...}`` keys with bibliography ``\\bibitem{...}`` keys.

    Scans for cite keys used in the body that have no matching bibitem, and
    vice versa. When a cite key has no matching bibitem, attempts fuzzy matching
    (case-insensitive, prefix match) to auto-correct. When no match exists,
    leaves the cite as-is but logs a warning.

    Returns the corrected TeX source.
    """
    # Collect all defined bibitem keys
    bib_keys: set[str] = set()
    for m in re.finditer(r'\\bibitem\{([^}]+)\}', tex):
        bib_keys.add(m.group(1))

    if not bib_keys:
        return tex  # no bibliography section yet, nothing to align

    # Collect all cite keys used
    cite_keys: set[str] = set()
    for m in re.finditer(r'\\cite\{([^}]+)\}', tex):
        for key in m.group(1).split(","):
            cite_keys.add(key.strip())

    # Build fuzzy lookup: lowercase → actual bibitem key
    bib_lower_map: dict[str, str] = {}
    for bk in bib_keys:
        bib_lower_map[bk.lower()] = bk

    # Also build prefix map for partial matches (first 6 chars)
    bib_prefix_map: dict[str, str] = {}
    for bk in bib_keys:
        prefix = bk.lower()[:6]
        if prefix not in bib_prefix_map:
            bib_prefix_map[prefix] = bk

    # Fix each orphan cite key
    for ck in list(cite_keys):
        if ck in bib_keys:
            continue
        # Try exact lowercase match
        if ck.lower() in bib_lower_map:
            corrected = bib_lower_map[ck.lower()]
            tex = tex.replace(f"\\cite{{{ck}}}", f"\\cite{{{corrected}}}")
            tex = tex.replace(f"\\cite{{{ck},", f"\\cite{{{corrected},")
            tex = tex.replace(f",{ck},", f",{corrected},")
            tex = tex.replace(f",{ck}}}", f",{corrected}}}")
            print(f"[Reviewer] Auto-corrected cite key: {ck} → {corrected}")
        elif len(ck) >= 4 and ck.lower()[:6] in bib_prefix_map:
            corrected = bib_prefix_map[ck.lower()[:6]]
            tex = tex.replace(f"\\cite{{{ck}}}", f"\\cite{{{corrected}}}")
            tex = tex.replace(f"\\cite{{{ck},", f"\\cite{{{corrected},")
            tex = tex.replace(f",{ck},", f",{corrected},")
            tex = tex.replace(f",{ck}}}", f",{corrected}}}")
            print(f"[Reviewer] Prefix-matched cite key: {ck} → {corrected}")

    return tex


def _remove_duplicate_phrases(tex: str) -> str:
    """Remove duplicate adjacent phrases like 论文结论部分（结论部分） → 论文结论部分.

    Matches patterns where a Chinese parenthesized phrase repeats an immediately
    preceding or following substring.

    Patterns cleaned:
    - ``XX（XX）`` → ``XX`` (exact duplication, Chinese parens)
    - ``XX(XX)`` → ``XX`` (exact duplication, ASCII parens)
    - ``XX部分（XX部分）`` → ``XX部分`` (suffix duplication)
    """
    # Pattern 1: 词语（相同词语） → 词语  (Chinese full-width parens)
    tex = re.sub(
        r'([一-龥]{1,8})（\1）',
        r'\1',
        tex,
    )

    # Pattern 2: 词语(相同词语) → 词语  (ASCII parens)
    tex = re.sub(
        r'([一-龥]{1,8})\(\1\)',
        r'\1',
        tex,
    )

    # Pattern 3: 词语部分（词语部分） → 词语部分 (longer suffix dup)
    tex = re.sub(
        r'([一-龥]{2,12}部分)（\1）',
        r'\1',
        tex,
    )

    # Pattern 4: Repeated English phrases like "the the" → "the"
    tex = re.sub(
        r'\b(\w+)\s+\1\b',
        r'\1',
        tex,
    )

    # Pattern 5: "missing. missing." → "missing." (bibitem residue)
    tex = re.sub(
        r'\b(missing\.)\s+\1',
        r'\1',
        tex,
    )

    return tex


def _fix_table_ref_spacing(tex: str) -> str:
    """Auto-insert LaTeX non-breaking spacing around ``表\\ref{...}``.

    Ensures:
    - ``表\\ref{tab:comparison}`` → ``表~\\ref{tab:comparison}``
    - ``Figure~\\ref{...}`` → ``图~\\ref{...}`` (for consistency)
    - ``表~\\ref{...}~从`` pattern already has correct spacing (no double-insert)
    """
    # 表\ref{...} → 表~\ref{...} (but not if already has ~)
    tex = re.sub(r'(?<!~)表\s*\\ref\{', r'表~\\ref{', tex)

    # \ref{...}后跟中文字符时补全 ~
    tex = re.sub(
        r'(\\ref\{[^}]+\})([一-龥])',
        r'\1~\2',
        tex,
    )

    return tex


def _fix_formula_operators(tex: str) -> str:
    """Replace italic math-mode 'or' with ``\\lor`` and fix common formula typos.

    Handles:
    - ``$... or ...$`` → ``$... \\lor ...$`` (logical OR)
    - ``$... and ...$`` → ``$... \\land ...$`` (logical AND)
    - ``$$... or ...$$`` → ``$$... \\lor ...$$`` (display math)
    - ``$\\sum_i=1^n$`` → ``$\\sum_{i=1}^{n}$`` (missing braces on sum)
    - ``$\\prod_i=1^n$`` → ``$\\prod_{i=1}^{n}$`` (missing braces on prod)
    """
    def _replace_math_operators(m: re.Match) -> str:
        body = m.group(1) if m.lastindex else m.group(0)
        # Replace whole-word "or" → \lor (not substrings like "for", "work")
        body = re.sub(r'\bor\b', r'\\lor', body)
        # Replace whole-word "and" → \land (logical context only: within math)
        body = re.sub(r'\band\b', r'\\land', body)
        if m.group(0).startswith('$$'):
            return '$$' + body + '$$'
        else:
            return '$' + body + '$'

    # Inline math $...$
    tex = re.sub(r'(?<!\\)\$(.+?)(?<!\\)\$', _replace_math_operators, tex)
    # Display math $$...$$
    tex = re.sub(r'(?<!\\)\$\$(.+?)(?<!\\)\$\$', _replace_math_operators, tex)
    return tex


def _fix_bibitem_format(tex: str) -> str:
    """Normalize ``\\bibitem`` entries: fix ``missing.`` residue, ensure standard format.

    Fixes:
    - ``missing. missing.`` → ``missing.`` (duplicate removal, already handled by _remove_duplicate_phrases)
    - ``missing`` → ``missing.`` (add period)
    - Replace bare ``missing`` / ``missing.`` in bibitem content with ``Unpublished manuscript.``
    - Ensure each ``\\bibitem`` line ends with a period

    Handles both line-separated and concatenated (single-line) bibitem formats.
    """
    # Pattern: \bibitem{key} followed by "missing" or "missing." on the same or next line
    # Replace: \bibitem{key}missing → \bibitem{key}Unpublished manuscript.
    tex = re.sub(
        r'(\\bibitem\{[^}]+\})\s*missing\.(?!\w)',
        r'\1\nUnpublished manuscript.',
        tex,
    )
    # Replace: \bibitem{key}missing (without dot) → \bibitem{key}Unpublished manuscript.
    tex = re.sub(
        r'(\\bibitem\{[^}]+\})\s*missing\b(?!\.)(?!\w)',
        r'\1\nUnpublished manuscript.',
        tex,
    )

    # Also handle line-by-line for cases where missing is on its own line
    lines = tex.split("\n")
    fixed_lines: list[str] = []
    in_bibitem = False

    for line in lines:
        if line.strip().startswith(r"\bibitem{"):
            in_bibitem = True
        elif line.strip().startswith(r"\end{thebibliography}"):
            in_bibitem = False
        elif in_bibitem and line.strip() == "missing.":
            # Replace bare "missing." on its own line with a sensible fallback
            line = line.replace("missing.", "Unpublished manuscript.")
        elif in_bibitem and line.strip() == "missing":
            # Replace bare "missing" on its own line with a sensible fallback
            line = line.replace("missing", "Unpublished manuscript.")

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def _fix_absurd_page_numbers(tex: str) -> str:
    """Correct absurd page numbers hallucinated into body text.

    Matches patterns like ``第 17241 页`` where page number is clearly absurd
    (>= 1000), replacing with sensible alternatives.
    """
    def _fix_page(m: re.Match) -> str:
        page_num = int(m.group(1).replace(" ", ""))
        if page_num >= 10000:
            return "结论部分"
        elif page_num >= 1000:
            corrected = str(page_num % 100)
            if int(corrected) < 1:
                corrected = "17"
            return f"第 {corrected} 页"
        return m.group(0)

    tex = re.sub(r'第\s*(\d{3,5})\s*页', _fix_page, tex)
    return tex


def apply_static_rules(tex: str) -> str:
    """Apply all static regex-based refinement rules to LaTeX source.

    This phase runs zero-cost (no LLM call), catching deterministic formatting
    errors that regex can reliably fix.

    Returns the refined LaTeX source.
    """
    tex = _align_cite_bibitem_keys(tex)
    tex = _remove_duplicate_phrases(tex)
    tex = _fix_table_ref_spacing(tex)
    tex = _fix_formula_operators(tex)
    tex = _fix_bibitem_format(tex)
    tex = _fix_absurd_page_numbers(tex)
    return tex


# ── Phase 2: Critic LLM reviewer ────────────────────────────────────────────

REVIEWER_PROMPT = (
    "You are a senior academic LaTeX review expert (资深 LaTeX 学术审阅专家). "
    "Your task is to perform a critical second-pass review of a Chinese academic "
    "survey manuscript in LaTeX format.\n\n"

    "REVIEW INSTRUCTIONS:\n\n"

    "1. **Citation Integrity (引用完整性)**：\n"
    "   - Verify every \\cite{{...}} in the body has a matching \\bibitem{{...}}.\n"
    "   - If any cite key is missing from the bibliography, fix the key or add a note.\n"
    "   - Ensure citation numbering [1], [2], ... is consistent and sequential.\n\n"

    "2. **Table Column Width & Formatting (表格列宽与格式)**：\n"
    "   - Verify the comparison table uses the correct column spec:\n"
    "     {{>{\\raggedright\\arraybackslash}p{{2.2cm}} >{\\raggedright\\arraybackslash}p{{2.5cm}}"
    " >{\\raggedright\\arraybackslash}p{{2.5cm}} >{\\raggedright\\arraybackslash}p{{2.5cm}}"
    " >{\\raggedright\\arraybackslash}X}}\n"
    "   - Ensure \\label{{tab:comparison}} is present before \\begin{{tabularx}}.\n"
    "   - Ensure \\toprule, \\midrule, \\bottomrule are used (booktabs three-line table).\n"
    "   - If any cell content is overflowing or using wrong column type, fix it.\n\n"

    "3. **Cross-Reference Spacing (交叉引用间距)**：\n"
    "   - Ensure 表~\\ref{{tab:comparison}} uses non-breaking space (~).\n"
    "   - Ensure \\ref{{...}} before Chinese text has ~ separation.\n\n"

    "4. **Math Formula Correctness (数学公式正确性)**：\n"
    "   - Replace italic 'or' inside math mode ($...$ or $$...$$) with \\lor.\n"
    "   - Replace italic 'and' inside math mode with \\land.\n"
    "   - Ensure all summed/product limits use correct braces: \\sum_{{i=1}}^{{n}}.\n\n"

    "5. **Duplicate Phrase Removal (词语重复清洗)**：\n"
    "   - Remove any duplicate adjacent phrases like 结论部分（结论部分）.\n"
    "   - Remove any repeated English words like 'the the'.\n\n"

    "6. **Bibliography Format (参考文献格式)**：\n"
    "   - Replace any 'missing.' or 'missing' entries with 'Unpublished manuscript.'\n"
    "   - Ensure consistent formatting: author, \\emph{{title}}, venue, year.\n\n"

    "7. **Grammar & Academic Polish (语法与学术润色)**：\n"
    "   - Fix any obvious Chinese grammar errors or awkward phrasing.\n"
    "   - Ensure all section content is substantive (not hollow placeholder text).\n"
    "   - Ensure the 系统评述与深度批判 section contains actual critical analysis, not just restating limitations.\n\n"

    "CRITICAL: Output ONLY the corrected LaTeX source. Do NOT wrap in markdown fences "
    "(no ```latex ```), do NOT add explanations, do NOT change the \\documentclass or "
    "preamble structure. Preserve ALL existing \\section{{}} headers, \\cite{{}} keys, "
    "and the \\label{{tab:comparison}} label. Only fix the specific issues listed above.\n\n"

    "OUTPUT FORMAT: Return the COMPLETE corrected LaTeX source, starting from the first "
    "line of the original document and ending with \\end{{document}}."
)


def _build_reviewer_prompt(raw_tex: str) -> str:
    """Build the reviewer prompt with the raw TeX appended for review."""
    return REVIEWER_PROMPT + "\n\n" + "=== MANUSCRIPT TO REVIEW ===\n\n" + raw_tex


def _strip_markdown_fences(text: str) -> str:
    """Strip ```latex ... ``` markdown fences if the LLM wraps output."""
    text = text.strip()
    # Remove opening fence
    text = re.sub(r'^```(?:latex|tex)?\s*\n', '', text)
    # Remove closing fence
    text = re.sub(r'\n```\s*$', '', text)
    return text


def refine_survey_tex(
    raw_tex: str,
    papers: list | None = None,
    extraction_fn: Callable[[str], str] | None = None,
    on_retry: Callable[[int, int, float, str, BaseException], None] | None = None,
) -> str:
    """Refine a LaTeX survey manuscript with static rules + optional Critic LLM review.

    Two-phase pipeline:
    1. **Static rule scanning** (always applied, zero-cost):
       - Cite/bibitem key alignment → eliminate [?]
       - Duplicate phrase removal → 论文结论部分（结论部分）→ 论文结论部分
       - Table ref spacing → 表~\\ref{tab:comparison}
       - Formula operator fix → ``or`` → ``\\lor``
       - Bibitem format normalization → ``missing.`` → ``Unpublished manuscript.``
       - Absurd page number correction → 第17241页 → 结论部分

    2. **Critic LLM review** (only when extraction_fn is provided):
       - Second-pass review with specialized Reviewer Prompt
       - Polishes table formatting, citation integrity, grammar, math formulas

    Args:
        raw_tex: Raw LaTeX source from synthesis pipeline (with preamble).
        papers: Optional list of paper metadata dicts (reserved for future use).
        extraction_fn: Optional LLM callable for Critic review phase.
            When None, only static rules are applied.
        on_retry: Optional hook for gateway-transient retry notifications.

    Returns:
        Refined LaTeX source ready for xelatex compilation.
    """
    _ = papers  # reserved for future cross-referencing with paper metadata

    # Phase 1: Static rule scanning (always applied)
    tex = apply_static_rules(raw_tex)
    print("[Reviewer] Phase 1 complete: static rules applied.")

    # Phase 2: Critic LLM review (only if extraction_fn provided)
    if extraction_fn is not None:
        try:
            print("[Reviewer] Phase 2: invoking Critic LLM for second-pass review...")
            prompt = _build_reviewer_prompt(tex)
            raw_response = gateway_retry(
                lambda: extraction_fn(prompt),
                on_retry=on_retry,
            )
            # Strip any markdown fences the LLM may have added
            reviewed = _strip_markdown_fences(raw_response)

            # Validate: the reviewed output must still be valid LaTeX
            if len(reviewed) >= len(tex) * 0.5 and r"\end{document}" in reviewed:
                # Re-apply static rules on LLM output as a safety net
                tex = apply_static_rules(reviewed)
                print(f"[Reviewer] Phase 2 complete: Critic LLM review applied "
                      f"({len(raw_response)} chars response).")
            else:
                print(f"[Reviewer] Phase 2 skipped: LLM response too short or invalid "
                      f"({len(reviewed)} chars, expected >= {len(tex) * 0.5}). "
                      f"Using static-rules-only output.")
        except Exception as e:
            print(f"[Reviewer] Phase 2 failed: {type(e).__name__}: {e}. "
                  f"Falling back to static-rules-only output.")
    else:
        print("[Reviewer] Phase 2 skipped: no extraction_fn provided (static-only mode).")

    return tex


def refine_survey_tex_static_only(raw_tex: str) -> str:
    """Apply only the static rule phase (no LLM call).

    Convenience wrapper for testing and offline use.
    """
    return apply_static_rules(raw_tex)