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

    # Check 3: Curly brace {} balance
    brace_count = 0
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
        i += 1
    if brace_count > 0:
        errors.append(f"Unclosed brace: {brace_count} unmatched opening brace(s).")

    return errors


def build_synthesis_prompt(topic: str, rows: list[AcademicMatrixRow]) -> str:
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
        f"\\begin{{tabular}}{{lll}}\n"
        f"  Paper & Method & Limitation \\\\\n"
        f"  \\midrule\n{matrix_rows}"
        f"\\end{{tabular}}\n\n"
        f"REQUIREMENTS:\n"
        f"1. Use \\documentclass{{ctexart}} and \\usepackage{{booktabs}}.\n"
        f"2. Include EXACTLY these six sections:\n"
        f"   \\section{{Abstract and Introduction}}\n"
        f"   \\section{{Technical Taxonomy}}\n"
        f"   \\section{{Systematic Review and Deep Critique}}\n"
        f"   \\section{{Academic Comparison Matrix}}\n"
        f"   \\section{{Research Gaps and Future Work}}\n"
        f"   \\section{{Conclusion}}\n"
        f"3. The \\section{{Academic Comparison Matrix}} must contain a full booktabs table.\n"
        f"4. Each critique of a paper's limitation must reference its evidence_page.\n"
        f"5. Write body text in Chinese, keep evidence quotes in English.\n"
        f"6. Total length: 3000-5000 Chinese characters.\n"
        f"7. Return ONLY valid LaTeX source. No markdown fences, no explanations.\n"
        f"8. All $, {{, }}, \\begin, \\end must be properly balanced.\n"
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
        + "<self-healing-instruction>\n"
        + "  The LaTeX source above contains syntax errors. "
        + "Fix ALL errors listed above and return ONLY the corrected LaTeX source.\n"
        + "</self-healing-instruction>"
    )


def render_survey_tex_with_llm(
    topic: str,
    rows: list[AcademicMatrixRow],
    extraction_fn: Callable[[str], str],
    progress_callback: Callable[[int, int, str, str], None] | None = None,
) -> str:
    """Generate a full Chinese LaTeX manuscript using LLM-driven synthesis.

    Args:
        topic: Review topic string.
        rows: Verified academic matrix rows.
        extraction_fn: LLM callable (prompt -> raw response).
        progress_callback: Optional progress callback.

    Returns:
        Complete LaTeX manuscript string (may contain syntax errors if
        self-healing retry is exhausted -- caller decides how to handle).
    """
    prompt = build_synthesis_prompt(topic, rows)

    for attempt in range(MAX_SYNTHESIS_RETRIES + 1):
        if progress_callback:
            state = "extracting" if attempt == 0 else "self_healing"
            detail = "Generating LaTeX manuscript..." if attempt == 0 else f"Retry {attempt}/{MAX_SYNTHESIS_RETRIES}: Fixing LaTeX syntax errors..."
            progress_callback(0, 1, state, detail)

        raw = extraction_fn(prompt)
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