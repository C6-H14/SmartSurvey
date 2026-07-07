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
from core.pdf_parser import parse_pdf_bytes
from core.pipeline import extract_with_self_healing, generate_artifacts, filter_rows_by_evidence
from core.schema import domain_fields_for_topic


INPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "input_pdfs")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "output_docs")
TOPIC = "industrial automation lab spatial anomaly detection"


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

    # Extract matrix rows with self-healing for each paper
    domain_fields = domain_fields_for_topic(TOPIC)
    all_rows: list = []
    all_warnings: list = []
    for paper in papers:
        if paper.error:
            continue
        for page in paper.pages:
            print(f"  Extracting from {paper.file_name} page {page.page_number}...")
            rows, warnings = extract_with_self_healing(
                page_text=page.text,
                page_number=page.page_number,
                topic=TOPIC,
                domain_fields=domain_fields,
                extraction_fn=extraction_fn,
                max_retries=3,
            )
            all_rows.extend(rows)
            all_warnings.extend(warnings)
            time.sleep(0.2)  # Inter-page delay to reduce rate-limit risk

    # Filter by evidence (second pass)
    accepted, blocked = filter_rows_by_evidence(all_rows, papers)

    # Generate artifacts
    artifacts = generate_artifacts(TOPIC, accepted, blocked)

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