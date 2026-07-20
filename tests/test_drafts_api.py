"""API tests for draft generation, approval, and discard workflows."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from customer_support_agent.api.app_factory import create_app
from customer_support_agent.core.settings import get_settings
from customer_support_agent.services import copilot_service, draft_service


class FakeCopilotService:
    """Deterministic copilot stub so API tests never require real API keys."""

    def generate_draft(self, request):
        return SimpleNamespace(
            draft_text=(
                f"Draft for {request.customer_email}: collect photos, verify the deductible, "
                "and confirm the repair estimate before settlement."
            ),
            context_used={
                "memory_hits": [],
                "knowledge_hits": [],
                "tool_calls": [],
                "errors": [],
                "signals": {"memory_enabled": True},
            },
        )


class FakeMemoryStore:
    """Memory stub used to verify approval flow without real LangMem writes."""

    def write_resolution_memory(self, **_: object) -> dict[str, str]:
        return {
            "customer_memory_id": "mem-customer-1",
            "company_memory_id": "mem-company-1",
        }


@pytest.fixture(autouse=True)
def mock_draft_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace external AI dependencies with deterministic test doubles."""
    monkeypatch.setattr(
        copilot_service,
        "get_copilot_service",
        lambda: FakeCopilotService(),
    )
    monkeypatch.setattr(
        draft_service,
        "get_memory_store",
        lambda: FakeMemoryStore(),
    )


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """Create a test client with an isolated temporary SQLite database."""
    settings = get_settings()
    settings.app_env = "test"
    settings.sqlite_db_path = tmp_path / "test_drafts.db"
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_customer(client: TestClient) -> dict:
    """Create a sample customer for draft workflow tests."""
    response = client.post(
        "/customers",
        json={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "company_name": "Acme Insurance Co",
            "phone": "555-1234",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def sample_ticket(client: TestClient, sample_customer: dict) -> dict:
    """Create a sample ticket for draft workflow tests."""
    response = client.post(
        "/tickets",
        json={
            "customer_id": sample_customer["id"],
            "subject": "Rear-end collision",
            "claim_type": "Auto Collision",
            "claim_narrative": "Rear-ended at a stoplight with bumper damage.",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def sample_draft_data(sample_customer: dict, sample_ticket: dict) -> dict:
    """Request payload for draft generation."""
    return {
        "ticket_id": sample_ticket["id"],
        "customer_id": sample_customer["id"],
        "regenerate": False,
    }


class TestGenerateDraft:
    def test_generate_draft_success(self, client: TestClient, sample_draft_data: dict) -> None:
        response = client.post("/drafts", json=sample_draft_data)

        assert response.status_code == 201
        data = response.json()
        assert data["ticket_id"] == sample_draft_data["ticket_id"]
        assert data["customer_id"] == sample_draft_data["customer_id"]
        assert data["status"] == "pending"
        assert data["is_new"] is True
        assert data["created_at"] is not None
        assert "draft_text" in data

    def test_generate_draft_returns_existing_when_regenerate_false(
        self,
        client: TestClient,
        sample_draft_data: dict,
    ) -> None:
        first_response = client.post("/drafts", json=sample_draft_data)
        second_response = client.post("/drafts", json=sample_draft_data)

        assert first_response.status_code == 201
        assert second_response.status_code == 201
        first = first_response.json()
        second = second_response.json()
        assert second["id"] == first["id"]
        assert second["is_new"] is False

    def test_generate_draft_missing_ticket_id(
        self,
        client: TestClient,
        sample_customer: dict,
    ) -> None:
        response = client.post(
            "/drafts",
            json={"customer_id": sample_customer["id"], "regenerate": False},
        )
        assert response.status_code == 422


class TestGetDraft:
    def test_get_draft_by_id_success(self, client: TestClient, sample_draft_data: dict) -> None:
        create_response = client.post("/drafts", json=sample_draft_data)
        draft_id = create_response.json()["id"]

        response = client.get(f"/drafts/{draft_id}")

        assert response.status_code == 200
        assert response.json()["id"] == draft_id

    def test_get_draft_by_id_not_found(self, client: TestClient) -> None:
        response = client.get("/drafts/nonexistent-id")
        assert response.status_code == 404

    def test_list_ticket_drafts(self, client: TestClient, sample_draft_data: dict) -> None:
        client.post("/drafts", json=sample_draft_data)

        response = client.get(f"/drafts/ticket/{sample_draft_data['ticket_id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["drafts"]) == 1


class TestApproveDraft:
    def test_approve_draft_success(self, client: TestClient, sample_draft_data: dict) -> None:
        create_response = client.post("/drafts", json=sample_draft_data)
        draft_id = create_response.json()["id"]

        response = client.put(
            f"/drafts/{draft_id}/approve",
            json={
                "approved_by": "Adjuster A",
                "adjuster_notes": "Approved after review",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"
        assert data["approved_by"] == "Adjuster A"
        assert data["approved_at"] is not None

    def test_approve_draft_missing_approved_by(
        self,
        client: TestClient,
        sample_draft_data: dict,
    ) -> None:
        create_response = client.post("/drafts", json=sample_draft_data)
        draft_id = create_response.json()["id"]

        response = client.put(
            f"/drafts/{draft_id}/approve",
            json={"adjuster_notes": "Looks good"},
        )

        assert response.status_code == 422

    def test_approve_draft_not_found(self, client: TestClient) -> None:
        response = client.put(
            "/drafts/nonexistent-id/approve",
            json={"approved_by": "Adjuster A", "adjuster_notes": "Approved"},
        )
        assert response.status_code == 404


class TestDiscardDraft:
    def test_discard_draft_success(self, client: TestClient, sample_draft_data: dict) -> None:
        create_response = client.post("/drafts", json=sample_draft_data)
        draft_id = create_response.json()["id"]

        response = client.put(
            f"/drafts/{draft_id}/discard",
            json={"reason": "Needs more investigation"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "discarded"

    def test_discard_draft_missing_reason(
        self,
        client: TestClient,
        sample_draft_data: dict,
    ) -> None:
        create_response = client.post("/drafts", json=sample_draft_data)
        draft_id = create_response.json()["id"]

        response = client.put(f"/drafts/{draft_id}/discard", json={})
        assert response.status_code == 422


class TestDraftEditingAndRequestInfo:
    def test_update_draft_text(self, client: TestClient, sample_draft_data: dict) -> None:
        create_response = client.post("/drafts", json=sample_draft_data)
        draft_id = create_response.json()["id"]

        response = client.patch(
            f"/drafts/{draft_id}",
            json={"draft_text": "Updated draft after human review."},
        )

        assert response.status_code == 200
        assert response.json()["draft_text"] == "Updated draft after human review."

    def test_request_more_info(self, client: TestClient, sample_draft_data: dict) -> None:
        create_response = client.post("/drafts", json=sample_draft_data)
        draft_id = create_response.json()["id"]

        response = client.put(
            f"/drafts/{draft_id}/request-info",
            json={"reason": "Need repair estimate and more accident photos."},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "needs_info"
        assert "Need repair estimate" in response.json()["adjuster_notes"]

    def test_mark_pending(self, client: TestClient, sample_draft_data: dict) -> None:
        create_response = client.post("/drafts", json=sample_draft_data)
        draft_id = create_response.json()["id"]

        response = client.put(
            f"/drafts/{draft_id}/mark-pending",
            json={"reason": "Return to queue after adjuster note review."},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "pending"
        assert "Return to queue" in response.json()["adjuster_notes"]

    def test_regenerate_draft(self, client: TestClient, sample_draft_data: dict) -> None:
        create_response = client.post("/drafts", json=sample_draft_data)
        first_draft = create_response.json()

        response = client.post(
            f"/drafts/{first_draft['id']}/regenerate",
            json={"reason": "Need a fresh revision with more context."},
        )

        assert response.status_code == 200
        regenerated = response.json()
        assert regenerated["id"] != first_draft["id"]
        assert regenerated["status"] == "pending"
        assert regenerated["context_used"]["regeneration"]["prior_draft_id"] == first_draft["id"]

    def test_draft_history(self, client: TestClient, sample_draft_data: dict) -> None:
        create_response = client.post("/drafts", json=sample_draft_data)
        first_draft = create_response.json()
        regen_response = client.post(
            f"/drafts/{first_draft['id']}/regenerate",
            json={"reason": "Need a second version."},
        )
        regenerated = regen_response.json()

        response = client.get(f"/drafts/{regenerated['id']}/history")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert {draft["id"] for draft in data["drafts"]} == {
            first_draft["id"],
            regenerated["id"],
        }


class TestDraftIntegration:
    def test_generate_then_approve_workflow(
        self,
        client: TestClient,
        sample_draft_data: dict,
    ) -> None:
        generate_response = client.post("/drafts", json=sample_draft_data)
        draft_id = generate_response.json()["id"]

        approve_response = client.put(
            f"/drafts/{draft_id}/approve",
            json={"approved_by": "Adjuster B", "adjuster_notes": "Send to claimant"},
        )

        assert generate_response.status_code == 201
        assert approve_response.status_code == 200
        assert approve_response.json()["status"] == "approved"
