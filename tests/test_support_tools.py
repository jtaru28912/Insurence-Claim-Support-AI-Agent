"""
Unit and integration tests for support tools (lookup_customer_plan, lookup_open_ticket_load).

Tests cover:
- Tool execution with real customer data
- Tool execution with fallback defaults
- Tool output format and structure
- Integration with CustomerDataGateway protocol
- Graceful handling of missing data
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from customer_support_agent.integrations.tools.customer_data_gateway import (
    CustomerPlanInfo,
    InMemoryCustomerDataGateway,
    TicketLoadInfo,
    get_customer_data_gateway,
    set_customer_data_gateway,
)
from customer_support_agent.integrations.tools.support_tools import (
    lookup_customer_plan,
    lookup_open_ticket_load,
)


@pytest.fixture(autouse=True)
def reset_gateway():
    """Reset the global gateway to InMemoryCustomerDataGateway for each test."""
    set_customer_data_gateway(InMemoryCustomerDataGateway())
    yield
    set_customer_data_gateway(InMemoryCustomerDataGateway())


class TestLookupCustomerPlan:
    """Test lookup_customer_plan tool."""

    def test_lookup_customer_plan_found(self) -> None:
        """Test lookup for a customer in the demo data."""
        result = lookup_customer_plan.invoke({"customer_email": "jane.doe@example.com"})

        assert result["found"] is True
        assert result["customer_email"] == "jane.doe@example.com"
        assert result["plan_tier"] == "Premium Auto"
        assert result["sla_hours"] == 24
        assert result["policy_number"] == "POL-AUTO-10293"

    def test_lookup_customer_plan_not_found(self) -> None:
        """Test lookup for a customer not in demo data (should return default)."""
        result = lookup_customer_plan.invoke({"customer_email": "unknown@example.com"})

        assert result["found"] is True  # Gateway returns default, not None
        assert result["customer_email"] == "unknown@example.com"
        assert result["plan_tier"] == "Standard Auto"
        assert result["sla_hours"] == 48
        assert result["policy_number"] == "UNKNOWN"

    def test_lookup_customer_plan_email_normalization(self) -> None:
        """Test that email lookup is case-insensitive."""
        result1 = lookup_customer_plan.invoke({"customer_email": "jane.doe@example.com"})
        result2 = lookup_customer_plan.invoke({"customer_email": "JANE.DOE@EXAMPLE.COM"})
        result3 = lookup_customer_plan.invoke({"customer_email": "  jane.doe@example.com  "})

        # All should find the same customer
        assert result1["plan_tier"] == result2["plan_tier"] == result3["plan_tier"]
        assert (
            result1["policy_number"]
            == result2["policy_number"]
            == result3["policy_number"]
        )

    def test_lookup_customer_plan_output_format(self) -> None:
        """Test that output has expected keys."""
        result = lookup_customer_plan.invoke({"customer_email": "jane.doe@example.com"})

        assert isinstance(result, dict)
        assert "found" in result
        assert "customer_email" in result
        assert "plan_tier" in result
        assert "sla_hours" in result
        assert "policy_number" in result


class TestLookupOpenTicketLoad:
    """Test lookup_open_ticket_load tool."""

    def test_lookup_open_ticket_load_found(self) -> None:
        """Test ticket load lookup for a customer in demo data."""
        result = lookup_open_ticket_load.invoke({"customer_email": "jane.doe@example.com"})

        assert result["customer_email"] == "jane.doe@example.com"
        assert result["open_ticket_count"] == 1
        assert result["open_claim_count"] == 1

    def test_lookup_open_ticket_load_zero_load(self) -> None:
        """Test ticket load lookup for a customer with no open items."""
        result = lookup_open_ticket_load.invoke({"customer_email": "john.smith@example.com"})

        assert result["customer_email"] == "john.smith@example.com"
        assert result["open_ticket_count"] == 0
        assert result["open_claim_count"] == 0

    def test_lookup_open_ticket_load_not_found(self) -> None:
        """Test ticket load lookup for a customer not in demo data (should return default)."""
        result = lookup_open_ticket_load.invoke({"customer_email": "unknown@example.com"})

        assert result["customer_email"] == "unknown@example.com"
        assert result["open_ticket_count"] == 0
        assert result["open_claim_count"] == 0

    def test_lookup_open_ticket_load_email_normalization(self) -> None:
        """Test that email lookup is case-insensitive."""
        result1 = lookup_open_ticket_load.invoke({"customer_email": "jane.doe@example.com"})
        result2 = lookup_open_ticket_load.invoke({"customer_email": "JANE.DOE@EXAMPLE.COM"})

        assert (
            result1["open_ticket_count"]
            == result2["open_ticket_count"]
        )
        assert (
            result1["open_claim_count"]
            == result2["open_claim_count"]
        )

    def test_lookup_open_ticket_load_output_format(self) -> None:
        """Test that output has expected keys."""
        result = lookup_open_ticket_load.invoke({"customer_email": "jane.doe@example.com"})

        assert isinstance(result, dict)
        assert "customer_email" in result
        assert "open_ticket_count" in result
        assert "open_claim_count" in result


class TestInMemoryCustomerDataGateway:
    """Test the InMemoryCustomerDataGateway implementation."""

    def test_get_customer_plan_from_demo(self) -> None:
        """Test retrieving a customer plan from demo data."""
        gateway = InMemoryCustomerDataGateway()
        plan = gateway.get_customer_plan("jane.doe@example.com")

        assert plan is not None
        assert plan.customer_email == "jane.doe@example.com"
        assert plan.plan_tier == "Premium Auto"

    def test_get_customer_plan_default(self) -> None:
        """Test retrieving a customer plan not in demo data (returns default)."""
        gateway = InMemoryCustomerDataGateway()
        plan = gateway.get_customer_plan("unknown@example.com")

        assert plan is not None
        assert plan.customer_email == "unknown@example.com"
        assert plan.plan_tier == "Standard Auto"

    def test_get_open_ticket_load_from_demo(self) -> None:
        """Test retrieving ticket load from demo data."""
        gateway = InMemoryCustomerDataGateway()
        load = gateway.get_open_ticket_load("jane.doe@example.com")

        assert load.customer_email == "jane.doe@example.com"
        assert load.open_ticket_count == 1
        assert load.open_claim_count == 1

    def test_get_open_ticket_load_default(self) -> None:
        """Test retrieving ticket load not in demo data (returns default)."""
        gateway = InMemoryCustomerDataGateway()
        load = gateway.get_open_ticket_load("unknown@example.com")

        assert load.customer_email == "unknown@example.com"
        assert load.open_ticket_count == 0
        assert load.open_claim_count == 0


class TestCustomerDataGatewaySwapping:
    """Test dynamic gateway replacement for Phase 3."""

    def test_get_and_set_customer_data_gateway(self) -> None:
        """Test getting and setting the active gateway."""
        original_gateway = get_customer_data_gateway()
        assert isinstance(original_gateway, InMemoryCustomerDataGateway)

        # Create a mock gateway
        mock_gateway = Mock()
        mock_gateway.get_customer_plan = Mock(
            return_value=CustomerPlanInfo(
                customer_email="test@example.com",
                plan_tier="Test Plan",
                sla_hours=99,
                policy_number="TEST-123",
            )
        )

        # Swap it in
        set_customer_data_gateway(mock_gateway)
        active_gateway = get_customer_data_gateway()
        assert active_gateway == mock_gateway

        # Tools should use the new gateway
        result = lookup_customer_plan.invoke({"customer_email": "test@example.com"})
        assert result["plan_tier"] == "Test Plan"
        assert result["sla_hours"] == 99

    def test_tools_use_current_gateway(self) -> None:
        """Test that tools always use the current active gateway."""
        # Start with default gateway
        result1 = lookup_customer_plan.invoke({"customer_email": "jane.doe@example.com"})
        assert result1["plan_tier"] == "Premium Auto"

        # Swap to a mock gateway
        mock_gateway = Mock()
        mock_gateway.get_customer_plan = Mock(
            return_value=CustomerPlanInfo(
                customer_email="jane.doe@example.com",
                plan_tier="Mock Plan",
                sla_hours=1,
                policy_number="MOCK-999",
            )
        )
        set_customer_data_gateway(mock_gateway)

        # Tools should now use mock gateway
        result2 = lookup_customer_plan.invoke({"customer_email": "jane.doe@example.com"})
        assert result2["plan_tier"] == "Mock Plan"
        assert result2["sla_hours"] == 1


class TestCustomerInfoDataclasses:
    """Test CustomerPlanInfo and TicketLoadInfo dataclasses."""

    def test_customer_plan_info_creation(self) -> None:
        info = CustomerPlanInfo(
            customer_email="test@example.com",
            plan_tier="Premium",
            sla_hours=24,
            policy_number="POL-123",
        )

        assert info.customer_email == "test@example.com"
        assert info.plan_tier == "Premium"
        assert info.sla_hours == 24
        assert info.policy_number == "POL-123"

    def test_ticket_load_info_creation(self) -> None:
        info = TicketLoadInfo(
            customer_email="test@example.com",
            open_ticket_count=5,
            open_claim_count=2,
        )

        assert info.customer_email == "test@example.com"
        assert info.open_ticket_count == 5
        assert info.open_claim_count == 2
