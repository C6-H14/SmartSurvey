import json
import time
from typing import Callable

from core.evidence import validate_evidence
from core.extractor import build_extraction_prompt, build_json_healing_prompt, build_self_healing_prompt, parse_matrix_json
from core.models import AcademicMatrixRow, GeneratedArtifacts, ParsedPaper
from core.synthesis import render_survey_tex_with_llm
from core.templates import render_bibtex, render_markdown_preview, render_matrix_table_tex, render_survey_tex


def _call_with_rate_limit_backoff(
    extraction_fn: Callable[[str], str],
    prompt: str,
    max_retries: int = 3,
    progress_callback: Callable[[int, int, str, str], None] | None = None,
) -> str:
    """Call extraction_fn with rate-limit (429) and timeout retry + exponential backoff.

    Catches HTTP 429 errors and timeout errors, prints error type and wait
    duration to console, then retries up to max_retries times with 1s/2s/4s backoff.
    """
    for attempt in range(max_retries + 1):
        try:
            return extraction_fn(prompt)
        except Exception as e:
            status = getattr(e, 'status_code', None)
            is_timeout = isinstance(e, TimeoutError) or 'timed out' in str(e).lower() or 'timeout' in type(e).__name__.lower()
            should_retry = (status == 429 or is_timeout) and attempt < max_retries
            if should_retry:
                wait = 2 ** attempt  # 1, 2, 4 seconds
                error_type = "RateLimit" if status == 429 else "Timeout"
                print(
                    f"  [{error_type}] {type(e).__name__}: "
                    f"{wait}s后重试... "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                if progress_callback:
                    progress_callback(0, 1, "self_healing",
                        f"{error_type} backoff {wait}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
                continue
            raise
    # Fallback (should not reach here)
    return extraction_fn(prompt)


def _find_matching_paper(row: AcademicMatrixRow, papers: list[ParsedPaper]) -> ParsedPaper | None:
    """Match a row to its source paper using normalized title comparison.

    Uses progressive matching: exact title → file_name prefix → keyword overlap.
    All comparisons strip underscores so 'foo_bar' and 'foobar' are equivalent.
    """
    import re as _re

    def _norm(text: str) -> str:
        """Strip punctuation, underscores, and whitespace; lowercase."""
        return _re.sub(r"[\W_]+", "", text).lower()

    row_title = _norm(row.title) if row.title else ""

    for paper in papers:
        paper_title = _norm(paper.title) if paper.title else ""
        paper_fname = _norm(paper.file_name) if paper.file_name else ""

        # 1. Normalized title containment
        if row_title and paper_title:
            if row_title in paper_title or paper_title in row_title:
                return paper

        # 2. File name containment
        if row_title and paper_fname:
            if row_title in paper_fname or paper_fname in row_title:
                return paper

        # 3. Keyword overlap: share 2+ significant words (>4 chars)
        row_words = {w for w in row_title.split("_") if len(w) > 4}
        fname_words = {w for w in paper_fname.split("_") if len(w) > 4}
        if len(row_words & fname_words) >= 2:
            return paper

        # 4. Fallback: file_name prefix (first 20 chars)
        if paper.title in ("missing", "") and paper_fname:
            prefix = paper_fname[:20]
            if prefix in row_title or row_title[:20] in prefix:
                return paper

    return None


def filter_rows_by_evidence(
    rows: list[AcademicMatrixRow],
    papers: list[ParsedPaper],
) -> tuple[list[AcademicMatrixRow], list[str]]:
    accepted: list[AcademicMatrixRow] = []
    blocked: list[str] = []

    for row in rows:
        # Degraded rows pass through without containment validation
        if row.evidence_quote in ("missing", "retry_failed", "unverified"):
            accepted.append(row)
            continue

        # Per-paper isolation: find the specific paper this row belongs to
        matched_paper = _find_matching_paper(row, papers)

        if matched_paper is not None:
            page_texts = matched_paper.page_text_by_number()
        else:
            # Fallback: merge all pages (legacy behavior)
            page_texts: dict[int, str] = {}
            for p in papers:
                page_texts.update(p.page_text_by_number())

        result = validate_evidence(row.evidence_page, row.evidence_quote, page_texts)
        if result.accepted:
            accepted.append(row)
        else:
            blocked.append(result.message)
    return accepted, blocked


def generate_artifacts(
    topic: str,
    rows: list[AcademicMatrixRow],
    blocked_warnings: list[str],
    progress_callback: Callable[[int, int, str, str], None] | None = None,
) -> GeneratedArtifacts:
    if progress_callback:
        progress_callback(0, 1, "completed", "Generating artifacts...")
    return GeneratedArtifacts(
        markdown_preview=render_markdown_preview(topic, rows, blocked_warnings),
        survey_tex=render_survey_tex(topic, rows),
        matrix_table_tex=render_matrix_table_tex(rows),
        references_bib=render_bibtex(rows),
    )


def generate_llm_artifacts(
    topic: str,
    rows: list[AcademicMatrixRow],
    extraction_fn: Callable[[str], str],
    blocked_warnings: list[str],
    word_count_target: int = 3000,
    progress_callback: Callable[[int, int, str, str], None] | None = None,
) -> GeneratedArtifacts:
    """Generate artifacts with LLM-driven LaTeX synthesis instead of template.

    Falls back to template-based generation if synthesis produces empty output.
    """
    survey_tex = render_survey_tex_with_llm(
        topic, rows, extraction_fn,
        word_count_target=word_count_target,
        progress_callback=progress_callback,
    )
    # Fallback: if synthesis produced empty or broken output, use template
    if not survey_tex or len(survey_tex) < 100:
        from core.templates import render_survey_tex
        survey_tex = render_survey_tex(topic, rows)

    return GeneratedArtifacts(
        markdown_preview=render_markdown_preview(topic, rows, blocked_warnings),
        survey_tex=survey_tex,
        matrix_table_tex=render_matrix_table_tex(rows),
        references_bib=render_bibtex(rows),
    )


def extract_with_self_healing(
    merged_context: str,
    page_text_by_number: dict[int, str],
    topic: str,
    domain_fields: list[str],
    extraction_fn: Callable[[str], str],
    progress_callback: Callable[[int, int, str, str], None] | None = None,
    max_retries: int = 3,
) -> tuple[list[AcademicMatrixRow], list[str]]:
    """Extract ONE consolidated AcademicMatrixRow per paper with self-healing.

    Args:
        merged_context: Combined text from first 3 + last 2 core pages.
        page_text_by_number: Dict of ALL page texts for evidence validation.
        topic: Review topic string.
        domain_fields: Topic-specific domain field names.
        extraction_fn: DI callable (prompt → raw JSON string).
        progress_callback: Optional callback for progress reporting.
        max_retries: Max retries after the initial attempt.

    Returns:
        (accepted_rows, warnings_list) — at most 1 row per call.
    """
    prompt = build_extraction_prompt(topic, domain_fields, merged_context)
    warnings: list[str] = []

    if progress_callback:
        progress_callback(0, 1, "extracting", "Initial extraction attempt...")

    for attempt in range(max_retries + 1):  # +1 for the initial attempt
        raw_json = _call_with_rate_limit_backoff(extraction_fn, prompt, progress_callback=progress_callback)
        try:
            rows = parse_matrix_json(raw_json, domain_fields)
        except (ValueError, json.JSONDecodeError) as parse_err:
            # Defense 2: JSON parse failure → feed into self-healing loop
            # instead of crashing or returning empty
            if attempt >= max_retries:
                warnings.append(f"JSON parsing failed after {max_retries + 1} attempts: {parse_err}")
                if progress_callback:
                    progress_callback(0, 1, "completed",
                        f"JSON parsing failed: {parse_err}")
                return [], warnings
            prompt = build_json_healing_prompt(prompt)
            continue

        accepted: list[AcademicMatrixRow] = []
        blocked_any = False
        blocked_any = False
        for row in rows:
            # Validate against ALL pages of the paper, not just one page
            result = validate_evidence(
                row.evidence_page,
                row.evidence_quote,
                page_text_by_number,
            )
            if result.accepted:
                accepted.append(row)
            else:
                blocked_any = True
                # Adaptive degradation: keep general fields, mark evidence as unverified
                if attempt >= max_retries:
                    degraded = _apply_degradation(row)
                    accepted.append(degraded)
                    if result.message not in warnings:
                        warnings.append(result.message)

        if not blocked_any:
            if progress_callback:
                progress_callback(0, 1, "completed",
                    f"Accepted {len(accepted)} rows, {len(warnings)} corrections")
            return accepted, warnings

        # Build XML correction prompt for next attempt
        if attempt < max_retries:
            if progress_callback:
                progress_callback(0, 1, "self_healing",
                    f"Retry {attempt + 1}/{max_retries}: Evidence quote failed containment, rebuilding prompt...")
            # Use the evidence_page from the first failing row for the correction
            failed_page = rows[0].evidence_page
            failed_quote = rows[0].evidence_quote
            # Provide the specific page text as open-book reference
            page_text_for_correction = page_text_by_number.get(failed_page, merged_context)
            prompt = build_self_healing_prompt(
                prompt, failed_page, failed_quote, page_text_for_correction
            )

    if progress_callback:
        progress_callback(0, 1, "completed",
            f"Accepted {len(accepted)} rows, {len(warnings)} corrections")
    return accepted, warnings


def _apply_degradation(row: AcademicMatrixRow) -> AcademicMatrixRow:
    """Mark evidence-bound fields as unverified; keep general fields intact."""
    degraded_domain = {k: "missing (unverified)" for k in row.domain_fields}
    return AcademicMatrixRow(
        title=row.title,
        authors=row.authors,
        year=row.year,
        venue=row.venue,
        research_problem=row.research_problem,
        method=row.method,
        innovation="missing (unverified)",
        limitation="missing (unverified)",
        evidence_page=row.evidence_page,
        evidence_quote="unverified",
        confidence=row.confidence,
        trigger_reason=row.trigger_reason,
        domain_fields=degraded_domain,
    )
