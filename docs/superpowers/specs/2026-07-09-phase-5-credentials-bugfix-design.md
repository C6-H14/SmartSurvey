# Phase 5: Multi-Credential Manager & Bug Fixes

## Overview

Phase 5 upgrades the credential system from single-key to JSON multi-key storage,
fixes 3 blocking academic-quality bugs, and introduces a structured logging system
for LLM extraction monitoring.

**Branch:** `feat/task22`

---

## 1. CredentialStore Upgrade (Task 22.1)

### 1.1 JSON Credential Schema

```python
{
    "llm_api_key": "sk-...",
    "llm_api_base": "https://njusehub.info/v1",
    "llm_model_name": "deepseek-v4-flash"
}
```

### 1.2 CredentialStore API

| Method | Signature | Description |
|--------|-----------|-------------|
| `save_all` | `(api_key, api_base, model_name) -> None` | Serialize to JSON, write to `json_credentials` keyring entry |
| `get_all` | `() -> dict` | Read JSON; if missing, migrate legacy `llm_api_key`; if nothing, return defaults |
| `has_credentials` | `() -> bool` | Check JSON or legacy entry existence |
| `clear_all` | `() -> None` | Delete both JSON and legacy entries |

### 1.3 Migration Guard

`get_all()` auto-detects legacy `llm_api_key` keyring entry:
1. Read `json_credentials` → if exists, return parsed JSON
2. Read `llm_api_key` (legacy) → if exists, migrate to JSON format, clear legacy, return
3. Return defaults (`api_key=""`, `api_base=DEFAULT_API_BASE`, `model_name=DEFAULT_MODEL_NAME`)

Removed methods: `set_api_key()`, `get_api_key()`, `clear_api_key()`, `has_api_key()`

### 1.4 Constants

```python
SERVICE_NAME = "SmartSurvey"
JSON_USER = "json_credentials"
LEGACY_USER = "llm_api_key"
DEFAULT_API_BASE = "https://njusehub.info/v1"
DEFAULT_MODEL_NAME = "deepseek-v4-flash"
```

---

## 2. agent.py Three-Level Fallback Chain (Task 22.2)

### 2.1 Priority Chain

1. **Keyring** — `store.get_all()` returns dict with `llm_api_key`, `llm_api_base`, `llm_model_name`
2. **Environment variables** — `OPENAI_API_KEY`, `OPENAI_API_BASE`, `LLM_MODEL_NAME`
3. **Hardcoded defaults** — `DEFAULT_API_BASE`, `DEFAULT_MODEL_NAME` from `core/credentials.py`

### 2.2 Implementation Detail

`get_all()` returns non-empty defaults for `api_base`/`model_name` even when keyring is empty.
Therefore `has_credentials()` must gate keyring usage — a naive per-field `or` chain
would prevent env vars from ever being consulted.

```python
creds = store.get_all()
if store.has_credentials():
    api_key = creds["llm_api_key"] or os.getenv("OPENAI_API_KEY") or ""
    api_base = creds["llm_api_base"] or os.getenv("OPENAI_API_BASE") or DEFAULT_API_BASE
    model_name = creds["llm_model_name"] or os.getenv("LLM_MODEL_NAME") or DEFAULT_MODEL_NAME
else:
    api_key = os.getenv("OPENAI_API_KEY") or ""
    api_base = os.getenv("OPENAI_API_BASE") or DEFAULT_API_BASE
    model_name = os.getenv("LLM_MODEL_NAME") or DEFAULT_MODEL_NAME
```

---

## 3. main.py Three-Field Sidebar (Task 22.3)

Replaces the old single-key UI with a three-field form:

![Sidebar layout]
- **API Key**: password-masked input
- **API Base**: text input (pre-filled from `get_all()`)
- **Model Name**: text input (pre-filled from `get_all()`)
- **Save Credentials**: calls `save_all(api_key, api_base, model_name)`
- **Clear Credentials**: calls `clear_all()`
- Status display via `has_credentials()`
- Generate-preview guard via `has_credentials()`

---

## 4. Bug Fixes

### 4.1 Bug 1: Hollow Content Fallback (Task 22.4)

**Symptom:** Batch extraction produced `survey_draft.tex` where all sections except the
Academic Comparison Matrix contained only hollow placeholder text.

**Root cause:** `scripts/run_extraction.py` called `generate_artifacts` (template-based)
instead of `generate_llm_artifacts` (LLM-driven). Also used removed `has_api_key()`.

**Fixes:**
1. `scripts/run_extraction.py` — Replace `has_api_key()` → `has_credentials()`
2. `core/pipeline.py` — Add `print("⚠️ LLM synthesis returned empty or invalid, falling back to template.")`
3. `core/synthesis.py` — Add `print(f"[LLM] Generated {raw_len} chars: {raw_preview}")`

### 4.2 Bug 2: Giant English Table (Task 22.5)

**Symptom:** Table cells contained long untranslated English paragraphs; table overflowed.

**Fixes:**
1. `core/extractor.py` — Add CRITICAL rule: method/limitation fields MUST be Chinese, ≤20 chars
2. `core/synthesis.py` — Add same CRITICAL rule in synthesis prompt
3. `core/templates.py` — Inject `\footnotesize`, `\setlength{\tabcolsep}{4pt}`, raggedright X columns

### 4.3 Bug 3: Key Metric Missing (Task 22.6)

**Symptom:** Key Metric column showed all "missing" values.

**Fixes:**
1. `core/extractor.py` — Add semantic descriptions for each domain field key
2. `core/templates.py` — Strengthen metric fallback:
   `metric = next((v for v in row.domain_fields.values() if v not in ("missing", "")), row.innovation or "unavailable")`

---

## 5. Log File Architecture (Task 22.7)

### 5.1 Directory Layout

```
data/logs/
├── Agent_log.md        # Complete backup archive (Tasks 1–789, all sessions)
├── Agent_log1.md       # Early task archive (Tasks 0–15)
├── Agent_log2.md       # Current development log (Tasks 16+)
└── agent_run.log       # Runtime LLM extraction log (auto-generated)
```

### 5.2 gitignore Policy

`data/input_pdfs/` and `data/output_docs/` are gitignored.
`data/logs/` is **version-controlled** — logs are committed to the repository.

### 5.3 agent_run.log Format

Append-only text log, one event per line:

```
[2026-07-09 14:30:01] [EXTRACTION] Starting batch: 4 PDFs
[2026-07-09 14:30:05] [LLM] Paper "paper_name" → 1 row, 0 corrections
[2026-07-09 14:30:08] [LLM] Generated 4823 chars
[2026-07-09 14:30:08] [SYNTHESIS] LLM synthesis completed: 4823 chars
[2026-07-09 14:30:08] [EVIDENCE] 3 rows accepted, 1 blocked
[2026-07-09 14:30:08] [FALLBACK] ⚠️ LLM synthesis returned empty, using template
[2026-07-09 14:30:09] [DONE] Output: survey_draft.tex, matrix_table.tex, references.bib
```

### 5.4 Integration Points

| File | Events Logged |
|------|--------------|
| `core/synthesis.py` | LLM entry/exit, char count, synthesis completed |
| `core/pipeline.py` | Fallback warnings, evidence results |
| `scripts/run_extraction.py` | Batch start/end, per-paper results |

---

## 6. Commit History

| Task | Commit | Description |
|------|--------|-------------|
| 22.1 | `2fe81df` | Upgrade credential store to JSON multi-key with migration guard |
| 22.2 | `917a1fc` | Upgrade agent.py with three-level fallback chain |
| 22.3 | `e479d88` | Add three-field credential UI to streamlit sidebar |
| 22.4 | `6fe6ef4` | Fix Bug 1 — Hollow Content Fallback |
| 22.5 | `b04c12d` | Fix Bug 2 — Giant English Table (includes Bug 3) |
| 22.6 | `b04c12d` | Fix Bug 3 — Key Metric Missing (co-committed with 22.5) |

---

## 7. Test Results

- **Full suite**: 54/54 tests passing (up from 50 pre-Phase-5)
- **New tests (Task 22.2)**: 4 agent tests (keyring credentials, env var fallback, defaults, ChatOpenAI injection)
- **New tests (Task 22.1)**: 7 credential tests (get_all, save_all, migration, clear, has, validation)