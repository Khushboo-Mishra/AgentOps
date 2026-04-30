# AgentOps — 13-Stage Production Incident Response Pipeline

Apexon × NYU Capstone (CS04). A reference implementation of the AgentOps SOP framework: a 13-stage agent pipeline that ingests a production incident signal and runs it through reasoning, scoring, governance, execution, and continuous monitoring.

## Quick start

```bash
cd agentops
pip install -r requirements.txt
streamlit run app.py
```

That's it — the UI opens at <http://localhost:8501>.

### Optional: real LLM

The pipeline uses Ollama with `mistral:7b` if available, and otherwise falls back to a deterministic simulation (no install or network required).

```bash
# Optional — only if you want the real model
brew install ollama         # or follow https://ollama.com
ollama pull mistral:7b
ollama serve
```

The Streamlit sidebar shows whether the agent is using Ollama or the simulation backend.

## CLI quick-run

```bash
python pipeline.py
```

Runs every scenario through every stage and prints per-stage summaries.

## Layout

```
agentops/
├── requirements.txt
├── app.py                 # Streamlit UI
├── pipeline.py            # 13-stage orchestrator
├── llm.py                 # Ollama client + simulation fallback
├── data/
│   └── scenarios.py       # 4 hardcoded incident scenarios
└── agents/
    ├── stage_01_signal_ingestion.py
    ├── stage_02_context_aggregation.py
    ├── stage_03_preprocessing.py
    ├── stage_04_reasoning.py            # MPPR + CoVe
    ├── stage_05_confidence.py           # Triangulated certainty score
    ├── stage_06_risk.py                 # Impact & liability matrix
    ├── stage_07_policy.py
    ├── stage_08_decision_gateway.py
    ├── stage_09_action_execution.py
    ├── stage_10_human_in_the_loop.py
    ├── stage_11_audit.py
    ├── stage_12_feedback.py
    └── stage_13_monitoring.py
```

## The 4 scenarios

1. **DB connection pool exhausted** — payments-service, recent deploy introduces a connection leak.
2. **OOM crash loop** — recommendations-service in `CrashLoopBackOff` after a memory-leak release.
3. **API gateway P99 latency spike** — gateway worker pool saturated by upstream auth-service degradation.
4. **TLS certificate expiring** — wildcard cert renewal failing because of recent firewall tightening.

Each runs through all 13 stages and produces a different decision-zone outcome based on confidence, risk, and policy.

## Audit log

Every run appends a structured record to `audit_log.jsonl` in the project folder. Override the path with `AGENTOPS_AUDIT_LOG=/abs/path/audit.jsonl`.

## Environment variables

| Variable          | Default                  | Purpose                             |
|-------------------|--------------------------|-------------------------------------|
| `OLLAMA_HOST`     | `http://localhost:11434` | Ollama base URL                     |
| `OLLAMA_MODEL`    | `mistral:7b`             | Model tag                           |
| `OLLAMA_TIMEOUT`  | `30`                     | Per-request timeout (seconds)       |
| `AGENTOPS_AUDIT_LOG` | `./audit_log.jsonl`   | Audit log path                      |
