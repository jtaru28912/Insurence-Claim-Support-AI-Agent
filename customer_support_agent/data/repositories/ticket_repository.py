"""Ticket repository — SQLite-backed persistence for the `tickets` table."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass

from customer_support_agent.data.repositories.base_repository import BaseRepository


@dataclass
class TicketRecord:
    id: str
    customer_id: str
    subject: str
    claim_narrative: str
    claim_type: str | None
    status: str
    created_at: str
    updated_at: str


class TicketRepository(BaseRepository):
    def create(
        self,
        *,
        customer_id: str,
        subject: str,
        claim_narrative: str,
        claim_type: str | None = None,
    ) -> TicketRecord:
        ticket_id = str(uuid.uuid4())
        with self._database.connect() as conn:
            conn.execute(
                """INSERT INTO tickets (id, customer_id, subject, claim_narrative, claim_type)
                   VALUES (?, ?, ?, ?, ?)""",
                (ticket_id, customer_id, subject, claim_narrative, claim_type),
            )
        record = self.get_by_id(ticket_id)
        assert record is not None
        return record

    def get_by_id(self, ticket_id: str) -> TicketRecord | None:
        with self._database.connect() as conn:
            row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def list_by_customer(self, customer_id: str) -> list[TicketRecord]:
        with self._database.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tickets WHERE customer_id = ? ORDER BY created_at DESC",
                (customer_id,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def list_all(self) -> list[TicketRecord]:
        with self._database.connect() as conn:
            rows = conn.execute("SELECT * FROM tickets ORDER BY created_at DESC").fetchall()
        return [self._row_to_record(row) for row in rows]

    def count_all(self) -> int:
        with self._database.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM tickets").fetchone()
        return row["cnt"] if row else 0

    def update_status(self, ticket_id: str, status: str) -> None:
        with self._database.connect() as conn:
            conn.execute(
                "UPDATE tickets SET status = ?, updated_at = datetime('now') WHERE id = ?",
                (status, ticket_id),
            )

    def count_open_for_customer(self, customer_id: str) -> int:
        with self._database.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM tickets "
                "WHERE customer_id = ? AND status IN ('open', 'in_progress', 'pending')",
                (customer_id,),
            ).fetchone()
        return row["cnt"] if row else 0

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> TicketRecord:
        return TicketRecord(
            id=row["id"],
            customer_id=row["customer_id"],
            subject=row["subject"],
            claim_narrative=row["claim_narrative"],
            claim_type=row["claim_type"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
