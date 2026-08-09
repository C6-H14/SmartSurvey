"""Tests for the knowledge-graph frontend fixes (Streamlit Cloud).

Covers two observed cloud defects:
  1. Path exposure — the UI must NOT leak the container physical path
     (``/mount/src/...``) of the rendered HTML. Rendering must be in-memory
     (no disk artifact surfaced), and the status message must be a friendly
     academic line with a node count and no filesystem path.
  2. Height truncation — the PyVis iframe must render at a taller height so
     bottom nodes are not squeezed.
"""

import pytest

from core.graph import build_knowledge_graph, render_knowledge_graph_html


def _make_paper(paper_id: str = "2301.12345", title: str = "Paper A") -> dict:
    return {
        "id": paper_id,
        "title": title,
        "authors": ["Alice Wang", "Bob Li"],
        "year": "2024",
        "venue": "arXiv preprint",
        "abstract": "A test abstract.",
    }


@pytest.fixture
def sample_vault() -> list[dict]:
    return [
        _make_paper(paper_id="2301.11111", title="Paper A"),
        _make_paper(paper_id="2301.22222", title="Paper B"),
    ]


# ---------------------------------------------------------------------------
# 1. In-memory string rendering (no physical path surfaced)
# ---------------------------------------------------------------------------


def test_render_knowledge_graph_html_in_memory(sample_vault):
    """render_knowledge_graph_html returns an HTML string with node labels,
    WITHOUT writing any file or returning a filesystem path."""
    graph = build_knowledge_graph(sample_vault)

    html = render_knowledge_graph_html(graph)

    assert isinstance(html, str)
    assert len(html) > 0
    # Node labels are embedded in the in-memory HTML.
    assert "Paper A" in html
    assert "Alice Wang" in html
    # The result is content, not a path — it must not point at a file/dir.
    assert "<html" in html


def test_in_memory_render_leaks_no_disk_path(sample_vault, tmp_path, monkeypatch):
    """In-memory rendering must not force a write to a container path, i.e. it
    works without the rendered file existing on disk in the project data dir."""
    graph = build_knowledge_graph(sample_vault)

    # Render in-memory; the legacy disk artifact must not be required.
    html = render_knowledge_graph_html(graph)

    # The in-memory string must not contain a raw filesystem path to an html file.
    assert "/mount/src" not in html
    assert not any(
        token in html.lower() for token in ["knowledge_graph.html", "drive/app"]
    )


# ---------------------------------------------------------------------------
# 2. Friendly status message (no path leak + node count)
# ---------------------------------------------------------------------------


def test_status_message_is_friendly_and_has_no_path():
    """The success message is academic and friendly, shows the node count, and
    leaks no filesystem path."""
    from main import _knowledge_graph_status_message

    msg = _knowledge_graph_status_message(24)

    assert msg.startswith("✅ 知识图谱已就绪")
    assert "24" in msg
    assert "文献" in msg or "节点" in msg
    # No internal container path may be surfaced in the UI message.
    assert "/mount/" not in msg
    assert ".html" not in msg
    assert "data/knowledge" not in msg


def test_status_message_counts_paper_nodes(sample_vault):
    """The node count reported equals the number of paper/literature nodes."""
    from core.graph import count_paper_nodes

    from main import _knowledge_graph_status_message

    graph = build_knowledge_graph(sample_vault)
    n = count_paper_nodes(graph)

    assert n == len(sample_vault)
    assert str(n) in _knowledge_graph_status_message(n)


# ---------------------------------------------------------------------------
# 3. Iframe height constant (bottom nodes not squeezed)
# ---------------------------------------------------------------------------


def test_components_height_meets_minimum():
    """The embedded PyVis iframe height must be at least 750px to avoid
    squeezing the bottom nodes into a line."""
    from main import GRAPH_COMPONENT_HEIGHT

    assert GRAPH_COMPONENT_HEIGHT >= 750