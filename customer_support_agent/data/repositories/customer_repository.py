"""
Customer repository — SQLite-backed persistence for the `customers` table.

Design notes
------------
Implements ``CustomerDataGateway`` (see
integrations/tools/customer_data_gateway.py) so it can be swapped in for
the Phase 2 in-memory demo gateway via ``set_customer_data_gateway()`` at
application startup — the support tools require no code changes
(Liskov Substitution / Open-Closed Principle).
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass

from customer_support_agent.data.repositories.base_repository import BaseRepository
from customer_support_agent.integrations.tools.customer_data_gateway import (
    CustomerPlanInfo,
    TicketLoadInfo,
)


@dataclass
class CustomerRecord:
    id: str
    email: str
    name: str | None
    phone: str | None
    address: str | None
    company_name: str
    plan_tier: str
    sla_hours: int
    policy_number: str | None
    updated_at: str
    created_at: str


class CustomerRepository(BaseRepository):
    """SQLite-backed CRUD for customers, plus the CustomerDataGateway protocol."""

    def create(
        self,
        *,
        email: str,
        company_name: str,
        name: str | None = None,
        phone: str | None = None,
        address: str | None = None,
        plan_tier: str = "Standard Auto",
        sla_hours: int = 48,
        policy_number: str | None = None,
    ) -> CustomerRecord:
        customer_id = str(uuid.uuid4())
        normalized_email = email.strip().lower()
        with self._database.connect() as conn:
            conn.execute(
                """INSERT INTO customers
                   (id, email, name, phone, address, company_name, plan_tier, sla_hours, policy_number)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    customer_id,
                    normalized_email,
                    name,
                    phone,
                    address,
                    company_name,
                    plan_tier,
                    sla_hours,
                    policy_number,
                ),
            )
        record = self.get_by_id(customer_id)
        assert record is not None  # created in the same transaction, must exist
        return record

    def get_by_email(self, email: str) -> CustomerRecord | None:
        with self._database.connect() as conn:
            row = conn.execute(
                "SELECT * FROM customers WHERE email = ?", (email.strip().lower(),)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def get_by_id(self, customer_id: str) -> CustomerRecord | None:
        with self._database.connect() as conn:
            row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def list_all(self) -> list[CustomerRecord]:
        with self._database.connect() as conn:
            rows = conn.execute("SELECT * FROM customers ORDER BY created_at DESC").fetchall()
        return [self._row_to_record(row) for row in rows]

    def count_all(self) -> int:
        with self._database.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM customers").fetchone()
        return row["cnt"] if row else 0

    def get_or_create(
        self,
        *,
        email: str,
        company_name: str,
        name: str | None = None,
        phone: str | None = None,
        address: str | None = None,
        plan_tier: str = "Standard Auto",
        sla_hours: int = 48,
        policy_number: str | None = None,
    ) -> CustomerRecord:
        existing = self.get_by_email(email)
        if existing:
            return existing
        try:
            return self.create(
                email=email,
                company_name=company_name,
                name=name,
                phone=phone,
                address=address,
                plan_tier=plan_tier,
                sla_hours=sla_hours,
                policy_number=policy_number,
            )
        except sqlite3.IntegrityError:
            # Race: another request created it between our SELECT and INSERT.
            existing = self.get_by_email(email)
            assert existing is not None
            return existing

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> CustomerRecord:
        return CustomerRecord(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            phone=row["phone"],
            address=row["address"],
            company_name=row["company_name"],
            plan_tier=row["plan_tier"],
            sla_hours=row["sla_hours"],
            policy_number=row["policy_number"],
            updated_at=row["updated_at"],
            created_at=row["created_at"],
        )

    # -------------------------------------------- CustomerDataGateway protocol
    def get_customer_plan(self, customer_email: str) -> CustomerPlanInfo | None:
        record = self.get_by_email(customer_email)
        if record is None:
            return None
        return CustomerPlanInfo(
            customer_email=record.email,
            plan_tier=record.plan_tier,
            sla_hours=record.sla_hours,
            policy_number=record.policy_number or "UNKNOWN",
        )

    def get_open_ticket_load(self, customer_email: str) -> TicketLoadInfo:
        record = self.get_by_email(customer_email)
        if record is None:
            return TicketLoadInfo(
                customer_email=customer_email, open_ticket_count=0, open_claim_count=0
            )
        with self._database.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM tickets "
                "WHERE customer_id = ? AND status IN ('open', 'in_progress', 'pending')",
                (record.id,),
            ).fetchone()
        open_count = row["cnt"] if row else 0
        return TicketLoadInfo(
            customer_email=record.email, open_ticket_count=open_count, open_claim_count=open_count
        )
