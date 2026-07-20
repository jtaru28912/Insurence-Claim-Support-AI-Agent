"""
Structured LangChain tools available to the copilot agent.

Per spec: "Current tools: lookup_customer_plan, lookup_open_ticket_load —
enrich recommendations with plan tier, SLA expectations, current
open-ticket volume." Both tools delegate to ``CustomerDataGateway`` (see
customer_data_gateway.py) rather than hard-coding data lookups, so the
Phase 3 SQLite-backed implementation can be swapped in without touching
these tool definitions.
"""

from __future__ import annotations

from langchain_core.tools import tool

from customer_support_agent.integrations.tools.claim_risk_tools import analyze_claim_risk
from customer_support_agent.integrations.tools.customer_data_gateway import (
    get_customer_data_gateway,
)


@tool
def lookup_customer_plan(customer_email: str) -> dict:
    """Look up a customer's insurance plan tier, SLA expectation, and policy number by email.

    Use this when you need to know what coverage plan the customer is on
    or what response-time SLA applies to their claim.
    """
    gateway = get_customer_data_gateway()
    info = gateway.get_customer_plan(customer_email)
    if info is None:
        return {"found": False, "customer_email": customer_email}
    return {
        "found": True,
        "customer_email": info.customer_email,
        "plan_tier": info.plan_tier,
        "sla_hours": info.sla_hours,
        "policy_number": info.policy_number,
    }


@tool
def lookup_open_ticket_load(customer_email: str) -> dict:
    """Look up how many open support tickets and open claims a customer currently has.

    Use this to gauge current operational load before recommending next
    steps or an escalation.
    """
    gateway = get_customer_data_gateway()
    info = gateway.get_open_ticket_load(customer_email)
    return {
        "customer_email": info.customer_email,
        "open_ticket_count": info.open_ticket_count,
        "open_claim_count": info.open_claim_count,
    }


SUPPORT_TOOLS = [lookup_customer_plan, lookup_open_ticket_load, analyze_claim_risk]
