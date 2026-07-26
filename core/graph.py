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
    node_counter = [0]

    def _add_node(label: str, group: str, title: str = "", size: int = 10) -> int:
        """Add a node if not already present; return its id."""
        key = (label, group)
        if key in added_nodes:
            # Find the existing node id
            for node in graph.nodes:
                if node.get("label") == label:
                    return node["id"]
            # Fallback: create a new one (shouldn't happen)
        nid = node_counter[0]
        node_counter[0] += 1
        added_nodes.add(key)

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