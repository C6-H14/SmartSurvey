import json
import re
from typing import Any

from core.models import AcademicMatrixRow
from core.schema import GENERAL_FIELDS


def _extract_json_bracket(text: str) -> str:
    """Defense 1: Regex bracket extraction — find outermost [...] or {...}.

    Strips any text before the first '[' and after the last ']'.
    If no [...] found, tries to find {...} and wraps it as a single-element list.
    """
    # Try outermost [...] first (standard JSON array)
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return match.group()
    # Fallback: outermost {...} → wrap as single-element list
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return f"[{match.group()}]"
    return text


def build_extraction_prompt(topic: str, domain_fields: list[str], page_text: str) -> str:
    all_fields = GENERAL_FIELDS + ["trigger_reason"] + domain_fields
    semantic_hints = {
        "sensor": "sensor: the type or model of sensor used in the experiment",
        "accuracy": "accuracy: the reported numerical accuracy or performance metric",
        "method": "method: the core algorithm or approach proposed",
        "dataset": "dataset: the benchmark dataset or experimental environment used",
    }
    domain_hints = "; ".join(
        semantic_hints.get(f, f"{f}: the key metric or result reported for {f}")
        for f in domain_fields
    )
    return (
        "You extract a structured academic comparison matrix from PDF text.\n"
        f"Review topic: {topic}\n"
        f"Required fields: {', '.join(all_fields)}\n"
        f"Field semantics: {domain_hints}\n"
        "Rules:\n"
        "- Use missing for fields not supported by the text.\n"
        "- Every limitation, risk, or research gap must include evidence_page and evidence_quote.\n"
        "- evidence_quote must be 1-3 exact English source sentences from the supplied page text.\n"
        "- The text below merges the paper's FIRST pages (title, abstract, method) "
        "and LAST pages (conclusion, limitations). Extract ONE consolidated row per paper.\n"
        "- CRITICAL WARNING: Any slight modification of the evidence_quote (even a single "
        "capitalization or punctuation difference) will cause our verification system to reject "
        "your input completely. You MUST copy-paste the exact verbatim substring from the PDF text.\n"
        "- CRITICAL: The 'method' and 'limitation' fields MUST be written in Chinese, "
        "no more than 20 Chinese characters each, as a concise academic summary. "
        "Keep evidence_quote in English as-is. No long English paragraphs allowed in the table cells.\n"
        f"- CRITICAL: When extracting metrics or error measures, you MUST capture the original "
        f"LaTeX math formulas (e.g., $E(u) = \\int_\\Omega |\\nabla u|^2 dx$) used in the paper. "
        f"Include these formulas in the extracted fields for academic rigor.\n"
        "- Return JSON only: a list containing exactly ONE object.\n\n"
        f"Merged PDF text (first + last pages):\n{page_text}"
    )


def _string_value(data: dict[str, Any], field: str) -> str:
    value = data.get(field, "missing")
    return str(value) if value not in (None, "") else "missing"


def _int_value(data: dict[str, Any], field: str) -> int:
    """Extract int from field, returning 0 if field is missing or non-numeric."""
    value = data.get(field, 0)
    if isinstance(value, str):
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    return int(value) if value else 0


def _float_value(data: dict[str, Any], field: str) -> float:
    """Extract float from field, returning 0.0 if field is missing or non-numeric."""
    value = data.get(field, 0.0)
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    return float(value) if value else 0.0


def parse_matrix_json(raw_json: str, domain_fields: list[str]) -> list[AcademicMatrixRow]:
    # Defense 1: Regex bracket extraction — extract outermost [...] or {...}
    raw_json = _extract_json_bracket(raw_json.strip())

    # Strips markdown code fences in case regex didn't catch them
    if raw_json.startswith("```"):
        first_newline = raw_json.find("\n")
        if first_newline != -1:
            raw_json = raw_json[first_newline + 1:]
        if raw_json.endswith("```"):
            raw_json = raw_json[:-3]
    raw_json = raw_json.strip()

    data = json.loads(raw_json)
    if not isinstance(data, list):
        raise ValueError("Matrix JSON must be a list of row objects.")

    rows: list[AcademicMatrixRow] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("Each matrix row must be an object.")
        rows.append(
            AcademicMatrixRow(
                title=_string_value(item, "title"),
                authors=_string_value(item, "authors"),
                year=_string_value(item, "year"),
                venue=_string_value(item, "venue"),
                research_problem=_string_value(item, "research_problem"),
                method=_string_value(item, "method"),
                innovation=_string_value(item, "innovation"),
                limitation=_string_value(item, "limitation"),
                evidence_page=_int_value(item, "evidence_page"),
                evidence_quote=_string_value(item, "evidence_quote"),
                confidence=_float_value(item, "confidence"),
                trigger_reason=_string_value(item, "trigger_reason"),
                domain_fields={field: _string_value(item, field) for field in domain_fields},
            )
        )
    return rows


def build_json_healing_prompt(original_prompt: str) -> str:
    """Defense 2: JSON-specific self-healing correction prompt."""
    correction = (
        "\n\n<self-healing-correction>\n"
        "  <error>JSON 格式损坏，无法被 json.loads 解析。请一字不差地输出"
        "符合 Schema 的标准 JSON 格式，严格禁止任何解释性文字或 Markdown 标记外溢。</error>\n"
        "</self-healing-correction>"
    )
    return original_prompt + correction


def build_self_healing_prompt(
    original_prompt: str,
    failed_page: int,
    failed_quote: str,
    page_text: str,
) -> str:
    correction = (
        "\n\n<self-healing-correction>\n"
        f"  <failed-page>{failed_page}</failed-page>\n"
        f"  <failed-quote>{failed_quote}</failed-quote>\n"
        "  <error>The evidence_quote was NOT found in the specified page text. "
        "Please re-extract with a quote that literally exists on this page.</error>\n"
        f"  <page-text>{page_text}</page-text>\n"
        "</self-healing-correction>"
    )
    return original_prompt + correction
