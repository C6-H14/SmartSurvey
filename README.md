# SmartSurvey

SmartSurvey is an AI4SE non-harness application for evidence-bound academic literature review generation.

## Features

- Batch PDF parsing with core section detection and fallback page slices.
- Two-layer academic matrix schema.
- Evidence containment validation before writing limitations or risks.
- Markdown preview and LaTeX/BibTeX exports.
- OS keyring API key storage.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run main.py
```

## Test

```bash
python -m pytest tests -v
```

## Docker

```bash
docker build -t smartsurvey:local .
docker run --rm -p 8501:8501 smartsurvey:local
```

## Credential Safety

SmartSurvey stores the LLM API key in the operating system keyring. The full key is never displayed in the UI, logs, exported files, Docker images, or committed source files.

For development compatibility, `.env` may still supply `OPENAI_API_BASE` and `LLM_MODEL_NAME` only. Do not put real API keys in `.env` or Git.

## Known Limits

The first version does not automatically download papers, reconstruct perfect PDF paragraphs, or guarantee zero-edit LaTeX compilation in every Overleaf template.
