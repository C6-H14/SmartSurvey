import json
import time
from typing import Callable

from core.evidence import validate_evidence
from core.extractor import build_extraction_prompt, build_self_healing_prompt, parse_matrix_json
from core.models import AcademicMatrixRow, GeneratedArtifacts, ParsedPaper
from core.templates import render_bibtex, render_markdown_preview, render_matrix_table_tex, render_survey_tex


def _call_with_rate_limit_backoff(
    extraction_fn: Callable[[str], str],
    prompt: str,
    max_retries: int = 3,
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
                time.sleep(wait)
                continue
            raise
    # Fallback (should not reach here)
    return extraction_fn(prompt)


def filter_rows_by_evidence(
    rows: list[AcademicMatrixRow],
    papers: list[ParsedPaper],
) -> tuple[list[AcademicMatrixRow], list[str]]:
    page_texts: dict[int, str] = {}
    for paper in papers:
        page_texts.update(paper.page_text_by_number())

    accepted: list[AcademicMatrixRow] = []
    blocked: list[str] = []
    for row in rows:
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
) -> GeneratedArtifacts:
    return GeneratedArtifacts(
        markdown_preview=render_markdown_preview(topic, rows, blocked_warnings),
        survey_tex=render_survey_tex(topic, rows),
        matrix_table_tex=render_matrix_table_tex(rows),
        references_bib=render_bibtex(rows),
    )


def extract_with_self_healing(
    page_text: str,
    page_number: int,
    topic: str,
    domain_fields: list[str],
    extraction_fn: Callable[[str], str],
    max_retries: int = 3,
) -> tuple[list[AcademicMatrixRow], list[str]]:
    """Extract academic matrix rows with self-healing retry loop.

    Uses dependency injection for the LLM call (extraction_fn).
    Returns (accepted_rows, warnings_list).
    """
    prompt = build_extraction_prompt(topic, domain_fields, page_text)
    warnings: list[str] = []

    for attempt in range(max_retries + 1):  # +1 for the initial attempt
        raw_json = _call_with_rate_limit_backoff(extraction_fn, prompt)
        time.sleep(0.1)  # Base delay between requests to reduce rate-limit risk
        try:
            rows = parse_matrix_json(raw_json, domain_fields)
        except (ValueError, json.JSONDecodeError):
            warnings.append("JSON parsing failed; skipping self-healing for this row.")
            return [], warnings

        accepted: list[AcademicMatrixRow] = []
        blocked_any = False
        for row in rows:
            result = validate_evidence(
                row.evidence_page,
                row.evidence_quote,
                {page_number: page_text},
            )
            if result.accepted:
                accepted.append(row)
            else:
                blocked_any = True
                # Adaptive degradation: if we've exhausted retries,
                # keep the row but mark evidence-bound fields as retry_failed
                if attempt >= max_retries:
                    degraded = _apply_degradation(row)
                    accepted.append(degraded)
                    if result.message not in warnings:
                        warnings.append(result.message)

        if not blocked_any:
            return accepted, warnings

        # Build XML correction prompt for next attempt
        if attempt < max_retries:
            failed_quote = rows[0].evidence_quote  # use first failing row's quote
            prompt = build_self_healing_prompt(prompt, page_number, failed_quote, page_text)

    return accepted, warnings


def _apply_degradation(row: AcademicMatrixRow) -> AcademicMatrixRow:
    """Mark evidence-bound fields as retry_failed; keep general fields intact."""
    degraded_domain = {k: "retry_failed" for k in row.domain_fields}
    return AcademicMatrixRow(
        title=row.title,
        authors=row.authors,
        year=row.year,
        venue=row.venue,
        research_problem=row.research_problem,
        method=row.method,
        innovation="retry_failed",
        limitation="retry_failed",
        evidence_page=row.evidence_page,
        evidence_quote="retry_failed",
        confidence=row.confidence,
        trigger_reason=row.trigger_reason,
        domain_fields=degraded_domain,
    )
