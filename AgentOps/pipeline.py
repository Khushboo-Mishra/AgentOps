"""
AgentOps Pipeline Orchestrator.

Threads a scenario through all 13 stages and yields stage-by-stage output
so the Streamlit UI (or any caller) can stream progress.
"""

from __future__ import annotations

from typing import Any, Iterator

from llm import LLMClient
from agents import (
    stage_01_signal_ingestion,
    stage_02_context_aggregation,
    stage_03_preprocessing,
    stage_04_reasoning,
    stage_05_confidence,
    stage_06_risk,
    stage_07_policy,
    stage_08_decision_gateway,
    stage_09_action_execution,
    stage_10_human_in_the_loop,
    stage_11_audit,
    stage_12_feedback,
    stage_13_monitoring,
)


STAGE_NAMES = [
    "1. Signal Ingestion",
    "2. Context Aggregation",
    "3. Pre-processing & Validation",
    "4. Reasoning Engine (MPPR + CoVe)",
    "5. Confidence Scoring",
    "6. Risk Scoring",
    "7. Policy / Guardrail Evaluation",
    "8. Decision Gateway",
    "9. Action Execution",
    "10. Human-in-the-Loop",
    "11. Audit & Trace Logging",
    "12. Feedback & Learning Loop",
    "13. Continuous Monitoring",
]


def run_pipeline(
    scenario: dict[str, Any],
    llm: LLMClient | None = None,
    hitl_decision: str | None = None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """
    Run all 13 stages, yielding (stage_name, stage_output) per stage.

    The caller can collect, stream, or render these incrementally.
    """
    llm = llm or LLMClient()

    out1 = stage_01_signal_ingestion.run(scenario)
    yield STAGE_NAMES[0], out1

    out2 = stage_02_context_aggregation.run(scenario, out1)
    yield STAGE_NAMES[1], out2

    out3 = stage_03_preprocessing.run(out2)
    yield STAGE_NAMES[2], out3

    out4 = stage_04_reasoning.run(scenario, out3, llm)
    yield STAGE_NAMES[3], out4

    out5 = stage_05_confidence.run(out3, out4, llm)
    yield STAGE_NAMES[4], out5

    out6 = stage_06_risk.run(scenario, out5)
    yield STAGE_NAMES[5], out6

    out7 = stage_07_policy.run(scenario, out4, out6)
    yield STAGE_NAMES[6], out7

    out8 = stage_08_decision_gateway.run(out4, out5, out6, out7)
    yield STAGE_NAMES[7], out8

    out9 = stage_09_action_execution.run(out4, out8, hitl_decision=hitl_decision)
    yield STAGE_NAMES[8], out9

    out10 = stage_10_human_in_the_loop.run(
        scenario, out4, out5, out6, out7, out8, hitl_decision=hitl_decision,
    )
    yield STAGE_NAMES[9], out10

    out11 = stage_11_audit.run(
        scenario,
        {
            "signal_ingestion": out1,
            "context_aggregation": out2,
            "preprocessing": out3,
            "reasoning": out4,
            "confidence": out5,
            "risk": out6,
            "policy": out7,
            "decision_gateway": out8,
            "action_execution": out9,
            "hitl": out10,
        },
    )
    yield STAGE_NAMES[10], out11

    out12 = stage_12_feedback.run(scenario, out5, out6, out8, out9, hitl_decision=hitl_decision)
    yield STAGE_NAMES[11], out12

    out13 = stage_13_monitoring.run(scenario, out9, out12)
    yield STAGE_NAMES[12], out13


def run_pipeline_collect(
    scenario: dict[str, Any],
    llm: LLMClient | None = None,
    hitl_decision: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Convenience wrapper that materializes the whole run as a dict."""
    return {name: out for name, out in run_pipeline(scenario, llm=llm, hitl_decision=hitl_decision)}


if __name__ == "__main__":
    # CLI quick-run for sanity checks
    import json
    from data.scenarios import SCENARIOS

    llm_client = LLMClient()
    backend = "ollama" if llm_client.is_available() else "simulation"
    print(f"LLM backend: {backend}")

    for sid, scenario in SCENARIOS.items():
        print(f"\n{'=' * 70}\nScenario: {scenario['label']}\n{'=' * 70}")
        for stage_name, stage_out in run_pipeline(scenario, llm=llm_client):
            print(f"\n--- {stage_name} ---")
            print(stage_out.get("summary", json.dumps(stage_out, default=str)[:200]))
