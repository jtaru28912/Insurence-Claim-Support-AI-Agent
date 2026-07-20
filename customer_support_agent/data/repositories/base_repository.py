"""Repository pattern base class."""

from __future__ import annotations

from customer_support_agent.data.database import Database


class BaseRepository:
    """Shared connection-access foundation for all repositories."""

    def __init__(self, database: Database) -> None:
        self._database = database
