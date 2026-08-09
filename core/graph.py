"""Build and render 2D interactive knowledge graphs from vault data.

Visualises paper-author-venue-year relationships as a PyVis interactive HTML graph.
"""

import os


def _extract_entities(paper: dict) -> dict:
    """Extract entity nodes (authors, year, venue) from a paper metadata dict.

    Parameters
    ----------
    paper : dict
        A paper dict with keys ``authors``, ``year``, ``venue``.

    Returns
    -------
    dict
        Dictionary with keys ``authors`` (list of str), ``year`` (str),
        ``venue`` (str).  Missing keys default to empty list / ``"unknown"``.
    """
    return {
        "authors": list(paper.get("authors", [])),
        "year": str(paper.get("year", "unknown")),
        "venue": paper.get("venue", "unknown"),
    }


def build_knowledge_graph(vault_data: list[dict]) -> "Network":
    """Build a pyvis Network graph from vault data.

    Nodes represent papers, authors, venues, and years.
    Edges connect papers to their authors, venue, and year.

    Parameters
    ----------
    vault_data : list[dict]
        List of paper metadata dicts (as produced by ``fetch_vault``).

    Returns
    -------
    pyvis.network.Network
        Populated graph with colour-coded, sized nodes.
    """
    from pyvis.network import Network

    graph = Network(height="600px", width="100%", directed=False, notebook=False)

    graph.set_options("""
    var options = {
      "physics": {
        "enabled": true,
        "barnesHut": {
          "gravitationalConstant": -3000,
          "centralGravity": 0.3,
          "springLength": 200,
          "springConstant": 0.04,
          "damping": 0.09
        }
      }
    }
    """)

    added_nodes: set[tuple[str, str]] = set()
    node_id_by_key: dict[tuple[str, str], int] = {}
    next_id = 0

    def _add_node(label: str, group: str, title: str = "", size: int = 10) -> int:
        """Add a node if not already present; return its id."""
        nonlocal next_id
        key = (label, group)
        if key in added_nodes:
            return node_id_by_key[key]
        nid = next_id
        next_id += 1
        added_nodes.add(key)
        node_id_by_key[key] = nid

        color_map = {
            "paper": "#97c2fc",
            "author": "#fc9797",
            "venue": "#97fcb8",
            "year": "#fcf897",
        }
        color = color_map.get(group, "#d3d3d3")
        graph.add_node(nid, label=label, title=title, color=color, size=size, group=group)
        return nid

    for paper in vault_data:
        entities = _extract_entities(paper)
        title = paper.get("title", paper.get("id", "unknown"))
        paper_id = _add_node(title, "paper", title=title, size=15)

        # Author nodes + edges
        for author in entities["authors"]:
            author_id = _add_node(author, "author", title=f"Author: {author}", size=10)
            graph.add_edge(paper_id, author_id)

        # Venue node + edge
        venue = entities["venue"]
        venue_id = _add_node(venue, "venue", title=f"Venue: {venue}", size=10)
        graph.add_edge(paper_id, venue_id)

        # Year node + edge
        year = entities["year"]
        year_id = _add_node(year, "year", title=f"Year: {year}", size=10)
        graph.add_edge(paper_id, year_id)

    return graph


# Lazily-created singleton so the st.cache_data instance is stable and its
# ``.clear()`` remains reachable (Streamlit keys caches by function + args, so
# a per-call closure would leak cache slots across calls/tests).
_CACHED_HTML = None


def _get_cached_html_builder(ttl: int = 3600):
    """Return the module-level cached graph-HTML builder (created on first use).

    The expensive Lazy-Load step in the UI is *build + render to HTML*, so we
    cache the rendered HTML string rather than the raw :class:`Network`. A
    Network is structurally hashed by Streamlit in a way that can conflate
    distinct vault inputs (verified: id/title-only differences collide), whereas
    a plain HTML string hashes reliably and is exactly what the UI consumes.
    """
    global _CACHED_HTML
    if _CACHED_HTML is None:
        import streamlit as st

        @st.cache_data(ttl=ttl, show_spinner=False)
        def _cached_html(vault_key: tuple) -> tuple:
            # NOTE: args must NOT start with '_' — Streamlit treats underscore-
            # prefixed params as *unguarded* and excludes them from the cache
            # key, which would collapse all vaults into one cache slot.
            graph = build_knowledge_graph(list(vault_key))
            # In-memory rendering: no file is written, so no container path is
            # ever surfaced (fixes the Streamlit Cloud path-exposure flaw).
            html = render_knowledge_graph_html(graph)
            paper_count = sum(1 for n in graph.nodes if n.get("group") == "paper")
            return html, paper_count

        _CACHED_HTML = _cached_html
    return _CACHED_HTML


def build_knowledge_graph_cached(vault_data: list[dict]) -> tuple[str, int]:
    """Streamlit-cached, in-memory build+render of the knowledge graph.

    Wraps :func:`build_knowledge_graph` + :func:`render_knowledge_graph_html`
    with ``st.cache_data(ttl=3600)`` so repeated calls with identical vault data
    hit the in-memory cache instead of recomputing the network or re-rendering
    the HTML (the expensive Lazy-Load step in the UI). The result is a pure
    in-memory HTML string — no file is written to disk, so no container physical
    path can leak into the UI. Streamlit is imported lazily to keep this module
    importable outside a running Streamlit app (CLI, tests).

    Returns
    -------
    (html, paper_count)
        The rendered graph HTML content and the number of paper/literature
        ("文献/主题") nodes (canonical source for the UI status message).
    """
    return _get_cached_html_builder()(tuple(vault_data))


def clear_graph_cache() -> None:
    """Drop the cached graph HTML so the next call recomputes and re-renders."""
    cached = _get_cached_html_builder()
    cached.clear()


def render_knowledge_graph(graph: "Network", output_dir: str = "data") -> str:
    """Render a pyvis Network to an HTML file and return the absolute path.

    Parameters
    ----------
    graph : pyvis.network.Network
        The graph to render.
    output_dir : str
        Directory to write the HTML file into (created if missing).

    Returns
    -------
    str
        Absolute path to the generated HTML file.
    """
    os.makedirs(output_dir, exist_ok=True)
    html_path = os.path.join(output_dir, "knowledge_graph.html")
    graph.save_graph(html_path)
    return os.path.abspath(html_path)


def render_knowledge_graph_html(graph: "Network") -> str:
    """Render a pyvis Network to an HTML string entirely in memory.

    Uses :meth:`pyvis.network.Network.generate_html` so no file is written and
    no physical container path is produced. This is the Streamlit-safe path: the
    returned string can be embedded directly via ``st.components.v1.html``
    without leaking a ``/mount/src/.../knowledge_graph.html`` path to the UI.

    Parameters
    ----------
    graph : pyvis.network.Network
        The graph to render.

    Returns
    -------
    str
        The full HTML document as a string.
    """
    return graph.generate_html()


def count_paper_nodes(graph: "Network") -> int:
    """Count the paper/literature nodes in a knowledge graph.

    The builder tags paper nodes with ``group="paper"``; this returns how many
    such "文献/主题" nodes are present (used for the friendly status message).

    Parameters
    ----------
    graph : pyvis.network.Network
        The populating graph.

    Returns
    -------
    int
        Number of paper/literature nodes.
    """
    return sum(1 for n in graph.nodes if n.get("group") == "paper")