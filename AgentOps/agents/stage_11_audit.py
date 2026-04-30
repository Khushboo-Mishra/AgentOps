"""
Stage 11 — Audit & Trace Logging.

Builds a structured, immutable-style audit record that captures the entire
decision trail from signal to execution. In production this would be
written to an append-only store (S3 + Object Lock, BigQuery, etc.).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


AUDIT_LOG_PATH = os.environ.get(
    "AGENTOPS_AUDIT_LOG", os.path.join(os.path.dirname(__file__), "..", "audit_log.jsonl")
)


def run(scenario: dict[str, Any], stage_outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    record = {
        "audit_id": f"audit-{scenario['signal']['signal_id']}",
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "scenario_id": scenario["id"],
        "scenario_label": scenario["label"],
        "signal": scenario["signal"],
        "trail": {
            stage_name: {
                "summary": out.get("summary"),
                "ok": out.get("ok", True),
                **{k: v for k, v in out.items() if k in (
                    "decision", "final_zone", "decision_zone", "total_confidence",
                    "composite_risk_score", "executed", "execution_id",
                    "denials", "warnings", "winning_hypothesis", "proposed_action",
                    "redactions_applied", "needs_hitl",
                )},
            }
            for stage_name, out in stage_outputs.items()
        },
    }

    # Append-only log on disk for replay / compliance
    try:
        path = os.path.abspath(AUDIT_LOG_PATH)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
        wrote_path = path
    except Exception as e:
        wrote_path = f"<failed: {e}>"

    return {
        "stage": "audit",
        "ok": True,
        "audit_record": record,
        "audit_log_path": wrote_path,
        "summary": f"Audit record persisted to {wrote_path}",
    }
