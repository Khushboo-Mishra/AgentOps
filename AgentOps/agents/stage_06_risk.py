"""
Stage 6 — Dynamic Impact & Liability Matrix (Risk Scoring).

Computes risk along three axes (irreversibility, blast radius, data gravity)
then enforces the Risk-Confidence Intersection rule: even very high
confidence cannot bypass HITL for irreversible or PII/PHI/PCI actions.
"""

from __future__ import annotations

from typing import Any


IRREVERSIBILITY_SCORES = {
    "reversible": 0.20,
    "semi_reversible": 0.55,
    "irreversible": 0.95,
}


def _blast_radius_score(services_affected: list[str], total_services: int = 50) -> float:
    if not services_affected:
        return 0.10
    if "all-customer-traffic" in services_affected or "all-public-apis" in services_affected:
        return 0.95
    pct = len(services_affected) / max(total_services, 1)
    return min(0.95, max(0.15, pct * 4.0))  # 1 svc / 50 = 0.08 -> floor 0.15


def _data_gravity_score(gravity: dict[str, bool]) -> float:
    if gravity.get("phi"):
        return 1.0
    if gravity.get("pci"):
        return 0.9
    if gravity.get("pii"):
        return 0.8
    return 0.1


def run(scenario: dict[str, Any], stage5_out: dict[str, Any]) -> dict[str, Any]:
    tuning = scenario.get("tuning", {})

    irrev_label = tuning.get("irreversibility", "semi_reversible")
    irrev = IRREVERSIBILITY_SCORES.get(irrev_label, 0.55)

    blast_services = tuning.get("blast_radius_services", [])
    blast = _blast_radius_score(blast_services)

    gravity = tuning.get("data_gravity", {"pii": False, "phi": False, "pci": False})
    grav = _data_gravity_score(gravity)

    composite = round(irrev * 0.4 + blast * 0.3 + grav * 0.3, 3)
    risk_level = "high" if composite >= 0.7 else "medium" if composite >= 0.4 else "low"

    # ----- Risk-Confidence Intersection -----
    confidence = stage5_out["total_confidence"]
    confidence_zone = stage5_out["decision_zone"]

    intersection_rule = None
    enforced_zone = confidence_zone

    if irrev_label == "irreversible":
        intersection_rule = "Irreversible action — forces AMBER even at high confidence."
        if enforced_zone == "green":
            enforced_zone = "amber"

    if grav >= 0.8:
        intersection_rule = (intersection_rule + " " if intersection_rule else "") + (
            "Action touches PII/PHI/PCI — forces AMBER."
        )
        if enforced_zone == "green":
            enforced_zone = "amber"

    if confidence < 0.60:
        intersection_rule = (intersection_rule + " " if intersection_rule else "") + (
            "Confidence below 0.60 — RED full-stop."
        )
        enforced_zone = "red"

    return {
        "stage": "risk",
        "ok": True,
        "components": {
            "irreversibility_score": round(irrev, 3),
            "irreversibility_label": irrev_label,
            "blast_radius_score": round(blast, 3),
            "blast_radius_services": blast_services,
            "data_gravity_score": round(grav, 3),
            "data_gravity": gravity,
        },
        "composite_risk_score": composite,
        "risk_level": risk_level,
        "confidence_at_intersection": confidence,
        "enforced_zone": enforced_zone,
        "intersection_rule_triggered": intersection_rule is not None,
        "intersection_rule": intersection_rule,
        "summary": (
            f"Risk={composite:.2f} ({risk_level}). Enforced zone after intersection: "
            f"{enforced_zone.upper()}."
        ),
    }
