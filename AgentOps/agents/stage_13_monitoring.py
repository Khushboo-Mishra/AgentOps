"""
Stage 13 — Continuous Monitoring (post-action).

After an action is taken (or HITL approves one), this stage re-checks the
system to verify resolution, detect regressions, and decide whether to
re-trigger the loop.

Uses the scenario's pre-baked before/after metrics for the demo dashboard.
"""

from __future__ import annotations

from typing import Any


def run(
    scenario: dict[str, Any],
    stage9_out: dict[str, Any],
    stage12_out: dict[str, Any],
) -> dict[str, Any]:
    executed = stage9_out["executed"]
    success = stage12_out["success"]

    before_after = scenario.get("before_after_metrics", [])

    # Time-series snapshots over a 5-minute window
    if not executed:
        snapshot = {
            "1m": "no change — awaiting human decision",
            "3m": "no change — awaiting human decision",
            "5m": "no change — awaiting human decision",
        }
        regression = False
        stable = False
    else:
        sid = scenario["id"]
        snapshots_by_id = {
            "db_pool_exhausted": {
                "1m": "pool 380/750 (51%); error rate 4%",
                "3m": "pool 210/750 (28%); error rate 0.6%",
                "5m": "pool 127/750 (17%); error rate 0.2%",
            },
            "oom_crash_loop": {
                "1m": "memory 88% → 71%; restarts halted",
                "3m": "memory 60%; replicas 4/6 ready",
                "5m": "memory 54%; replicas 6/6 ready",
            },
            "api_p99_latency_spike": {
                "1m": "circuit breaker active; P99 7.1s; 504/min 800",
                "3m": "index build 60%; P99 1.8s; 504/min 14",
                "5m": "index built; P99 235ms; 504/min 0",
            },
            "tls_cert_expiring": {
                "1m": "@security-team paged; awaiting IAM approval",
                "3m": "IAM patch applied; renewal retry queued",
                "5m": "cert renewed (89d valid); 12 ingress reloaded",
            },
        }
        snapshot = snapshots_by_id.get(sid, {"1m": "ok", "3m": "ok", "5m": "ok"})
        regression = False
        stable = success

    retrigger = regression or (executed and not stable)

    return {
        "stage": "continuous_monitoring",
        "ok": True,
        "post_action_snapshots": snapshot,
        "before_after_metrics": before_after,
        "regression_detected": regression,
        "stable": stable,
        "retrigger_loop": retrigger,
        "summary": (
            f"Post-action monitoring: stable={stable}, regression={regression}, "
            f"retrigger={retrigger}."
        ),
    }
