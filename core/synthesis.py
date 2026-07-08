import re
from typing import Callable

from core.models import AcademicMatrixRow


def build_synthesis_prompt(
    topic: str,
    rows: list[AcademicMatrixRow],
    word_count_target: int = 3000,
) -> str:
    """Build a system prompt for LLM-based survey synthesis.

    The prompt instructs the LLM to generate a Chinese academic survey
    with the specified word count target and required LaTeX preamble.
    """
    paper_list = "\n".join(
        f"- {r.title} ({r.year}) — {r.method}: {r.limitation}"
        for r in rows
    )
    return (
        "You are an academic writing assistant. Generate a Chinese survey manuscript "
        "in LaTeX format covering the following papers.\n\n"
        f"Topic: {topic}\n\n"
        "Papers:\n"
        f"{paper_list}\n\n"
        "Requirements:\n"
        "- Use \\documentclass{ctexart}\n"
        "- Use \\usepackage{booktabs}\n"
        "- Use \\usepackage{tabularx}\n"
        "- Include these sections: Abstract and Introduction, Technical Taxonomy, "
        "Systematic Review and Deep Critique, Academic Comparison Matrix, "
        "Research Gaps and Future Work, Conclusion\n"
        f"- Target length: {word_count_target} Chinese characters\n"
        "- Output valid LaTeX only, no extra commentary."
    )


def render_survey_tex_with_llm(
    topic: str,
    rows: list[AcademicMatrixRow],
    extraction_fn: Callable[[str], str],
    word_count_target: int = 3000,
    progress_callback: Callable[[int, int, str, str], None] | None = None,
) -> str:
    """Generate a full LaTeX manuscript using LLM-driven synthesis.

    Args:
        topic: Review topic string.
        rows: Verified academic matrix rows.
        extraction_fn: LLM callable (prompt -> raw response).
        word_count_target: Target word count for the manuscript.
        progress_callback: Optional progress callback.

    Returns:
        Complete LaTeX manuscript string.
    """
    prompt = build_synthesis_prompt(topic, rows, word_count_target=word_count_target)

    if progress_callback:
        progress_callback(0, 1, "extracting", "Generating LaTeX manuscript...")

    raw = extraction_fn(prompt)

    if progress_callback:
        progress_callback(0, 1, "completed", "LaTeX manuscript generated successfully.")

    return raw


def validate_latex_syntax(source: str) -> list[str]:
    """Validate that LaTeX environments are properly balanced.

    Checks that every \\begin{env} has a matching \\end{env}.
    Returns a list of errors (empty if valid).
    """
    errors: list[str] = []
    stack: list[str] = []
    for match in re.finditer(r"\\(begin|end)\{(\w+)\}", source):
        keyword, env = match.groups()
        if keyword == "begin":
            stack.append(env)
        elif keyword == "end":
            if not stack:
                errors.append(f"Unexpected \\end{{{env}}} without \\begin{{{env}}}")
            elif stack[-1] != env:
                errors.append(
                    f"Mismatched environment: \\end{{{env}}} does not match "
                    f"\\begin{{{stack[-1]}}}"
                )
            else:
                stack.pop()
    if stack:
        for env in reversed(stack):
            errors.append(f"Missing \\end{{{env}}} for \\begin{{{env}}}")
    return errors