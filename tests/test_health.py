"""Tests for the lightweight health endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from customer_support_agent.api.app_factory import create_app
from customer_support_agent.core.settings import get_settings


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = get_settings()
    settings.app_env = "test"
    settings.sqlite_db_path = tmp_path / "test_health.db"
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["environment"] == "test"
    assert data["llm_provider"] == "openai"
    assert data["embedding_provider"] == "openai"


def test_health_is_dependency_free_shape(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert set(response.json().keys()) == {
        "status",
        "app_name",
        "environment",
        "llm_provider",
        "embedding_provider",
    }
