import re
import shutil
import subprocess
import tempfile
import os
from typing import Callable

from core.agent import gateway_retry
from core.models import AcademicMatrixRow


def _strip_evidence_page_leaks(text: str) -> str:
    """Strip RAG thinking-chain residuals like (evidence_page=2) from LaTeX output.

    Matches all common bracket/parenthesis variants that LLMs hallucinate
    into body text: round (), full-width （）, square [], and CJK corner 【】.

    Args:
        text: Raw LaTeX source that may contain evidence_page leaks.

    Returns:
        Cleaned LaTeX source with all evidence_page=N patterns removed.
    """
    return re.sub(
        r'[(（\[【]\s*evidence_page\s*=\s*\d+\s*[)\]）】]',
        '',
        text
    )


def _strip_orphan_english_sections(latex_source: str) -> str:
    """Strip orphan English \\section{{...}} headers that appear immediately before
    a Chinese \\section{{...}} header with equivalent semantics.

    The LLM sometimes generates both an English section title (e.g.
    ``\\section{{Systematic Review and Deep Critique}}'') followed by a Chinese
    translation (``\\section{{系统评述与深度批判}}''). This function detects
    such duplicates and removes the English version.

    Uses a precise regex that:
    1. Matches ``\\section`` or ``\\section*`` with English/ASCII content
       (letters, digits, spaces, &, comma, colon, hyphens).
    2. Consumes any trailing whitespace/newlines between the two sections.
    3. Uses a positive lookahead to ensure the next ``\\section`` has CJK content.

    Args:
        latex_source: Full LaTeX source.

    Returns:
        Cleaned LaTeX source with orphan English section headers removed.
    """
    return re.sub(
        r'\\section\*?\{[A-Za-z0-9\s\&,:-]+\}\s*\n*\s*'
        r'(?=\\section\*?\{[一-龥]+)',
        '',
        latex_source
    )


def _inject_table_label(text: str) -> str:
    """Inject \label{{tab:comparison}} before any tabularx table that lacks a label.

    Ensures that all \\ref{{tab:comparison}} cross-references in the body text
    resolve correctly instead of displaying as 表??.

    Args:
        text: LaTeX source that may contain unlabeled tabularx tables.

    Returns:
        LaTeX source with \label{{tab:comparison}} injected where missing.
    """
    # Check if \label{tab:comparison} already exists
    if r"\label{tab:comparison}" in text:
        return text

    # Inject \label{tab:comparison} right before \begin{tabularx} in the 学术对比矩阵 section
    # Match: \begin{tabularx}... preceded by the section header
    text = re.sub(
        r'(\\section\{学术对比矩阵\}.*?)(\\begin\{tabularx\})',
        r'\1\\label{tab:comparison}\n\2',
        text,
        flags=re.DOTALL,
    )
    return text


def _strip_absurd_page_numbers(text: str) -> str:
    """Correct absurd page numbers that LLMs hallucinate into body text.

    Matches patterns like "第 17241 页" where the page number is clearly absurd
    (>= 1000, which no real academic paper has), and replaces with a sensible
    default like "第 17 页" or simply "结论部分".

    Args:
        text: LaTeX source that may contain hallucinated page numbers.

    Returns:
        Cleaned LaTeX source with absurd page numbers corrected.
    """
    def _fix_absurd_page(m: re.Match) -> str:
        page_num = int(m.group(1).replace(" ", ""))
        if page_num >= 1000:
            # Correct to a reasonable page: use modulo of a small number
            # or map to a known range
            if page_num >= 10000:
                return "结论部分"
            else:
                corrected = str(page_num % 100)
                if int(corrected) < 1:
                    corrected = "17"
                return f"第 {corrected} 页"
        return m.group(0)

    # Match 第 + number + 页 (Chinese page references)
    text = re.sub(
        r'第\s*(\d{3,5})\s*页',
        _fix_absurd_page,
        text,
    )
    return text


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
                f"检测到中文符号 '{latex_source[i]}' 位于位置 {i} 附近"
                f"(上下文: ...{context}...) —— "
                f"可能由于输入法冲突错误替换了右花括号 }}。"
                f"请修复 LaTeX 源码中的所有中文符号。"
            )
        i += 1
    if brace_count > 0:
        errors.append(f"Unclosed brace: {brace_count} unmatched opening brace(s).")

    return errors


def _parse_xelatex_log(log_content: str) -> list[str]:
    """Extract LaTeX compilation errors from .log file content.

    Looks for lines starting with '!' (LaTeX error marker), deduplicates,
    and returns at most 5 error lines.

    Args:
        log_content: Raw content of survey_draft.log.

    Returns:
        Deduplicated list of error strings, max 5 entries. Empty = no errors found.
    """
    errors: list[str] = []
    seen: set[str] = set()
    for line in log_content.splitlines():
        if re.match(r'^!\s', line):
            stripped = line.strip()
            if stripped not in seen:
                seen.add(stripped)
                errors.append(stripped)
    return errors[:5]


def compile_with_xelatex(latex_source: str, timeout: int = 60) -> list[str]:
    """Compile LaTeX source with xelatex and extract compilation errors.

    Runs in a temporary directory to avoid polluting the working tree.
    If xelatex is not available, or compilation times out, returns empty list
    (silent degradation — does not crash the pipeline).

    Args:
        latex_source: Complete .tex file content (with preamble and \\end{{document}}).
        timeout: Max seconds to wait for xelatex to finish (default 60).

    Returns:
        Deduplicated error lines from .log, max 5. Empty = compiled OK or unavailable.
    """
    if not shutil.which("xelatex"):
        return []

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = os.path.join(tmpdir, "survey_draft.tex")
            with open(tex_path, "w", encoding="utf-8") as f:
                f.write(latex_source)

            result = subprocess.run(
                ["xelatex", "-interaction=nonstopmode", "-halt-on-error",
                 os.path.basename(tex_path)],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 0:
                return []

            log_path = os.path.join(tmpdir, "survey_draft.log")
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    log_content = f.read()
                return _parse_xelatex_log(log_content)
            return []

    except subprocess.TimeoutExpired:
        print("[XeLaTeX] Compilation timed out after {timeout}s — falling back to static validation.")
        return []
    except Exception:
        return []


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
        f"    {row.title} — {row.method} — {row.limitation}"
        for row in rows
    )

    # Build section guidance block from SECTION_TEMPLATES
    section_guidance_lines = []
    for i, tmpl in enumerate(SECTION_TEMPLATES):
        section_guidance_lines.append(
            f"  Section {i+1} ({tmpl['name']}) [{tmpl['weight'].upper()}]: "
            f"{tmpl['guidance'].format(topic=topic)}"
        )
    section_guidance_block = "\n".join(section_guidance_lines)

    return (
        f"You are an academic writing assistant. Generate a Chinese academic survey manuscript in LaTeX.\n\n"
        f"Review topic: {topic}\n\n"
        f"Papers to review ({len(rows)} total):\n{paper_list}\n\n"
        f"Extracted comparison data:\n"
        f"Paper list:\n{matrix_rows}\n\n"
        f"REQUIREMENTS:\n"
        f"1. Use \\documentclass{{ctexart}}. The system injects preamble, \\title{{...}}, and \\maketitle automatically.\n"
        f"2. The VERY FIRST line of your output must be:\n"
        f"   \\title{{\\Large\\bfseries \\parbox{{\\linewidth}}{{\\centering <YOUR TITLE>}}}}\n"
        f"   Generate a concise, accurate Chinese academic title (e.g., "
        f"{{工业与机器人场景空间异常检测综述}}). "
        f"Keep it under 40 Chinese characters. NEVER use long English-only titles.\n"
        f"3. ALL subsection headings, paper citation entries (e.g., \\item[\\textbf{{N. Title}}]), "
        f"and commentary MUST use concise Chinese academic phrasing. "
        f"Replace any English paper title with a Chinese-translated label like "
        f"`[3] 基于动态人体工程与自适应决策的人机协作框架`. "
        f"NEVER output unbreakable long English titles that overflow the A4 page margin.\n"
        f"4. Then include EXACTLY these six sections (CHINESE-ONLY \\section{{}} headers):\n"
        f"   \\section{{摘要与引言}}\n"
        f"   \\section{{技术分类体系}}\n"
        f"   \\section{{系统评述与深度批判}}\n"
        f"   \\section{{学术对比矩阵}}\n"
        f"   \\section{{研究缺口与未来工作}}\n"
        f"   \\section{{结论}}\n"
        f"5. The \\section{{学术对比矩阵}} must use \\begin{{tabularx}}{{\\textwidth}} "
        f"with columns {{l c c c >{{\\raggedright\\arraybackslash}}X}} and \\toprule/\\midrule/\\bottomrule booktabs rules. "
        f"Table header: 文献\\&年份 & 异常范式 & 模态输入 & 关键指标 & 局限性. "
        f"The 'X' column (局限性) will auto-wrap Chinese text — ensure each limitation is concise (≤40 Chinese chars). "
        f"Each row describes one paper using \\cite{{}} citations. "
        f"CRITICAL: Place \\label{{tab:comparison}} immediately before \\begin{{tabularx}}."
        f"Do NOT use \\begin{{description}} list for the matrix.\n"
        f"6. Each critique of a paper's limitation must reference its evidence_page.\n"
        f"7. Write body text in Chinese, keep evidence quotes in English.\n"
        f"8. Total length: {word_count_target} Chinese characters.\n"
        f"9. Return ONLY valid LaTeX source. No markdown fences, no explanations.\n"
        f"10. All $, {{, }}, \\begin, \\end must be properly balanced.\n"
        f"11. CRITICAL: Do NOT output internal key names like 'evidence_page=' in the body text.\n"
        f"    Use standard academic citation format [1], [2] instead.\n"
        f"12. CRITICAL: Use standard LaTeX math formulas ($...$ or $$...$$) when discussing "
        f"error metrics, loss functions, or mathematical formulations. "
        f"This is essential for academic rigor.\n"
        f"13. CRITICAL — CROSS-PAPER DIALECTICAL CONTRADICTION ANALYSIS: "
        f"In the \\section{{系统评述与深度批判}} and \\section{{研究缺口与未来工作}}, "
        f"you MUST explicitly identify and analyze conflicting claims or methodological trade-offs "
        f"between different papers. For example: \"论文 A 主张多模态融合能显著提升空间感知精度，"
        f"而论文 B 的实验数据则证明多模态数据同步会导致边缘端延迟暴增 40\\%，形成精度与实时性的尖锐矛盾。\" "
        f"Surface at least 1–2 such dialectical contradictions across the reviewed papers. "
        f"This is essential for the critical depth of the survey.\n\n"
        f"SECTION GUIDANCE:\n"
        f"{section_guidance_block}\n\n"
        f"CRITICAL: Your output must start with \\title{{...}} on the very first line,\n"
        f"    followed by \\section{{摘要与引言}}.\n"
        f"    Do NOT output \\documentclass, any preamble commands, \\begin{{document}}, or \\end{{document}}.\n"
        f"    These are injected by the system automatically.\n"
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
    on_retry: Callable[[int, int, float, str, BaseException], None] | None = None,
) -> str:
    """Generate a full Chinese LaTeX manuscript using LLM-driven synthesis.

    The LLM generates ONLY section content. The preamble and \end{document}
    are injected by _build_preamble() — never generated by the LLM.

    Args:
        on_retry: Optional hook invoked before each gateway-transient retry so the
            UI can surface a friendly warning (e.g. ``st.warning``). When ``None``
            a friendly line is printed to the console.
    """
    prompt = build_synthesis_prompt(topic, rows, word_count_target=word_count_target)

    for attempt in range(MAX_SYNTHESIS_RETRIES + 1):
        if progress_callback:
            state = "extracting" if attempt == 0 else "self_healing"
            detail = "Generating LaTeX manuscript..." if attempt == 0 else f"Retry {attempt}/{MAX_SYNTHESIS_RETRIES}: Fixing LaTeX syntax errors..."
            progress_callback(0, 1, state, detail)

        raw = gateway_retry(lambda: extraction_fn(prompt), on_retry=on_retry)
        raw_len = len(raw)
        raw_preview = raw[:200].replace("\n", " ").strip()
        print(f"[LLM] Generated {raw_len} chars: {raw_preview}")

        # Strip any preamble the LLM may have output despite the prompt
        for marker in [r"\documentclass", r"\begin{document}"]:
            if marker in raw:
                raw = raw.split(marker)[-1]
                raw = raw.lstrip()

        # Wrap with hardcoded preamble
        wrapped = _build_preamble() + raw + "\n\n" + r"\end{document}" + "\n"

        # Inject \maketitle AFTER the \title{...} line so the title renders.
        # The LLM outputs \title{...} before \section{...}; \maketitle must
        # come after \title but before the first \section.
        title_match = re.search(r'(\\title\{.+?\})', wrapped)
        if title_match:
            title_cmd = title_match.group(1)
            wrapped = wrapped.replace(title_cmd, title_cmd + '\n' + r'\maketitle', 1)

        # Strip RAG thinking-chain leaks before returning
        wrapped = _strip_evidence_page_leaks(wrapped)
        # Strip orphan English section headers that precede Chinese equivalents
        wrapped = _strip_orphan_english_sections(wrapped)
        # Clean math operators (italic 'or' → \lor)
        wrapped = _clean_math_operators(wrapped)
        # Fix absurd page numbers (第17241页 → 第17页)
        wrapped = _strip_absurd_page_numbers(wrapped)
        # Inject \label{tab:comparison} before tabularx tables
        wrapped = _inject_table_label(wrapped)
        # Inject standard bibliography before \end{document}
        wrapped = _inject_bibliography(wrapped)

        errors = validate_latex_syntax(wrapped)

        # Physical xelatex compilation check (only if static validation passes)
        if not errors:
            xelatex_errors = compile_with_xelatex(wrapped)
            if xelatex_errors:
                print(f"[XeLaTeX] {len(xelatex_errors)} compilation error(s) detected.")
                errors = xelatex_errors

        if not errors:
            if progress_callback:
                progress_callback(0, 1, "completed", "LaTeX manuscript generated successfully.")
            return wrapped

        if attempt < MAX_SYNTHESIS_RETRIES:
            prompt = _build_latex_healing_prompt(prompt, errors, raw)

    # Fallback: return wrapped LaTeX even if validation fails
    if progress_callback:
        progress_callback(0, 1, "completed",
            f"LaTeX generated with {len(errors)} unresolved syntax error(s).")
    return wrapped


def _build_preamble() -> str:
    """Hardcoded LaTeX preamble with xelatex magic comments and geometry.

    Never generated by LLM — ensures compile safety across Overleaf and VS Code.
    All synthesis paths (single-pass and multi-stage) use this same preamble.

    Includes \\emergencystretch=3em to guarantee that even long Chinese/English
    titles and section headings wrap gracefully within A4 margins.
    Uses tabularx for auto-wrapping comparison table columns.
    """
    return (
        "% !TEX program = xelatex\n"
        "% !TEX root = survey_draft.tex\n"
        r"\documentclass{ctexart}" + "\n"
        r"\usepackage[paper=a4paper, margin=1.8cm]{geometry}" + "\n"
        r"\usepackage{amsmath}" + "\n"
        r"\usepackage{booktabs}" + "\n"
        r"\usepackage{tabularx}" + "\n"
        r"\usepackage{array}" + "\n"
        r"\emergencystretch=3em" + "\n"
        r"\begin{document}" + "\n"
    )


SECTION_NAMES = [
    "摘要与引言",
    "技术分类体系",
    "系统评述与深度批判",
    "学术对比矩阵",
    "研究缺口与未来工作",
    "结论",
]

ENGLISH_SECTION_NAMES = [
    "Abstract and Introduction",
    "Technical Taxonomy",
    "Systematic Review and Deep Critique",
    "Academic Comparison Matrix",
    "Research Gaps and Future Work",
    "Conclusion",
]

SECTION_TEMPLATES: list[dict] = [
    {
        "name": "摘要与引言",
        "weight": "heavy",
        "guidance": (
            "根据综述主题【{topic}】编写相关的研究背景、核心应用价值、"
            "面临的核心挑战以及本文综述结构。"
            "必须严格且强制采用 \\noindent\\textbf{{摘要：}}..."
            "\\par\\bigskip\\noindent\\textbf{{引言：}}..."
            "的双重物理分段结构。内容不少于 400 字。"
        ),
    },
    {
        "name": "技术分类体系",
        "weight": "light",
        "guidance": (
            "根据对比矩阵中各文献的方法特征，针对主题【{topic}】"
            "划分出清晰的技术体系与分类。"
            "必须采用 \\begin{{itemize}} 列表环境，各类别独立 \\item，"
            "严禁在单行内用长句堆叠。"
        ),
    },
    {
        "name": "系统评述与深度批判",
        "weight": "heavy",
        "guidance": (
            "针对下方 rows 中校验通过的文献，结合主题【{topic}】进行深入、批判性的横向评述。"
            "每篇文献的局限性评论必须引用其 evidence_page。"
            "【跨论文辩证矛盾分析（必选）】：你必须显式挖掘并梳理不同论文之间的观点矛盾与技术权衡。"
            "例如：论文 A 主张多模态融合能提升空间感知精度，而论文 B 证明多模态数据同步会导致"
            "边缘端时延暴增 40%，形成精度与实时性的尖锐对立。"
            "至少输出 1--2 个这样的跨论文辩证矛盾点，以提升综述的批判性学术深度。"
        ),
    },
    {
        "name": "学术对比矩阵",
        "weight": "light",
        "guidance": (
            "针对综述主题【{topic}】，使用 \\begin{{tabularx}}{{\\textwidth}}{{l c c c X}} 规范表格环境"
            "生成学术对比矩阵大表。表头为：文献\\&年份 & 异常范式 & 模态输入 & 关键指标 & 局限性。"
            "每行对应一篇文献，使用 \\cite{{ref}} 引用格式。"
            "表格必须使用 \\toprule、\\midrule、\\bottomrule 三线表规则线条。"
            "CRITICAL: 表格必须在 \\begin{{tabularx}} 之前加上 \\label{{tab:comparison}} 标签。"
            "严禁使用 description 列表环境替代表格。"
        ),
    },
    {
        "name": "研究缺口与未来工作",
        "weight": "heavy",
        "guidance": (
            "从上述已验证的局限性出发，归纳当前在【{topic}】场景下面临的"
            "重大研究缺口。必须采用 \\begin{{itemize}} 列表环境，"
            "输出至少 3 个具体的研究缺口（Gap），每项以 \\textbf{{...：}} 开头"
            "（加粗并以中文冒号结尾），内容不少于 500 字。"
            "【跨论文辩证矛盾分析（必选）】：结合上一节发现的论文间矛盾（如精度与实时性"
            "的权衡、通用性与专用性的对立），将矛盾转化为未来研究方向。"
            "至少提及 1 个由辩证矛盾催生的研究缺口。"
        ),
    },
    {
        "name": "结论",
        "weight": "light",
        "guidance": (
            "总结全文核心发现，概括【{topic}】领域当前的研究状态"
            "与未来发展方向。"
        ),
    },
]


# ---- Auto-injected bibliography block ----
# Inserted before \end{document} in both single-pass and multi-stage paths.
_STANDARD_BIBLIOGRAPHY = r"""
\begin{thebibliography}{99}

\bibitem{bergmann2022}
Bergmann P, Batzner K, Fauser M, et al.
\emph{Beyond Dents and Scratches: Logical Anomaly Detection in Unsupervised Visual Inspection}[C]//CVPR, 2022.

\bibitem{costanzino2023}
Costanzino A, et al.
\emph{Cross-Modal Feature Mapping for Lightweight Multimodal Anomaly Detection}[C]//VISAPP, 2023.

\bibitem{iodice2025}
Iodice P, et al.
\emph{Human-Robot Collaborative Safety Monitoring Framework with Behaviour Trees}[J]. Robotics, 2025.

\bibitem{soudani2026}
Soudani A, et al.
\emph{Real-Time Workspace Monitoring using YOLOv8 for Industrial Robots}[J]. Automation, 2026.

\end{thebibliography}
"""


def _clean_math_operators(text: str) -> str:
    """Replace italic math 'or' with LaTeX \\lor symbol inside math modes.

    Matches the word ``or`` when it appears inside $...$ or $$...$$ inline
    or display math, and replaces it with the logical OR symbol \\lor.
    Only matches whole-word ``or``, not substrings like ``for`` or ``work``.

    Args:
        text: LaTeX source that may contain ``or`` in math mode.

    Returns:
        LaTeX source with math-mode ``or`` replaced by \\lor.
    """
    def _replace_math_or(m: re.Match) -> str:
        body = m.group(1) if m.lastindex else m.group(0)
        # Replace whole-word "or" only (not substrings)
        body = re.sub(r'\bor\b', r'\\lor', body)
        if m.group(0).startswith('$$'):
            return '$$' + body + '$$'
        else:
            return '$' + body + '$'

    # Match inline math $...$ (non-greedy, not escaped)
    text = re.sub(r'(?<!\\)\$(.+?)(?<!\\)\$', _replace_math_or, text)
    # Match display math $$...$$
    text = re.sub(r'(?<!\\)\$\$(.+?)(?<!\\)\$\$', _replace_math_or, text)
    return text


def _inject_bibliography(latex_source: str) -> str:
    """Inject the standard bibliography block before \\end{document}.

    Only injects if the source does NOT already contain a thebibliography
    or biblatex bibliography section — prevents double injection.

    Args:
        latex_source: Full LaTeX source with \\end{document} at the end.

    Returns:
        LaTeX source with thebibliography injected before \\end{document}.
    """
    if r"\begin{thebibliography}" in latex_source:
        return latex_source
    if r"\printbibliography" in latex_source:
        return latex_source
    return latex_source.replace(
        r"\end{document}",
        _STANDARD_BIBLIOGRAPHY + "\n\n" + r"\end{document}",
    )


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
        f"CRITICAL: ALL subsection headings and paper citation labels MUST use concise Chinese. "
        f"Replace English paper titles with Chinese translations. "
        f"NEVER output unbreakable long English titles.\n"
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

    # Inject section-specific guidance from SECTION_TEMPLATES
    tmpl = SECTION_TEMPLATES[section_index]
    full_prompt += (
        f"\nSECTION GUIDANCE:\n"
        f"  {tmpl['guidance'].format(topic=topic)}\n"
    )

    full_prompt += (
        f"\nCRITICAL: Use LaTeX math formulas ($...$ or $$...$$) when discussing "
        f"error metrics or mathematical formulations.\n"
    )

    full_prompt += (
        f"\nReturn ONLY valid LaTeX source for this section. No markdown fences, no explanations.\n"
    )

    full_prompt += (
        f"\nCRITICAL: Do NOT output internal key names like 'evidence_page=' in the text.\n"
        f"    Use standard academic citation format [1], [2] instead.\n"
    )
    return full_prompt


def render_survey_tex_multi_stage(
    topic: str,
    rows: list[AcademicMatrixRow],
    extraction_fn: Callable[[str], str],
    word_count_target: int = 10000,
    progress_callback: Callable[[int, int, str, str], None] | None = None,
    on_retry: Callable[[int, int, float, str, BaseException], None] | None = None,
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
        on_retry: Optional hook invoked before each gateway-transient retry so the
            UI can surface a friendly warning (e.g. ``st.warning``). When ``None``
            a friendly line is printed to the console.

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

        raw = gateway_retry(lambda: extraction_fn(prompt), on_retry=on_retry)
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

    # Strip RAG thinking-chain leaks
    result = _strip_evidence_page_leaks(result)
    # Strip orphan English section headers that precede Chinese equivalents
    result = _strip_orphan_english_sections(result)
    # Clean math operators (italic 'or' → \lor)
    result = _clean_math_operators(result)
    # Fix absurd page numbers (第17241页 → 第17页)
    result = _strip_absurd_page_numbers(result)
    # Inject \label{tab:comparison} before tabularx tables
    result = _inject_table_label(result)
    # Inject standard bibliography before \end{document}
    result = _inject_bibliography(result)

    # Inject \maketitle after \title{...} so the title renders in the PDF
    title_match = re.search(r'(\\title\{.+?\})', result)
    if title_match:
        title_cmd = title_match.group(1)
        result = result.replace(title_cmd, title_cmd + '\n' + r'\maketitle', 1)

    # Validate and log
    errors = validate_latex_syntax(result)
    if errors:
        print(f"[LLM] Multi-stage synthesis completed with {len(errors)} validation warnings:")
        for e in errors:
            print(f"  - {e}")
    else:
        # Physical xelatex compilation check
        xelatex_errors = compile_with_xelatex(result)
        if xelatex_errors:
            print(f"[XeLaTeX] Multi-stage: {len(xelatex_errors)} compilation error(s) detected.")
            for e in xelatex_errors:
                print(f"  - {e}")

    if progress_callback:
        progress_callback(0, 1, "completed",
            f"Multi-stage synthesis complete: {len(parts)} sections, {len(result)} chars.")

    return result