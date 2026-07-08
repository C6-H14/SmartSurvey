import streamlit as st

from core.agent import create_extraction_fn
from core.credentials import CredentialStore
from core.models import ParsedPaper
from core.pdf_parser import parse_pdf_bytes
from core.pipeline import extract_with_self_healing, generate_artifacts, generate_llm_artifacts, filter_rows_by_evidence
from core.schema import domain_fields_for_topic


def run_app() -> None:
    st.set_page_config(page_title="SmartSurvey", layout="wide")
    st.title("SmartSurvey")

    credential_store = CredentialStore()
    with st.sidebar:
        st.header("Credentials")
        st.caption("API Key is stored in the OS keyring. Full keys are never displayed.")
        key_status = "Configured" if credential_store.has_api_key() else "Missing"
        st.write(f"API Key status: {key_status}")
        new_key = st.text_input("Update API Key", type="password")
        if st.button("Save API Key") and new_key:
            credential_store.set_api_key(new_key)
            st.success("API Key saved to OS keyring.")
        if st.button("Clear API Key"):
            credential_store.clear_api_key()
            st.warning("API Key cleared.")

    topic = st.text_input("Review topic", value="industrial automation lab spatial anomaly detection")
    uploaded_files = st.file_uploader("Upload academic PDFs", type=["pdf"], accept_multiple_files=True)

    word_count_target = st.slider(
        "Target word count for manuscript",
        min_value=1000, max_value=10000, value=3000, step=500,
        help="Controls how many Chinese characters the LLM synthesis should target.",
    )

    if uploaded_files:
        parsed = [parse_pdf_bytes(file.getvalue(), file.name) for file in uploaded_files]
        st.subheader("Parsed PDFs")
        for paper in parsed:
            st.write(
                {
                    "file_name": paper.file_name,
                    "pages": len(paper.pages),
                    "abstract": paper.sections["abstract"] != "missing",
                    "error": paper.error,
                }
            )

        if st.button("Generate preview from verified rows"):
            if not credential_store.has_api_key():
                st.error("API Key is required. Please configure it in the sidebar.")
            else:
                extraction_fn = create_extraction_fn(credential_store=credential_store)
                progress_bar = st.progress(0)
                status_text = st.empty()

                def _streamlit_progress_callback(current_idx, total_papers, state, detail):
                    prog = (current_idx + 1) / total_papers if total_papers > 0 else 0
                    progress_bar.progress(prog)
                    status_text.text(f"**{state}**: {detail}")

                domain_fields = domain_fields_for_topic(topic)
                all_rows: list = []
                all_warnings: list = []

                for idx, paper in enumerate(parsed):
                    if paper.error:
                        continue
                    _streamlit_progress_callback(idx, len(parsed), "parsing", paper.file_name)
                    merged_context, page_text_by_number = _get_merged_core_pages(paper)
                    rows, warnings = extract_with_self_healing(
                        merged_context=merged_context,
                        page_text_by_number=page_text_by_number,
                        topic=topic,
                        domain_fields=domain_fields,
                        extraction_fn=extraction_fn,
                        progress_callback=_streamlit_progress_callback,
                        max_retries=3,
                    )
                    all_rows.extend(rows)
                    all_warnings.extend(warnings)

                accepted, blocked = filter_rows_by_evidence(all_rows, parsed)
                if accepted:
                    with st.spinner("Generating full-text manuscript with LLM..."):
                        artifacts = generate_llm_artifacts(
                            topic, accepted, extraction_fn, blocked,
                            word_count_target=word_count_target,
                            progress_callback=_streamlit_progress_callback,
                        )
                else:
                    artifacts = generate_artifacts(
                        topic, accepted, blocked,
                        progress_callback=_streamlit_progress_callback,
                    )
                st.markdown(artifacts.markdown_preview)
                st.download_button("Download survey_draft.tex", artifacts.survey_tex, "survey_draft.tex")
                st.download_button("Download matrix_table.tex", artifacts.matrix_table_tex, "matrix_table.tex")
                st.download_button("Download references.bib", artifacts.references_bib, "references.bib")


def _get_merged_core_pages(paper: ParsedPaper) -> tuple[str, dict[int, str]]:
    """Merge first 3 pages and last 2 non-reference pages into one context."""
    import re
    page_text_by_number = paper.page_text_by_number()
    sorted_nums = sorted(page_text_by_number.keys())
    core_page_nums = set(sorted_nums[:3])
    for p in reversed(sorted_nums):
        if len(core_page_nums) >= 5:
            break
        if p in core_page_nums:
            continue
        if _is_reference_page(page_text_by_number[p]):
            continue
        core_page_nums.add(p)
    core_pages_sorted = sorted(core_page_nums)
    merged_parts = [f"--- PAGE {p} ---\n{page_text_by_number[p]}" for p in core_pages_sorted]
    return "\n\n".join(merged_parts), page_text_by_number


def _is_reference_page(page_text: str) -> bool:
    """Heuristic: if the page contains many citation patterns, it's likely a reference page."""
    lower = page_text.lower()
    ref_markers = ["[1]", "[2]", "[3]", "[4]", "[5]"]
    count = sum(1 for m in ref_markers if m in lower)
    return count >= 3 or "references" in lower[:80]


if __name__ == "__main__":
    run_app()
