GENERAL_FIELDS = [
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


def domain_fields_for_topic(topic: str) -> list[str]:
    normalized = topic.lower()
    if "brauer" in normalized or "manin" in normalized:
        return ["mathematical_object", "obstruction_type", "theorem_result", "proof_technique"]
    if "matrix" in normalized and ("multiplication" in normalized or "complexity" in normalized):
        return [
            "complexity_bound",
            "algorithmic_technique",
            "tensor_rank_or_border_rank",
            "theoretical_result",
        ]
    if any(token in normalized for token in ["anomaly", "industrial", "automation", "robot", "workspace"]):
        return ["sensor", "accuracy", "latency", "deployment_scene", "decision_mechanism"]
    return ["method", "metric", "application"]
