from core.models import AcademicMatrixRow, PageSlice, ParsedPaper
from core.pipeline import filter_rows_by_evidence, generate_artifacts


def test_filter_rows_by_evidence_blocks_uncontained_quote():
    paper = ParsedPaper(
        file_name="paper.pdf",
        pages=[PageSlice(page_number=1, text="This page supports a real limitation.")],
    )
    rows = [
        AcademicMatrixRow(
            title="Paper A",
            authors="missing",
            year="2024",
            venue="missing",
            research_problem="missing",
            method="missing",
            innovation="missing",
            limitation="fake",
            evidence_page=1,
            evidence_quote="Not present.",
            confidence=0.5,
            trigger_reason="missing",
        )
    ]

    accepted, blocked = filter_rows_by_evidence(rows, [paper])

    assert accepted == []
    assert blocked == ["发现无事实根据的空气警告，已自动拦截"]


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
