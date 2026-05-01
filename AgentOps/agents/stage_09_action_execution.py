"""
Stage 9 — Action Execution.

Simulated execution layer. Executes the plan when:
  - the gateway is GREEN (auto_execute), OR
  - the gateway is AMBER and a human approved via HITL.

When AMBER + approved-by-human, every action in the plan executes
(including ones individually marked "human" — the human just approved them).
When AMBER + rejected, nothing executes.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any


def _execution_id(seed: str) -> str:
    h = hashlib.sha1(f"{seed}|{int(time.time())}".encode()).hexdigest()[:10]
    return f"exec-{h}"


def run(
    stage4_out: dict[str, Any],
    stage8_out: dict[str, Any],
    hitl_decision: str | None = None,
) -> dict[str, Any]:
    decision = stage8_out["decision"]
    plan = stage4_out.get("proposed_actions", [])

    # Determine execution mode
    auto_mode = decision == "auto_execute"
    hitl_approved = decision == "request_hitl_approval" and hitl_decision == "approved"

    if not auto_mode and not hitl_approved:
        # AMBER+rejected, RED+anything, blocked, or AMBER awaiting decision
        reason = (
            "rejected by human" if hitl_decision == "rejected"
            else f"awaiting human decision (gateway={decision})" if decision == "request_hitl_approval"
            else f"not executed (gateway={decision})"
        )
        return {
            "stage": "action_execution",
            "ok": True,
            "executed": False,
            "executed_actions": [],
            "skipped_actions": [a["title"] for a in plan],
            "execution_id": None,
            "rollback_handle": None,
            "execution_mode": "blocked",
            "summary": f"Action plan {reason}.",
        }

    executed: list[dict[str, Any]] = []
    skipped: list[str] = []
    for act in plan:
        # In auto mode: only "auto" actions execute
        # In hitl_approved mode: ALL actions execute (human signed off)
        if auto_mode and act.get("decision") != "auto":
            skipped.append(act["title"])
            continue
        exec_id = _execution_id(act["command"])
        executed.append({
            "title":     act["title"],
            "command":   act["command"],
            "execution_id": exec_id,
            "rollback_handle": f"rollback-{exec_id}",
            "steps": [
                {"step": "acquire_lock",             "ok": True, "ms": 12},
                {"step": "validate_idempotency_key", "ok": True, "ms": 8},
                {"step": "apply_change",             "ok": True, "ms": 240},
                {"step": "verify_post_state",        "ok": True, "ms": 110},
            ],
        })

    primary_id = executed[0]["execution_id"] if executed else None
    mode = "auto" if auto_mode else "hitl_approved"

    return {
        "stage": "action_execution",
        "ok": True,
        "executed": len(executed) > 0,
        "executed_actions": executed,
        "skipped_actions": skipped,
        "execution_id": primary_id,
        "rollback_handle": f"rollback-{primary_id}" if primary_id else None,
        "execution_mode": mode,
        "summary": (
            f"[{mode}] Executed {len(executed)} action(s); skipped {len(skipped)}."
        ),
    }
