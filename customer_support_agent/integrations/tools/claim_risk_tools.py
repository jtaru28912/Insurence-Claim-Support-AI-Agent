"""Claim risk analysis tools used to flag potentially suspicious narratives.

This bonus tool uses deterministic keyword heuristics so it stays
explainable, fast, and usable without another model dependency.
"""

from __future__ import annotations

from langchain_core.tools import tool

_RISK_PATTERNS: dict[str, tuple[str, int]] = {
    "no witnesses": ("No witnesses were reported.", 2),
    "witnesses unavailable": ("Witnesses were mentioned but are unavailable.", 2),
    "urgent payout": ("The claimant is pushing for an unusually urgent payout.", 2),
    "cash only": ("The narrative references cash-only repair or settlement handling.", 2),
    "brand new policy": ("The loss appears soon after policy inception.", 2),
    "just bought": ("The insured asset was described as newly purchased before the loss.", 1),
    "police report unavailable": ("A police report was expected but is unavailable.", 2),
    "camera not working": ("Expected recording evidence was unavailable.", 1),
    "contradict": ("The narrative includes contradiction language.", 3),
    "inconsistent": ("The narrative includes inconsistency language.", 3),
    "hit and run": ("Hit-and-run wording suggests extra verification is appropriate.", 1),
    "late night": ("Late-night incident timing can reduce independent evidence.", 1),
    "stolen twice": ("Repeated theft wording may indicate a prior-loss pattern.", 2),
}


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _classify_risk(total_score: int) -> tuple[str, float]:
    if total_score >= 5:
        return "high", 0.9
    if total_score >= 3:
        return "medium", 0.7
    if total_score >= 1:
        return "low", 0.55
    return "low", 0.35


@tool
def analyze_claim_risk(claim_narrative: str, claim_type: str | None = None) -> dict:
    """Assess fraud-risk signals in a claim narrative using transparent keyword rules."""
    normalized_narrative = _normalize_text(claim_narrative)
    normalized_claim_type = _normalize_text(claim_type)

    fraud_signals: list[str] = []
    total_score = 0
    for keyword, (signal, weight) in _RISK_PATTERNS.items():
        if keyword in normalized_narrative:
            fraud_signals.append(signal)
            total_score += weight

    if "theft" in normalized_claim_type and "police" not in normalized_narrative:
        fraud_signals.append("Theft-related claim without an explicit police-report reference.")
        total_score += 2

    risk_level, confidence = _classify_risk(total_score)
    summary = (
        f"Detected {len(fraud_signals)} potential fraud-risk signal(s) in the narrative."
        if fraud_signals
        else "No explicit fraud-risk keywords were detected in the narrative."
    )
    if risk_level == "high":
        recommended_action = (
            "Escalate for supervisor or fraud-review handling before finalizing coverage guidance."
        )
    elif risk_level == "medium":
        recommended_action = (
            "Request stronger documentation and verify chronology before recommending settlement."
        )
    else:
        recommended_action = "Continue standard intake and document collection."

    return {
        "risk_level": risk_level,
        "confidence": confidence,
        "fraud_signals": fraud_signals,
        "summary": summary,
        "recommended_action": recommended_action,
    }
