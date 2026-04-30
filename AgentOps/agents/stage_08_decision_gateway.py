"""
Stage 8 — Decision Gateway (Control Layer).

Combines confidence, risk, and policy signals into a single authorization
decision. Determines whether the action is auto-executed (Green),
requires HITL approval (Amber), or is fully blocked (Red).
"""

from __future__ import annotations

from typing import Any


def run(
    stage4_out: dict[str, Any],
    stage5_out: dict[str, Any],
    stage6_out: dict[str, Any],
    stage7_out: dict[str, Any],
) -> dict[str, Any]:
    confidence_zone = stage5_out["decision_zone"]
    risk_zone = stage6_out["enforced_zone"]
    policy_denied = not stage7_out["ok"]
    cove_blocked = not stage4_out["plan_approved_by_cove"]
    policy_forces_amber = bool(stage7_out["forces_amber_policy_ids"])

    reasons: list[str] = []

    # Worst-of-three for the zone
    zone_order = {"green": 0, "amber": 1, "red": 2}
    worst_zone = max(
        [confidence_zone, risk_zone, "amber" if policy_forces_amber else "green"],
        key=lambda z: zone_order[z],
    )

    if confidence_zone != "green":
        reasons.append(f"Confidence is {confidence_zone.upper()}.")
    if risk_zone != "green":
        reasons.append(f"Risk-adjusted zone is {risk_zone.upper()}.")
    if policy_forces_amber:
        reasons.append(f"Policy forces AMBER: {','.join(stage7_out['forces_amber_policy_ids'])}.")

    if policy_denied:
        decision = "blocked"
        worst_zone = "red"
        reasons.append(f"Policy denials: {[d['id'] for d in stage7_out['denials']]}.")
    elif cove_blocked:
        decision = "blocked"
        worst_zone = "red"
        reasons.append("CoVe simulation blocked the plan.")
    elif worst_zone == "green":
        decision = "auto_execute"
    elif worst_zone == "amber":
        decision = "request_hitl_approval"
    else:
        decision = "full_stop_handover"

    return {
        "stage": "decision_gateway",
        "ok": True,
        "decision": decision,
        "final_zone": worst_zone,
        "reasons": reasons or ["All gates green — autonomous execution permitted."],
        "summary": f"Gateway decision: {decision} (zone={worst_zone.upper()}).",
    }
