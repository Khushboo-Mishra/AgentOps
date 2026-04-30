"""
Stage 10 — Human-in-the-Loop Interface.

Builds the HITL approval payload that the Streamlit UI presents to the
on-call engineer when the decision gateway lands in AMBER (or any time
HITL is forced by policy / risk intersection).
"""

from __future__ import annotations

from typing import Any


def run(
    scenario: dict[str, Any],
    stage4_out: dict[str, Any],
    stage5_out: dict[str, Any],
    stage6_out: dict[str, Any],
    stage7_out: dict[str, Any],
    stage8_out: dict[str, Any],
) -> dict[str, Any]:
    decision = stage8_out["decision"]
    needs_hitl = decision in ("request_hitl_approval", "full_stop_handover")

    summary_card = {
        "incident": scenario["label"],
        "service": scenario["signal"]["service"],
        "severity": scenario["signal"]["severity"],
        "winning_hypothesis": stage4_out["winning_hypothesis"]["hypothesis"],
        "proposed_action": stage4_out["proposed_action"],
        "confidence": stage5_out["total_confidence"],
        "risk_score": stage6_out["composite_risk_score"],
        "policy_compliance_tags": stage7_out["compliance_tags"],
        "final_zone": stage8_out["final_zone"],
        "reasons": stage8_out["reasons"],
        "oncall": scenario["context"].get("oncall_info", {}),
    }

    options = (
        ["approve_and_execute", "reject", "modify_then_approve", "escalate"]
        if needs_hitl
        else ["informational_review_only"]
    )

    return {
        "stage": "human_in_the_loop",
        "ok": True,
        "needs_hitl": needs_hitl,
        "summary_card": summary_card,
        "available_options": options,
        "summary": (
            "HITL approval required" if needs_hitl else "No HITL needed — informational only"
        ),
    }
