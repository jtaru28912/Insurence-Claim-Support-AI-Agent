"""Dashboard service providing operational summary metrics."""

from __future__ import annotations

import logging

from customer_support_agent.data.database import Database
from customer_support_agent.data.repositories.customer_repository import CustomerRepository
from customer_support_agent.data.repositories.draft_repository import DraftRepository
from customer_support_agent.data.repositories.ticket_repository import TicketRepository

logger = logging.getLogger(__name__)


class DashboardService:
    """Aggregates top-level stats for the Streamlit dashboard."""

    def __init__(self, database: Database) -> None:
        self._customers = CustomerRepository(database)
        self._tickets = TicketRepository(database)
        self._drafts = DraftRepository(database)
        logger.debug("DashboardService initialized")

    def get_stats(self) -> dict[str, int]:
        logger.info("Dashboard stats requested")
        total_claims = self._tickets.count_all()
        closed_claims = len(
            [ticket for ticket in self._tickets.list_all() if ticket.status == "closed"]
        )
        stats = {
            "total_customers": self._customers.count_all(),
            "total_claims": total_claims,
            "open_claims": total_claims - closed_claims,
            "drafts_pending": self._drafts.count_by_status("pending"),
            "drafts_needing_info": self._drafts.count_by_status("needs_info"),
        }
        logger.debug("Dashboard stats computed: %s", stats)
        return stats


def get_dashboard_service(database: Database) -> DashboardService:
    """Factory for DashboardService."""
    return DashboardService(database)
