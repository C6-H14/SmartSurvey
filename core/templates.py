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
    ragged = ">{\\raggedright\\arraybackslash}X"
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Academic Comparison Matrix}",
        r"\footnotesize",
        r"\setlength{\tabcolsep}{4pt}",
        r"\noindent",
        r"\begin{tabularx}{\textwidth}{" + f"{ragged}{ragged}{ragged}{ragged}" + "}",
        r"\toprule",
        r"Paper & Method & Key Metric & Limitation \\",
        r"\midrule",
    ]
    for row in rows:
        metric = next(
            (v for v in row.domain_fields.values() if v not in ("missing", "")),
            row.innovation or "unavailable",
        )
        title = _add_tex_spacing(latex_escape(row.title))
        method = _add_tex_spacing(latex_escape(row.method))
        metric_str = _add_tex_spacing(latex_escape(str(metric)))
        limitation = _add_tex_spacing(latex_escape(row.limitation))
        lines.append(
            f"{title} & {method} & {metric_str} & {limitation} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabularx}", r"\end{table}"])
    return "\n".join(lines)


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
    return "\\documentclass{ctexart}\n\\usepackage{booktabs}\n\\usepackage{tabularx}\n\\begin{document}\n" + body + "\n\\end{document}\n"


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
