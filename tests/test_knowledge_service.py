"""Unit tests for knowledge service behavior with mocked KB backend."""

from __future__ import annotations

from pathlib import Path

import pytest

from customer_support_agent.core.settings import get_settings
from customer_support_agent.services import knowledge_service as knowledge_service_module
from customer_support_agent.services.knowledge_service import KnowledgeService


class FakeCollection:
    def __init__(self, count: int) -> None:
        self._count = count

    def count(self) -> int:
        return self._count


class FakeKnowledgeBase:
    def __init__(self, count: int = 0) -> None:
        self._collection = FakeCollection(count)
        self.ingest_calls: list[Path] = []

    def ingest_directory(self, directory: Path) -> int:
        self.ingest_calls.append(directory)
        return 7

    def search(self, query: str, top_k: int | None = None) -> list:
        class Hit:
            def __init__(self) -> None:
                self.content = "Collect photos before settlement."
                self.source = "insurance-auto-claims-fnol-intake-checklist.md"
                self.chunk_index = 0
                self.score = 0.42

        return [Hit()]

    def get_collection_count(self) -> int:
        return self._collection.count()

    def get_indexed_sources(self) -> list[str]:
        return ["insurance-test.md"]


@pytest.fixture
def settings_tmp_kb(tmp_path: Path) -> Path:
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "insurance-test.md").write_text("# Test\n\nknowledge", encoding="utf-8")
    settings = get_settings()
    settings.knowledge_base_path = kb_dir
    return kb_dir


def test_ingest_knowledge_base_returns_counts(
    monkeypatch: pytest.MonkeyPatch,
    settings_tmp_kb: Path,
) -> None:
    fake_kb = FakeKnowledgeBase(count=11)
    monkeypatch.setattr(knowledge_service_module, "get_knowledge_base", lambda: fake_kb)

    service = KnowledgeService()
    result = service.ingest_knowledge_base()

    assert result["status"] == "ingested"
    assert result["chunks_count"] == 7
    assert result["collection_count"] == 11
    assert fake_kb.ingest_calls == [settings_tmp_kb]


def test_query_knowledge_base_shapes_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        knowledge_service_module,
        "get_knowledge_base",
        lambda: FakeKnowledgeBase(count=1),
    )

    service = KnowledgeService()
    result = service.query_knowledge_base("photos", top_k=3)

    assert result["query"] == "photos"
    assert result["hits_count"] == 1
    assert result["hits"][0]["source"] == "insurance-auto-claims-fnol-intake-checklist.md"


def test_get_collection_stats_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        knowledge_service_module,
        "get_knowledge_base",
        lambda: FakeKnowledgeBase(count=5),
    )

    service = KnowledgeService()
    result = service.get_collection_stats()

    assert result == {
        "collection_count": 5,
        "status": "ready",
        "indexed_sources": ["insurance-test.md"],
    }


def test_get_collection_stats_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        knowledge_service_module,
        "get_knowledge_base",
        lambda: FakeKnowledgeBase(count=0),
    )

    service = KnowledgeService()
    result = service.get_collection_stats()

    assert result == {
        "collection_count": 0,
        "status": "empty",
        "indexed_sources": ["insurance-test.md"],
    }
