"""
Stage 4 — Multi-Path Probabilistic Reasoning (MPPR).

Generates competing hypotheses (LLM if available, scenario fixtures otherwise),
selects the highest-scoring, builds a multi-step remediation plan, and runs a
Chain-of-Verification (CoVe) pre-flight check on each proposed action.
"""

from __future__ import annotations

import json
import re
from typing import Any

from llm import LLMClient


def _try_parse_hypotheses(text: str) -> list[dict[str, Any]] | None:
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "hypotheses" in obj:
            return obj["hypotheses"]
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict) and "hypotheses" in obj:
                return obj["hypotheses"]
        except Exception:
            return None
    return None


def _cove_check(action_text: str) -> list[str]:
    violations: list[str] = []
    a = action_text.lower()
    if any(v in a for v in [" delete ", "drop table", "rm -rf", "truncate "]):
        # Allow `kubectl delete certificaterequest` (a routine cert-manager op)
        if "certificaterequest" not in a:
            violations.append("Destructive verb detected — blocked.")
    if "force" in a and "production" in a:
        violations.append("Force-mode production change — blocked.")
    return violations


def run(scenario: dict[str, Any], stage3_out: dict[str, Any], llm: LLMClient) -> dict[str, Any]:
    ctx = stage3_out["context"]
    signal = ctx["signal"]

    # ----- Hypothesis generation -----
    prompt = (
        "You are a senior SRE assisting with incident triage. Given the signal "
        "and context below, produce three competing hypotheses for root cause. "
        "Return JSON of the form: {\"hypotheses\": [{\"hypothesis\": str, \"prior\": float}]}.\n\n"
        f"SIGNAL: {signal.get('normalized_summary','')}\n"
        f"SERVICE: {signal.get('service','')}\n"
        f"RECENT LOGS:\n" + "\n".join(ctx.get("recent_logs", [])[:5]) + "\n"
        f"SYSTEM HEALTH: {ctx.get('system_health', {})}\n"
        f"RECENT DEPLOYS: {ctx.get('recent_deployments', [])}\n"
    )
    llm_resp = llm.generate(prompt, system="You are a careful, conservative SRE.", max_tokens=400)

    hypotheses = None
    used_scenario_fixtures = False
    # Prefer the scenario's rich, pre-baked hypotheses whenever the LLM is in
    # simulation mode — the demo content is more specific than the generic
    # template the simulator emits. With real Ollama, parse the LLM output.
    expected = scenario.get("expected_hypotheses", [])
    if llm_resp.backend == "simulation" and expected:
        hypotheses = [
            {"hypothesis": h["hypothesis"], "prior": h["prior"], "detail": h.get("detail", "")}
            for h in expected
        ]
        used_scenario_fixtures = True
    else:
        hypotheses = _try_parse_hypotheses(llm_resp.text)
        if not hypotheses and expected:
            hypotheses = [
                {"hypothesis": h["hypothesis"], "prior": h["prior"], "detail": h.get("detail", "")}
                for h in expected
            ]
            used_scenario_fixtures = True
    if not hypotheses:
        hypotheses = [
            {"hypothesis": "Infrastructure-level resource exhaustion", "prior": 0.45},
            {"hypothesis": "Application logic regression", "prior": 0.35},
            {"hypothesis": "External dependency degradation", "prior": 0.20},
        ]

    # Posterior bump from runbook keyword overlap
    runbook_text = " ".join(t.get("content", "") for t in ctx.get("retrieved_tsgs", [])).lower()
    for h in hypotheses:
        boost = 0.0
        for word in re.findall(r"[a-z]{4,}", h["hypothesis"].lower()):
            if word in runbook_text:
                boost += 0.02
        h["posterior"] = min(0.99, float(h.get("prior", 0.33)) + boost)

    winning = max(hypotheses, key=lambda h: h["posterior"])

    # ----- Reasoning narrative -----
    narrative = scenario.get("expected_reasoning_narrative", "")
    if llm_resp.backend == "ollama" and llm_resp.text and not used_scenario_fixtures:
        narrative = narrative + "\n\n[LLM augment]\n" + llm_resp.text.strip()[:600]

    # ----- Multi-action plan -----
    expected_actions = scenario.get("expected_actions", [])
    proposed_actions: list[dict[str, Any]] = []
    for act in expected_actions:
        violations = _cove_check(act["command"])
        proposed_actions.append({
            "title": act["title"],
            "description": act["description"],
            "command": act["command"],
            "decision": act["decision"],
            "risk": act["risk"],
            "confidence": act["confidence"],
            "cove_violations": violations,
            "cove_approved": len(violations) == 0,
        })

    primary_action = proposed_actions[0] if proposed_actions else {
        "title": "Apply standard remediation",
        "description": "Apply the standard runbook for this incident class.",
        "command": "# manual",
        "decision": "human", "risk": "medium", "confidence": 0.6,
        "cove_violations": [], "cove_approved": True,
    }

    plan_approved = all(a["cove_approved"] for a in proposed_actions) if proposed_actions else True

    summary = (
        f"Selected: '{winning['hypothesis']}' (posterior={winning['posterior']:.2f}). "
        f"{len(proposed_actions)} action(s) planned. CoVe approved={plan_approved}."
    )

    return {
        "stage": "reasoning",
        "ok": True,
        "llm_backend": llm_resp.backend,
        "llm_latency_ms": llm_resp.latency_ms,
        "used_scenario_fixtures": used_scenario_fixtures,
        "hypotheses": hypotheses,
        "winning_hypothesis": winning,
        "reasoning_narrative": narrative,
        "proposed_actions": proposed_actions,
        "proposed_action": primary_action["description"] + " — " + primary_action["command"],
        "primary_action": primary_action,
        "plan_approved_by_cove": plan_approved,
        "stall_triggered": False,
        "trace_steps": [
            {"step": "Generated 3 hypotheses", "backend": llm_resp.backend},
            {"step": f"Selected winning hypothesis (posterior {winning['posterior']:.2f})"},
            {"step": f"Built multi-action plan ({len(proposed_actions)} actions)"},
            {"step": f"CoVe pre-flight check — {'all approved' if plan_approved else 'one or more blocked'}"},
        ],
        "summary": summary,
    }
