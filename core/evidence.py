import re

from core.models import EvidenceValidationResult


AIR_WARNING_BLOCKED = "发现无事实根据的空气警告，已自动拦截"


def normalize_for_containment(text: str) -> str:
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def validate_evidence(
    evidence_page: int,
    evidence_quote: str,
    page_text_by_number: dict[int, str],
) -> EvidenceValidationResult:
    normalized_quote = normalize_for_containment(evidence_quote)
    normalized_page = normalize_for_containment(page_text_by_number.get(evidence_page, ""))
    accepted = bool(normalized_quote) and normalized_quote in normalized_page
    return EvidenceValidationResult(
        accepted=accepted,
        message="accepted" if accepted else AIR_WARNING_BLOCKED,
        normalized_quote=normalized_quote,
    )
