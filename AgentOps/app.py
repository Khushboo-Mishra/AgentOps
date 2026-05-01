"""
AgentOps — Streamlit UI

Run with:
    pip install -r requirements.txt
    streamlit run app.py

If Ollama is running locally with `mistral:7b` pulled, the agent will use it.
Otherwise the pipeline transparently falls back to deterministic simulation
that uses each scenario's pre-baked reasoning narrative + action plan.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm import LLMClient
from data.scenarios import SCENARIOS, scenario_labels
from pipeline import run_pipeline, STAGE_NAMES


st.set_page_config(page_title="AgentOps — Incident Response Pipeline", layout="wide")

# ---- Light styling for monospace command blocks etc.
st.markdown(
    """
    <style>
    .agentops-cmd {
        background: #0f1117; color: #34d399;
        font-family: ui-monospace, 'SF Mono', Menlo, monospace;
        font-size: 12px; padding: 8px 10px; border-radius: 6px;
        border: 1px solid #2d3748; overflow-x: auto;
        white-space: pre; margin-top: 4px;
    }
    .agentops-narrative {
        background: #161b27; color: #cbd5e1;
        font-family: ui-monospace, 'SF Mono', Menlo, monospace;
        font-size: 12px; padding: 12px 14px; border-radius: 6px;
        border: 1px solid #2d3748; white-space: pre-wrap; line-height: 1.55;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.title("AgentOps")
    st.caption("13-stage AI agent pipeline for production incident response")

    label_pairs = scenario_labels()
    label_to_id = {label: sid for sid, label in label_pairs}
    chosen_label = st.selectbox("Incident scenario", list(label_to_id.keys()), index=0)
    scenario_id = label_to_id[chosen_label]
    scenario = SCENARIOS[scenario_id]

    st.divider()
    st.subheader("LLM backend")
    llm = LLMClient()
    backend = llm.active_backend
    if backend == "groq":
        st.success(f"Groq API — using `{llm.active_model}`")
    elif backend == "ollama":
        st.success(f"Ollama detected — using `{llm.active_model}`")
    else:
        st.warning(
            "No LLM backend reachable — using simulation.\n\n"
            "Local: `ollama serve` and `ollama pull mistral:7b`\n\n"
            "Cloud: set `GROQ_API_KEY` in Streamlit secrets."
        )

    st.divider()
    st.subheader("HITL decision")
    st.caption("Used by Stage 12 if the gateway requests human approval.")
    hitl_decision = st.radio(
        "If approval requested, simulate:",
        ["approved", "rejected", "no decision yet"],
        index=0, label_visibility="collapsed",
    )
    hitl_decision_value = None if hitl_decision == "no decision yet" else hitl_decision

    st.divider()
    run_btn = st.button("Run pipeline", type="primary", use_container_width=True)


# --------------------------------------------------------------------------
# Header + scenario dashboard
# --------------------------------------------------------------------------
st.title("AgentOps Incident Response")
st.caption(
    "Apexon × NYU — production agent operations framework. "
    "Pick a scenario in the sidebar and run the 13-stage pipeline."
)

col_a, col_b, col_c, col_d = st.columns([2, 1, 1, 1])
col_a.markdown(f"**Scenario:** {scenario['label']}")
col_b.markdown(f"**Service:** `{scenario['signal']['service']}`")
col_c.markdown(f"**Severity:** `{scenario['signal']['severity']}`")
col_d.markdown(f"**Category:** `{scenario['category']}`")

# Live metrics dashboard (pre-incident state)
st.markdown("##### Current state")
dash = scenario.get("metrics_dashboard", [])
if dash:
    cols = st.columns(len(dash))
    color_map = {"red": "🔴", "yellow": "🟡", "green": "🟢"}
    for col, m in zip(cols, dash):
        col.metric(
            label=f"{color_map.get(m['color'], '⚪')} {m['label']}",
            value=m["value"],
            delta=m["sub"],
            delta_color="off",
        )

with st.expander("Raw signal envelope"):
    st.json(scenario["signal"])


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
ZONE_BADGE = {
    "green": ":green[GREEN — autonomous]",
    "amber": ":orange[AMBER — HITL approval]",
    "red":   ":red[RED — full stop]",
}


def _cmd_block(cmd: str) -> str:
    safe = cmd.replace("<", "&lt;").replace(">", "&gt;")
    return f'<div class="agentops-cmd">{safe}</div>'


def _narrative_block(text: str) -> str:
    safe = text.replace("<", "&lt;").replace(">", "&gt;")
    return f'<div class="agentops-narrative">{safe}</div>'


def render_stage(name: str, out: dict[str, Any]):
    with st.expander(name, expanded=True):
        if "summary" in out:
            st.markdown(f"**Summary:** {out['summary']}")

        stage = out.get("stage")

        if stage == "signal_ingestion":
            sig = out["signal"]
            st.markdown(
                f"**Source:** `{sig.get('source')}` · "
                f"**Severity:** `{sig.get('severity')}` · "
                f"**Priority:** {out['priority']} · "
                f"**Deduplicated:** {'yes' if out['deduplicated'] else 'no'}"
            )

        elif stage == "context_aggregation":
            cols = st.columns(3)
            ctx = out["context"]
            cols[0].metric("Log lines",      len(ctx.get("recent_logs", [])))
            cols[1].metric("Traces",          len(ctx.get("active_traces", [])))
            cols[2].metric("Runbooks",        len(ctx.get("retrieved_tsgs", [])))
            st.markdown("**Recent logs:**")
            log_text = "\n".join(ctx.get("recent_logs", []))
            st.markdown(_narrative_block(log_text), unsafe_allow_html=True)
            with st.expander("System health"):
                st.json(ctx.get("system_health", {}))
            with st.expander("Retrieved runbooks"):
                for t in ctx.get("retrieved_tsgs", []):
                    st.markdown(f"- **{t['title']}** _(relevance {t['relevance_score']:.2f})_  \n  {t['content']}")
            with st.expander("Similar past incidents"):
                for i in ctx.get("similar_past_incidents", []):
                    st.markdown(
                        f"- **{i['id']}** _(similarity {i.get('similarity', 0):.2f})_  \n"
                        f"  {i.get('summary','')}  \n"
                        f"  Resolution: {i.get('resolution','')}"
                    )

        elif stage == "preprocessing":
            cols = st.columns(2)
            cols[0].metric("Redaction rules triggered", len(out["redactions_applied"]))
            cols[1].metric("Context complete", "no" if out["context_incomplete"] else "yes")

        elif stage == "reasoning":
            st.markdown(
                f"**LLM backend:** `{out['llm_backend']}` · "
                f"**latency:** {out['llm_latency_ms']} ms · "
                f"**CoVe:** {'✅ all approved' if out['plan_approved_by_cove'] else '❌ blocked'}"
            )
            cols = st.columns(3)
            for i, h in enumerate(out["hypotheses"][:3]):
                with cols[i]:
                    st.metric(
                        f"Hypothesis {i+1}",
                        f"{h.get('posterior', h.get('prior', 0)):.2f}",
                        h["hypothesis"][:55] + ("…" if len(h["hypothesis"]) > 55 else ""),
                    )
                    if h.get("detail"):
                        st.caption(h["detail"])
            st.markdown(f"**Winning hypothesis:** _{out['winning_hypothesis']['hypothesis']}_")
            if out.get("reasoning_narrative"):
                st.markdown("**Reasoning trace:**")
                st.markdown(_narrative_block(out["reasoning_narrative"]), unsafe_allow_html=True)

            st.markdown("**Proposed remediation plan:**")
            risk_color = {"low": "green", "medium": "yellow", "high": "red"}
            dec_label = {"auto": "AUTO", "human": "HITL", "escalate": "ESCALATE"}
            for i, a in enumerate(out["proposed_actions"], 1):
                with st.container(border=True):
                    head_cols = st.columns([4, 1, 1, 1])
                    head_cols[0].markdown(f"**{i}. {a['title']}**")
                    head_cols[1].markdown(f":{risk_color.get(a['risk'],'gray')}[{a['risk'].upper()} RISK]")
                    head_cols[2].markdown(f"`{dec_label.get(a['decision'], a['decision'].upper())}`")
                    head_cols[3].markdown(f"conf {a['confidence']:.2f}")
                    st.caption(a["description"])
                    st.markdown(_cmd_block(a["command"]), unsafe_allow_html=True)
                    if a["cove_violations"]:
                        st.error(f"CoVe blocked: {a['cove_violations']}")

        elif stage == "confidence":
            cols = st.columns(4)
            for col, (k, v) in zip(cols, out["components"].items()):
                col.metric(k.replace("_", " ").title(), f"{v:.2f}")
            st.markdown(
                f"**Total confidence:** `{out['total_confidence']:.2f}` → "
                f"{ZONE_BADGE.get(out['decision_zone'], out['decision_zone'])}"
            )
            st.markdown(f"**Judge verdict:** `{out['judge']['verdict']}` — {out['judge']['summary']}")

        elif stage == "risk":
            cols = st.columns(3)
            comp = out["components"]
            cols[0].metric("Irreversibility", f"{comp['irreversibility_score']:.2f}",
                           comp["irreversibility_label"])
            cols[1].metric("Blast radius", f"{comp['blast_radius_score']:.2f}",
                           ", ".join(comp["blast_radius_services"]) or "none")
            cols[2].metric("Data gravity", f"{comp['data_gravity_score']:.2f}",
                           ", ".join(k.upper() for k, v in comp["data_gravity"].items() if v) or "none")
            st.markdown(
                f"**Composite risk:** `{out['composite_risk_score']:.2f}` "
                f"({out['risk_level']}) → enforced zone "
                f"{ZONE_BADGE.get(out['enforced_zone'], out['enforced_zone'])}"
            )
            if out.get("intersection_rule"):
                st.warning(f"Intersection rule: {out['intersection_rule']}")

        elif stage == "policy":
            st.markdown(
                f"**Policy version:** `{out['policy_version']}` · "
                f"**RBAC authorized:** {'✅' if out['rbac_authorized'] else '❌'}"
            )
            if out["compliance_tags"]:
                st.markdown(f"**Compliance tags:** {', '.join(out['compliance_tags'])}")
            if out["denials"]:
                st.error(f"Denials: {[d['name'] for d in out['denials']]}")
            if out["warnings"]:
                st.warning(f"Warnings: {[w['name'] for w in out['warnings']]}")
            if out["forces_amber_policy_ids"]:
                st.info(f"Force-AMBER policies: {out['forces_amber_policy_ids']}")

        elif stage == "decision_gateway":
            st.markdown(
                f"**Decision:** `{out['decision']}` → "
                f"{ZONE_BADGE.get(out['final_zone'], out['final_zone'])}"
            )
            st.markdown("**Reasons:**")
            for r in out["reasons"]:
                st.markdown(f"- {r}")

        elif stage == "action_execution":
            executed_actions = out.get("executed_actions", [])
            skipped = out.get("skipped_actions", [])
            if executed_actions:
                st.success(f"Executed {len(executed_actions)} action(s)")
                for a in executed_actions:
                    st.markdown(f"**▶ {a['title']}** — `{a['execution_id']}`")
                    st.markdown(_cmd_block(a["command"]), unsafe_allow_html=True)
                    st.dataframe(a["steps"], hide_index=True, use_container_width=True)
            if skipped:
                st.info(f"Skipped (require human approval): {skipped}")
            if not executed_actions and not skipped:
                st.info("Action plan not auto-executed.")

        elif stage == "human_in_the_loop":
            if out["needs_hitl"]:
                st.warning("Human approval required.")
                st.json(out["summary_card"])
                st.markdown(f"**Available options:** {out['available_options']}")
            else:
                st.success("No HITL needed — informational only.")

        elif stage == "audit":
            st.markdown(f"**Audit log:** `{out['audit_log_path']}`")
            with st.expander("Full audit record (JSON)"):
                st.json(out["audit_record"])

        elif stage == "feedback":
            cols = st.columns(4)
            cols[0].metric("Auto-resolved",   "yes" if out["metrics"]["auto_resolution"] else "no")
            cols[1].metric("HITL required",   "yes" if out["metrics"]["human_approval_required"] else "no")
            cols[2].metric("Blocked",         "yes" if out["metrics"]["blocked"] else "no")
            cols[3].metric("Success",         "yes" if out["success"] else "no")
            if out["learning_suggestions"]:
                st.markdown("**Learning signals:**")
                for s in out["learning_suggestions"]:
                    st.markdown(f"- {s}")

        elif stage == "continuous_monitoring":
            cols = st.columns(3)
            for col, (k, v) in zip(cols, out["post_action_snapshots"].items()):
                col.metric(f"+{k}", v)
            st.markdown(
                f"**Stable:** {'✅' if out['stable'] else '❌'} · "
                f"**Regression:** {'⚠️' if out['regression_detected'] else 'none'} · "
                f"**Re-trigger loop:** {'yes' if out['retrigger_loop'] else 'no'}"
            )
            ba = out.get("before_after_metrics", [])
            if ba:
                st.markdown("**Before / After:**")
                table = [{"Metric": m["label"], "Before": m["before"], "After": m["after"]} for m in ba]
                st.dataframe(table, hide_index=True, use_container_width=True)

        else:
            with st.expander("Raw output"):
                st.json(out)


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------
if run_btn:
    progress = st.progress(0.0, text="Starting pipeline…")
    container = st.container()
    total = len(STAGE_NAMES)

    final_outputs: dict[str, dict[str, Any]] = {}
    for i, (stage_name, out) in enumerate(
        run_pipeline(scenario, llm=llm, hitl_decision=hitl_decision_value), start=1
    ):
        final_outputs[stage_name] = out
        with container:
            render_stage(stage_name, out)
        progress.progress(i / total, text=f"Completed: {stage_name}")

    progress.empty()
    st.success("Pipeline complete.")

    final_zone = final_outputs[STAGE_NAMES[7]]["final_zone"]
    decision = final_outputs[STAGE_NAMES[7]]["decision"]
    st.markdown("---")
    st.subheader("Final outcome")
    cols = st.columns(3)
    cols[0].metric("Final zone", final_zone.upper())
    cols[1].metric("Decision", decision)
    cols[2].metric("Stable post-action",
                   "yes" if final_outputs[STAGE_NAMES[12]]["stable"] else "no")

    with st.expander("Download full pipeline output (JSON)"):
        st.download_button(
            "Download JSON",
            data=json.dumps(final_outputs, indent=2, default=str),
            file_name=f"agentops_run_{scenario_id}.json",
            mime="application/json",
        )
        st.json(final_outputs)
else:
    st.info("Choose a scenario in the sidebar and click **Run pipeline**.")
