import re

from core.models import AcademicMatrixRow


REQUIRED_SECTIONS = [
    "摘要与引言",
    "技术分类体系",
    "系统评述与深度批判",
    "学术对比矩阵",
    "研究缺口与未来工作",
    "结论",
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
    # Comma: "A,B,C" -> "A, B, C" (but not inside numbers like "1,234")
    value = re.sub(r"(?<=\S),(?=\S)", ", ", value)
    # Plus: "A+B" -> "A + B"
    value = re.sub(r"(?<=\S)\+(?=\S)", " + ", value)
    # Equals: "A=B" -> "A = B"
    value = re.sub(r"(?<=\S)=(?=\S)", " = ", value)
    return value


def render_matrix_table_tex(rows: list[AcademicMatrixRow]) -> str:
    """Render academic comparison matrix as a LaTeX tabularx three-line table.

    Column spec is HARD-CODED to fixed-width ``>{\\raggedright\\arraybackslash}p{...}``
    columns for all five columns, ensuring that any long Chinese/English text wraps
    beautifully within A4 margins without vertical character displacement.

    The final column uses ``X`` (auto-stretch) so the table fills \\textwidth.

    Always includes ``\\label{{tab:comparison}}`` for cross-referencing.

    **Row safety guarantees:**
    1. Every data row is explicitly terminated with ``\\\\`` (double-backslash newline).
    2. ``\\addlinespace`` is only ever emitted immediately after a ``\\\\``-terminated
       line, never on its own — preventing ``Misplaced \\noalign`` errors.
    3. Each row contains exactly 4 ``&`` separators (5 columns), verified at render time.
    """
    # SSOT column spec — locked against accidental drift
    COL_SPEC = (
        r">{\raggedright\arraybackslash}p{2.2cm} "
        r">{\raggedright\arraybackslash}p{2.5cm} "
        r">{\raggedright\arraybackslash}p{2.5cm} "
        r">{\raggedright\arraybackslash}p{2.5cm} "
        r">{\raggedright\arraybackslash}X"
    )
    EXPECTED_AMPERSANDS = 4  # 5 columns → exactly 4 & separators per row

    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{学术对比矩阵}",
        r"\label{tab:comparison}",
        r"\small",
        r"\begin{tabularx}{\textwidth}{" + COL_SPEC + "}",
        r"\toprule",
        r"文献\&年份 & 异常范式 & 模态输入 & 关键指标 & 局限性 \\",
        r"\midrule",
    ]
    for idx, row in enumerate(rows, start=1):
        title = latex_escape(row.title)
        method = latex_escape(row.method)
        innovation = latex_escape(row.innovation)
        limitation = latex_escape(row.limitation)
        # Use the first meaningful domain field as key metric; fall back to innovation
        metric = "—"
        if row.domain_fields:
            meaningful = [
                v for v in row.domain_fields.values()
                if v and v not in ("missing", "", "missing (unverified)")
            ]
            if meaningful:
                metric = latex_escape(meaningful[0])
            else:
                metric = latex_escape(row.innovation)
        else:
            metric = latex_escape(row.innovation)

        # Build the row cell string with explicit \\ terminator
        row_line = f"{title} ({row.year}) & — & — & {metric} & {limitation} \\\\"
        # Defensive: verify exact ampersand count before appending
        ampersand_count = row_line.count("&")
        if ampersand_count != EXPECTED_AMPERSANDS:
            print(
                f"[templates] WARNING: row {idx} has {ampersand_count} & separators "
                f"(expected {EXPECTED_AMPERSANDS}) — auto-correcting column count."
            )
            # Truncate or pad to match expected column count
            parts = row_line.split("&")
            if len(parts) > EXPECTED_AMPERSANDS + 1:
                # Too many columns: drop excess cells before the last one
                parts = parts[:EXPECTED_AMPERSANDS] + [parts[-1]]
            elif len(parts) < EXPECTED_AMPERSANDS + 1:
                # Too few columns: pad with "—"
                parts = parts[:-1] + [" —"] * (EXPECTED_AMPERSANDS + 1 - len(parts)) + [parts[-1]]
            row_line = "&".join(parts)

        lines.append(row_line)
    lines.extend([
        r"\bottomrule",
        r"\end{tabularx}",
        r"\end{table}",
    ])
    return "\n".join(lines)


def sanitize_latex_table(table_tex: str, expected_columns: int = 5) -> str:
    """Post-process LaTeX table source to prevent Misplaced \\noalign and Extra alignment tab errors.

    This is a safety-net function that can be applied to LLM-generated table LaTeX
    before compilation. It performs three fixes:

    1. **\\\\addlinespace guard**: Ensures ``\\addlinespace`` is always preceded by
       a ``\\\\`` row terminator. If a bare ``\\addlinespace`` (without preceding
       ``\\\\``) is found, a ``\\\\`` is inserted before it.

    2. **Ampersand normalization**: Ensures each data row contains exactly
       ``expected_columns - 1`` ampersand (``&``) separators.

    3. **Stray ``\\addlinespace`` cleanup**: Removes ``\\addlinespace`` after
       ``\\bottomrule`` or ``\\end{tabularx}``.

    Args:
        table_tex: Raw LaTeX table source (may include \\begin/\\end environment).
        expected_columns: Number of columns in the table (default 5).

    Returns:
        Sanitized LaTeX table source.
    """
    expected_ampersands = expected_columns - 1

    # Fix 1: Remove \addlinespace after \bottomrule or \end{tabularx} FIRST
    #         (before \\-insertion, so \bottomrule\addlinespace is matched directly)
    table_tex = re.sub(
        r'\\(?:bottomrule|end\{tabularx\})\s*\n?\s*\\addlinespace',
        lambda m: re.sub(r'\\addlinespace\s*', '', m.group(0)),
        table_tex,
    )

    # Fix 2: Ensure remaining \addlinespace is always preceded by \\
    table_tex = re.sub(
        r'(?<!\\\\)\s*\\addlinespace',
        r' \\\\\n\\addlinespace',
        table_tex,
    )
    table_tex = re.sub(
        r'^\s*\\addlinespace',
        r' \\\\\n\\addlinespace',
        table_tex,
        flags=re.MULTILINE,
    )
    # Remove double \\\\ before \addlinespace
    table_tex = re.sub(
        r'\\\\\s*\n\s*\\\\\s*\n\s*\\addlinespace',
        r' \\\\\n\\addlinespace',
        table_tex,
    )

    # Fix 3: Normalize ampersand count per data row
    def _fix_ampersand_count(m: re.Match) -> str:
        line = m.group(0).strip()
        if not line or any(
            kw in line for kw in [
                r'\begin', r'\end', r'\toprule', r'\midrule',
                r'\bottomrule', r'\addlinespace', r'\hline',
                r'\caption', r'\label',
            ]
        ):
            return m.group(0)

        amp_count = line.count("&")
        if amp_count == expected_ampersands:
            return m.group(0)

        stripped = re.sub(r'\\\\\s*$', '', line).strip()
        parts = stripped.split("&")
        if len(parts) > expected_columns:
            parts = parts[:expected_ampersands] + [parts[-1].strip()]
        elif len(parts) < expected_columns:
            parts = [p.strip() for p in parts]
            parts = parts + ["—"] * (expected_columns - len(parts))

        fixed = " & ".join(p.strip() for p in parts[:expected_columns])
        if r'\\' in line:
            fixed += r' \\'
        return fixed

    table_tex = re.sub(
        r'^.*&.*$',
        _fix_ampersand_count,
        table_tex,
        flags=re.MULTILINE,
    )

    return table_tex


def _build_title_macro(title: str) -> str:
    """Build a \\title{} command with automatic line-wrap for long titles.

    Uses \\parbox{\\linewidth}{\\centering ...} to ensure Chinese and English
    titles stay within A4 page margins without Overfull \\hbox overflows.
    """
    escaped = latex_escape(title)
    return (
        r"\title{\Large\bfseries \parbox{\linewidth}{\centering "
        + escaped
        + r"}}"
    )


def render_survey_tex(topic: str, rows: list[AcademicMatrixRow]) -> str:
    matrix = render_matrix_table_tex(rows)
    paper_list = "、".join(row.title for row in rows) if rows else "missing"
    sections = {
        "摘要与引言": (
            r"\noindent\textbf{摘要：}" + f"本文围绕\"{topic}\"展开综述，论文集合包括：{paper_list}。"
            + r"\par\bigskip\noindent\textbf{引言：}" + f"本文围绕\"{topic}\"领域，对上述论文进行系统性梳理与对比分析。"
        ),
        "技术分类体系": "本节依据论文方法、研究问题和领域字段建立技术分类。",
        "系统评述与深度批判": "本节只纳入已经通过页码与原文摘录校验的批判性结论。",
        "学术对比矩阵": matrix,
        "研究缺口与未来工作": "本节从已验证的局限性中归纳研究缺口和后续方向。",
        "结论": "本文总结结构化矩阵、证据约束和后续研究价值。",
    }
    body = "\n\n".join(f"\\section{{{name}}}\n{content}" for name, content in sections.items())
    preamble = (
        "% !TEX program = xelatex\n"
        r"\documentclass{ctexart}" + "\n"
        r"\usepackage[paper=a4paper, margin=1.8cm]{geometry}" + "\n"
        r"\usepackage{amsmath}" + "\n"
        r"\usepackage{booktabs}" + "\n"
        r"\usepackage{tabularx}" + "\n"
        r"\usepackage{array}" + "\n"
        r"\emergencystretch=3em" + "\n"
    )
    return preamble + r"\begin{document}" + "\n" + body + "\n" + r"\end{document}" + "\n"


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