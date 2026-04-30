"""
Stage 2 — Context Aggregation.

Pulls everything the agent needs in order to reason: recent logs, traces,
system health, deployments, runbooks (TSGs), similar past incidents.

In production this would call Elasticsearch, Prometheus, vector search, etc.
For the demo we lift the fields straight off the scenario fixture.
"""

from __future__ import annotations

from typing import Any


def run(scenario: dict[str, Any], stage1_out: dict[str, Any]) -> dict[str, Any]:
    ctx = scenario["context"]

    aggregated = {
        "signal": stage1_out["signal"],
        "recent_logs": ctx.get("recent_logs", []),
        "active_traces": ctx.get("active_traces", []),
        "system_health": ctx.get("system_health", {}),
        "recent_deployments": ctx.get("recent_deployments", []),
        "retrieved_tsgs": ctx.get("retrieved_tsgs", []),
        "similar_past_incidents": ctx.get("similar_past_incidents", []),
        "oncall_info": ctx.get("oncall_info", {}),
    }

    # Approximate latency budget reporting (illustrative only)
    latencies = {
        "metadata_lookup_ms": 240,
        "log_search_ms": 1100,
        "vector_search_ms": 1850,
    }

    summary = (
        f"Aggregated context: {len(aggregated['recent_logs'])} log lines, "
        f"{len(aggregated['active_traces'])} traces, "
        f"{len(aggregated['retrieved_tsgs'])} TSGs, "
        f"{len(aggregated['similar_past_incidents'])} similar past incidents."
    )

    return {
        "stage": "context_aggregation",
        "ok": True,
        "context": aggregated,
        "retrieval_latency_ms": latencies,
        "summary": summary,
    }
