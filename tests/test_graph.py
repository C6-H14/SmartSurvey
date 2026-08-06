"""Tests for core/graph.py — 2D interactive knowledge graph builder."""

import os

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_PAPER = {
    "id": "2301.12345",
    "title": "Test Paper on Anomaly Detection",
    "authors": ["Alice Wang", "Bob Li"],
    "year": "2024",
    "venue": "arXiv preprint",
    "abstract": "This is a test abstract.",
}


def _make_paper(
    paper_id: str = "2301.12345",
    title: str = "Test Paper",
    authors: list[str] | None = None,
    year: str = "2024",
    venue: str = "arXiv preprint",
) -> dict:
    if authors is None:
        authors = ["Alice Wang", "Bob Li"]
    return {
        "id": paper_id,
        "title": title,
        "authors": list(authors),
        "year": year,
        "venue": venue,
        "abstract": "A test abstract.",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_extract_entities_from_paper():
    """_extract_entities returns authors list, year, and venue from a paper dict."""
    from core.graph import _extract_entities

    result = _extract_entities(_SAMPLE_PAPER)

    assert "authors" in result
    assert isinstance(result["authors"], list)
    assert "Alice Wang" in result["authors"]
    assert "Bob Li" in result["authors"]
    assert result["year"] == "2024"
    assert result["venue"] == "arXiv preprint"


def test_build_knowledge_graph_returns_network():
    """build_knowledge_graph returns a pyvis Network with nodes and edges."""
    from core.graph import build_knowledge_graph

    vault_data = [
        _make_paper(paper_id="2301.11111", title="Paper A", authors=["Alice Wang", "Bob Li"]),
        _make_paper(paper_id="2301.22222", title="Paper B", authors=["Alice Wang", "Charlie Chen"]),
    ]

    graph = build_knowledge_graph(vault_data)

    assert graph is not None
    assert len(graph.nodes) >= 4
    assert len(graph.edges) >= 3


def test_build_knowledge_graph_handles_single_paper():
    """build_knowledge_graph works with a single paper."""
    from core.graph import build_knowledge_graph

    vault_data = [
        _make_paper(paper_id="2301.33333", title="Single Paper", authors=["Diana Li"]),
    ]

    graph = build_knowledge_graph(vault_data)

    assert graph is not None
    assert len(graph.nodes) >= 3  # paper + author + venue


def test_build_knowledge_graph_empty_vault():
    """build_knowledge_graph handles empty vault data gracefully."""
    from core.graph import build_knowledge_graph

    graph = build_knowledge_graph([])

    assert graph is not None
    assert len(graph.nodes) == 0


def test_render_knowledge_graph_creates_html(tmp_path):
    """render_knowledge_graph saves an HTML file with node labels."""
    from pyvis.network import Network

    from core.graph import render_knowledge_graph

    # Build a minimal graph
    graph = Network(height="600px", width="100%", directed=False, notebook=False)
    graph.add_node(1, label="Paper A", title="Test Paper", color="#97c2fc")
    graph.add_node(2, label="Alice Wang", title="Author", color="#fc9797")
    graph.add_edge(1, 2)

    html_path = render_knowledge_graph(graph, output_dir=str(tmp_path))

    assert os.path.exists(html_path)
    assert os.path.isfile(html_path)
    assert html_path.endswith(".html")

    with open(html_path, encoding="utf-8") as f:
        content = f.read()
    assert "Paper A" in content
    assert "Alice Wang" in content