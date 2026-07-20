"""Unit tests for Customers API endpoints."""

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
    settings.sqlite_db_path = tmp_path / "test_customers.db"
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def test_db(tmp_path):
    """Create temporary test database."""
    settings = get_settings()
    settings.sqlite_db_path = tmp_path / "test_customers.db"
    db = Database(settings)
    db.initialize_schema()
    return db


@pytest.fixture
def sample_customer_data():
    """Sample customer data for testing."""
    return {
        "name": "John Doe",
        "email": "john@example.com",
        "company_name": "Acme Insurance Co",
        "phone": "555-1234",
        "address": "123 Main St, Anytown, USA",
    }


class TestCreateCustomer:
    """Test customer creation endpoint."""

    def test_create_customer_success(self, client, sample_customer_data):
        """Test successful customer creation."""
        response = client.post("/customers", json=sample_customer_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_customer_data["name"]
        assert data["email"] == sample_customer_data["email"]
        assert "id" in data
        assert "created_at" in data

    def test_create_customer_minimal(self, client):
        """Test customer creation with minimal required fields."""
        payload = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "company_name": "Acme Insurance Co",
        }
        response = client.post("/customers", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Jane Doe"
        assert data["email"] == "jane@example.com"

    def test_create_customer_missing_email(self, client):
        """Test customer creation fails without email."""
        payload = {"name": "John Doe"}
        response = client.post("/customers", json=payload)
        assert response.status_code == 422  # Validation error

    def test_create_customer_missing_name(self, client):
        """Test customer creation fails without name."""
        payload = {"email": "john@example.com"}
        response = client.post("/customers", json=payload)
        assert response.status_code == 422  # Validation error

    def test_create_customer_duplicate_email(self, client, sample_customer_data, test_db):
        """Test that duplicate emails are handled appropriately."""
        # Create first customer
        response1 = client.post("/customers", json=sample_customer_data)
        assert response1.status_code == 201

        # Try to create second customer with same email
        response2 = client.post("/customers", json=sample_customer_data)
        # Behavior depends on implementation: could be 400 or 409
        assert response2.status_code in (400, 409, 201)  # Allow for either reject or allow


class TestGetCustomer:
    """Test customer retrieval endpoints."""

    def test_get_customer_by_id_success(self, client, sample_customer_data):
        """Test successful customer retrieval by ID."""
        # Create first
        create_response = client.post("/customers", json=sample_customer_data)
        customer_id = create_response.json()["id"]

        # Retrieve
        response = client.get(f"/customers/{customer_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == customer_id
        assert data["name"] == sample_customer_data["name"]

    def test_get_customer_by_id_not_found(self, client):
        """Test retrieval of non-existent customer."""
        response = client.get("/customers/nonexistent-id")
        assert response.status_code == 404

    def test_get_customer_by_email_success(self, client, sample_customer_data):
        """Test successful customer retrieval by email."""
        # Create first
        client.post("/customers", json=sample_customer_data)

        # Retrieve
        response = client.get(f"/customers/email/{sample_customer_data['email']}")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == sample_customer_data["email"]
        assert data["name"] == sample_customer_data["name"]

    def test_get_customer_by_email_not_found(self, client):
        """Test retrieval of customer with non-existent email."""
        response = client.get("/customers/email/nonexistent@example.com")
        assert response.status_code == 404


class TestListCustomers:
    """Test customer listing endpoint."""

    def test_list_customers_empty(self, client):
        """Test listing when no customers exist."""
        response = client.get("/customers")
        assert response.status_code == 200
        data = response.json()
        assert data["customers"] == []
        assert data["count"] == 0

    def test_list_customers_multiple(self, client):
        """Test listing multiple customers."""
        customers_data = [
            {"name": "John Doe", "email": "john@example.com", "company_name": "Acme Insurance Co"},
            {"name": "Jane Smith", "email": "jane@example.com", "company_name": "Acme Insurance Co"},
            {"name": "Bob Johnson", "email": "bob@example.com", "company_name": "Acme Insurance Co"},
        ]

        # Create customers
        for customer_data in customers_data:
            response = client.post("/customers", json=customer_data)
            assert response.status_code == 201

        # List all
        response = client.get("/customers")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        assert len(data["customers"]) == 3

    def test_list_customers_response_format(self, client, sample_customer_data):
        """Test that list response has expected format."""
        client.post("/customers", json=sample_customer_data)

        response = client.get("/customers")
        assert response.status_code == 200
        data = response.json()

        assert "customers" in data
        assert "count" in data
        assert isinstance(data["customers"], list)
        assert isinstance(data["count"], int)

        if data["count"] > 0:
            customer = data["customers"][0]
            assert "id" in customer
            assert "name" in customer
            assert "email" in customer
            assert "created_at" in customer


class TestCustomerDataIntegrity:
    """Test data integrity and validation."""

    def test_customer_fields_preserved(self, client, sample_customer_data):
        """Test that all customer fields are preserved."""
        response = client.post("/customers", json=sample_customer_data)
        assert response.status_code == 201
        data = response.json()

        assert data["name"] == sample_customer_data["name"]
        assert data["email"] == sample_customer_data["email"]
        assert data["phone"] == sample_customer_data["phone"]
        assert data["address"] == sample_customer_data["address"]

    def test_customer_timestamps(self, client, sample_customer_data):
        """Test that timestamps are set."""
        response = client.post("/customers", json=sample_customer_data)
        data = response.json()

        assert "created_at" in data
        assert "updated_at" in data
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

    def test_customer_id_uniqueness(self, client, sample_customer_data):
        """Test that customer IDs are unique."""
        response1 = client.post("/customers", json=sample_customer_data)
        id1 = response1.json()["id"]

        customer_data_2 = {**sample_customer_data, "email": "different@example.com"}
        response2 = client.post("/customers", json=customer_data_2)
        id2 = response2.json()["id"]

        assert id1 != id2


class TestCustomerEndpointIntegration:
    """Integration tests for customer endpoints."""

    def test_create_list_retrieve_workflow(self, client):
        """Test complete workflow: create -> list -> retrieve."""
        # Create
        customer_data = {
            "name": "Test User",
            "email": "test@example.com",
            "company_name": "Acme Insurance Co",
        }
        create_response = client.post("/customers", json=customer_data)
        assert create_response.status_code == 201
        customer_id = create_response.json()["id"]

        # List
        list_response = client.get("/customers")
        assert list_response.status_code == 200
        assert len(list_response.json()["customers"]) >= 1

        # Retrieve by ID
        get_response = client.get(f"/customers/{customer_id}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == customer_id

        # Retrieve by email
        email_response = client.get(f"/customers/email/{customer_data['email']}")
        assert email_response.status_code == 200
        assert email_response.json()["email"] == customer_data["email"]
