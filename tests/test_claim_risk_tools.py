"""Tests for the deterministic claim risk analysis tool."""

from __future__ import annotations

from customer_support_agent.integrations.tools.claim_risk_tools import analyze_claim_risk


def test_analyze_claim_risk_flags_high_risk_narrative() -> None:
    result = analyze_claim_risk.invoke(
        {
            "claim_narrative": (
                "Late night hit and run, no witnesses, police report unavailable, "
                "and the claimant wants an urgent payout."
            ),
            "claim_type": "Auto Collision",
        }
    )

    assert result["risk_level"] == "high"
    assert result["confidence"] >= 0.9
    assert len(result["fraud_signals"]) >= 3


def test_analyze_claim_risk_handles_clean_narrative() -> None:
    result = analyze_claim_risk.invoke(
        {
            "claim_narrative": "Rear-ended at a traffic light with photos and police report attached.",
            "claim_type": "Auto Collision",
        }
    )

    assert result["risk_level"] == "low"
    assert result["fraud_signals"] == []
    assert "No explicit fraud-risk keywords" in result["summary"]
