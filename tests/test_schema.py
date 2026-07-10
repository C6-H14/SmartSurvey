from core.schema import GENERAL_FIELDS, domain_fields_for_topic


def test_general_fields_match_spec():
    assert GENERAL_FIELDS == [
        "title",
        "authors",
        "year",
        "venue",
        "research_problem",
        "method",
        "innovation",
        "limitation",
        "evidence_page",
        "evidence_quote",
        "confidence",
    ]


def test_domain_fields_for_industrial_anomaly_detection():
    fields = domain_fields_for_topic("industrial automation lab spatial anomaly detection")

    assert "sensor" in fields
    assert "accuracy" in fields
    assert "latency" in fields
    assert "decision_mechanism" in fields


def test_domain_fields_for_brauer_manin():
    fields = domain_fields_for_topic("Brauer-Manin obstruction")

    assert fields == ["mathematical_object", "obstruction_type", "theorem_result", "proof_technique"]


def test_domain_fields_for_matrix_multiplication():
    fields = domain_fields_for_topic("matrix multiplication complexity upper bounds")

    assert "complexity_bound" in fields
    assert "tensor_rank_or_border_rank" in fields


def test_domain_fields_generic_fallback():
    """Unknown topic must return generic fallback fields, not empty list."""
    for unknown_topic in ["medical lesion segmentation", "graph neural networks", "quantum computing"]:
        fields = domain_fields_for_topic(unknown_topic)
        assert fields == ["method", "metric", "application"], f"Failed for {unknown_topic}: {fields}"
