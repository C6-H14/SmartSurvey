import streamlit as st

from core.credentials import CredentialStore
from core.pdf_parser import parse_pdf_bytes
from core.pipeline import generate_artifacts


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
            artifacts = generate_artifacts(topic, [], ["Matrix extraction is not connected yet."])
            st.markdown(artifacts.markdown_preview)
            st.download_button("Download survey_draft.tex", artifacts.survey_tex, "survey_draft.tex")
            st.download_button("Download matrix_table.tex", artifacts.matrix_table_tex, "matrix_table.tex")
            st.download_button("Download references.bib", artifacts.references_bib, "references.bib")


if __name__ == "__main__":
    run_app()
