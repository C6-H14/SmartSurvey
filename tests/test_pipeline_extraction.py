from typing import Any

from core.evidence import AIR_WARNING_BLOCKED
from core.models import AcademicMatrixRow
from core.pipeline import extract_with_self_healing


class StatefulMockExtractor:
    """Pure Python callable with internal call-count state.

    First call returns a hallucinated quote that fails containment.
    Second call returns a corrected quote that passes.
    Third and subsequent calls always return corrected quotes.
    """
    def __init__(self):
        self.call_count = 0
        self.prompts_received: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.call_count += 1
        self.prompts_received.append(prompt)
        if self.call_count == 1:
            # Hallucinated quote — NOT in the page text below
            return (
                '[{"title":"Paper A","authors":"Alice","year":"2024",'
                '"venue":"ICRA","research_problem":"detection",'
                '"method":"vision","innovation":"new","limitation":"lighting",'
                '"evidence_page":1,"evidence_quote":"This sentence does not exist on this page.",'
                '"confidence":0.7,"trigger_reason":"stated"}]'
            )
        # Corrected quote — literally present in page_text
        return (
            '[{"title":"Paper A","authors":"Alice","year":"2024",'
            '"venue":"ICRA","research_problem":"detection",'
            '"method":"vision","innovation":"new","limitation":"lighting",'
            '"evidence_page":1,"evidence_quote":"This page supports a real limitation.",'
            '"confidence":0.9,"trigger_reason":"stated"}]'
        )


PAGE_TEXT = "This page supports a real limitation. Other content here."
PAGE_NUMBER = 1


def test_self_healing_retry_succeeds_on_second_attempt():
    """First call fails containment → XML correction prompt built → second call passes."""
    extractor = StatefulMockExtractor()
    domain = ["sensor"]
    rows, warnings = extract_with_self_healing(
        page_text=PAGE_TEXT,
        page_number=PAGE_NUMBER,
        topic="anomaly detection",
        domain_fields=domain,
        extraction_fn=extractor,
        max_retries=3,
    )

    # Must have extracted one row successfully
    assert len(rows) == 1
    assert rows[0].title == "Paper A"
    assert rows[0].evidence_quote == "This page supports a real limitation."
    # No air-warning blocks for the final result
    assert warnings == []
    # Must have called exactly 2 times (1 failed + 1 retry)
    assert extractor.call_count == 2
    # Second prompt must contain the XML correction tag
    assert "<self-healing-correction>" in extractor.prompts_received[1]


def test_self_healing_stops_after_max_retries_with_adaptive_degradation():
    """All 3 retries fail → adaptive degradation: retain general fields, mark evidence-bound as retry_failed.

    max_retries=3 means 3 retries after the initial attempt = 4 total LLM calls.
    """
    class AlwaysFailingExtractor:
        def __init__(self):
            self.call_count = 0
        def __call__(self, prompt: str) -> str:
            self.call_count += 1
            return (
                '[{"title":"Paper B","authors":"Bob","year":"2023",'
                '"venue":"CVPR","research_problem":"detection",'
                '"method":"cnn","innovation":"fast","limitation":"fails at night",'
                '"evidence_page":1,"evidence_quote":"This is pure hallucination.",'
                '"confidence":0.6,"trigger_reason":"stated"}]'
            )

    extractor = AlwaysFailingExtractor()
    rows, warnings = extract_with_self_healing(
        page_text=PAGE_TEXT,
        page_number=PAGE_NUMBER,
        topic="anomaly detection",
        domain_fields=["sensor"],
        extraction_fn=extractor,
        max_retries=3,
    )

    # Must have attempted 4 times (initial + 3 retries)
    assert extractor.call_count == 4
    # Adaptive degradation: general fields retained
    assert len(rows) == 1
    assert rows[0].title == "Paper B"
    assert rows[0].authors == "Bob"
    # Evidence-bound fields marked as retry_failed
    assert rows[0].limitation == "retry_failed"
    assert rows[0].evidence_quote == "retry_failed"
    # Domain fields also marked as retry_failed
    assert rows[0].domain_fields["sensor"] == "retry_failed"
    # Must contain air-warning in the warnings list
    assert len(warnings) == 1
    assert AIR_WARNING_BLOCKED in warnings[0]