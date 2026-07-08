from core.evidence import AIR_WARNING_BLOCKED, normalize_for_containment, validate_evidence


def test_normalize_for_containment_collapses_whitespace_and_hyphen_breaks():
    text = "The method is light-\n ing sensitive."

    assert normalize_for_containment(text) == "the method is lighting sensitive"


def test_validate_evidence_accepts_quote_on_page(sample_page_texts):
    result = validate_evidence(
        evidence_page=2,
        evidence_quote="The limitation is lighting sensitivity.",
        page_text_by_number=sample_page_texts,
    )

    assert result.accepted is True


def test_validate_evidence_rejects_missing_quote(sample_page_texts):
    result = validate_evidence(
        evidence_page=2,
        evidence_quote="This sentence is not in the paper.",
        page_text_by_number=sample_page_texts,
    )

    assert result.accepted is False
    assert result.message == AIR_WARNING_BLOCKED
