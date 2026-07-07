from core.extractor import build_extraction_prompt, build_self_healing_prompt, parse_matrix_json


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


def test_build_self_healing_prompt_contains_xml_tags():
    original = build_extraction_prompt("test topic", ["sensor"], "Page 1 text.")
    corrected = build_self_healing_prompt(
        original_prompt=original,
        failed_page=1,
        failed_quote="Fake quote.",
        page_text="Page 1 text.",
    )

    assert "<self-healing-correction>" in corrected
    assert "<failed-page>1</failed-page>" in corrected
    assert "<failed-quote>Fake quote.</failed-quote>" in corrected
    assert "<page-text>Page 1 text.</page-text>" in corrected
    assert "<error>" in corrected
    assert "</self-healing-correction>" in corrected
    # Original prompt content must be preserved
    assert "test topic" in corrected
    assert "Return JSON only" in corrected
