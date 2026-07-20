"""Tests for runtime logging inspection and update endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from customer_support_agent.api.app_factory import create_app
from customer_support_agent.core.logging_config import get_log_level, set_log_level
from customer_support_agent.core.settings import get_settings


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = get_settings()
    settings.app_env = "test"
    settings.sqlite_db_path = tmp_path / "test_logging.db"
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_get_logging_level(client: TestClient) -> None:
    response = client.get("/logging/level")

    assert response.status_code == 200
    assert response.json()["level"] == get_log_level()


def test_update_logging_level(client: TestClient) -> None:
    original = get_log_level()
    try:
        response = client.put("/logging/level", json={"level": "DEBUG"})
        assert response.status_code == 200
        assert response.json()["level"] == "DEBUG"
        assert get_log_level() == "DEBUG"
    finally:
        set_log_level(original)
