"""
Stage 12 — Feedback & Learning Loop.

Captures the post-incident outcome and converts it into signals the system
can learn from: prompt refinements, threshold adjustments, runbook updates.
"""

from __future__ import annotations

from typing import Any


def run(
    scenario: dict[str, Any],
    stage5_out: dict[str, Any],
    stage6_out: dict[str, Any],
    stage8_out: dict[str, Any],
    stage9_out: dict[str, Any],
    hitl_decision: str | None = None,
) -> dict[str, Any]:
    """
    Args:
        hitl_decision: one of {"approved", "rejected", None} — only relevant
                       if the decision gateway requested HITL approval.
    """
    success = False
    if stage8_out["decision"] == "auto_execute" and stage9_out["executed"]:
        success = True
    if stage8_out["decision"] == "request_hitl_approval" and hitl_decision == "approved":
        success = True

    # Heuristic learning signals
    suggestions: list[str] = []
    if stage5_out["total_confidence"] < 0.65:
        suggestions.append(
            "Confidence under 0.65 — recommend enriching runbook coverage for "
            f"'{scenario['label']}' to improve retrieval groundedness."
        )
    if stage6_out["composite_risk_score"] >= 0.7 and success:
        suggestions.append(
            "High-risk action succeeded under HITL — consider lowering AMBER threshold "
            "for this incident class after 5 successful HITL approvals (graduated autonomy)."
        )
    if not success and stage8_out["decision"] != "blocked":
        suggestions.append("Outcome unsuccessful — flag scenario for runbook review.")

    metrics = {
        "auto_resolution": stage8_out["decision"] == "auto_execute" and stage9_out["executed"],
        "human_approval_required": stage8_out["decision"] == "request_hitl_approval",
        "blocked": stage8_out["decision"] == "full_stop_handover" or stage8_out["decision"] == "blocked",
        "success": success,
    }

    return {
        "stage": "feedback",
        "ok": True,
        "success": success,
        "metrics": metrics,
        "learning_suggestions": suggestions,
        "summary": (
            f"Outcome={'success' if success else 'pending/failure'}. "
            f"{len(suggestions)} learning signal(s) emitted."
        ),
    }
