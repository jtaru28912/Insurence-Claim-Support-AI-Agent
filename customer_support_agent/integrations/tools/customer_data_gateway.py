"""
Customer/ticket data access abstraction used by support_tools.py.

Design notes
------------
Phase 2 needs `lookup_customer_plan` / `lookup_open_ticket_load` tools to
be callable and testable *before* Phase 3's SQLite-backed repository
layer exists. Rather than hard-coding demo data into the tools
themselves, this module defines a small ``Protocol``
(``CustomerDataGateway``) that the tools depend on (Dependency Inversion)
plus an in-memory demo implementation.

In Phase 3, ``data/repositories/customer_repository.py`` will implement
this same protocol against SQLite, and ``set_customer_data_gateway()``
will be called once at application startup to swap the demo
implementation for the real one — no changes needed in
``support_tools.py`` itself (Open/Closed Principle).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class CustomerPlanInfo:
    customer_email: str
    plan_tier: str
    sla_hours: int
    policy_number: str


@dataclass
class TicketLoadInfo:
    customer_email: str
    open_ticket_count: int
    open_claim_count: int


class CustomerDataGateway(Protocol):
    """Abstract data access needed by the support tools."""

    def get_customer_plan(self, customer_email: str) -> CustomerPlanInfo | None: ...

    def get_open_ticket_load(self, customer_email: str) -> TicketLoadInfo: ...


class InMemoryCustomerDataGateway:
    """
    Demo/fallback implementation with a handful of sample customers, used
    until Phase 3's SQLite-backed repository is wired in via
    ``set_customer_data_gateway()``. Unknown emails return a sensible
    default rather than raising, so a tool call never breaks draft
    generation just because a customer isn't in the demo data.
    """

    _DEMO_PLANS: dict[str, CustomerPlanInfo] = {
        "jane.doe@example.com": CustomerPlanInfo(
            customer_email="jane.doe@example.com",
            plan_tier="Premium Auto",
            sla_hours=24,
            policy_number="POL-AUTO-10293",
        ),
        "john.smith@example.com": CustomerPlanInfo(
            customer_email="john.smith@example.com",
            plan_tier="Standard Auto",
            sla_hours=48,
            policy_number="POL-AUTO-88421",
        ),
    }

    _DEMO_LOADS: dict[str, TicketLoadInfo] = {
        "jane.doe@example.com": TicketLoadInfo(
            customer_email="jane.doe@example.com", open_ticket_count=1, open_claim_count=1
        ),
        "john.smith@example.com": TicketLoadInfo(
            customer_email="john.smith@example.com", open_ticket_count=0, open_claim_count=0
        ),
    }

    def get_customer_plan(self, customer_email: str) -> CustomerPlanInfo | None:
        normalized = customer_email.strip().lower()
        return self._DEMO_PLANS.get(normalized) or CustomerPlanInfo(
            customer_email=normalized,
            plan_tier="Standard Auto",
            sla_hours=48,
            policy_number="UNKNOWN",
        )

    def get_open_ticket_load(self, customer_email: str) -> TicketLoadInfo:
        normalized = customer_email.strip().lower()
        return self._DEMO_LOADS.get(normalized) or TicketLoadInfo(
            customer_email=normalized, open_ticket_count=0, open_claim_count=0
        )


_active_gateway: CustomerDataGateway = InMemoryCustomerDataGateway()


def get_customer_data_gateway() -> CustomerDataGateway:
    """Return the currently active gateway (module-level singleton)."""
    return _active_gateway


def set_customer_data_gateway(gateway: CustomerDataGateway) -> None:
    """
    Swap the active gateway implementation. Called once during Phase 3
    startup to replace the in-memory demo gateway with the SQLite-backed
    repository implementation — the support tools require no changes.
    """
    global _active_gateway
    _active_gateway = gateway
