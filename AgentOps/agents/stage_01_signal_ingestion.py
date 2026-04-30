"""
Stage 1 — Signal / Event Ingestion.

Normalizes a raw incident signal into the canonical envelope used by the rest
of the pipeline, performs lightweight dedup + prioritization, and emits a
machine-readable result.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


# In-process dedup window so successive runs of the same signal don't fan out.
_RECENT_SIGNALS: dict[str, str] = {}


def _dedup_key(signal: dict[str, Any]) -> str:
    base = f"{signal.get('service','?')}|{signal.get('signal_type','?')}|{signal.get('severity','?')}"
    return hashlib.md5(base.encode()).hexdigest()


def run(scenario: dict[str, Any]) -> dict[str, Any]:
    signal = dict(scenario["signal"])  # shallow copy

    # ensure required fields
    signal.setdefault("ingested_at", datetime.now(timezone.utc).isoformat())

    # dedup
    key = _dedup_key(signal)
    is_dup = key in _RECENT_SIGNALS
    _RECENT_SIGNALS[key] = signal["signal_id"]

    # prioritization
    severity_priority = {"critical": 1, "high": 2, "medium": 3, "low": 4}
    priority = severity_priority.get(signal.get("severity", "medium"), 3)

    return {
        "stage": "signal_ingestion",
        "ok": True,
        "signal": signal,
        "deduplicated": is_dup,
        "priority": priority,
        "summary": (
            f"Ingested {signal.get('severity','?')} signal from "
            f"{signal.get('source','?')} for service "
            f"{signal.get('service','?')}: {signal.get('normalized_summary','')}"
        ),
    }
