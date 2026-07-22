import re

from core.models import AcademicMatrixRow


REQUIRED_SECTIONS = [
    "Abstract and Introduction",
    "Technical Taxonomy",
    "Systematic Review and Deep Critique",
    "Academic Comparison Matrix",
    "Research Gaps and Future Work",
    "Conclusion",
]


def latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(char, char) for char in value)


def citation_key(row: AcademicMatrixRow) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", row.title.lower()).strip("_") or "paper"
    return f"{base[:32]}_{row.year}"


def _add_tex_spacing(value: str) -> str:
    """Insert spaces after commas and around operators to help LaTeX line breaking."""
    # Comma: "A,B,C" → "A, B, C" (but not inside numbers like "1,234")
    value = re.sub(r"(?<=\S),(?=\S)", ", ", value)
    # Plus: "A+B" → "A + B"
    value = re.sub(r"(?<=\S)\+(?=\S)", " + ", value)
    # Equals: "A=B" → "A = B"
    value = re.sub(r"(?<=\S)=(?=\S)", " = ", value)
    return value


def render_matrix_table_tex(rows: list[AcademicMatrixRow]) -> str:
    """Render academic comparison matrix as a LaTeX description list.

    Each paper becomes a \item[\textbf{N. Title (Year)：}] with structured
    paragraphs for method, innovation, and limitation — avoiding tabular overflow.
    """
    lines = [
        r"\begin{description}",
    ]
    for idx, row in enumerate(rows, start=1):
        title = latex_escape(row.title)
        method = latex_escape(row.method)
        innovation = latex_escape(row.innovation)
        limitation = latex_escape(row.limitation)
        lines.append(
            f"  \\item[\\textbf{{{idx}. {title} ({row.year})：}}] \\hfill \\\\\n"
            f"    \\textbf{{技术方法：}}{method} \\\\\n"
            f"    \\textbf{{关键优势：}}{innovation} \\\\\n"
            f"    \\textbf{{核心局限：}}{limitation}"
        )
    lines.append(r"\end{description}")
    return "\n\n".join(lines)


def render_survey_tex(topic: str, rows: list[AcademicMatrixRow]) -> str:
    matrix = render_matrix_table_tex(rows)
    paper_list = "、".join(row.title for row in rows) if rows else "missing"
    sections = {
        "Abstract and Introduction": (
            r"\noindent\textbf{摘要：}" + f"本文围绕“{topic}”展开综述，论文集合包括：{paper_list}。"
            + r"\par\bigskip\noindent\textbf{引言：}" + f"本文围绕“{topic}”领域，对上述论文进行系统性梳理与对比分析。"
        ),
        "Technical Taxonomy": "本节依据论文方法、研究问题和领域字段建立技术分类。",
        "Systematic Review and Deep Critique": "本节只纳入已经通过页码与原文摘录校验的批判性结论。",
        "Academic Comparison Matrix": matrix,
        "Research Gaps and Future Work": "本节从已验证的局限性中归纳研究缺口和后续方向。",
        "Conclusion": "本文总结结构化矩阵、证据约束和后续研究价值。",
    }
    body = "\n\n".join(f"\\section{{{name}}}\n{content}" for name, content in sections.items())
    return "\\documentclass{ctexart}\n\\begin{document}\n" + body + "\n\\end{document}\n"


def render_markdown_preview(
    topic: str,
    rows: list[AcademicMatrixRow],
    blocked_warnings: list[str] | None = None,
) -> str:
    blocked_warnings = blocked_warnings or []
    lines = [f"# SmartSurvey Preview: {topic}", "", "| Paper | Method | Limitation | Evidence |", "| --- | --- | --- | --- |"]
    for row in rows:
        lines.append(
            f"| {row.title} | {row.method} | {row.limitation} | p.{row.evidence_page}: {row.evidence_quote} |"
        )
    if blocked_warnings:
        lines.extend(["", "## Blocked Warnings"])
        lines.extend(f"- {warning}" for warning in blocked_warnings)
    return "\n".join(lines)


def render_bibtex(rows: list[AcademicMatrixRow]) -> str:
    entries = []
    for row in rows:
        entries.append(
            "@article{"
            + citation_key(row)
            + ",\n"
            + f"  title = {{{row.title}}},\n"
            + f"  author = {{{row.authors}}},\n"
            + f"  year = {{{row.year}}},\n"
            + f"  journal = {{{row.venue}}},\n"
            + f"  evidencepages = {{{row.evidence_page}}}\n"
            + "}"
        )
    return "\n\n".join(entries)
