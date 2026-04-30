"""
Stage 5 — Confidence (Triangulated Certainty Score).

Replaces LLM self-reported confidence with four objectively measurable
dimensions, weighted per the framework:

  retrieval groundedness     30%
  tool-output consistency    30%
  historical success rate    20%
  model consensus            20%
"""

from __future__ import annotations

import json
import re
from typing import Any

from llm import LLMClient


GREEN_THRESHOLD = 0.85
AMBER_THRESHOLD = 0.60


def _retrieval_groundedness(ctx: dict[str, Any]) -> float:
    tsgs = ctx.get("retrieved_tsgs", [])
    if not tsgs:
        return 0.30
    avg_rel = sum(float(t.get("relevance_score", 0.5)) for t in tsgs) / len(tsgs)
    # Reward >=2 retrieved TSGs slightly
    bonus = 0.05 if len(tsgs) >= 2 else 0.0
    return min(0.99, avg_rel + bonus)


def _tool_consistency(ctx: dict[str, Any]) -> float:
    """Cross-check whether logs/traces/system_health tell the same story."""
    score = 0.6
    health = ctx.get("system_health", {})
    health_text = " ".join(
        f"{k} {v}".lower() for k, v in health.items()
    )
    log_text = "\n".join(ctx.get("recent_logs", [])).lower()
    if ("oom" in log_text or "outofmemory" in log_text) and (
        "memory" in health_text or "heap" in health_text
    ):
        score = 0.93
    elif ("connection" in log_text and "pool" in log_text) and "pool" in health_text:
        score = 0.91
    elif "504" in log_text or "p99" in log_text or "timeout" in log_text:
        score = 0.88
    elif "acme" in log_text or "challenge failed" in log_text or "cert" in log_text:
        score = 0.94
    elif "saturated" in log_text or "saturation" in health_text:
        score = 0.86
    return score


def _historical_success(ctx: dict[str, Any]) -> float:
    incidents = ctx.get("similar_past_incidents", [])
    if not incidents:
        return 0.40
    weighted = 0.0
    weight_sum = 0.0
    for inc in incidents:
        sim = float(inc.get("similarity", 0.5))
        outcome = inc.get("outcome", "partial")
        outcome_score = {"success": 1.0, "partial": 0.6, "failure": 0.1}.get(outcome, 0.5)
        weighted += sim * outcome_score
        weight_sum += sim
    return min(0.99, weighted / max(weight_sum, 0.01))


def _model_consensus(reasoning_out: dict[str, Any], llm: LLMClient) -> tuple[float, dict[str, Any]]:
    prompt = (
        "Act as a judge LLM reviewing another agent's reasoning chain for an incident. "
        "Decide if the reasoning is logically coherent and grounded. "
        "Reply as JSON: {\"verdict\": \"agrees|disagrees|partial\", \"summary\": str, \"flaws\": [str]}.\n\n"
        f"WINNING HYPOTHESIS: {reasoning_out['winning_hypothesis']['hypothesis']}\n"
        f"PROPOSED ACTION: {reasoning_out['proposed_action']}\n"
    )
    resp = llm.generate(prompt, system="You are a strict, careful judge.", max_tokens=250)
    verdict = "agrees"
    summary = resp.text
    flaws: list[str] = []
    try:
        m = re.search(r"\{[\s\S]*\}", resp.text)
        if m:
            obj = json.loads(m.group(0))
            verdict = obj.get("verdict", "agrees")
            summary = obj.get("summary", summary)
            flaws = obj.get("flaws", [])
    except Exception:
        pass

    score_map = {"agrees": 0.92, "partial": 0.65, "disagrees": 0.25}
    return score_map.get(verdict, 0.7), {
        "verdict": verdict,
        "summary": summary,
        "flaws": flaws,
        "backend": resp.backend,
    }


def _zone(score: float) -> str:
    if score >= GREEN_THRESHOLD:
        return "green"
    if score >= AMBER_THRESHOLD:
        return "amber"
    return "red"


def run(stage3_out: dict[str, Any], stage4_out: dict[str, Any], llm: LLMClient) -> dict[str, Any]:
    ctx = stage3_out["context"]

    g = _retrieval_groundedness(ctx)
    t = _tool_consistency(ctx)
    h = _historical_success(ctx)
    c, judge = _model_consensus(stage4_out, llm)

    total = round(g * 0.30 + t * 0.30 + h * 0.20 + c * 0.20, 3)
    zone = _zone(total)

    return {
        "stage": "confidence",
        "ok": True,
        "components": {
            "retrieval_groundedness": round(g, 3),
            "tool_consistency": round(t, 3),
            "historical_success": round(h, 3),
            "model_consensus": round(c, 3),
        },
        "weights": {
            "retrieval_groundedness": 0.30,
            "tool_consistency": 0.30,
            "historical_success": 0.20,
            "model_consensus": 0.20,
        },
        "judge": judge,
        "total_confidence": total,
        "decision_zone": zone,
        "summary": f"Total confidence {total:.2f} → {zone.upper()} zone.",
    }
