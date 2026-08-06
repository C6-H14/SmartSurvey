# scripts/fetch_vault.py
import argparse
import json
import os
import re
from typing import Any


def _sanitize_topic(topic: str) -> str:
    """Convert a topic string into a safe filesystem fragment."""
    slug = re.sub(r"[^a-zA-Z0-9_\- ]", "", topic)
    slug = slug.strip().replace(" ", "_")
    return slug[:60]


def _build_query(topic: str) -> str:
    """
    Build an arXiv query string from a free-form topic.

    Splits the topic into keywords and constructs a boolean OR query
    on the abstract field, scoped to cs (Computer Science) category.
    """
    keywords = [kw.strip() for kw in re.split(r"[,;]+", topic) if kw.strip()]
    if not keywords:
        keywords = ["anomaly detection"]

    parts = " OR ".join(f'abs:"{kw}"' for kw in keywords)
    return f"cat:cs.CV AND ({parts})"


def fetch_lab_anomaly_vault(
    arxiv_client: Any | None = None,
    max_results: int = 100,
    topic: str = "3D anomaly detection",
) -> list[dict]:
    """
    自动从 arXiv 检索并抓取指定学术主题的论文元数据与摘要。

    Parameters
    ----------
    arxiv_client : arxiv.Client or None
        Inject an arxiv.Client instance (or a fake for testing).
        When None, a real arxiv.Client is created lazily.
    max_results : int
        Maximum number of results to fetch.
    topic : str
        Research topic to search for. Supports comma/semicolon-separated keywords.

    Returns
    -------
    list[dict]
        Paper metadata entries harvested from ArXiv.
    """
    topic_slug = _sanitize_topic(topic)
    print(f"🚀 开始从 arXiv 自动收割文献 (主题: {topic}, 目标: {max_results} 篇)...")

    query = _build_query(topic)

    import arxiv  # lazy import to avoid top-level dependency in CI

    if arxiv_client is None:
        client = arxiv.Client()
    else:
        client = arxiv_client

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    vault_data = []
    os.makedirs("data", exist_ok=True)

    results = list(client.results(search))
    for idx, result in enumerate(results):
        paper_info = {
            "id": result.entry_id.split("/")[-1],
            "title": result.title.replace("\n", " ").strip(),
            "authors": [author.name for author in result.authors],
            "year": str(result.published.year),
            "venue": result.journal_ref or "arXiv preprint",
            "abstract": result.summary.replace("\n", " ").strip(),
            "pdf_url": result.pdf_url,
        }
        vault_data.append(paper_info)
        print(
            f"  [{idx+1}/{len(results)}] 成功收割: {paper_info['title'][:55]}... ({paper_info['year']})"
        )

    out_path = f"data/vault_{topic_slug}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(vault_data, f, ensure_ascii=False, indent=2)

    print(
        f"\n🎉 恭喜！{len(vault_data)} 篇【{topic}】专属文献数据库已自动构建完成！保存于: {out_path}"
    )

    return vault_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="从 arXiv 自动收割指定学术主题的文献元数据与摘要"
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="3D anomaly detection",
        help='研究主题关键词，支持逗号/分号分隔多个关键词 (默认: "3D anomaly detection")',
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="最大收割论文数量 (默认: 100)",
    )
    args = parser.parse_args()

    fetch_lab_anomaly_vault(max_results=args.limit, topic=args.topic)