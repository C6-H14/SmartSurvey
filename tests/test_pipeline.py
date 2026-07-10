from core.models import AcademicMatrixRow
from core.pipeline import extract_with_self_healing, generate_artifacts


def test_zero_drop_retains_degraded_row():
    """Even after 3 failed validation attempts, the row must appear in output."""
    class AlwaysFailingExtractor:
        def __init__(self):
            self.call_count = 0
        def __call__(self, prompt: str) -> str:
            self.call_count += 1
            return (
                '[{"title":"Paper A","authors":"Alice","year":"2024",'
                '"venue":"ICRA","research_problem":"detection",'
                '"method":"vision","innovation":"new","limitation":"lighting",'
                '"evidence_page":1,"evidence_quote":"This is pure hallucination.",'
                '"confidence":0.6,"trigger_reason":"stated"}]'
            )

    page_text = "This page supports a real limitation."
    rows, warnings = extract_with_self_healing(
        merged_context=page_text,
        page_text_by_number={1: page_text},
        topic="test",
        domain_fields=["sensor"],
        extraction_fn=AlwaysFailingExtractor(),
        max_retries=3,
    )

    # Zero-Drop: must return exactly 1 row (degraded)
    assert len(rows) == 1
    assert rows[0].title == "Paper A"
    # Evidence-bound fields must be marked as unverified
    assert rows[0].evidence_quote == "unverified"
    assert rows[0].limitation == "missing (unverified)"


def test_zero_drop_accepts_valid_row():
    """Row with valid evidence passes through unchanged."""
    class ValidExtractor:
        def __call__(self, prompt: str) -> str:
            return (
                '[{"title":"Paper A","authors":"Alice","year":"2024",'
                '"venue":"ICRA","research_problem":"detection",'
                '"method":"vision","innovation":"new","limitation":"lighting",'
                '"evidence_page":1,"evidence_quote":"This page supports a real limitation.",'
                '"confidence":0.9,"trigger_reason":"stated"}]'
            )

    page_text = "This page supports a real limitation."
    rows, warnings = extract_with_self_healing(
        merged_context=page_text,
        page_text_by_number={1: page_text},
        topic="test",
        domain_fields=["sensor"],
        extraction_fn=ValidExtractor(),
        max_retries=3,
    )

    assert len(rows) == 1
    assert rows[0].evidence_quote == "This page supports a real limitation."
    assert warnings == []


def test_generate_artifacts_returns_all_downloads():
    row = AcademicMatrixRow(
        title="Paper A",
        authors="Alice",
        year="2024",
        venue="ICRA",
        research_problem="problem",
        method="method",
        innovation="innovation",
        limitation="limitation",
        evidence_page=1,
        evidence_quote="Quote",
        confidence=0.8,
        trigger_reason="reason",
    )

    artifacts = generate_artifacts("topic", [row], [])

    assert "Paper A" in artifacts.markdown_preview
    assert "\\begin{table}" in artifacts.matrix_table_tex
    assert "\\documentclass{ctexart}" in artifacts.survey_tex
    assert "@article" in artifacts.references_bib


def test_extract_with_self_healing_invokes_progress_callback():
    """Verify that progress_callback is called with correct states."""
    from core.pipeline import extract_with_self_healing
    from tests.test_pipeline_extraction import PAGE_TEXT, StatefulMockExtractor

    events: list[tuple] = []
    def callback(idx: int, total: int, state: str, detail: str) -> None:
        events.append((idx, total, state, detail))

    extractor = StatefulMockExtractor()  # first call fails, second succeeds
    rows, warnings = extract_with_self_healing(
        merged_context=PAGE_TEXT,
        page_text_by_number={1: PAGE_TEXT},
        topic="test",
        domain_fields=["sensor"],
        extraction_fn=extractor,
        progress_callback=callback,
        max_retries=3,
    )

    # Must have at least one 'extracting' event
    states = [e[2] for e in events]
    assert "extracting" in states
    # Must have 'completed' as the last state
    assert events[-1][2] == "completed"


def test_generate_artifacts_accepts_optional_callback():
    """Callback parameter is accepted but no-op for template-based generation."""
    from core.pipeline import generate_artifacts
    from core.models import AcademicMatrixRow

    called = False
    def callback(idx, total, state, detail):
        nonlocal called
        called = True

    row = AcademicMatrixRow(
        title="A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    artifacts = generate_artifacts("topic", [row], [], progress_callback=callback)
    assert artifacts is not None
    assert called  # Verify callback was actually invoked


def test_generate_llm_artifacts_falls_back_to_template_on_empty_synthesis():
    """When LLM synthesis returns empty, fall back to template-based generation."""
    from core.pipeline import generate_llm_artifacts

    class EmptyExtractor:
        def __call__(self, prompt: str) -> str:
            return ""

    row = AcademicMatrixRow(
        title="A", authors="B", year="2024", venue="C",
        research_problem="P", method="M", innovation="I", limitation="L",
        evidence_page=1, evidence_quote="Q", confidence=0.5, trigger_reason="R",
    )
    artifacts = generate_llm_artifacts(
        "topic", [row], extraction_fn=EmptyExtractor(), blocked_warnings=[]
    )
    # Must fall back to template-based rendering
    assert r"\documentclass{ctexart}" in artifacts.survey_tex
    assert "Paper A" not in artifacts.survey_tex  # template uses row.title


def test_zero_drop_retains_all_three_papers():
    """3 papers in, 3 rows out — Paper C degraded to missing (unverified).

    This tests the full zero-drop guarantee: no paper is silently dropped
    even when evidence validation fails on all retries.
    """
    from core.pipeline import extract_with_self_healing

    class ThreePaperExtractor:
        """Simulates 3 papers: A passes, B passes after 1 retry, C fails all retries."""
        def __init__(self):
            self.call_count = 0
            # First call: return all 3 as valid JSON
            self.first_response = (
                '[\n'
                '  {"title": "Paper A", "authors": "Alice", "year": "2024", '
                '"venue": "C", "research_problem": "P1", "method": "M1", '
                '"innovation": "I1", "limitation": "L1", "evidence_page": 1, '
                '"evidence_quote": "valid quote A", "confidence": 0.8, '
                '"trigger_reason": "stated", "domain_fields": {"metric": "acc"}},\n'
                '  {"title": "Paper B", "authors": "Bob", "year": "2023", '
                '"venue": "D", "research_problem": "P2", "method": "M2", '
                '"innovation": "I2", "limitation": "L2", "evidence_page": 2, '
                '"evidence_quote": "valid quote B", "confidence": 0.7, '
                '"trigger_reason": "stated", "domain_fields": {"metric": "f1"}},\n'
                '  {"title": "Paper C", "authors": "Carol", "year": "2022", '
                '"venue": "E", "research_problem": "P3", "method": "M3", '
                '"innovation": "I3", "limitation": "L3", "evidence_page": 3, '
                '"evidence_quote": "hallucinated quote C", "confidence": 0.6, '
                '"trigger_reason": "stated", "domain_fields": {"metric": "auc"}}\n'
                ']'
            )
            # Subsequent calls: same but fix Paper B's quote
            self.fix_response = (
                '[\n'
                '  {"title": "Paper A", "authors": "Alice", "year": "2024", '
                '"venue": "C", "research_problem": "P1", "method": "M1", '
                '"innovation": "I1", "limitation": "L1", "evidence_page": 1, '
                '"evidence_quote": "valid quote A", "confidence": 0.8, '
                '"trigger_reason": "stated", "domain_fields": {"metric": "acc"}},\n'
                '  {"title": "Paper B", "authors": "Bob", "year": "2023", '
                '"venue": "D", "research_problem": "P2", "method": "M2", '
                '"innovation": "I2", "limitation": "L2", "evidence_page": 2, '
                '"evidence_quote": "valid quote B", "confidence": 0.7, '
                '"trigger_reason": "stated", "domain_fields": {"metric": "f1"}},\n'
                '  {"title": "Paper C", "authors": "Carol", "year": "2022", '
                '"venue": "E", "research_problem": "P3", "method": "M3", '
                '"innovation": "I3", "limitation": "L3", "evidence_page": 3, '
                '"evidence_quote": "hallucinated quote C", "confidence": 0.6, '
                '"trigger_reason": "stated", "domain_fields": {"metric": "auc"}}\n'
                ']'
            )

        def __call__(self, prompt: str) -> str:
            self.call_count += 1
            if self.call_count == 1:
                return self.first_response
            return self.fix_response

    page_text = {
        1: "valid quote A is present in this text",
        2: "valid quote B is present in this text",
        3: "no matching text here at all",
    }

    extractor = ThreePaperExtractor()
    rows, warnings = extract_with_self_healing(
        merged_context="sample context",
        page_text_by_number=page_text,
        topic="test topic",
        domain_fields=["metric"],
        extraction_fn=extractor,
        max_retries=3,
    )

    assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"
    # Paper A should be accepted with full data
    paper_a = [r for r in rows if r.title == "Paper A"]
    assert len(paper_a) == 1
    assert paper_a[0].limitation == "L1"
    assert paper_a[0].evidence_quote == "valid quote A"
    # Paper B should be accepted with full data
    paper_b = [r for r in rows if r.title == "Paper B"]
    assert len(paper_b) == 1
    assert paper_b[0].limitation == "L2"
    assert paper_b[0].evidence_quote == "valid quote B"
    # Paper C should be degraded
    paper_c = [r for r in rows if r.title == "Paper C"]
    assert len(paper_c) == 1
    assert paper_c[0].limitation == "missing (unverified)"
    assert paper_c[0].evidence_quote == "unverified"
