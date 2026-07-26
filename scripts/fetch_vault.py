# scripts/fetch_vault.py
import json
import os
from typing import Any


def fetch_lab_anomaly_vault(
    arxiv_client: Any | None = None, max_results: int = 100
) -> list[dict]:
    """
    自动从 arXiv 检索并抓取【自动化实验室异常检测与机器人安全】方向的 Top-100 论文元数据与摘要。

    Parameters
    ----------
    arxiv_client : arxiv.Client or None
        Inject an arxiv.Client instance (or a fake for testing).
        When None, a real arxiv.Client is created lazily.
    max_results : int
        Maximum number of results to fetch.

    Returns
    -------
    list[dict]
        Paper metadata entries harvested from ArXiv.
    """
    print(f"🚀 开始从 arXiv 自动收割【自动化实验室/机器人异常检测】前沿文献 (目标: {max_results} 篇)...")

    # 针对您大研场景（RealSense + YOLO + 机械臂 + 异常检测）定制的精确检索式
    query = 'cat:cs.CV AND (abs:"anomaly detection" OR abs:"workspace safety" OR abs:"intrusion detection" OR abs:"robotic arm")'

    import arxiv  # lazy import to avoid top-level dependency in CI

    if arxiv_client is None:
        client = arxiv.Client()
    else:
        client = arxiv_client

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,  # 按相关度排序
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

    out_path = "data/vault_100_lab_anomaly.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(vault_data, f, ensure_ascii=False, indent=2)

    print(
        f"\n🎉 恭喜！100 篇【实验室异常检测】专属文献数据库已自动构建完成！保存于: {out_path}"
    )

    return vault_data


if __name__ == "__main__":
    fetch_lab_anomaly_vault(max_results=100)