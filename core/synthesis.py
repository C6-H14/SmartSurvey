import re
from typing import Callable

from core.models import AcademicMatrixRow


def validate_latex_syntax(latex_source: str) -> list[str]:
    """Validate LaTeX syntax with zero-dependency stack scanning.

    Checks:
    1. Inline math $...$ parity (ignoring escaped \\$)
    2. Display math $$...$$ parity
    3. \\begin{env}/\\end{env} pairing via stack
    4. Curly brace {} balance (ignoring escaped \\{ \\})

    Returns list of error messages (empty = valid).
    """
    errors: list[str] = []

    # Check 1: Inline math $...$ and display math $$...$$ parity
    in_display_math = False
    in_inline_math = False
    i = 0
    while i < len(latex_source):
        if latex_source[i] == '\\' and i + 1 < len(latex_source):
            i += 2  # skip escaped character
            continue
        if latex_source[i] == '$':
            # Check if it's $$ (display math)
            if i + 1 < len(latex_source) and latex_source[i + 1] == '$':
                in_display_math = not in_display_math
                i += 2
            else:
                in_inline_math = not in_inline_math
                i += 1
        else:
            i += 1
    if in_display_math:
        errors.append("Unclosed display math: $$ without closing $$.")
    if in_inline_math:
        errors.append("Unclosed inline math: $ without closing $.")

    # Check 2: \begin{env} / \end{env} pairing
    env_stack: list[str] = []
    for match in re.finditer(r'\\(begin|end)\{(\w+)\}', latex_source):
        keyword, env_name = match.group(1), match.group(2)
        if keyword == 'begin':
            env_stack.append(env_name)
        elif keyword == 'end':
            if not env_stack:
                errors.append(f"Extra \\end{{{env_name}}} with no matching \\begin.")
            else:
                opened = env_stack.pop()
                if opened != env_name:
                    errors.append(
                        f"Mismatched environment: \\begin{{{opened}}} closed by \\end{{{env_name}}}."
                    )
    if env_stack:
        for leftover in env_stack:
            errors.append(f"Unclosed environment: \\begin{{{leftover}}} has no matching \\end.")

    # Check 3: Curly brace {} balance with CJK bracket detection
    brace_count = 0
    cjk_brackets = {"》", "】", "」"}
    i = 0
    while i < len(latex_source):
        if latex_source[i] == '\\' and i + 1 < len(latex_source):
            i += 2  # skip escaped character
            continue
        if latex_source[i] == '{':
            brace_count += 1
        elif latex_source[i] == '}':
            brace_count -= 1
            if brace_count < 0:
                errors.append("Extra closing brace encountered.")
                brace_count = 0
        elif latex_source[i] in cjk_brackets and brace_count > 0:
            # CJK bracket detected while braces are still open -- likely a hallucination
            context_start = max(0, i - 20)
            context_end = min(len(latex_source), i + 10)
            context = latex_source[context_start:context_end].replace("\n", " ")
            errors.append(
                f"CJK character '{latex_source[i]}' detected near position {i} "
                f"(context: ...{context}...) -- possibly replacing '}}'. "
                f"Fix all CJK brackets in LaTeX source."
            )
        i += 1
    if brace_count > 0:
        errors.append(f"Unclosed brace: {brace_count} unmatched opening brace(s).")

    return errors


def build_synthesis_prompt(
    topic: str,
    rows: list[AcademicMatrixRow],
    word_count_target: int = 3000,
) -> str:
    """Build a constrained system prompt for LLM-driven LaTeX synthesis.

    The prompt forces the LLM to:
    - Use ctexart document class.
    - Include exactly 6 required \\section{...} headers.
    - Embed the booktabs matrix table from provided row data.
    - Return ONLY valid LaTeX source (no markdown fences, no explanations).
    """
    paper_list = "\n".join(
        f"  - {row.title} ({row.authors}, {row.year}, {row.venue})"
        for row in rows
    )

    matrix_rows = "\n".join(
        f"    {row.title} & {row.method} & {row.limitation} \\\\"
        for row in rows
    )

    return (
        f"You are an academic writing assistant. Generate a Chinese academic survey manuscript in LaTeX.\n\n"
        f"Review topic: {topic}\n\n"
        f"Papers to review ({len(rows)} total):\n{paper_list}\n\n"
        f"Extracted comparison data:\n"
        f"\\begin{{tabularx}}{{\\textwidth}}{{XXXX}}\n"
        f"  Paper & Method & Limitation \\\\\n"
        f"  \\midrule\n{matrix_rows}"
        f"\\end{{tabularx}}\n\n"
        f"REQUIREMENTS:\n"
        f"1. Use \\documentclass{{ctexart}}, \\usepackage{{booktabs}}, and \\usepackage{{tabularx}}.\n"
        f"2. Include EXACTLY these six sections:\n"
        f"   \\section{{Abstract and Introduction}}\n"
        f"   \\section{{Technical Taxonomy}}\n"
        f"   \\section{{Systematic Review and Deep Critique}}\n"
        f"   \\section{{Academic Comparison Matrix}}\n"
        f"   \\section{{Research Gaps and Future Work}}\n"
        f"   \\section{{Conclusion}}\n"
        f"3. The \\section{{Academic Comparison Matrix}} must contain a full booktabs table using tabularx.\n"
        f"4. Each critique of a paper's limitation must reference its evidence_page.\n"
        f"5. Write body text in Chinese, keep evidence quotes in English.\n"
        f"6. Total length: {word_count_target} Chinese characters.\n"
        f"7. Return ONLY valid LaTeX source. No markdown fences, no explanations.\n"
        f"8. All $, {{, }}, \\begin, \\end must be properly balanced.\n"
        f"9. CRITICAL: Chapter 1 (Abstract and Introduction) MUST strictly start and format with: "
        f"\\noindent\\textbf{{摘要：}}[abstract text]\\par\\bigskip\\noindent\\textbf{{引言：}}[introduction text]\n"
        f"   Do NOT output long paragraphs without this format separation.\n"
        f"10. CRITICAL: In the Academic Comparison Matrix table, the 'method' and 'limitation' "
        f"columns MUST be written in Chinese, no more than 20 Chinese characters each, "
        f"as a concise academic summary. No long English paragraphs allowed in table cells.\n"
    )


MAX_SYNTHESIS_RETRIES = 1


def _build_latex_healing_prompt(
    original_prompt: str,
    errors: list[str],
    broken_latex: str,
) -> str:
    """Build XML correction prompt for LaTeX self-healing."""
    error_xml = "\n".join(f"  <error>{e}</error>" for e in errors)
    return (
        original_prompt
        + "\n\n<latex-validation-errors>\n"
        + error_xml
        + "\n</latex-validation-errors>\n"
        + "<broken-latex>\n"
        + "```latex\n"
        + broken_latex
        + "\n```\n"
        + "</broken-latex>\n"
        + "<self-healing-instruction>\n"
        + "  The LaTeX source above contains syntax errors. "
        + "Fix ALL errors listed above and return ONLY the corrected LaTeX source.\n"
        + "</self-healing-instruction>"
    )


def render_survey_tex_with_llm(
    topic: str,
    rows: list[AcademicMatrixRow],
    extraction_fn: Callable[[str], str],
    word_count_target: int = 3000,
    progress_callback: Callable[[int, int, str, str], None] | None = None,
) -> str:
    """Generate a full Chinese LaTeX manuscript using LLM-driven synthesis.

    Validates the output with LaTeX syntax checking and triggers a self-healing
    retry if validation fails. Falls back to returning the raw LaTeX source
    (even with errors) after exhausting retries -- the caller decides how to
    handle imperfect output.

    Args:
        topic: Review topic string.
        rows: Verified academic matrix rows.
        extraction_fn: LLM callable (prompt -> raw response).
        word_count_target: Target word count for the manuscript.
        progress_callback: Optional progress callback.

    Returns:
        Complete LaTeX manuscript string (may contain syntax errors if
        self-healing retry is exhausted -- caller decides how to handle).
    """
    prompt = build_synthesis_prompt(topic, rows, word_count_target=word_count_target)

    for attempt in range(MAX_SYNTHESIS_RETRIES + 1):
        if progress_callback:
            state = "extracting" if attempt == 0 else "self_healing"
            detail = "Generating LaTeX manuscript..." if attempt == 0 else f"Retry {attempt}/{MAX_SYNTHESIS_RETRIES}: Fixing LaTeX syntax errors..."
            progress_callback(0, 1, state, detail)

        raw = extraction_fn(prompt)
        raw_len = len(raw)
        raw_preview = raw[:200].replace("\n", " ").strip()
        print(f"[LLM] Generated {raw_len} chars: {raw_preview}")
        errors = validate_latex_syntax(raw)

        if not errors:
            if progress_callback:
                progress_callback(0, 1, "completed", "LaTeX manuscript generated successfully.")
            return raw

        if attempt < MAX_SYNTHESIS_RETRIES:
            prompt = _build_latex_healing_prompt(prompt, errors, raw)

    # Fallback: return raw LaTeX even if validation fails
    if progress_callback:
        progress_callback(0, 1, "completed",
            f"LaTeX generated with {len(errors)} unresolved syntax error(s).")
    return raw


def _build_preamble() -> str:
    """Hardcoded LaTeX preamble with xelatex magic comments.

    Never generated by LLM — ensures compile safety across Overleaf and VS Code.
    """
    return (
        "% !TEX program = xelatex\n"
        "% !TEX root = survey_draft.tex\n"
        r"\documentclass{ctexart}" + "\n"
        r"\usepackage{booktabs}" + "\n"
        r"\usepackage{tabularx}" + "\n"
        r"\usepackage[backend=biber,style=gb7714-2015]{biblatex}" + "\n"
        r"\addbibresource{references.bib}" + "\n"
        r"\begin{document}" + "\n"
    )


SECTION_NAMES = [
    "Abstract and Introduction",
    "Technical Taxonomy",
    "Systematic Review and Deep Critique",
    "Academic Comparison Matrix",
    "Research Gaps and Future Work",
    "Conclusion",
]


def _build_section_prompt(
    section_index: int,
    topic: str,
    rows: list[AcademicMatrixRow],
    word_count_target: int,
    chained_context: str = "",
) -> str:
    """Build a prompt for generating one section of the survey.

    Args:
        section_index: 0-based index of the section (0-5).
        topic: Review topic string.
        rows: All academic matrix rows (full data for cross-paper comparison).
        word_count_target: Total target word count (divided among sections).
        chained_context: Previously generated sections (1..N-1) for style continuity.

    Returns:
        Complete prompt string for the LLM call.
    """
    section_name = SECTION_NAMES[section_index]
    section_word_target = max(300, word_count_target // 6)

    paper_list = "\n".join(
        f"  - {row.title} ({row.authors}, {row.year}, {row.venue})"
        for row in rows
    )

    full_prompt = (
        f"You are an academic writing assistant. Generate ONE section of a Chinese academic survey manuscript in LaTeX.\n\n"
        f"Review topic: {topic}\n\n"
        f"All papers in the review ({len(rows)} total):\n{paper_list}\n\n"
        f"Full extracted comparison data (rows JSON):\n"
        f"{rows}\n\n"
        f"YOUR TASK: Generate ONLY the LaTeX content for this section:\n"
        f"  \\section{{{section_name}}}\n\n"
        f"Target: ~{section_word_target} Chinese characters for this section.\n"
        f"IMPORTANT: Output ONLY the section content, starting with \\section{{{section_name}}}.\n"
        f"Do NOT include \\documentclass, preamble, \\begin{{document}}, or \\end{{document}}.\n"
        f"Write body text in Chinese, keep evidence quotes in English.\n"
    )

    if chained_context:
        full_prompt += (
            f"\nPREVIOUSLY GENERATED SECTIONS (read for style continuity, do NOT repeat):\n"
            f"{chained_context}\n\n"
            f"Please carefully review the writing style, terminology, and logical flow of the previously "
            f"generated sections above. Continue naturally from where the last section ended, "
            f"ensuring consistent terminology and seamless transitions. Do NOT repeat content "
            f"that was already covered in previous sections.\n"
        )

    # Add separator constraint for section 0
    if section_index == 0:
        full_prompt += (
            f"\nCRITICAL FORMAT REQUIREMENT for Section 1:\n"
            f"  \\noindent\\textbf{{摘要：}}[abstract text]"
            f"\\par\\bigskip\\noindent\\textbf{{引言：}}[introduction text]\n"
            f"  Do NOT output long paragraphs without this format separation.\n"
        )

    full_prompt += (
        f"\nReturn ONLY valid LaTeX source for this section. No markdown fences, no explanations.\n"
    )
    return full_prompt


def render_survey_tex_multi_stage(
    topic: str,
    rows: list[AcademicMatrixRow],
    extraction_fn: Callable[[str], str],
    word_count_target: int = 10000,
    progress_callback: Callable[[int, int, str, str], None] | None = None,
) -> str:
    """Generate a full Chinese LaTeX manuscript using chained multi-stage synthesis.

    Splits the 6 sections into 6 independent LLM calls, each receiving the full
    rows data and previously generated sections as chained context.

    Args:
        topic: Review topic string.
        rows: Verified academic matrix rows.
        extraction_fn: LLM callable (prompt -> raw response).
        word_count_target: Total target word count (divided among sections).
        progress_callback: Optional progress callback.

    Returns:
        Complete LaTeX manuscript string with preamble + 6 sections + \end{document}.
    """
    # Start with hardcoded preamble
    parts = [_build_preamble()]
    chained_context = ""

    for i, section_name in enumerate(SECTION_NAMES):
        if progress_callback:
            progress_callback(0, 1, "extracting",
                f"Generating section {i+1}/6: {section_name}...")

        prompt = _build_section_prompt(
            section_index=i,
            topic=topic,
            rows=rows,
            word_count_target=word_count_target,
            chained_context=chained_context,
        )

        raw = extraction_fn(prompt)
        raw_len = len(raw)
        print(f"[LLM] Multi-stage section {i+1}/6 ({section_name}): {raw_len} chars")

        # Strip potential preamble from section 1 output
        if i == 0:
            for marker in [r"\documentclass", r"\begin{document}"]:
                if marker in raw:
                    raw = raw.split(marker)[-1]
                    raw = raw.lstrip()

        parts.append(raw + "\n\n")
        chained_context += f"\\section{{{section_name}}}\n{raw}\n\n"

    # Append \end{document}
    parts.append(r"\end{document}" + "\n")

    result = "".join(parts)

    # Validate and log
    errors = validate_latex_syntax(result)
    if errors:
        print(f"[LLM] Multi-stage synthesis completed with {len(errors)} validation warnings:")
        for e in errors:
            print(f"  - {e}")

    if progress_callback:
        progress_callback(0, 1, "completed",
            f"Multi-stage synthesis complete: {len(parts)} sections, {len(result)} chars.")

    return result