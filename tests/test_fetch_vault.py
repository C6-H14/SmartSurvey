"""Tests for scripts/fetch_vault.py — ArXiv harvest with DI."""

import json
import os
from collections import namedtuple
from datetime import datetime

import pytest

# ---------------------------------------------------------------------------
# Fake ArXiv client — no network calls
# ---------------------------------------------------------------------------

FakeArxivResult = namedtuple(
    "FakeArxivResult",
    ["entry_id", "title", "authors", "published", "journal_ref", "summary", "pdf_url"],
)


class FakeArxivClient:
    """Simulates arxiv.Client without touching the network."""

    def __init__(self, results: list[FakeArxivResult]):
        self._results = results

    def results(self, search):
        """Return the pre-configured fake results, ignoring the search object."""
        return iter(self._results)


def _make_result(
    entry_id: str = "http://arxiv.org/abs/2301.12345v1",
    title: str = "Fake Paper Title",
    authors: list | None = None,
    year: int = 2023,
    journal_ref: str | None = None,
    abstract: str = "This is a fake abstract.",
    pdf_url: str = "http://arxiv.org/pdf/2301.12345v1",
) -> FakeArxivResult:
    if authors is None:
        authors = [type("Author", (), {"name": "Doe, John"})()]
    return FakeArxivResult(
        entry_id=entry_id,
        title=title,
        authors=authors,
        published=datetime(year, 1, 1),
        journal_ref=journal_ref,
        summary=abstract,
        pdf_url=pdf_url,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fetch_vault_returns_list_of_dicts(monkeypatch, tmp_path):
    """Call with fake client → returns list[dict] with correct metadata."""
    from scripts.fetch_vault import fetch_lab_anomaly_vault

    fake_results = [
        _make_result(
            entry_id="http://arxiv.org/abs/2301.11111v1",
            title="Anomaly Detection in Lab Environments",
            year=2023,
            pdf_url="http://arxiv.org/pdf/2301.11111v1",
        ),
        _make_result(
            entry_id="http://arxiv.org/abs/2302.22222v1",
            title="Robotic Arm Safety via Vision",
            year=2024,
            pdf_url="http://arxiv.org/pdf/2302.22222v1",
        ),
    ]
    fake_client = FakeArxivClient(fake_results)

    monkeypatch.chdir(tmp_path)
    result = fetch_lab_anomaly_vault(arxiv_client=fake_client, max_results=10)

    assert isinstance(result, list)
    assert len(result) == 2

    assert result[0]["title"] == "Anomaly Detection in Lab Environments"
    assert result[0]["year"] == "2023"
    assert result[0]["pdf_url"] == "http://arxiv.org/pdf/2301.11111v1"
    assert isinstance(result[0]["authors"], list)
    assert len(result[0]["authors"]) == 1

    assert result[1]["title"] == "Robotic Arm Safety via Vision"
    assert result[1]["year"] == "2024"


def test_fetch_vault_saves_json_file(monkeypatch, tmp_path):
    """Call with fake client → JSON file is written to data/."""
    from scripts.fetch_vault import fetch_lab_anomaly_vault

    fake_results = [
        _make_result(
            entry_id="http://arxiv.org/abs/2301.33333v1",
            title="Workspace Intrusion Detection",
            year=2025,
        ),
    ]
    fake_client = FakeArxivClient(fake_results)

    monkeypatch.chdir(tmp_path)
    result = fetch_lab_anomaly_vault(arxiv_client=fake_client, max_results=10)

    # The file is written to data/vault_100_lab_anomaly.json relative to cwd
    file_path = tmp_path / "data" / "vault_100_lab_anomaly.json"
    assert file_path.exists()

    with open(file_path, encoding="utf-8") as f:
        saved = json.load(f)

    assert isinstance(saved, list)
    assert len(saved) == 1
    assert saved[0]["title"] == "Workspace Intrusion Detection"
    assert saved[0]["year"] == "2025"
    # The returned list and the saved list should match
    assert saved == result


def test_fetch_vault_empty_results(monkeypatch, tmp_path):
    """Call with empty fake client → returns empty list, writes empty JSON."""
    from scripts.fetch_vault import fetch_lab_anomaly_vault

    fake_client = FakeArxivClient([])

    monkeypatch.chdir(tmp_path)
    result = fetch_lab_anomaly_vault(arxiv_client=fake_client, max_results=10)

    assert isinstance(result, list)
    assert len(result) == 0

    file_path = tmp_path / "data" / "vault_100_lab_anomaly.json"
    assert file_path.exists()

    with open(file_path, encoding="utf-8") as f:
        saved = json.load(f)
    assert saved == []