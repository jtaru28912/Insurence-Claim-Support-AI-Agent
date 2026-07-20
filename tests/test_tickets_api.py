"""Unit tests for Tickets API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from customer_support_agent.api.app_factory import create_app
from customer_support_agent.core.settings import get_settings
from customer_support_agent.data.database import Database


@pytest.fixture
def client(tmp_path):
    """Create test client with isolated temporary SQLite."""
    settings = get_settings()
    settings.app_env = "test"
    settings.sqlite_db_path = tmp_path / "test_tickets.db"
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database."""
    settings = get_settings()
    settings.sqlite_db_path = tmp_path / "test_tickets.db"
    db = Database(settings)
    db.initialize_schema()
    return db


@pytest.fixture
def sample_customer(client):
    """Create a sample customer for testing."""
    customer_data = {
        "name": "John Doe",
        "email": "john@example.com",
        "company_name": "Acme Insurance Co",
        "phone": "555-1234",
    }
    response = client.post("/customers", json=customer_data)
    return response.json()


@pytest.fixture
def sample_ticket_data(sample_customer):
    """Sample ticket data for testing."""
    return {
        "customer_id": sample_customer["id"],
        "subject": "Auto collision at intersection",
        "claim_type": "Auto Collision",
        "claim_narrative": "My car was hit by another vehicle at Main and 5th. Both vehicles damaged. No injuries.",
    }


class TestCreateTicket:
    """Test ticket creation endpoint."""

    def test_create_ticket_success(self, client, sample_ticket_data):
        """Test successful ticket creation."""
        response = client.post("/tickets", json=sample_ticket_data)
        assert response.status_code == 201
        data = response.json()
        assert data["subject"] == sample_ticket_data["subject"]
        assert data["claim_type"] == sample_ticket_data["claim_type"]
        assert data["status"] == "open"
        assert "id" in data

    def test_create_ticket_all_fields(self, client, sample_ticket_data):
        """Test that all fields are preserved."""
        response = client.post("/tickets", json=sample_ticket_data)
        assert response.status_code == 201
        data = response.json()

        assert data["customer_id"] == sample_ticket_data["customer_id"]
        assert data["subject"] == sample_ticket_data["subject"]
        assert data["claim_type"] == sample_ticket_data["claim_type"]
        assert data["claim_narrative"] == sample_ticket_data["claim_narrative"]

    def test_create_ticket_missing_customer_id(self, client):
        """Test ticket creation fails without customer_id."""
        payload = {
            "subject": "Test claim",
            "claim_type": "Auto Collision",
            "claim_narrative": "Test narrative",
        }
        response = client.post("/tickets", json=payload)
        assert response.status_code == 422  # Validation error

    def test_create_ticket_missing_subject(self, client, sample_customer):
        """Test ticket creation fails without subject."""
        payload = {
            "customer_id": sample_customer["id"],
            "claim_type": "Auto Collision",
            "claim_narrative": "Test narrative",
        }
        response = client.post("/tickets", json=payload)
        assert response.status_code == 422

    def test_create_ticket_missing_narrative(self, client, sample_customer):
        """Test ticket creation fails without narrative."""
        payload = {
            "customer_id": sample_customer["id"],
            "subject": "Test claim",
            "claim_type": "Auto Collision",
        }
        response = client.post("/tickets", json=payload)
        assert response.status_code == 422

    def test_create_ticket_invalid_customer_id(self, client):
        """Test ticket creation with invalid customer ID."""
        payload = {
            "customer_id": "nonexistent-id",
            "subject": "Test claim",
            "claim_type": "Auto Collision",
            "claim_narrative": "Test narrative",
        }
        response = client.post("/tickets", json=payload)
        # Should fail either 400 or 404 depending on implementation
        assert response.status_code in (400, 404)


class TestGetTicket:
    """Test ticket retrieval endpoints."""

    def test_get_ticket_by_id_success(self, client, sample_ticket_data):
        """Test successful ticket retrieval by ID."""
        # Create first
        create_response = client.post("/tickets", json=sample_ticket_data)
        ticket_id = create_response.json()["id"]

        # Retrieve
        response = client.get(f"/tickets/{ticket_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == ticket_id
        assert data["subject"] == sample_ticket_data["subject"]

    def test_get_ticket_by_id_not_found(self, client):
        """Test retrieval of non-existent ticket."""
        response = client.get("/tickets/nonexistent-id")
        assert response.status_code == 404

    def test_list_customer_tickets_empty(self, client, sample_customer):
        """Test listing when customer has no tickets."""
        response = client.get(f"/tickets/customer/{sample_customer['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["tickets"] == []
        assert data["count"] == 0

    def test_list_customer_tickets_multiple(self, client, sample_customer):
        """Test listing multiple tickets for customer."""
        # Create multiple tickets
        tickets_data = [
            {
                "customer_id": sample_customer["id"],
                "subject": f"Claim {i}",
                "claim_type": "Auto Collision",
                "claim_narrative": f"Narrative {i}",
            }
            for i in range(3)
        ]

        for ticket_data in tickets_data:
            response = client.post("/tickets", json=ticket_data)
            assert response.status_code == 201

        # List all
        response = client.get(f"/tickets/customer/{sample_customer['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        assert len(data["tickets"]) == 3

    def test_list_customer_tickets_response_format(self, client, sample_ticket_data):
        """Test that list response has expected format."""
        client.post("/tickets", json=sample_ticket_data)

        response = client.get(f"/tickets/customer/{sample_ticket_data['customer_id']}")
        assert response.status_code == 200
        data = response.json()

        assert "tickets" in data
        assert "count" in data
        assert isinstance(data["tickets"], list)
        assert isinstance(data["count"], int)

        if data["count"] > 0:
            ticket = data["tickets"][0]
            assert "id" in ticket
            assert "subject" in ticket
            assert "status" in ticket
            assert "created_at" in ticket


class TestUpdateTicketStatus:
    """Test ticket status update endpoint."""

    def test_update_ticket_status_success(self, client, sample_ticket_data):
        """Test successful ticket status update."""
        # Create first
        create_response = client.post("/tickets", json=sample_ticket_data)
        ticket_id = create_response.json()["id"]

        # Update status
        response = client.patch(f"/tickets/{ticket_id}", json={"status": "in_progress"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_progress"

    def test_update_ticket_status_to_closed(self, client, sample_ticket_data):
        """Test updating ticket status to closed."""
        create_response = client.post("/tickets", json=sample_ticket_data)
        ticket_id = create_response.json()["id"]

        response = client.patch(f"/tickets/{ticket_id}", json={"status": "closed"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "closed"

    def test_update_ticket_status_not_found(self, client):
        """Test updating status of non-existent ticket."""
        response = client.patch("/tickets/nonexistent", json={"status": "closed"})
        assert response.status_code == 404

    def test_update_ticket_status_missing_field(self, client, sample_ticket_data):
        """Test status update with missing status field."""
        create_response = client.post("/tickets", json=sample_ticket_data)
        ticket_id = create_response.json()["id"]

        response = client.patch(f"/tickets/{ticket_id}", json={})
        assert response.status_code == 422  # Validation error

    def test_update_ticket_status_preserves_other_fields(self, client, sample_ticket_data):
        """Test that status update doesn't change other fields."""
        create_response = client.post("/tickets", json=sample_ticket_data)
        original = create_response.json()
        ticket_id = original["id"]

        # Update status
        client.patch(f"/tickets/{ticket_id}", json={"status": "closed"})

        # Retrieve and verify other fields intact
        response = client.get(f"/tickets/{ticket_id}")
        updated = response.json()

        assert updated["subject"] == original["subject"]
        assert updated["claim_type"] == original["claim_type"]
        assert updated["claim_narrative"] == original["claim_narrative"]


class TestTicketDataIntegrity:
    """Test data integrity and validation."""

    def test_ticket_timestamps(self, client, sample_ticket_data):
        """Test that timestamps are set."""
        response = client.post("/tickets", json=sample_ticket_data)
        data = response.json()

        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

    def test_ticket_default_status(self, client, sample_ticket_data):
        """Test that default status is 'open'."""
        response = client.post("/tickets", json=sample_ticket_data)
        data = response.json()
        assert data["status"] == "open"

    def test_ticket_id_uniqueness(self, client, sample_customer):
        """Test that ticket IDs are unique."""
        ticket_data_1 = {
            "customer_id": sample_customer["id"],
            "subject": "Claim 1",
            "claim_type": "Auto Collision",
            "claim_narrative": "Narrative 1",
        }
        response1 = client.post("/tickets", json=ticket_data_1)
        id1 = response1.json()["id"]

        ticket_data_2 = {**ticket_data_1, "subject": "Claim 2"}
        response2 = client.post("/tickets", json=ticket_data_2)
        id2 = response2.json()["id"]

        assert id1 != id2


class TestTicketEndpointIntegration:
    """Integration tests for ticket endpoints."""

    def test_full_ticket_lifecycle(self, client, sample_ticket_data):
        """Test complete ticket lifecycle: create -> retrieve -> update."""
        # Create
        create_response = client.post("/tickets", json=sample_ticket_data)
        assert create_response.status_code == 201
        ticket_id = create_response.json()["id"]

        # Retrieve
        get_response = client.get(f"/tickets/{ticket_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "open"

        # Update to in_progress
        update_response = client.patch(
            f"/tickets/{ticket_id}", json={"status": "in_progress"}
        )
        assert update_response.status_code == 200
        assert update_response.json()["status"] == "in_progress"

        # Update to closed
        update_response = client.patch(
            f"/tickets/{ticket_id}", json={"status": "closed"}
        )
        assert update_response.status_code == 200
        assert update_response.json()["status"] == "closed"

    def test_customer_with_multiple_tickets(self, client, sample_customer):
        """Test customer with multiple tickets in different states."""
        ticket_ids = []

        # Create 3 tickets
        for i in range(3):
            ticket_data = {
                "customer_id": sample_customer["id"],
                "subject": f"Claim {i}",
                "claim_type": "Auto Collision",
                "claim_narrative": f"Narrative {i}",
            }
            response = client.post("/tickets", json=ticket_data)
            ticket_ids.append(response.json()["id"])

        # Update each to different status
        client.patch(f"/tickets/{ticket_ids[0]}", json={"status": "open"})
        client.patch(f"/tickets/{ticket_ids[1]}", json={"status": "in_progress"})
        client.patch(f"/tickets/{ticket_ids[2]}", json={"status": "closed"})

        # List and verify all present
        response = client.get(f"/tickets/customer/{sample_customer['id']}")
        data = response.json()
        assert data["count"] == 3

        statuses = [ticket["status"] for ticket in data["tickets"]]
        assert "open" in statuses
        assert "in_progress" in statuses
        assert "closed" in statuses
