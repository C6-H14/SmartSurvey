"""Tests for BibTeX author field hardening in parse_matrix_json.

Covers three author input formats:
- Python list literal (e.g. ['Paul Bergmann', 'Kilian Batzner'])
- Comma-separated string (e.g. "Paul Bergmann, Kilian Batzner")
- Already standard BibTeX "and" format (e.g. "Paul Bergmann and Kilian Batzner")
"""

from core.extractor import parse_matrix_json


SAMPLE_DOMAIN = ["sensor"]

# --- Test A: Python list literal ---

def test_parse_authors_python_list_literal():
    """When authors is a Python list literal like ['A', 'B'], normalize to 'A and B'."""
    raw = (
        '[{"title":"Paper A","authors":["Paul Bergmann","Kilian Batzner"],'
        '"year":"2024","venue":"ICRA","research_problem":"detection",'
        '"method":"vision","innovation":"new","limitation":"lighting",'
        '"evidence_page":1,"evidence_quote":"Quote.","confidence":0.7,'
        '"trigger_reason":"stated"}]'
    )
    rows = parse_matrix_json(raw, SAMPLE_DOMAIN)

    assert rows[0].authors == "Paul Bergmann and Kilian Batzner"


# --- Test B: Comma-separated string ---

def test_parse_authors_comma_separated_string():
    """When authors is a comma-separated string, normalize to 'and' format."""
    raw = (
        '[{"title":"Paper A","authors":"Paul Bergmann, Kilian Batzner",'
        '"year":"2024","venue":"ICRA","research_problem":"detection",'
        '"method":"vision","innovation":"new","limitation":"lighting",'
        '"evidence_page":1,"evidence_quote":"Quote.","confidence":0.7,'
        '"trigger_reason":"stated"}]'
    )
    rows = parse_matrix_json(raw, SAMPLE_DOMAIN)

    assert rows[0].authors == "Paul Bergmann and Kilian Batzner"


# --- Test C: Already standard ---

def test_parse_authors_already_standard():
    """When authors is already in standard 'and' format, keep unchanged."""
    raw = (
        '[{"title":"Paper A","authors":"Paul Bergmann and Kilian Batzner",'
        '"year":"2024","venue":"ICRA","research_problem":"detection",'
        '"method":"vision","innovation":"new","limitation":"lighting",'
        '"evidence_page":1,"evidence_quote":"Quote.","confidence":0.7,'
        '"trigger_reason":"stated"}]'
    )
    rows = parse_matrix_json(raw, SAMPLE_DOMAIN)

    assert rows[0].authors == "Paul Bergmann and Kilian Batzner"


# --- Test D: Single author (no delimiter) ---

def test_parse_authors_single_author():
    """A single author name should pass through unchanged."""
    raw = (
        '[{"title":"Paper A","authors":"Paul Bergmann",'
        '"year":"2024","venue":"ICRA","research_problem":"detection",'
        '"method":"vision","innovation":"new","limitation":"lighting",'
        '"evidence_page":1,"evidence_quote":"Quote.","confidence":0.7,'
        '"trigger_reason":"stated"}]'
    )
    rows = parse_matrix_json(raw, SAMPLE_DOMAIN)

    assert rows[0].authors == "Paul Bergmann"


# --- Test E: Missing authors ---

def test_parse_authors_missing():
    """When authors is missing, it should remain 'missing'."""
    raw = (
        '[{"title":"Paper A","year":"2024","venue":"ICRA",'
        '"research_problem":"detection","method":"vision",'
        '"innovation":"new","limitation":"lighting",'
        '"evidence_page":1,"evidence_quote":"Quote.","confidence":0.7,'
        '"trigger_reason":"stated"}]'
    )
    rows = parse_matrix_json(raw, SAMPLE_DOMAIN)

    assert rows[0].authors == "missing"