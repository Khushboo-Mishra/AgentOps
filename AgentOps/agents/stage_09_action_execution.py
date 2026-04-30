"""
Stage 9 — Action Execution.

Simulated execution layer. In production this would call k8s, ArgoCD,
Terraform, etc. We simulate idempotent execution of every action in the
multi-action plan whose own decision is "auto", with a deterministic
"execution id" and precomputed rollback handle.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any


def _execution_id(seed: str) -> str:
    h = hashlib.sha1(f"{seed}|{int(time.time())}".encode()).hexdigest()[:10]
    return f"exec-{h}"


def run(stage4_out: dict[str, Any], stage8_out: dict[str, Any]) -> dict[str, Any]:
    decision = stage8_out["decision"]
    plan = stage4_out.get("proposed_actions", [])

    # If the gateway didn't approve auto-execution, skip everything
    if decision != "auto_execute":
        return {
            "stage": "action_execution",
            "ok": True,
            "executed": False,
            "executed_actions": [],
            "skipped_actions": [a["title"] for a in plan],
            "execution_id": None,
            "rollback_handle": None,
            "summary": f"Action plan not executed automatically (decision={decision}).",
        }

    executed: list[dict[str, Any]] = []
    skipped: list[str] = []
    for act in plan:
        # Only auto-marked actions execute. "human" actions in the plan still
        # need approval even when the overall gateway is green.
        if act.get("decision") != "auto":
            skipped.append(act["title"])
            continue
        exec_id = _execution_id(act["command"])
        executed.append({
            "title":     act["title"],
            "command":   act["command"],
            "execution_id": exec_id,
            "rollback_handle": f"rollback-{exec_id}",
            "steps": [
                {"step": "acquire_lock",            "ok": True, "ms": 12},
                {"step": "validate_idempotency_key", "ok": True, "ms": 8},
                {"step": "apply_change",            "ok": True, "ms": 240},
                {"step": "verify_post_state",       "ok": True, "ms": 110},
            ],
        })

    primary_id = executed[0]["execution_id"] if executed else None

    return {
        "stage": "action_execution",
        "ok": True,
        "executed": len(executed) > 0,
        "executed_actions": executed,
        "skipped_actions": skipped,
        "execution_id": primary_id,
        "rollback_handle": f"rollback-{primary_id}" if primary_id else None,
        "summary": (
            f"Executed {len(executed)} action(s); skipped {len(skipped)} (require human approval)."
        ),
    }
