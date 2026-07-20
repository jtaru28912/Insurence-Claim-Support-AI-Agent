"""Focused tests for newly completed Phase 3 dashboard support endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from customer_support_agent.api.app_factory import create_app
from customer_support_agent.core.settings import get_settings


class FakeKnowledgeService:
    def get_collection_stats(self) -> dict:
        return {"collection_count": 5, "status": "ready"}

    def ingest_knowledge_base(self) -> dict:
        return {"status": "ingested", "chunks_count": 12, "collection_count": 5}

    def query_knowledge_base(self, query: str, top_k: int | None = None) -> dict:
        return {
            "query": query,
            "hits_count": 1,
            "hits": [
                {
                    "content": "Collect deductible details before settlement.",
                    "source": "insurance-auto-coverage-and-deductible-guidelines.md",
                    "chunk_index": 0,
                    "score": 0.88,
                }
            ],
        }


class FakeMemoryService:
    def probe_memories(
        self,
        *,
        customer_email: str,
        company_name: str,
        query: str,
        limit: int | None = None,
    ) -> dict:
        return {
            "customer_email": customer_email,
            "company_name": company_name,
            "query": query,
            "semantic_search_used": True,
            "hits_count": 1,
            "hits": [
                {
                    "memory_id": "mem-1",
                    "content": "Prior approved rear-end collision resolution.",
                    "scope": "customer",
                    "score": 0.92,
                    "metadata": {"draft_id": "draft-1"},
                }
            ],
            "error": None,
        }

    def get_backend_status(self) -> dict:
        return {
            "status": "ready",
            "backend": "langgraph_in_memory_store",
            "semantic_search_enabled": True,
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "memory_top_k": 5,
        }


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = get_settings()
    settings.app_env = "test"
    settings.sqlite_db_path = tmp_path / "test_phase3.db"

    from customer_support_agent.api.routers import knowledge_router, memory_router

    app = create_app()
    app.dependency_overrides[knowledge_router.get_knowledge_service] = (
        lambda: FakeKnowledgeService()
    )
    app.dependency_overrides[memory_router.get_memory_service] = (
        lambda: FakeMemoryService()
    )
    with TestClient(app) as test_client:
        yield test_client


def test_dashboard_stats_endpoint(client: TestClient) -> None:
    response = client.get("/dashboard/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["total_customers"] == 0
    assert data["total_claims"] == 0
    assert data["open_claims"] == 0


def test_knowledge_stats_endpoint(client: TestClient) -> None:
    response = client.get("/knowledge/stats")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_knowledge_query_endpoint(client: TestClient) -> None:
    response = client.post("/knowledge/query", json={"query": "deductible", "top_k": 3})

    assert response.status_code == 200
    assert response.json()["hits_count"] == 1


def test_memory_probe_endpoint(client: TestClient) -> None:
    response = client.get(
        "/memory/probe",
        params={
            "customer_email": "jane@example.com",
            "company_name": "Acme Insurance Co",
            "query": "rear-end collision",
            "limit": 3,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["hits_count"] == 1
    assert data["semantic_search_used"] is True


def test_memory_status_endpoint(client: TestClient) -> None:
    response = client.get("/memory/status")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["semantic_search_enabled"] is True
