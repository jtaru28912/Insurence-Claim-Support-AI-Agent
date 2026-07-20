"""
SQLite connection management and schema initialization.

Design notes
------------
A single small ``Database`` class owns connection creation and schema
setup. Repositories (data/repositories/*.py) depend on this class for
connections rather than opening sqlite3 connections themselves — Single
Responsibility, and it makes repositories easy to unit test by handing
them a ``Database`` pointed at ``:memory:``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from customer_support_agent.core.settings import Settings, get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    phone TEXT,
    address TEXT,
    company_name TEXT NOT NULL,
    plan_tier TEXT NOT NULL DEFAULT 'Standard Auto',
    sla_hours INTEGER NOT NULL DEFAULT 48,
    policy_number TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    subject TEXT NOT NULL,
    claim_narrative TEXT NOT NULL,
    claim_type TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS drafts (
    id TEXT PRIMARY KEY,
    ticket_id TEXT NOT NULL REFERENCES tickets(id),
    draft_text TEXT NOT NULL,
    context_used TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    approved_by TEXT,
    approved_at TEXT,
    adjuster_notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tickets_customer_id ON tickets(customer_id);
CREATE INDEX IF NOT EXISTS idx_drafts_ticket_id ON drafts(ticket_id);
"""


class Database:
    """Thin wrapper around sqlite3: connection management + schema init."""

    def __init__(self, settings: Settings) -> None:
        self._db_path = settings.sqlite_db_path

    def initialize_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(_SCHEMA)
            self._ensure_column(conn, "drafts", "approved_by", "TEXT")
            self._ensure_column(conn, "drafts", "approved_at", "TEXT")

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        existing_columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in existing_columns:
            conn.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


_db_instance: Database | None = None


def get_database() -> Database:
    """Process-wide singleton accessor, used as a FastAPI dependency."""
    global _db_instance
    settings = get_settings()
    if _db_instance is None or _db_instance._db_path != settings.sqlite_db_path:
        _db_instance = Database(settings)
    return _db_instance
