import json
from typing import Any

from core.models import AcademicMatrixRow
from core.schema import GENERAL_FIELDS


def build_extraction_prompt(topic: str, domain_fields: list[str], page_text: str) -> str:
    all_fields = GENERAL_FIELDS + ["trigger_reason"] + domain_fields
    return (
        "You extract a structured academic comparison matrix from PDF text.\n"
        f"Review topic: {topic}\n"
        f"Required fields: {', '.join(all_fields)}\n"
        "Rules:\n"
        "- Use missing for fields not supported by the text.\n"
        "- Every limitation, risk, or research gap must include evidence_page and evidence_quote.\n"
        "- evidence_quote must be 1-3 exact English source sentences from the supplied page text.\n"
        "- Return JSON only: a list of objects.\n\n"
        f"PDF text:\n{page_text}"
    )


def _string_value(data: dict[str, Any], field: str) -> str:
    value = data.get(field, "missing")
    return str(value) if value not in (None, "") else "missing"


def parse_matrix_json(raw_json: str, domain_fields: list[str]) -> list[AcademicMatrixRow]:
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
                evidence_page=int(item.get("evidence_page", 0) or 0),
                evidence_quote=_string_value(item, "evidence_quote"),
                confidence=float(item.get("confidence", 0.0) or 0.0),
                trigger_reason=_string_value(item, "trigger_reason"),
                domain_fields={field: _string_value(item, field) for field in domain_fields},
            )
        )
    return rows


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
