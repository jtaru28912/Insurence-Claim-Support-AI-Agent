"""Draft repository — SQLite-backed persistence for the `drafts` table."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from typing import Any

from customer_support_agent.data.repositories.base_repository import BaseRepository


@dataclass
class DraftRecord:
    id: str
    ticket_id: str
    draft_text: str
    context_used: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending | approved | discarded
    approved_by: str | None = None
    approved_at: str | None = None
    adjuster_notes: str | None = None
    created_at: str = ""
    updated_at: str = ""


class DraftRepository(BaseRepository):
    def create(
        self,
        *,
        ticket_id: str,
        draft_text: str,
        context_used: dict[str, Any],
    ) -> DraftRecord:
        draft_id = str(uuid.uuid4())
        with self._database.connect() as conn:
            conn.execute(
                """INSERT INTO drafts (id, ticket_id, draft_text, context_used, status)
                   VALUES (?, ?, ?, ?, 'pending')""",
                (draft_id, ticket_id, draft_text, json.dumps(context_used)),
            )
        record = self.get_by_id(draft_id)
        assert record is not None
        return record

    def get_by_id(self, draft_id: str) -> DraftRecord | None:
        with self._database.connect() as conn:
            row = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def list_by_ticket(self, ticket_id: str) -> list[DraftRecord]:
        with self._database.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM drafts WHERE ticket_id = ? ORDER BY created_at DESC", (ticket_id,)
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def count_all(self) -> int:
        with self._database.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM drafts").fetchone()
        return row["cnt"] if row else 0

    def count_by_status(self, status: str) -> int:
        with self._database.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM drafts WHERE status = ?",
                (status,),
            ).fetchone()
        return row["cnt"] if row else 0

    def update_text(self, draft_id: str, draft_text: str) -> None:
        with self._database.connect() as conn:
            conn.execute(
                "UPDATE drafts SET draft_text = ?, updated_at = datetime('now') WHERE id = ?",
                (draft_text, draft_id),
            )

    def update_context(self, draft_id: str, context_used: dict[str, Any]) -> None:
        with self._database.connect() as conn:
            conn.execute(
                "UPDATE drafts SET context_used = ?, updated_at = datetime('now') WHERE id = ?",
                (json.dumps(context_used), draft_id),
            )

    def update_status(self, draft_id: str, status: str, adjuster_notes: str | None = None) -> None:
        with self._database.connect() as conn:
            conn.execute(
                "UPDATE drafts SET status = ?, adjuster_notes = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (status, adjuster_notes, draft_id),
            )

    def approve(self, draft_id: str, approved_by: str, adjuster_notes: str | None = None) -> None:
        """Mark a draft as approved."""
        with self._database.connect() as conn:
            conn.execute(
                """UPDATE drafts
                   SET status = 'approved',
                       approved_by = ?,
                       approved_at = datetime('now'),
                       adjuster_notes = ?,
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (approved_by, adjuster_notes, draft_id),
            )

    def discard(self, draft_id: str, reason: str | None = None) -> None:
        """Mark a draft as discarded."""
        with self._database.connect() as conn:
            conn.execute(
                """UPDATE drafts 
                   SET status = 'discarded',
                       adjuster_notes = ?,
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (reason, draft_id),
            )

    def request_info(self, draft_id: str, reason: str) -> None:
        """Mark a draft as needing more information."""
        with self._database.connect() as conn:
            conn.execute(
                """UPDATE drafts
                   SET status = 'needs_info',
                       adjuster_notes = ?,
                       updated_at = datetime('now')
                   WHERE id = ?""",
                (reason, draft_id),
            )

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> DraftRecord:
        return DraftRecord(
            id=row["id"],
            ticket_id=row["ticket_id"],
            draft_text=row["draft_text"],
            context_used=json.loads(row["context_used"]) if row["context_used"] else {},
            status=row["status"],
            approved_by=row["approved_by"],
            approved_at=row["approved_at"],
            adjuster_notes=row["adjuster_notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
