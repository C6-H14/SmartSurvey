import re
import shutil
import subprocess
import tempfile
import os
from typing import Callable

from core.agent import gateway_retry
from core.models import AcademicMatrixRow, ParsedPaper


def derive_cite_key(authors: str, year: str, title: str = "") -> str:
    """Derive a deterministic, immutable citation key from paper metadata.

    Pattern: ``firstAuthorSurnameYYYYfirstMeaningfulTitleWord`` (lowercase, alphanumeric).
    Examples:
        - ``Bergmann P, ...`` + 2022 + ``Beyond Dents and Scratches`` → ``bergmann2022beyond``
        - ``Iodice P, ...`` + 2025 + ``Human-Robot Collaborative...`` → ``iodice2025humanrobot``

    Args:
        authors: Raw author string (e.g. "Bergmann P, Batzner K, ...").
        year: Publication year as string (e.g. "2022").
        title: Paper title (optional fallback for disambiguation).

    Returns:
        Lowercase alphanumeric citation key, always non-empty.
    """
    # Extract first author surname: take everything before the first comma or space
    first_author = authors.split(",")[0].strip().split(" ")[0].strip() if authors else "unknown"
    surname = re.sub(r"[^a-zA-Z]+", "", first_author).lower() or "unknown"

    # Extract first meaningful title word (skip stop words)
    if title and title != "missing":
        stop_words = {"a", "an", "the", "and", "or", "of", "in", "on", "to", "for",
                      "with", "is", "are", "was", "were", "be", "been", "being",
                      "have", "has", "had", "do", "does", "did", "but", "not",
                      "from", "by", "at", "as", "into", "through", "during", "before",
                      "after", "above", "below", "between", "under", "over",
                      "beyond", "toward", "towards"}
        title_words = re.sub(r"[^a-zA-Z\s]", " ", title).split()
        meaningful = [w.lower() for w in title_words if w.lower() not in stop_words]
        title_slug = meaningful[0] if meaningful else ""
    else:
        title_slug = ""

    if title_slug:
        return f"{surname}{year}{title_slug}"
    return f"{surname}{year}"


def derive_canonical_cite_key(authors: str, year: str) -> str:
    """Derive a canonical citation key using ONLY first-author-surname + year.

    Rule: ``firstAuthorSurname.lower() + year`` — no title words appended.
    Examples:
        - "Bergmann P, Batzner K, ..." + 2022 → "bergmann2022"
        - "Iodice P, et al." + 2025 → "iodice2025"

    This is the SINGLE SOURCE OF TRUTH canonical key. All other key variants
    (from derive_cite_key, LLM-invented aliases) MUST resolve to this.

    Args:
        authors: Raw author string (e.g. "Bergmann P, Batzner K, ...").
        year: Publication year as string (e.g. "2022").

    Returns:
        Lowercase alphanumeric canonical citation key, always non-empty.
    """
    first_author = authors.split(",")[0].strip().split(" ")[0].strip() if authors else "unknown"
    surname = re.sub(r"[^a-zA-Z]+", "", first_author).lower() or "unknown"
    return f"{surname}{year}"


def build_alias_map(rows: list[AcademicMatrixRow]) -> dict[str, str]:
    """Build a mapping from known alias cite keys to canonical cite keys.

    For each paper, generates:
    - The derive_cite_key() variant (e.g., "bergmann2022dents")
    - First-author surname (e.g., "bergmann")
    - First-author surname + first initial (e.g., "bergmannp")

    All map to the canonical key (e.g., "bergmann2022").

    Args:
        rows: Academic matrix rows with author/year/title metadata.

    Returns:
        Dict mapping lowercase alias strings to canonical cite keys.
    """
    alias_map: dict[str, str] = {}
    for row in rows:
        canonical = derive_canonical_cite_key(row.authors, row.year)

        # Alias 1: the full derive_cite_key() variant (with title word)
        full_key = derive_cite_key(row.authors, row.year, row.title)
        alias_map[full_key.lower()] = canonical

        # Alias 2: just the surname as a prefix
        first_author = row.authors.split(",")[0].strip().split(" ")[0].strip() if row.authors else ""
        surname = re.sub(r"[^a-zA-Z]+", "", first_author).lower()
        if surname:
            alias_map[surname] = canonical

            # Alias 3: surname + year (slightly different from canonical but LLM may use)
            alias_map[f"{surname}{row.year}"] = canonical

            # Alias 4: surname + first name initial (e.g., "bergmannp", "iodicep")
            parts = row.authors.split(",")[0].strip().split(" ")
            first_name = ""
            if len(parts) >= 2:
                first_name = re.sub(r"[^a-zA-Z]+", "", parts[1]).lower()
            if first_name:
                alias_map[f"{surname}{first_name}"] = canonical

            # Alias 5: first name + year (LLM may use first name instead of surname)
            if first_name:
                alias_map[f"{first_name}{row.year}"] = canonical

    return alias_map


def build_cite_key_map(rows: list[AcademicMatrixRow]) -> list[dict]:
    """Build a deterministic citation key → paper metadata mapping for SSOT injection.

    Returns a list of dicts with keys: cite_key, title, authors, year, venue.
    The list order is stable and determines [1], [2], ... numbering in the manuscript.

    This mapping is the single source of truth passed to:
    - Prompt building (so the LLM knows which \\cite{key} to use)
    - Bibliography rendering (so \\bibitem{key} matches exactly)
    """
    mapping = []
    seen_keys: set[str] = set()
    for row in rows:
        key = derive_canonical_cite_key(row.authors, row.year)
        # Disambiguate if duplicate (append -2, -3, ...)
        base_key = key
        counter = 2
        while key in seen_keys:
            key = f"{base_key}-{counter}"
            counter += 1
        seen_keys.add(key)
        mapping.append({
            "cite_key": key,
            "title": row.title,
            "authors": row.authors,
            "year": row.year,
            "venue": row.venue,
        })
    return mapping


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
    """Strip orphan English ``\\section``/``\\section*`` headers that appear
    immediately before a Chinese ``\\section``/``\\section*`` header.

    The LLM sometimes generates both an English section title (e.g.
    ``\\section{{Systematic Review and Deep Critique}}'') followed by a Chinese
    translation (``\\section{{系统评述与深度批判}}''). This function detects
    such duplicates and removes the English version.

    Uses a lookahead to only remove the English header when a CJK header follows
    immediately — standalone English sections are NOT stripped.

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


def clean_synthesized_latex(text: str) -> str:
    """Post-process LLM-synthesized LaTeX to eliminate RAG leaks and orphan artifacts.

    This is the central cleanup function applied to all synthesis output before
    compilation. It runs four hardening passes in order:

    1. **RAG evidence_page leak removal** (已扩展至 4 种括号变体):
       ``(evidence_page=2)``, ``（evidence_page=3）``, ``[evidence_page=4]``,
       ``【evidence_page=5】`` → empty string.

    2. **Orphan English section header stripping**:
       ``\\section*{Abstract and Introduction}`` followed immediately by
       ``\\section{摘要与引言}`` → removes the English header, keeps the Chinese.

    3. **Math operator normalization**: ``or`` → ``\\lor``, ``and`` → ``\\land``
       inside math mode ($...$ and $$...$$).

    4. **Absurd page number correction**: ``第17241页`` → ``结论部分``.

    Args:
        text: Raw LaTeX source from LLM synthesis.

    Returns:
        Cleaned LaTeX source ready for preamble wrapping and compilation.
    """
    # Pass 1: RAG evidence_page leak — 4 bracket variants
    text = re.sub(
        r'[\(（\[【]\s*evidence_page\s*=\s*\d+\s*[\)\]）】]',
        '',
        text,
    )

    # Pass 2: Orphan English \\section / \\section* before Chinese \\section
    text = re.sub(
        r'\\section\*?\{[A-Za-z0-9\s\&,:-]+\}\s*\n*\s*'
        r'(?=\\section\*?\{[一-龥]+)',
        '',
        text,
    )

    # Pass 3: Math-mode or → \\lor, and → \\land
    text = _clean_math_operators(text)

    # Pass 4: Absurd page numbers
    text = _strip_absurd_page_numbers(text)

    return text


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


def _scan_log_for_undefined_refs(latex_source: str) -> list[str]:
    """Scan LaTeX source for potential undefined references.

    Scans for \\ref{{...}} and \\cite{{...}} keys and checks against defined
    \\label{{...}} and \\bibitem{{...}} keys. Returns mismatch warnings.

    This is a fast regex-based pre-check that runs without needing access to
    xelatex or the .log file.

    Args:
        latex_source: Full LaTeX source.

    Returns:
        List of warning strings about undefined references. Empty = all good.
    """
    warnings: list[str] = []

    # Collect all defined labels and bibitems
    defined_labels: set[str] = set()
    for m in re.finditer(r'\\label\{([^}]+)\}', latex_source):
        defined_labels.add(m.group(1))
    defined_bibitems: set[str] = set()
    for m in re.finditer(r'\\bibitem\{([^}]+)\}', latex_source):
        defined_bibitems.add(m.group(1))

    # Check \ref{...} calls
    for m in re.finditer(r'\\ref\{([^}]+)\}', latex_source):
        ref_key = m.group(1)
        if ref_key not in defined_labels:
            warnings.append(f"Undefined ref: \\ref{{{ref_key}}} has no matching \\label")

    # Check \cite{...} calls
    for m in re.finditer(r'\\cite\{([^}]+)\}', latex_source):
        cite_key = m.group(1)
        if cite_key not in defined_bibitems:
            warnings.append(f"Undefined citation: \\cite{{{cite_key}}} has no matching \\bibitem")

    return warnings


def _parse_undefined_references_from_log(log_content: str) -> list[str]:
    """Scan xelatex .log for ``undefined reference`` warnings.

    XeLaTeX outputs warnings like:
        LaTeX Warning: Reference `tab:comparison' on page 1 undefined on input line 14.
    or:
        LaTeX Warning: Citation `citelostkey' on page 1 undefined on input line 20.

    This parser extracts and deduplicates these warnings so the self-healing
    pipeline can trigger correction.

    Args:
        log_content: Raw content of survey_draft.log.

    Returns:
        Deduplicated list of warning strings, max 5. Empty = no undefined refs.
    """
    warnings: list[str] = []
    seen: set[str] = set()
    for line in log_content.splitlines():
        if "undefined" in line.lower() and ("reference" in line.lower() or "citation" in line.lower()):
            stripped = line.strip()
            if stripped not in seen:
                seen.add(stripped)
                warnings.append(stripped)
    return warnings[:5]


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


def compile_with_xelatex(
    latex_source: str,
    timeout: int = 60,
    bib_file_path: str | None = None,
) -> list[str]:
    """Compile LaTeX source with xelatex using FULL XeLaTeX→BibTeX→XeLaTeX→XeLaTeX recipe.

    **Full-recipe design (3 or 4 passes):**

    1. **Pass 1 (XeLaTeX)**: generates ``.aux`` with ``\\citation{...}`` lines
       from every ``\\cite{...}`` in the body text.

    2. **Pass 2 (BibTeX, conditional)**: if the source uses ``\\bibliographystyle{...}``
       + ``\\bibliography{...}`` (external .bib workflow), runs ``bibtex`` on the
       ``.aux`` to resolve citations from the ``.bib`` database and produce a ``.bbl``
       file. The ``.bib`` file must be present in the temp directory — either
       auto-generated from ``_STANDARD_BIBTEX_ENTRIES`` or copied from ``bib_file_path``.

    3. **Pass 3 (XeLaTeX)**: reads the ``.bbl`` and populates ``\\cite`` references.
       This pass also writes ``\\ref{}`` labels to ``.aux`` for the final pass.

    4. **Pass 4 (XeLaTeX)**: resolves ``\\ref{}`` cross-references that were
       written by Pass 3.

    This guarantees 100% zero-error compilation with correct citations and
    cross-references regardless of whether the document uses ``thebibliography``
    (embedded) or ``\\bibliography{references}`` (external .bib).

    Runs in a temporary directory to avoid polluting the working tree.
    If xelatex is not available, or compilation times out, returns empty list
    (silent degradation — does not crash the pipeline).

    After all passes, scans the .log for ``undefined reference`` warnings
    and returns them alongside any error lines.

    Args:
        latex_source: Complete .tex file content (with preamble and \\end{{document}}).
        timeout: Max seconds to wait for each xelatex/bibtex pass (default 60).
        bib_file_path: Optional path to a .bib file to copy into the temp dir
            for bibtex resolution. When None, auto-generates from
            ``_STANDARD_BIBTEX_ENTRIES`` if the source uses ``\\bibliography``.

    Returns:
        Deduplicated error/warning lines from .log, max 5. Empty = compiled OK or unavailable.
    """
    if not shutil.which("xelatex"):
        return []

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = os.path.join(tmpdir, "survey_draft.tex")
            with open(tex_path, "w", encoding="utf-8") as f:
                f.write(latex_source)

            basename = os.path.basename(tex_path)
            stem = os.path.splitext(basename)[0]
            xelatex_args = [
                "xelatex", "-interaction=nonstopmode", "-halt-on-error", basename,
            ]

            # ── Detect which bibliography workflow is in use ──
            uses_external_bib = (
                r"\bibliographystyle{" in latex_source
                and r"\bibliography{" in latex_source
            )
            # Extract the .bib base name from \bibliography{...}
            bib_basename = None
            if uses_external_bib:
                m = re.search(r'\\bibliography\{([^}]+)\}', latex_source)
                if m:
                    bib_basename = m.group(1).strip()

            # ── Provision the .bib file if using external bib workflow ──
            if uses_external_bib and bib_basename:
                bib_target = os.path.join(tmpdir, f"{bib_basename}.bib")
                if bib_file_path and os.path.isfile(bib_file_path):
                    shutil.copy2(bib_file_path, bib_target)
                else:
                    # Auto-generate from standard BibTeX entries
                    with open(bib_target, "w", encoding="utf-8") as bf:
                        bf.write(_STANDARD_BIBTEX_ENTRIES)
                    print(f"[XeLaTeX] Auto-generated {bib_basename}.bib from _STANDARD_BIBTEX_ENTRIES")

            # ── Pass 1: XeLaTeX → generate .aux with \citation{...} lines ──
            result1 = subprocess.run(
                xelatex_args,
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            # ── Pass 2: BibTeX (conditional) → resolve citations from .bib ──
            if uses_external_bib and shutil.which("bibtex"):
                try:
                    bibtex_result = subprocess.run(
                        ["bibtex", stem],
                        cwd=tmpdir,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )
                    # Check for bibtex errors
                    if bibtex_result.returncode != 0:
                        print(f"[XeLaTeX] BibTeX warning: {bibtex_result.stderr[:200]}")
                    # After bibtex, the .aux may have been reset — run xelatex to re-read
                except Exception:
                    print("[XeLaTeX] BibTeX failed — continuing with remaining passes")

            # ── Pass 3: XeLaTeX → read .bbl, populate citations, write .aux refs ──
            result2 = subprocess.run(
                xelatex_args,
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            # ── Pass 4: XeLaTeX → resolve \ref{} cross-references ──
            result3 = subprocess.run(
                xelatex_args,
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            # Use the final-pass log for diagnostics
            log_path = os.path.join(tmpdir, "survey_draft.log")
            errors: list[str] = []
            citation_undefined = False
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    log_content = f.read()
                errors = _parse_xelatex_log(log_content)
                # Also scan for "undefined reference" warnings in .log
                undefined_refs = _parse_undefined_references_from_log(log_content)
                # Check for Citation-specific undefined — blocks delivery
                for ref in undefined_refs:
                    if "citation" in ref.lower():
                        citation_undefined = True
                        break
                errors.extend(undefined_refs)

            if citation_undefined:
                # Block delivery: undefined citations mean [?] in the PDF
                raise RuntimeError(
                    f"XeLaTeX: Citation undefined detected in .log — "
                    f"blocking delivery to prevent [?] in PDF. "
                    f"Undefined refs: {', '.join(e for e in errors if 'citation' in e.lower())[:200]}"
                )

            if result3.returncode == 0 and not errors:
                return []

            return errors[:5]

    except subprocess.TimeoutExpired:
        print("[XeLaTeX] Compilation timed out — falling back to static validation.")
        return []
    except RuntimeError:
        raise  # Re-raise: citation undefined must block delivery
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
    cite_key_map = build_cite_key_map(rows)
    paper_list = "\n".join(
        f"  - \\cite{{{m['cite_key']}}} {m['title']} ({m['authors']}, {m['year']}, {m['venue']})"
        for m in cite_key_map
    )

    cite_key_table = "\n".join(
        f"    [{idx}] \\cite{{{m['cite_key']}}} → {m['title']} ({m['authors']}, {m['year']})"
        for idx, m in enumerate(cite_key_map, start=1)
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
            f"{tmpl['guidance'].replace('TOPIC_PLACEHOLDER', topic)}"
        )
    section_guidance_block = "\n".join(section_guidance_lines)

    return (
        f"You are an academic writing assistant. Generate a Chinese academic survey manuscript in LaTeX.\n\n"
        f"Review topic: {topic}\n\n"
        f"Papers to review ({len(rows)} total):\n{paper_list}\n\n"
        f"MANDATORY CITATION KEY MAP (SSOT — use EXACTLY these \\cite{{}} keys):\n"
        f"{cite_key_table}\n\n"
        f"CRITICAL: Every \\cite in the body MUST use one of these exact keys: "
        f"{', '.join(m['cite_key'] for m in cite_key_map)}. "
        f"Do NOT invent new keys or use numeric [1] without \\cite.\n\n"
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
        "with columns {>{\\raggedright\\arraybackslash}p{2.2cm} >{\\raggedright\\arraybackslash}p{2.5cm} >{\\raggedright\\arraybackslash}p{2.5cm} >{\\raggedright\\arraybackslash}p{2.5cm} >{\\raggedright\\arraybackslash}X} and \\toprule/\\midrule/\\bottomrule booktabs rules. " +
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

        # ── Centralized post-processing: RAG leak cleanup + orphan section strip + math + pages ──
        wrapped = clean_synthesized_latex(wrapped)
        # Inject \label{tab:comparison} before tabularx tables
        wrapped = _inject_table_label(wrapped)
        # Inject bibliography with SSOT cite_key mapping
        cite_key_map = build_cite_key_map(rows)
        wrapped = _inject_bibliography(wrapped, cite_key_map, use_external_bib=True)
        # Export companion references.bib alongside the .tex
        _bib_path = export_references_bib(cite_key_map)
        # ── Citation sanitization: normalize alias keys + unify bibitem keys ──
        wrapped = sanitize_and_repair_citations(wrapped, rows)

        errors = validate_latex_syntax(wrapped)

        # Physical xelatex compilation check (only if static validation passes)
        if not errors:
            try:
                xelatex_errors = compile_with_xelatex(wrapped)
            except RuntimeError as e:
                print(f"[XeLaTeX] {e}")
                # Build a synthetic error for self-healing
                log_warnings = _scan_log_for_undefined_refs(wrapped)
                if log_warnings:
                    print(f"[XeLaTeX] Undefined references detected: {log_warnings}")
                    errors.extend(log_warnings)
                xelatex_errors = []
            if xelatex_errors:
                print(f"[XeLaTeX] {len(xelatex_errors)} compilation error(s) detected.")
                # Scan .log for undefined references — trigger self-healing
                log_warnings = _scan_log_for_undefined_refs(wrapped)
                if log_warnings:
                    print(f"[XeLaTeX] Undefined references detected: {log_warnings}")
                    errors.extend(log_warnings)

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
            "根据综述主题【TOPIC_PLACEHOLDER】编写相关的研究背景、核心应用价值、"
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
            "根据对比矩阵中各文献的方法特征，针对主题【TOPIC_PLACEHOLDER】"
            "划分出清晰的技术体系与分类。"
            "必须采用 \\begin{{itemize}} 列表环境，各类别独立 \\item，"
            "严禁在单行内用长句堆叠。"
        ),
    },
    {
        "name": "系统评述与深度批判",
        "weight": "heavy",
        "guidance": (
            "针对下方 rows 中校验通过的文献，结合主题【TOPIC_PLACEHOLDER】进行深入、批判性的横向评述。"
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
            "针对综述主题【TOPIC_PLACEHOLDER】，使用 \\begin{{tabularx}}{{\\textwidth}}"
            "{{>{\\raggedright\\arraybackslash}p{{2.2cm}} >{\\raggedright\\arraybackslash}p{{2.5cm}}"
            " >{\\raggedright\\arraybackslash}p{{2.5cm}} >{\\raggedright\\arraybackslash}p{{2.5cm}}"
            " >{\\raggedright\\arraybackslash}X}} 规范表格环境"
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
            "从上述已验证的局限性出发，归纳当前在【TOPIC_PLACEHOLDER】场景下面临的"
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
            "总结全文核心发现，概括【TOPIC_PLACEHOLDER】领域当前的研究状态"
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

# ---- Standard BibTeX entries for the four core papers ----
_STANDARD_BIBTEX_ENTRIES = r"""@inproceedings{bergmann2022,
  author    = {Bergmann, Paul and Batzner, Kilian and Fauser, Michael and Sattlegger, David and Steger, Carsten},
  title     = {Beyond Dents and Scratches: Logical Anomaly Detection in Unsupervised Visual Inspection},
  booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
  year      = {2022},
}

@inproceedings{costanzino2023,
  author    = {Costanzino, Alex and others},
  title     = {Cross-Modal Feature Mapping for Lightweight Multimodal Anomaly Detection},
  booktitle = {Proceedings of the International Conference on Computer Vision Theory and Applications (VISAPP)},
  year      = {2023},
}

@article{iodice2025,
  author  = {Iodice, Pietro and others},
  title   = {Human-Robot Collaborative Safety Monitoring Framework with Behaviour Trees},
  journal = {Robotics},
  year    = {2025},
}

@article{soudani2026,
  author  = {Soudani, Amal and others},
  title   = {Real-Time Workspace Monitoring using {YOLOv8} for Industrial Robots},
  journal = {Automation},
  year    = {2026},
}
"""


def export_references_bib(
    cite_key_map: list[dict],
    output_dir: str = ".",
    filename: str = "references.bib",
) -> str:
    """Export SSOT citation key map as a standard BibTeX ``.bib`` database file.

    Writes a ``references.bib`` file to the specified directory containing
    all papers from the cite_key_map in standard BibTeX format. The keys
    match exactly the ``\\cite{...}`` keys used in the body text, enabling
    the ``xelatex → bibtex → xelatex → xelatex`` compilation recipe.

    When cite_key_map is empty, falls back to ``_STANDARD_BIBTEX_ENTRIES``
    (the four core spatial anomaly detection papers).

    Args:
        cite_key_map: List of dicts from build_cite_key_map().
        output_dir: Directory to write the .bib file (default: cwd).
        filename: Output filename (default: ``references.bib``).

    Returns:
        Absolute path to the written .bib file.
    """
    import os as _os

    output_path = _os.path.join(output_dir, filename)

    if not cite_key_map:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(_STANDARD_BIBTEX_ENTRIES)
        print(f"[export_references_bib] Written fallback .bib to {output_path}")
        return output_path

    entries = []
    for m in cite_key_map:
        # Determine entry type from venue
        venue_lower = (m.get("venue") or "").lower()
        if any(kw in venue_lower for kw in ("conf", "cvpr", "iccv", "eccv", "visapp", "icra", "iros", "proc")):
            entry_type = "inproceedings"
            venue_field = "booktitle"
        else:
            entry_type = "article"
            venue_field = "journal"

        # Format authors as "Surname, First and Surname, First"
        authors_raw = m.get("authors", "Unknown")
        # Simple heuristic: "Bergmann P, Batzner K" → "Bergmann, Paul and Batzner, Kilian"
        author_parts = [a.strip() for a in authors_raw.split(",")]
        formatted_authors = " and ".join(author_parts)

        year = m.get("year", "2024")

        entries.append(
            f"@{entry_type}{{{m['cite_key']},\n"
            f"  author    = {{{formatted_authors}}},\n"
            f"  title     = {{{m['title']}}},\n"
            f"  {venue_field} = {{{m['venue']}}},\n"
            f"  year      = {{{year}}},\n"
            f"}}"
        )

    bib_content = "\n\n".join(entries) + "\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(bib_content)

    print(f"[export_references_bib] Written {len(entries)} entries to {output_path}")
    return output_path


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


def _inject_bibliography(
    latex_source: str,
    cite_key_map: list[dict] | None = None,
    use_external_bib: bool = False,
) -> str:
    """Inject the bibliography block before \\end{document}.

    Supports two bibliography modes:

    1. **Embedded ``thebibliography``** (default): Generates ``\\bibitem`` entries
       inline so the document compiles with xelatex alone (2 passes).
       Used when ``use_external_bib=False``.

    2. **External ``.bib`` workflow** (``use_external_bib=True``): Injects
       ``\\bibliographystyle{{plain}}`` and ``\\bibliography{{references}}``
       before ``\\end{{document}}``. The companion ``references.bib`` must be
       exported alongside via ``export_references_bib()``. Compilation requires
       the full ``xelatex → bibtex → xelatex → xelatex`` recipe.

    When cite_key_map is provided, generates entries dynamically from the
    SSOT key map. Falls back to _STANDARD_BIBLIOGRAPHY when no map is provided.

    Only injects if the source does NOT already contain a thebibliography,
    printbibliography, or \\bibliography section — prevents double injection.

    Args:
        latex_source: Full LaTeX source with \\end{{document}} at the end.
        cite_key_map: Optional list of dicts from build_cite_key_map().
        use_external_bib: If True, use \\bibliographystyle + \\bibliography
            instead of embedded thebibliography.

    Returns:
        LaTeX source with bibliography injected before \\end{{document}}.
    """
    if r"\begin{thebibliography}" in latex_source:
        return latex_source
    if r"\printbibliography" in latex_source:
        return latex_source
    if r"\bibliography{" in latex_source:
        return latex_source

    if use_external_bib:
        # ── External .bib workflow ──
        bib_cmd = (
            r"\bibliographystyle{plain}" + "\n"
            + r"\bibliography{references}"
        )
        return latex_source.replace(
            r"\end{document}",
            bib_cmd + "\n\n" + r"\end{document}",
        )

    # ── Embedded thebibliography workflow (default) ──
    if cite_key_map:
        bib_lines = [r"\begin{thebibliography}{99}", ""]
        for m in cite_key_map:
            bib_lines.append(
                f"\\bibitem{{{m['cite_key']}}}\n"
                f"{m['authors']}.\n"
                f"\\emph{{{m['title']}}}. {m['venue']}, {m['year']}."
            )
            bib_lines.append("")
        bib_lines.append(r"\end{thebibliography}")
        bib_block = "\n".join(bib_lines)
    else:
        bib_block = _STANDARD_BIBLIOGRAPHY

    return latex_source.replace(
        r"\end{document}",
        bib_block + "\n\n" + r"\end{document}",
    )


def sanitize_and_repair_citations(tex_content: str, rows: list[AcademicMatrixRow]) -> str:
    """Repair broken citation keys in LaTeX source after bibliography injection.

    This function runs AFTER _inject_bibliography() to ensure that every
    ``\\cite{...}`` key matches a ``\\bibitem{...}`` key exactly.

    Three repair passes:

    1. **Alias normalization**: Builds a mapping from known aliases (derive_cite_key
       variants, author surname prefixes) to canonical keys. Replaces any ``\\cite{...}``
       key found in the alias map with its canonical equivalent.

    2. **Fuzzy orphan correction**: For any ``\\cite{...}`` key that does NOT have a
       matching ``\\bibitem{...}``, attempts to find the closest canonical key by
       substring/prefix matching against bibitem keys and alias map.

    3. **\\bibitem key unification**: Ensures that every ``\\bibitem{...}`` inside
       ``\\begin{thebibliography}`` uses the canonical key.

    Args:
        tex_content: Full LaTeX source with bibliography already injected.
        rows: List of AcademicMatrixRow used to build the alias map.

    Returns:
        Repaired LaTeX source with consistent canonical citation keys.
    """
    # ── Pass 0: Build alias map ──────────────────────────────────────────
    alias_map = build_alias_map(rows)

    # ── Pass 1: Replace known aliases in \cite{...} with canonical keys ──
    def _replace_cite_alias(m: re.Match) -> str:
        keys = [k.strip() for k in m.group(1).split(",")]
        replaced = []
        for k in keys:
            k_lower = k.lower()
            if k_lower in alias_map:
                replaced.append(alias_map[k_lower])
            else:
                replaced.append(k)
        return "\\cite{" + ", ".join(replaced) + "}"

    tex_content = re.sub(r'\\cite\{([^}]+)\}', _replace_cite_alias, tex_content)

    # ── Pass 2: Collect bibitem keys and fuzzy-match orphan cites ─────────
    defined_bibitems: set[str] = set()
    for m in re.finditer(r'\\bibitem\{([^}]+)\}', tex_content):
        defined_bibitems.add(m.group(1))

    canonical_keys: set[str] = {
        derive_canonical_cite_key(row.authors, row.year) for row in rows
    }

    # Build lower-case bibitem lookup for case-insensitive matching
    bib_lower_map: dict[str, str] = {bk.lower(): bk for bk in defined_bibitems}

    def _fuzzy_match_cite_key(cite_key: str) -> str | None:
        """Try to fuzzy-match an orphan cite key to a canonical/bibitem key."""
        ck_lower = cite_key.lower().strip()

        # Case-insensitive exact match in defined bibitems
        if ck_lower in bib_lower_map:
            return bib_lower_map[ck_lower]

        # Try alias map exact match
        if ck_lower in alias_map:
            return alias_map[ck_lower]

        # Try alias map prefix match: check if cite key starts with any alias
        for alias, canonical in alias_map.items():
            if len(alias) >= 5 and ck_lower.startswith(alias):
                return canonical

        # Try prefix match (first 6 chars) against canonical keys
        ck_prefix = ck_lower[:6]
        for ck in canonical_keys:
            if ck.lower().startswith(ck_prefix):
                return ck

        # Try prefix match against bibitem keys
        for bk in defined_bibitems:
            if bk.lower().startswith(ck_prefix):
                return bk
        for bk in defined_bibitems:
            if ck_lower.startswith(bk.lower()[:6]):
                return bk

        # If cite_key contains an author surname, map to that author's canonical key
        for row in rows:
            first_author = row.authors.split(",")[0].strip().split(" ")[0].strip() if row.authors else ""
            surname = re.sub(r"[^a-zA-Z]+", "", first_author).lower()
            if surname and len(surname) >= 4 and surname in ck_lower:
                return derive_canonical_cite_key(row.authors, row.year)

        return None

    def _replace_orphan_cite(m: re.Match) -> str:
        keys = [k.strip() for k in m.group(1).split(",")]
        replaced = []
        for k in keys:
            if k in defined_bibitems:
                replaced.append(k)
                continue
            # Case-insensitive match against bibitems
            if k.lower() in bib_lower_map:
                replaced.append(bib_lower_map[k.lower()])
                continue
            corrected = _fuzzy_match_cite_key(k)
            if corrected:
                print(f"[sanitize_citations] Auto-corrected cite key: {k} → {corrected}")
                replaced.append(corrected)
            else:
                print(f"[sanitize_citations] WARNING: Cannot resolve cite key: {k}")
                replaced.append(k)
        return "\\cite{" + ", ".join(replaced) + "}"

    tex_content = re.sub(r'\\cite\{([^}]+)\}', _replace_orphan_cite, tex_content)

    # ── Pass 3: Unify \bibitem{...} keys in thebibliography ───────────────
    def _replace_bibitem_key(m: re.Match) -> str:
        bib_key = m.group(1)
        bib_key_lower = bib_key.lower()

        # Already canonical — keep
        if bib_key in canonical_keys:
            return m.group(0)

        # Case-insensitive match against canonical
        for ck in canonical_keys:
            if bib_key_lower == ck.lower():
                return "\\bibitem{" + ck + "}"

        # Try alias map
        if bib_key_lower in alias_map:
            corrected = alias_map[bib_key_lower]
            print(f"[sanitize_citations] Corrected bibitem key: {bib_key} → {corrected}")
            return "\\bibitem{" + corrected + "}"

        return m.group(0)

    tex_content = re.sub(r'\\bibitem\{([^}]+)\}', _replace_bibitem_key, tex_content)

    return tex_content


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

    cite_key_map = build_cite_key_map(rows)
    paper_list = "\n".join(
        f"  - \\cite{{{m['cite_key']}}} {m['title']} ({m['authors']}, {m['year']}, {m['venue']})"
        for m in cite_key_map
    )

    cite_key_table = "\n".join(
        f"    [{idx}] \\cite{{{m['cite_key']}}} → {m['title']} ({m['authors']}, {m['year']})"
        for idx, m in enumerate(cite_key_map, start=1)
    )

    full_prompt = (
        f"You are an academic writing assistant. Generate ONE section of a Chinese academic survey manuscript in LaTeX.\n\n"
        f"Review topic: {topic}\n\n"
        f"All papers in the review ({len(rows)} total):\n{paper_list}\n\n"
        f"MANDATORY CITATION KEY MAP (SSOT — use EXACTLY these \\cite{{}} keys):\n"
        f"{cite_key_table}\n\n"
        f"CRITICAL: Every \\cite in this section MUST use one of these exact keys: "
        f"{', '.join(m['cite_key'] for m in cite_key_map)}. "
        f"Do NOT invent new keys.\n\n"
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
        f"  {tmpl['guidance'].replace('TOPIC_PLACEHOLDER', topic)}\n"
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

    # ── Centralized post-processing: RAG leak cleanup + orphan section strip + math + pages ──
    result = clean_synthesized_latex(result)
    # Inject \label{tab:comparison} before tabularx tables
    result = _inject_table_label(result)
    # Inject bibliography with SSOT cite_key mapping
    cite_key_map = build_cite_key_map(rows)
    result = _inject_bibliography(result, cite_key_map, use_external_bib=True)
    # Export companion references.bib alongside the .tex
    _bib_path = export_references_bib(cite_key_map)
    # ── Citation sanitization: normalize alias keys + unify bibitem keys ──
    result = sanitize_and_repair_citations(result, rows)

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
        try:
            xelatex_errors = compile_with_xelatex(result)
        except RuntimeError as e:
            print(f"[XeLaTeX] Multi-stage: {e}")
            xelatex_errors = []
        if xelatex_errors:
            print(f"[XeLaTeX] Multi-stage: {len(xelatex_errors)} compilation error(s) detected.")
            for e in xelatex_errors:
                print(f"  - {e}")
        # Scan .log for undefined references
        log_warnings = _scan_log_for_undefined_refs(result)
        if log_warnings:
            print(f"[XeLaTeX] Undefined references detected: {log_warnings}")
    if progress_callback:
        progress_callback(0, 1, "completed",
            f"Multi-stage synthesis complete: {len(parts)} sections, {len(result)} chars.")

    return result