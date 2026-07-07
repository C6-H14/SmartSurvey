from core.extractor import build_extraction_prompt, parse_matrix_json


def test_build_extraction_prompt_includes_general_and_domain_fields():
    prompt = build_extraction_prompt(
        topic="industrial anomaly detection",
        domain_fields=["sensor", "accuracy"],
        page_text="Page 1 text",
    )

    assert "evidence_page" in prompt
    assert "evidence_quote" in prompt
    assert "sensor" in prompt
    assert "Return JSON only" in prompt


def test_parse_matrix_json_converts_missing_fields_to_missing():
    rows = parse_matrix_json(
        '[{"title":"Paper A","evidence_page":1,"evidence_quote":"Quote","confidence":0.7}]',
        domain_fields=["sensor"],
    )

    assert rows[0].title == "Paper A"
    assert rows[0].authors == "missing"
    assert rows[0].domain_fields["sensor"] == "missing"
