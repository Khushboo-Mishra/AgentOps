"""
AgentOps — Streamlit UI (polished dark theme, HTML-demo parity).

Run:
    streamlit run app.py
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
from typing import Any

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm import LLMClient
from data.scenarios import SCENARIOS, scenario_labels
from pipeline import run_pipeline, STAGE_NAMES


st.set_page_config(
    page_title="AgentOps — Incident Response Pipeline",
    layout="wide",
    initial_sidebar_state="expanded",
)


def md(html: str):
    """Render dedented HTML — Streamlit's markdown treats indented blocks as code."""
    st.markdown(textwrap.dedent(html).strip(), unsafe_allow_html=True)


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ============================================================================
# CSS
# ============================================================================
md("""
<style>
:root{
  --bg:#0f1117; --bg2:#161b27; --bg3:#1e2535; --bg4:#252d3f;
  --border:#2d3748; --border2:#3d4f6e;
  --text:#e2e8f0; --text2:#94a3b8; --text3:#64748b;
  --accent:#6366f1; --accent2:#818cf8;
  --green:#10b981; --green2:#34d399;
  --yellow:#f59e0b; --yellow2:#fbbf24;
  --red:#ef4444; --red2:#f87171;
  --blue:#3b82f6; --blue2:#60a5fa;
}
.block-container { padding-top: 1.2rem !important; padding-bottom: 4rem !important; max-width: 1200px; }
header[data-testid="stHeader"] { background: transparent; }
section[data-testid="stSidebar"] { background: var(--bg2); border-right: 1px solid var(--border); }
.ao-brand { display: flex; align-items: center; gap: 10px; font-weight: 800; font-size: 18px; margin-bottom: 4px; }
.ao-brand-badge { background: var(--accent); width: 28px; height: 28px; border-radius: 7px; display:flex; align-items:center; justify-content:center; color:#fff; font-weight:900; font-size: 13px; }
.ao-tagline { color: var(--text3); font-size: 11px; letter-spacing: .02em; margin-bottom: 14px; }
.ao-card-h { font-size: 11px; font-weight: 700; color: var(--text2); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 10px; display:flex; align-items:center; gap:8px; }
.ao-pill { display:inline-flex; align-items:center; gap:6px; padding: 3px 9px; border-radius: 999px; background: var(--bg3); border: 1px solid var(--border); font-size: 11px; color: var(--text2); margin-right:6px; margin-bottom:4px; }
.ao-pill-dot { width: 7px; height: 7px; border-radius: 50%; }
.ao-pill-g { background: rgba(16,185,129,.12); color: var(--green2); border-color: rgba(16,185,129,.3); }
.ao-pill-y { background: rgba(245,158,11,.12); color: var(--yellow2); border-color: rgba(245,158,11,.3); }
.ao-pill-r { background: rgba(239,68,68,.12); color: var(--red2); border-color: rgba(239,68,68,.3); }
.ao-pill-b { background: rgba(99,102,241,.12); color: var(--accent2); border-color: rgba(99,102,241,.3); }
.ao-sev-critical { background: rgba(239,68,68,.18); color: var(--red2); padding: 3px 9px; border-radius: 4px; font-weight: 700; font-size: 11px; letter-spacing:.04em; }
.ao-sev-high     { background: rgba(245,158,11,.18); color: var(--yellow2); padding: 3px 9px; border-radius: 4px; font-weight: 700; font-size: 11px; letter-spacing:.04em; }
.ao-sev-medium   { background: rgba(59,130,246,.18); color: var(--blue2); padding: 3px 9px; border-radius: 4px; font-weight: 700; font-size: 11px; letter-spacing:.04em; }
.ao-scenario-card { background: linear-gradient(135deg, var(--bg2), var(--bg3)); border: 1px solid var(--border2); border-radius: 12px; padding: 18px 22px; margin-bottom: 16px; }
.ao-scenario-title { font-size: 22px; font-weight: 800; color: #fff; margin-bottom: 4px; }
.ao-scenario-sub { color: var(--text2); font-size: 13px; display:flex; gap: 14px; flex-wrap: wrap; align-items:center; }
.ao-mgrid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 14px; }
.ao-mgrid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 14px; }
.ao-mgrid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px; }
@media (max-width: 1100px){ .ao-mgrid { grid-template-columns: repeat(3, 1fr); } }
.ao-mtile { background: var(--bg3); border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; }
.ao-mlbl { color: var(--text3); font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 4px; }
.ao-mval { font-size: 21px; font-weight: 800; line-height: 1.1; margin-bottom: 2px; }
.ao-msub { font-size: 10.5px; color: var(--text3); }
.ao-mval.red    { color: var(--red2); }
.ao-mval.yellow { color: var(--yellow2); }
.ao-mval.green  { color: var(--green2); }
.ao-log { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 11px 13px; font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 11.5px; line-height: 1.7; max-height: 240px; overflow-y: auto; white-space: pre-wrap; color: var(--text2); }
.ao-narr { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 12px; line-height: 1.65; color: var(--text); white-space: pre-wrap; }
.ao-hyp { background: var(--bg3); border: 1px solid var(--border); border-radius: 10px; padding: 11px 14px; margin-bottom: 8px; display: flex; gap: 12px; align-items: flex-start; }
.ao-hyp-rank { font-size: 18px; font-weight: 900; color: var(--text3); min-width: 22px; }
.ao-hyp-rank.r1 { color: var(--yellow2); }
.ao-hyp-title { font-size: 13px; font-weight: 700; color: var(--text); margin-bottom: 4px; }
.ao-hyp-detail { font-size: 11.5px; color: var(--text2); line-height: 1.55; }
.ao-bar { background: var(--bg4); height: 6px; border-radius: 4px; overflow: hidden; width: 110px; margin-top: 5px; }
.ao-bar-fill { height: 6px; border-radius: 4px; }
.ao-score { font-size: 11px; font-weight: 700; min-width: 38px; text-align: right; color: var(--text); }
.ao-action { background: var(--bg3); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; margin-bottom: 10px; }
.ao-action-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; gap: 10px; flex-wrap: wrap; }
.ao-action-title { font-size: 14px; font-weight: 700; color: var(--text); }
.ao-action-desc { font-size: 12px; color: var(--text2); line-height: 1.55; margin-bottom: 8px; }
.ao-cmd { background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 8px 11px; font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 11.5px; color: var(--green2); overflow-x: auto; white-space: pre; }
.ao-badge { padding: 2px 7px; border-radius: 4px; font-size: 10px; font-weight: 700; letter-spacing: .03em; }
.ao-bg-low    { background: rgba(16,185,129,.15); color: var(--green2); }
.ao-bg-medium { background: rgba(245,158,11,.15); color: var(--yellow2); }
.ao-bg-high   { background: rgba(239,68,68,.15); color: var(--red2); }
.ao-bg-auto   { background: rgba(16,185,129,.15); color: var(--green2); }
.ao-bg-human  { background: rgba(245,158,11,.15); color: var(--yellow2); }
.ao-bg-escalate { background: rgba(239,68,68,.15); color: var(--red2); }
.ao-banner { border-radius: 10px; padding: 14px 18px; display:flex; gap: 14px; align-items:center; margin: 6px 0 14px; border: 1px solid; }
.ao-banner-ic { width: 36px; height: 36px; border-radius: 50%; display:flex; align-items:center; justify-content:center; font-size: 18px; font-weight: 900; flex-shrink: 0; }
.ao-banner-tt { font-size: 14px; font-weight: 800; margin-bottom: 2px; }
.ao-banner-ds { font-size: 12px; }
.ao-banner.green  { background: rgba(16,185,129,.08); border-color: rgba(16,185,129,.35); }
.ao-banner.amber  { background: rgba(245,158,11,.08); border-color: rgba(245,158,11,.35); }
.ao-banner.red    { background: rgba(239,68,68,.08); border-color: rgba(239,68,68,.35); }
.ao-banner.green .ao-banner-ic  { background: rgba(16,185,129,.18); color: var(--green2); }
.ao-banner.amber .ao-banner-ic  { background: rgba(245,158,11,.18); color: var(--yellow2); }
.ao-banner.red   .ao-banner-ic  { background: rgba(239,68,68,.18); color: var(--red2); }
.ao-hitl { background: linear-gradient(135deg, rgba(245,158,11,.08), rgba(99,102,241,.05)); border: 1px solid rgba(245,158,11,.3); border-radius: 12px; padding: 18px 20px; margin: 8px 0 18px; }
.ao-hitl-h { font-size: 13px; font-weight: 800; color: var(--yellow2); margin-bottom: 4px; text-transform: uppercase; letter-spacing: .05em; }
.ao-hitl-s { font-size: 13px; color: var(--text); margin-bottom: 10px; }
button[data-testid="baseButton-primary"] {
  background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
  border: 0 !important;
  font-weight: 800 !important;
}
button[data-testid="baseButton-primary"]:hover {
  filter: brightness(1.1);
  box-shadow: 0 6px 20px rgba(99,102,241,.4);
}
div[data-testid="stExpander"] { background: var(--bg2); border: 1px solid var(--border) !important; border-radius: 10px !important; margin-bottom: 10px; }
div[data-testid="stExpander"] summary { font-weight: 700 !important; color: var(--text); padding: 10px 14px !important; }
.ao-ba { width:100%; border-collapse:collapse; margin-top:6px; }
.ao-ba th { color:var(--text3); font-size:11px; text-transform:uppercase; text-align:left; padding:6px 10px; }
.ao-ba td { padding:6px 10px; border-bottom:1px solid var(--border); }
.ao-ba .b { color:var(--red2); font-family:ui-monospace, monospace; }
.ao-ba .a { color:var(--green2); font-family:ui-monospace, monospace; }
.ao-ba .arrow { color:var(--text3); }
</style>
""")


# ============================================================================
# Session state
# ============================================================================
ss = st.session_state
ss.setdefault("hitl_decision", None)
ss.setdefault("run_token", 0)
ss.setdefault("scenario_id", None)


# ============================================================================
# Sidebar
# ============================================================================
with st.sidebar:
    md("""
    <div class="ao-brand"><span class="ao-brand-badge">A</span> AgentOps</div>
    <div class="ao-tagline">13-stage AI agent pipeline · production incident response</div>
    """)

    label_pairs = scenario_labels()
    label_to_id = {label: sid for sid, label in label_pairs}
    chosen_label = st.selectbox("Incident scenario", list(label_to_id.keys()), index=0)
    scenario_id = label_to_id[chosen_label]
    if ss.scenario_id != scenario_id:
        ss.scenario_id = scenario_id
        ss.hitl_decision = None
    scenario = SCENARIOS[scenario_id]

    st.markdown("---")
    md('<div class="ao-card-h">LLM backend</div>')
    llm = LLMClient()
    backend = llm.active_backend
    if backend == "groq":
        md(f'<span class="ao-pill ao-pill-g"><span class="ao-pill-dot" style="background:var(--green)"></span>Groq · {llm.active_model}</span>')
    elif backend == "ollama":
        md(f'<span class="ao-pill ao-pill-g"><span class="ao-pill-dot" style="background:var(--green)"></span>Ollama · {llm.active_model}</span>')
    else:
        md('<span class="ao-pill ao-pill-y"><span class="ao-pill-dot" style="background:var(--yellow)"></span>Simulation backend</span>')
        st.caption("Set GROQ_API_KEY in Streamlit secrets, or run Ollama locally.")

    st.markdown("---")
    if st.button("▶  Run pipeline", type="primary", use_container_width=True):
        ss.run_token += 1
        ss.hitl_decision = None

    st.caption("Pipeline runs all 13 stages and renders each one as it completes.")


# ============================================================================
# Header + scenario card
# ============================================================================
st.markdown("# AgentOps Incident Response")
st.caption("Apexon × NYU — production agent operations framework. Pick a scenario in the sidebar and run the 13-stage pipeline.")

sev = scenario['signal']['severity']
sev_class = f"ao-sev-{sev}"
oncall = scenario['context']['oncall_info'].get('slack_handle', '')
md(f'''
<div class="ao-scenario-card">
<div class="ao-scenario-title">{_esc(scenario['label'])}</div>
<div class="ao-scenario-sub">
<span class="{sev_class}">{sev.upper()}</span>
<span>📦 <code>{_esc(scenario['signal']['service'])}</code></span>
<span>📁 {_esc(scenario['category'])}</span>
<span>🔌 source: <code>{_esc(scenario['signal']['source'])}</code></span>
<span>👤 on-call: {_esc(oncall)}</span>
</div>
</div>
''')


# ============================================================================
# Metrics dashboard (live state) — flat HTML, no leading whitespace
# ============================================================================
def _tile(label: str, value: str, color: str = "", sub: str = "") -> str:
    return (
        f'<div class="ao-mtile">'
        f'<div class="ao-mlbl">{label}</div>'
        f'<div class="ao-mval {color}">{_esc(value)}</div>'
        f'<div class="ao-msub">{_esc(sub)}</div>'
        f'</div>'
    )


dash = scenario.get("metrics_dashboard", [])
if dash:
    color_dot = {"red": "🔴", "yellow": "🟡", "green": "🟢"}
    tiles = "".join(
        _tile(f"{color_dot.get(m['color'],'⚪')} {m['label']}", m["value"], m["color"], m["sub"])
        for m in dash
    )
    md(f'<div class="ao-mgrid">{tiles}</div>')


with st.expander("Raw signal envelope", expanded=False):
    st.json(scenario["signal"])


# ============================================================================
# Stage rendering
# ============================================================================
ZONE_BANNER = {
    "green": ("✓", "Action authorized — autonomous execution", "Pipeline reached GREEN. No human approval required.", "green"),
    "amber": ("!", "Human approval required",                  "Pipeline reached AMBER. Action queued for HITL.", "amber"),
    "red":   ("✕", "Full stop — handover to on-call",          "Confidence or risk threshold not met. Agent suspended.", "red"),
}


def _bar_color(score: float) -> str:
    if score >= 0.85: return "var(--green2)"
    if score >= 0.60: return "var(--yellow2)"
    return "var(--red2)"


def _hyp_html(rank: int, h: dict) -> str:
    score = float(h.get("posterior", h.get("prior", 0)))
    rank_class = " r1" if rank == 1 else ""
    detail = h.get("detail", "")
    return (
        f'<div class="ao-hyp">'
        f'<div class="ao-hyp-rank{rank_class}">{rank}</div>'
        f'<div style="flex:1">'
        f'<div class="ao-hyp-title">{_esc(h["hypothesis"])}</div>'
        f'<div class="ao-hyp-detail">{_esc(detail)}</div>'
        f'</div>'
        f'<div style="display:flex;align-items:center;gap:8px;min-width:170px">'
        f'<div class="ao-bar"><div class="ao-bar-fill" style="width:{int(score*100)}%;background:{_bar_color(score)}"></div></div>'
        f'<div class="ao-score">{score:.2f}</div>'
        f'</div>'
        f'</div>'
    )


def _action_html(i: int, a: dict) -> str:
    badges = (
        f'<span class="ao-badge ao-bg-{a["risk"]}">{a["risk"].upper()} RISK</span>'
        f'<span class="ao-badge ao-bg-{a["decision"]}">{a["decision"].upper()}</span>'
        f'<span class="ao-badge" style="background:var(--bg4);color:var(--text2)">conf {a["confidence"]:.2f}</span>'
    )
    return (
        f'<div class="ao-action">'
        f'<div class="ao-action-head">'
        f'<div class="ao-action-title">{i}. {_esc(a["title"])}</div>'
        f'<div style="display:flex;gap:6px;flex-wrap:wrap">{badges}</div>'
        f'</div>'
        f'<div class="ao-action-desc">{_esc(a["description"])}</div>'
        f'<div class="ao-cmd">$ {_esc(a["command"])}</div>'
        f'</div>'
    )


def _banner_html(zone: str, sub_text: str = "") -> str:
    ic, tt, _, klass = ZONE_BANNER.get(zone, ("?", "Unknown", "", "amber"))
    return (
        f'<div class="ao-banner {klass}">'
        f'<div class="ao-banner-ic">{ic}</div>'
        f'<div>'
        f'<div class="ao-banner-tt">{tt}</div>'
        f'<div class="ao-banner-ds">{sub_text}</div>'
        f'</div>'
        f'</div>'
    )


def _render_hitl_panel(summary_card: dict[str, Any]):
    info_pills = (
        f"<span><b>Service:</b> <code>{_esc(summary_card['service'])}</code></span>"
        f"<span><b>Confidence:</b> {summary_card['confidence']:.2f}</span>"
        f"<span><b>Risk:</b> {summary_card['risk_score']:.2f}</span>"
        f"<span><b>Compliance:</b> {_esc(', '.join(summary_card['policy_compliance_tags']) or 'none')}</span>"
        f"<span><b>On-call:</b> {_esc(summary_card['oncall'].get('slack_handle',''))}</span>"
    )
    md(
        f'<div class="ao-hitl">'
        f'<div class="ao-hitl-h">⚠ Human-in-the-Loop · approval required</div>'
        f'<div class="ao-hitl-s">{_esc(summary_card["proposed_action"])}</div>'
        f'<div style="display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--text2)">{info_pills}</div>'
        f'</div>'
    )

    cols = st.columns(4)
    if cols[0].button("✓ Approve & execute", key=f"hitl_approve_{ss.run_token}", type="primary", use_container_width=True):
        ss.hitl_decision = "approved"; ss.run_token += 1; st.rerun()
    if cols[1].button("✕ Reject", key=f"hitl_reject_{ss.run_token}", use_container_width=True):
        ss.hitl_decision = "rejected"; ss.run_token += 1; st.rerun()
    if cols[2].button("✎ Modify then approve", key=f"hitl_modify_{ss.run_token}", use_container_width=True):
        ss.hitl_decision = "approved"; ss.run_token += 1; st.rerun()
    if cols[3].button("⤴ Escalate", key=f"hitl_escalate_{ss.run_token}", use_container_width=True):
        ss.hitl_decision = "rejected"; ss.run_token += 1; st.rerun()


def render_stage(name: str, out: dict[str, Any]):
    stage = out.get("stage")
    expand_default = stage in (
        "reasoning", "confidence", "risk", "decision_gateway",
        "human_in_the_loop", "action_execution", "continuous_monitoring",
    )

    with st.expander(name, expanded=expand_default):
        if "summary" in out:
            md(f'<div style="color:var(--text2);font-size:12px;margin-bottom:10px">{_esc(out["summary"])}</div>')

        if stage == "signal_ingestion":
            sig = out["signal"]
            md(
                f'<span class="ao-pill ao-pill-b">source · {_esc(sig.get("source",""))}</span>'
                f'<span class="ao-pill ao-pill-r">severity · {_esc(sig.get("severity",""))}</span>'
                f'<span class="ao-pill">priority · {out["priority"]}</span>'
                f'<span class="ao-pill">deduplicated · {"yes" if out["deduplicated"] else "no"}</span>'
            )

        elif stage == "context_aggregation":
            ctx = out["context"]
            md(
                f'<span class="ao-pill">{len(ctx.get("recent_logs", []))} log lines</span>'
                f'<span class="ao-pill">{len(ctx.get("active_traces", []))} traces</span>'
                f'<span class="ao-pill">{len(ctx.get("retrieved_tsgs", []))} runbooks</span>'
                f'<span class="ao-pill">{len(ctx.get("similar_past_incidents", []))} similar past</span>'
            )
            st.markdown("**Recent logs**")
            colored = []
            for line in ctx.get("recent_logs", []):
                if " ERROR " in line:
                    colored.append(f'<span style="color:var(--red2)">{_esc(line)}</span>')
                elif " WARN " in line:
                    colored.append(f'<span style="color:var(--yellow2)">{_esc(line)}</span>')
                elif " INFO " in line:
                    colored.append(f'<span style="color:var(--blue2)">{_esc(line)}</span>')
                else:
                    colored.append(_esc(line))
            md(f'<div class="ao-log">{"<br/>".join(colored)}</div>')
            with st.expander("System health"):
                st.json(ctx.get("system_health", {}))
            with st.expander("Retrieved runbooks"):
                for t in ctx.get("retrieved_tsgs", []):
                    st.markdown(f"- **{t['title']}** _(relevance {t['relevance_score']:.2f})_  \n  {t['content']}")

        elif stage == "preprocessing":
            md(
                f'<span class="ao-pill">{len(out["redactions_applied"])} redaction rules triggered</span>'
                f'<span class="ao-pill {"ao-pill-g" if not out["context_incomplete"] else "ao-pill-r"}">'
                f'context · {"complete" if not out["context_incomplete"] else "incomplete"}</span>'
            )

        elif stage == "reasoning":
            md(
                f'<span class="ao-pill ao-pill-b">backend · {_esc(out["llm_backend"])}</span>'
                f'<span class="ao-pill">latency · {out["llm_latency_ms"]} ms</span>'
                f'<span class="ao-pill {"ao-pill-g" if out["plan_approved_by_cove"] else "ao-pill-r"}">'
                f'CoVe · {"approved" if out["plan_approved_by_cove"] else "blocked"}</span>'
            )
            st.markdown("**Hypotheses**")
            md("".join(_hyp_html(i, h) for i, h in enumerate(out["hypotheses"][:3], 1)))

            if out.get("reasoning_narrative"):
                st.markdown("**Reasoning trace**")
                md(f'<div class="ao-narr">{_esc(out["reasoning_narrative"])}</div>')

            st.markdown("**Proposed remediation plan**")
            md("".join(_action_html(i, a) for i, a in enumerate(out["proposed_actions"], 1)))

        elif stage == "confidence":
            comps = out["components"]
            tiles = "".join(
                _tile(k.replace("_", " "), f"{v:.2f}", "", f"weight {int(out['weights'][k]*100)}%")
                for k, v in comps.items()
            )
            md(f'<div class="ao-mgrid-4">{tiles}</div>')
            zone = out["decision_zone"]
            zone_color = {"green": "var(--green2)", "amber": "var(--yellow2)", "red": "var(--red2)"}[zone]
            md(
                f'<div style="margin-top:8px;font-size:14px"><b>Total:</b> '
                f'<span style="color:{zone_color};font-weight:800;font-size:20px">{out["total_confidence"]:.2f}</span> '
                f'→ <b style="color:{zone_color}">{zone.upper()}</b></div>'
            )
            st.caption(f"Judge verdict: {out['judge']['verdict']} — {out['judge']['summary']}")

        elif stage == "risk":
            comp = out["components"]
            tiles = (
                _tile("Irreversibility", f"{comp['irreversibility_score']:.2f}", "", comp["irreversibility_label"])
                + _tile("Blast radius", f"{comp['blast_radius_score']:.2f}", "", ", ".join(comp["blast_radius_services"]) or "none")
                + _tile("Data gravity", f"{comp['data_gravity_score']:.2f}", "",
                        ", ".join(k.upper() for k, v in comp["data_gravity"].items() if v) or "none")
            )
            md(f'<div class="ao-mgrid-3">{tiles}</div>')
            zone = out["enforced_zone"]
            zone_color = {"green": "var(--green2)", "amber": "var(--yellow2)", "red": "var(--red2)"}[zone]
            md(
                f'<div style="margin-top:8px;font-size:14px"><b>Composite risk:</b> '
                f'<span style="color:{zone_color};font-weight:800;font-size:20px">{out["composite_risk_score"]:.2f}</span> '
                f'({out["risk_level"]}) → enforced zone <b style="color:{zone_color}">{zone.upper()}</b></div>'
            )
            if out.get("intersection_rule"):
                st.warning(f"⚠️  {out['intersection_rule']}")

        elif stage == "policy":
            md(
                f'<span class="ao-pill">policy v{_esc(out["policy_version"])}</span>'
                f'<span class="ao-pill {"ao-pill-g" if out["rbac_authorized"] else "ao-pill-r"}">'
                f'RBAC · {"authorized" if out["rbac_authorized"] else "denied"}</span>'
                + "".join(f'<span class="ao-pill ao-pill-b">{_esc(t)}</span>' for t in out["compliance_tags"])
            )
            if out["denials"]:
                st.error("Denials: " + ", ".join(d['name'] for d in out["denials"]))
            if out["forces_amber_policy_ids"]:
                st.info("Force-AMBER policies: " + ", ".join(out["forces_amber_policy_ids"]))

        elif stage == "decision_gateway":
            md(_banner_html(out["final_zone"], f'Decision: <code>{_esc(out["decision"])}</code>'))
            st.markdown("**Reasons**")
            for r in out["reasons"]:
                st.markdown(f"- {r}")

        elif stage == "action_execution":
            executed = out.get("executed_actions", [])
            skipped = out.get("skipped_actions", [])
            if executed:
                st.success(f"Executed {len(executed)} action(s)")
                for a in executed:
                    md(
                        f'<div class="ao-action">'
                        f'<div class="ao-action-title">▶ {_esc(a["title"])} · '
                        f'<code style="color:var(--text2)">{_esc(a["execution_id"])}</code></div>'
                        f'<div class="ao-cmd">$ {_esc(a["command"])}</div>'
                        f'</div>'
                    )
                    st.dataframe(a["steps"], hide_index=True, use_container_width=True)
            if skipped:
                st.info(f"Skipped (require human approval): {', '.join(skipped)}")
            if not executed and not skipped:
                st.info("Action plan not auto-executed.")

        elif stage == "human_in_the_loop":
            if not out["needs_hitl"]:
                st.success("No HITL needed — informational only.")
            elif out.get("awaiting_decision"):
                _render_hitl_panel(out["summary_card"])
            else:
                # Decision was made — show what the human chose
                hd = out.get("human_decision", "")
                if hd == "approved":
                    md(
                        '<div class="ao-banner green">'
                        '<div class="ao-banner-ic">✓</div>'
                        '<div>'
                        '<div class="ao-banner-tt">Human approved</div>'
                        '<div class="ao-banner-ds">On-call engineer signed off — actions executed under human authority.</div>'
                        '</div></div>'
                    )
                elif hd == "rejected":
                    md(
                        '<div class="ao-banner red">'
                        '<div class="ao-banner-ic">✕</div>'
                        '<div>'
                        '<div class="ao-banner-tt">Human rejected</div>'
                        '<div class="ao-banner-ds">Plan halted by on-call engineer. Incident handed off.</div>'
                        '</div></div>'
                    )
                if st.button("↺ Revise decision", key=f"hitl_revise_{ss.run_token}"):
                    ss.hitl_decision = None
                    ss.run_token += 1
                    st.rerun()

        elif stage == "audit":
            md(f'<span class="ao-pill">📂 {_esc(out["audit_log_path"])}</span>')
            with st.expander("Full audit record (JSON)"):
                st.json(out["audit_record"])

        elif stage == "feedback":
            ms = out["metrics"]
            tiles = (
                _tile("Auto-resolved", "YES" if ms["auto_resolution"] else "NO", "green" if ms["auto_resolution"] else "red")
                + _tile("HITL required", "YES" if ms["human_approval_required"] else "NO", "yellow" if ms["human_approval_required"] else "")
                + _tile("Blocked", "YES" if ms["blocked"] else "NO", "red" if ms["blocked"] else "")
                + _tile("Success", "YES" if out["success"] else "PENDING", "green" if out["success"] else "red")
            )
            md(f'<div class="ao-mgrid-4">{tiles}</div>')
            if out["learning_suggestions"]:
                st.markdown("**Learning signals**")
                for s in out["learning_suggestions"]:
                    st.markdown(f"- {s}")

        elif stage == "continuous_monitoring":
            snaps = out["post_action_snapshots"]
            tiles = "".join(_tile(f"+{k}", v, "green") for k, v in snaps.items())
            md(f'<div class="ao-mgrid-3">{tiles}</div>')
            ba = out.get("before_after_metrics", [])
            if ba:
                st.markdown("**Before / After**")
                rows = "".join(
                    f'<tr><td>{_esc(m["label"])}</td>'
                    f'<td class="b">{_esc(m["before"])}</td>'
                    f'<td class="arrow">→</td>'
                    f'<td class="a">{_esc(m["after"])}</td></tr>'
                    for m in ba
                )
                md(
                    '<table class="ao-ba">'
                    '<thead><tr><th>Metric</th><th>Before</th><th></th><th>After</th></tr></thead>'
                    f'<tbody>{rows}</tbody>'
                    '</table>'
                )

        else:
            st.json(out)


# ============================================================================
# Run pipeline
# ============================================================================
if ss.run_token > 0:
    progress = st.progress(0.0, text="Starting pipeline…")
    container = st.container()
    total = len(STAGE_NAMES)

    final_outputs: dict[str, dict[str, Any]] = {}
    for i, (stage_name, out) in enumerate(
        run_pipeline(scenario, llm=llm, hitl_decision=ss.hitl_decision), start=1
    ):
        final_outputs[stage_name] = out
        with container:
            render_stage(stage_name, out)
        progress.progress(i / total, text=f"Completed: {stage_name}")

    progress.empty()

    final_zone = final_outputs[STAGE_NAMES[7]]["final_zone"]
    final_decision = final_outputs[STAGE_NAMES[7]]["decision"]
    stable = final_outputs[STAGE_NAMES[12]]["stable"]
    sub = f"Decision: <code>{_esc(final_decision)}</code> · Post-action stable: {'yes' if stable else 'no'}"
    if ss.hitl_decision:
        sub += f" · HITL choice: <b>{_esc(ss.hitl_decision)}</b>"
    md(f'<div style="margin-top:18px"></div>')
    md(_banner_html(final_zone, sub))

    with st.expander("Download full pipeline output (JSON)"):
        st.download_button(
            "Download JSON",
            data=json.dumps(final_outputs, indent=2, default=str),
            file_name=f"agentops_run_{scenario_id}.json",
            mime="application/json",
        )
        st.json(final_outputs)
else:
    st.info("Choose a scenario in the sidebar and click **Run pipeline** to see all 13 stages.")
