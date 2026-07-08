"""Batch extraction: parse PDFs, run self-healing extraction, export artifacts.

Usage:
    python -m scripts.run_extraction

Requires a valid LLM API key in the OS keyring.
"""

import glob
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.agent import create_extraction_fn
from core.credentials import CredentialStore
from core.models import AcademicMatrixRow, ParsedPaper
from core.pdf_parser import parse_pdf_bytes
from core.pipeline import extract_with_self_healing, generate_artifacts, generate_llm_artifacts, filter_rows_by_evidence
from core.schema import domain_fields_for_topic


INPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "input_pdfs")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "output_docs")
TOPIC = "industrial automation lab spatial anomaly detection"
PROGRESS_BAR_LEN = 20


def _print_progress(current: int, total: int, paper_name: str) -> None:
    """Print a single-line ASCII progress bar."""
    percent = int(current / total * 100)
    filled = int(PROGRESS_BAR_LEN * current / total)
    bar = "#" * filled + "-" * (PROGRESS_BAR_LEN - filled)
    print(
        f"\r[进度: {current}/{total}] [{bar}] {percent}% 正在深度解析并提取: {paper_name} ...",
        end="",
        flush=True,
    )


def _console_progress_callback(current_idx: int, total_papers: int, state: str, detail: str) -> None:
    """Progress callback for console extraction."""
    if state == "parsing":
        _print_progress(current_idx + 1, total_papers, detail)
    elif state == "extracting":
        print(f"\r  [{state}] {detail}...", end="", flush=True)
    elif state == "self_healing":
        print(f"\r  [{state}] {detail}...", end="", flush=True)
    elif state == "completed":
        print(f"\r  [{state}] {detail}\n", end="", flush=True)


def _is_reference_page(page_text: str) -> bool:
    """Heuristic: if the page contains many citation patterns, it's likely a reference page."""
    lower = page_text.lower()
    ref_markers = ["[1]", "[2]", "[3]", "[4]", "[5]"]
    count = sum(1 for m in ref_markers if m in lower)
    return count >= 3 or "references" in lower[:80]


def _get_merged_core_pages(paper: ParsedPaper) -> tuple[str, dict[int, str]]:
    """Merge first 3 pages and last 2 non-reference pages into one context.

    Returns:
        (merged_context, page_text_by_number)
    """
    page_text_by_number = paper.page_text_by_number()
    sorted_nums = sorted(page_text_by_number.keys())

    # First 3 pages — metadata, method, introduction
    core_page_nums = set(sorted_nums[:3])

    # Last 2 non-reference pages — conclusion, limitations
    for p in reversed(sorted_nums):
        if len(core_page_nums) >= 5:
            break
        if p in core_page_nums:
            continue
        if _is_reference_page(page_text_by_number[p]):
            continue
        core_page_nums.add(p)

    # Build merged context in page order
    core_pages_sorted = sorted(core_page_nums)
    merged_parts = []
    for p in core_pages_sorted:
        merged_parts.append(
            f"--- PAGE {p} ---\n{page_text_by_number[p]}"
        )
    merged_context = "\n\n".join(merged_parts)
    return merged_context, page_text_by_number


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Resolve credentials
    store = CredentialStore()
    if not store.has_api_key():
        print("ERROR: No API key found in OS keyring. Run 'streamlit run main.py' to configure one.")
        sys.exit(1)

    # Create extraction function (real LLM)
    extraction_fn = create_extraction_fn(credential_store=store)

    # Parse all PDFs
    pdf_paths = glob.glob(os.path.join(INPUT_DIR, "*.pdf"))
    if not pdf_paths:
        print(f"No PDFs found in {INPUT_DIR}")
        sys.exit(1)

    print(f"Parsing {len(pdf_paths)} PDFs...")
    papers = []
    for path in pdf_paths:
        with open(path, "rb") as f:
            paper = parse_pdf_bytes(f.read(), os.path.basename(path))
        papers.append(paper)
        status = "OK" if not paper.error else f"ERROR: {paper.error}"
        print(f"  [{status}] {paper.file_name} ({len(paper.pages)} pages)")

    # Extract one consolidated row per paper (not per page!)
    domain_fields = domain_fields_for_topic(TOPIC)
    all_rows: list = []
    all_warnings: list = []
    total_papers = len(papers)

    for idx, paper in enumerate(papers, start=1):
        if paper.error:
            continue

        short_name = os.path.splitext(paper.file_name)[0][:40]
        _console_progress_callback(idx - 1, total_papers, "parsing", short_name)

        merged_context, page_text_by_number = _get_merged_core_pages(paper)

        rows, warnings = extract_with_self_healing(
            merged_context=merged_context,
            page_text_by_number=page_text_by_number,
            topic=TOPIC,
            domain_fields=domain_fields,
            extraction_fn=extraction_fn,
            progress_callback=_console_progress_callback,
            max_retries=3,
        )

        # Defense 3: Ultimate filename fallback — if JSON extraction failed
        # after all retries, create a degraded row from the filename so
        # every paper appears in the final output.
        if not rows:
            fallback = AcademicMatrixRow(
                title=os.path.splitext(paper.file_name)[0],
                authors="unverified",
                year="unverified",
                venue="unverified",
                research_problem="unverified",
                method="unverified",
                innovation="unverified",
                limitation="JSON extraction failed after 3 retries",
                evidence_page=0,
                evidence_quote="unverified",
                confidence=0.0,
                trigger_reason="unverified",
                domain_fields={k: "unverified" for k in domain_fields},
            )
            rows = [fallback]
            print(f"  [降级兜底] 使用文件名作为 title: {fallback.title}")

        all_rows.extend(rows)
        all_warnings.extend(warnings)

        # Print result count inline after the progress bar line
        row_count = len(rows)
        warn_count = len(warnings)
        print(f"  [{row_count}行, {warn_count}次校正]")

        # 1.5s inter-paper delay
        time.sleep(1.5)

    # Clear progress line
    print()

    # Filter by evidence (second pass) — degraded rows pass through automatically
    accepted, blocked = filter_rows_by_evidence(all_rows, papers)

    # Generate artifacts with LLM synthesis (falls back to template)
    if accepted:
        artifacts = generate_llm_artifacts(
            TOPIC, accepted, extraction_fn, blocked,
            progress_callback=_console_progress_callback,
        )
    else:
        artifacts = generate_artifacts(TOPIC, accepted, blocked,
                                       progress_callback=_console_progress_callback)

    # Write outputs
    tex_path = os.path.join(OUTPUT_DIR, "survey_draft.tex")
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(artifacts.survey_tex)
    print(f"Written: {tex_path}")

    matrix_path = os.path.join(OUTPUT_DIR, "matrix_table.tex")
    with open(matrix_path, "w", encoding="utf-8") as f:
        f.write(artifacts.matrix_table_tex)
    print(f"Written: {matrix_path}")

    bib_path = os.path.join(OUTPUT_DIR, "references.bib")
    with open(bib_path, "w", encoding="utf-8") as f:
        f.write(artifacts.references_bib)
    print(f"Written: {bib_path}")

    # Summary
    total_accepted = len(accepted)
    total_blocked = len(blocked)
    print(f"\nDone. {total_accepted} rows accepted, {total_blocked} blocked warnings.")
    print(f"Self-healing details: {len(all_warnings)} correction events recorded.")


if __name__ == "__main__":
    main()