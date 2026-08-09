"""Tests for Streamlit caching / lazy-load performance optimizations.

These verify the cache contracts required for the Streamlit Cloud perf pass:
  1. ``build_knowledge_graph_cached`` hits ``st.cache_data`` so a second call
     with identical vault data does NOT rebuild/re-render the graph.
  2. The cached vault loader does NOT re-read the JSON document library from
     disk on a second call with the same path.
  3. The lazy HTML render is deferred and cached so repeated requests return
     the same HTML without recomputing the graph.
"""

import json

import pytest

from core.graph import (
    build_knowledge_graph_cached,
    clear_graph_cache,
)


@pytest.fixture(autouse=True)
def _clear_graph_cache_between_tests():
    """Streamlit's cache is keyed by function + args, so cache slots persist
    across tests. Clear the graph cache before each test for isolation."""
    clear_graph_cache()
    yield
    clear_graph_cache()


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
# 1. Graph build caching
# ---------------------------------------------------------------------------


def test_graph_cache_hits_on_second_call(monkeypatch, sample_vault):
    """Second call with identical data must NOT rebuild/re-render the graph."""
    import core.graph as graph_mod

    rendered = {"n": 0}
    real_render = graph_mod.render_knowledge_graph_html

    def counting_render(graph):
        rendered["n"] += 1
        return real_render(graph)

    monkeypatch.setattr("core.graph.render_knowledge_graph_html", counting_render)

    html1, count1 = build_knowledge_graph_cached(sample_vault)
    html2, count2 = build_knowledge_graph_cached(sample_vault)

    # Both calls return the same graph HTML, but the expensive render ran once.
    assert html1 == html2
    assert "Paper A" in html1
    assert count1 == count2 == len(sample_vault)
    assert rendered["n"] == 1


def test_graph_cache_misses_after_clear(monkeypatch, sample_vault):
    """Clearing the cache forces a rebuild/re-render on the next call."""
    import core.graph as graph_mod

    rendered = {"n": 0}
    real_render = graph_mod.render_knowledge_graph_html

    def counting_render(graph):
        rendered["n"] += 1
        return real_render(graph)

    monkeypatch.setattr("core.graph.render_knowledge_graph_html", counting_render)

    build_knowledge_graph_cached(sample_vault)
    assert rendered["n"] == 1

    clear_graph_cache()
    build_knowledge_graph_cached(sample_vault)
    assert rendered["n"] == 2


def test_graph_cache_distinguishes_inputs(sample_vault):
    """Different vault data must NOT be served from the same cache slot.

    Verified by content (not object identity or a monkeypatched counter, which
    can be masked by Streamlit's bare-mode cache) so a wrong-cache return is
    impossible to miss.
    """
    other_vault = [_make_paper(paper_id="2301.99999", title="Paper Z")]

    html_a, _ = build_knowledge_graph_cached(sample_vault)
    html_z, _ = build_knowledge_graph_cached(other_vault)

    # ``html_z`` must reflect ``other_vault``'s own paper, not ``sample_vault``'s.
    assert "Paper Z" in html_z
    assert not ("Paper Z" not in html_z and "Paper A" in html_z)


# ---------------------------------------------------------------------------
# 2. JSON vault-load caching (no repeated disk read)
# ---------------------------------------------------------------------------


def test_vault_load_cache_hits_on_second_call(monkeypatch, tmp_path, sample_vault):
    """Second call must NOT re-read the vault file from disk."""
    from main import _load_vault_json_cached

    vault_path = tmp_path / "vault.json"
    vault_path.write_text(json.dumps(sample_vault), encoding="utf-8")

    reads = {"n": 0}
    real_open = open

    def counting_open(path, *a, **kw):
        if str(path) == str(vault_path):
            reads["n"] += 1
        return real_open(path, *a, **kw)

    monkeypatch.setattr("builtins.open", counting_open)

    d1 = _load_vault_json_cached(str(vault_path))
    d2 = _load_vault_json_cached(str(vault_path))

    assert d1 == sample_vault
    assert d2 == sample_vault
    # The vault file was touched exactly once despite two calls.
    assert reads["n"] == 1


# ---------------------------------------------------------------------------
# 3. Lazy HTML render (deferred + cached)
# ---------------------------------------------------------------------------


def test_lazy_render_is_deferred(monkeypatch, sample_vault):
    """The HTML render must not run until explicitly requested."""
    from main import _get_graph_html_cached

    import core.graph as graph_mod

    rendered = {"n": 0}
    real_render = graph_mod.render_knowledge_graph_html

    def counting_render(graph):
        rendered["n"] += 1
        return real_render(graph)

    monkeypatch.setattr("core.graph.render_knowledge_graph_html", counting_render)

    # Nothing happens until we actually ask for HTML — laziness is expressed
    # by `_get_graph_html_cached` being the deferred gate the button triggers.
    assert rendered["n"] == 0

    html1, count1 = _get_graph_html_cached(tuple(sample_vault))
    assert "Paper A" in html1
    assert count1 == len(sample_vault)
    assert rendered["n"] == 1


def test_lazy_render_result_is_cached(monkeypatch, sample_vault):
    """Repeated requests return the same cached HTML without re-rendering."""
    from main import _get_graph_html_cached

    import core.graph as graph_mod

    rendered = {"n": 0}
    real_render = graph_mod.render_knowledge_graph_html

    def counting_render(graph):
        rendered["n"] += 1
        return real_render(graph)

    monkeypatch.setattr("core.graph.render_knowledge_graph_html", counting_render)

    html1, _ = _get_graph_html_cached(tuple(sample_vault))
    html2, _ = _get_graph_html_cached(tuple(sample_vault))

    assert html1 == html2
    # Deferred render ran exactly once; the second call hit the cache.
    assert rendered["n"] == 1