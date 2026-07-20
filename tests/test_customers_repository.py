"""Unit tests for the SQLite-backed customer repository."""

from __future__ import annotations

from pathlib import Path

import pytest

from customer_support_agent.core.settings import get_settings
from customer_support_agent.data.database import Database
from customer_support_agent.data.repositories.customer_repository import CustomerRepository
from customer_support_agent.data.repositories.ticket_repository import TicketRepository


@pytest.fixture
def repository(tmp_path: Path) -> CustomerRepository:
    settings = get_settings()
    settings.sqlite_db_path = tmp_path / "test_customer_repo.db"
    db = Database(settings)
    db.initialize_schema()
    return CustomerRepository(db)


@pytest.fixture
def ticket_repository(tmp_path: Path) -> TicketRepository:
    settings = get_settings()
    settings.sqlite_db_path = tmp_path / "test_customer_repo.db"
    db = Database(settings)
    db.initialize_schema()
    return TicketRepository(db)


def test_create_and_get_customer(repository: CustomerRepository) -> None:
    customer = repository.create(
        email="jane@example.com",
        company_name="Acme Insurance Co",
        name="Jane Doe",
        phone="555-1234",
    )

    fetched = repository.get_by_id(customer.id)

    assert fetched is not None
    assert fetched.email == "jane@example.com"
    assert fetched.company_name == "Acme Insurance Co"


def test_get_by_email_normalizes_input(repository: CustomerRepository) -> None:
    repository.create(
        email="Jane.Doe@Example.com",
        company_name="Acme Insurance Co",
        name="Jane Doe",
    )

    fetched = repository.get_by_email("  jane.doe@example.com  ")

    assert fetched is not None
    assert fetched.email == "jane.doe@example.com"


def test_count_all_tracks_created_customers(repository: CustomerRepository) -> None:
    repository.create(email="a@example.com", company_name="Acme", name="A")
    repository.create(email="b@example.com", company_name="Acme", name="B")

    assert repository.count_all() == 2


def test_get_or_create_returns_existing_customer(repository: CustomerRepository) -> None:
    created = repository.create(
        email="existing@example.com",
        company_name="Acme",
        name="Existing User",
    )

    fetched = repository.get_or_create(
        email="existing@example.com",
        company_name="Different Company",
        name="Ignored Name",
    )

    assert fetched.id == created.id
    assert fetched.company_name == "Acme"


def test_get_open_ticket_load_counts_non_closed_tickets(
    repository: CustomerRepository,
    ticket_repository: TicketRepository,
) -> None:
    customer = repository.create(
        email="load@example.com",
        company_name="Acme",
        name="Load Test",
    )
    ticket_repository.create(
        customer_id=customer.id,
        subject="Open claim",
        claim_narrative="Open narrative",
        claim_type="Auto Collision",
    )
    pending_info_ticket = ticket_repository.create(
        customer_id=customer.id,
        subject="Pending info claim",
        claim_narrative="Pending narrative",
        claim_type="Auto Collision",
    )
    closed_ticket = ticket_repository.create(
        customer_id=customer.id,
        subject="Closed claim",
        claim_narrative="Closed narrative",
        claim_type="Auto Collision",
    )

    ticket_repository.update_status(pending_info_ticket.id, "pending")
    ticket_repository.update_status(closed_ticket.id, "closed")

    load = repository.get_open_ticket_load("load@example.com")

    assert load.open_ticket_count == 2
    assert load.open_claim_count == 2


def test_get_customer_plan_returns_defaults_for_policy_number(repository: CustomerRepository) -> None:
    repository.create(
        email="plan@example.com",
        company_name="Acme",
        name="Plan User",
        plan_tier="Premium Auto",
        sla_hours=24,
    )

    plan = repository.get_customer_plan("plan@example.com")

    assert plan is not None
    assert plan.plan_tier == "Premium Auto"
    assert plan.sla_hours == 24
    assert plan.policy_number == "UNKNOWN"
