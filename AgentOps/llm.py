"""
Ollama LLM client with simulation fallback.

If Ollama (http://localhost:11434) is reachable and the configured model is
pulled, calls go to the real model. Otherwise we transparently fall back to a
deterministic simulation layer so the pipeline always runs end-to-end.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests


OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral:7b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "30"))


@dataclass
class LLMResponse:
    text: str
    backend: str  # "ollama" or "simulation"
    model: str
    latency_ms: int
    raw: Optional[dict] = None


class LLMClient:
    """Thin wrapper around Ollama's /api/generate endpoint with a sim fallback."""

    def __init__(
        self,
        host: str = OLLAMA_HOST,
        model: str = OLLAMA_MODEL,
        timeout: float = OLLAMA_TIMEOUT,
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._availability_cache: Optional[bool] = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------
    def is_available(self, refresh: bool = False) -> bool:
        if self._availability_cache is not None and not refresh:
            return self._availability_cache
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=2.0)
            if r.status_code != 200:
                self._availability_cache = False
                return False
            tags = r.json().get("models", [])
            names = [t.get("name", "") for t in tags]
            # Accept "mistral:7b", "mistral", or anything that starts with mistral
            ok = any(self.model in n or n.startswith(self.model.split(":")[0]) for n in names)
            self._availability_cache = ok
            return ok
        except Exception:
            self._availability_cache = False
            return False

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        force_simulation: bool = False,
    ) -> LLMResponse:
        start = time.time()

        if not force_simulation and self.is_available():
            try:
                payload: dict[str, Any] = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                }
                if system:
                    payload["system"] = system

                r = requests.post(
                    f"{self.host}/api/generate",
                    json=payload,
                    timeout=self.timeout,
                )
                r.raise_for_status()
                data = r.json()
                latency = int((time.time() - start) * 1000)
                return LLMResponse(
                    text=data.get("response", "").strip(),
                    backend="ollama",
                    model=self.model,
                    latency_ms=latency,
                    raw=data,
                )
            except Exception:
                # fall through to simulation
                pass

        # ---- Simulation fallback ----
        text = _simulate(prompt, system)
        latency = int((time.time() - start) * 1000)
        return LLMResponse(
            text=text,
            backend="simulation",
            model="sim-mistral-7b",
            latency_ms=latency,
            raw=None,
        )


# ----------------------------------------------------------------------
# Deterministic simulation that pattern-matches on prompt keywords.
# Returns plausible JSON / text that the pipeline can parse.
# ----------------------------------------------------------------------
def _simulate(prompt: str, system: Optional[str] = None) -> str:
    p = prompt.lower()

    # Reasoning stage: hypothesis generation
    if "hypothesis" in p or "root cause" in p:
        if "connection pool" in p or "db" in p:
            hyps = [
                {"hypothesis": "Database connection pool exhaustion due to leaked connections from a recent deploy", "prior": 0.55},
                {"hypothesis": "Sudden traffic spike overwhelming static pool size", "prior": 0.30},
                {"hypothesis": "Slow queries holding connections open", "prior": 0.15},
            ]
        elif "oom" in p or "memory" in p or "crash loop" in p:
            hyps = [
                {"hypothesis": "Memory leak introduced in latest application release", "prior": 0.60},
                {"hypothesis": "Pod memory limit set too low for current workload", "prior": 0.25},
                {"hypothesis": "External cache filling JVM heap unboundedly", "prior": 0.15},
            ]
        elif "p99" in p or "latency" in p or "gateway" in p:
            hyps = [
                {"hypothesis": "Upstream service degradation cascading through API gateway", "prior": 0.50},
                {"hypothesis": "Gateway worker pool saturation under elevated traffic", "prior": 0.30},
                {"hypothesis": "Recent gateway config change increased per-request overhead", "prior": 0.20},
            ]
        elif "tls" in p or "cert" in p:
            hyps = [
                {"hypothesis": "Certificate auto-renewal job failed and cert is approaching expiry", "prior": 0.70},
                {"hypothesis": "ACME challenge blocked by recent firewall rule change", "prior": 0.20},
                {"hypothesis": "Cert was manually issued and never enrolled in renewal", "prior": 0.10},
            ]
        else:
            hyps = [
                {"hypothesis": "Infrastructure-level resource exhaustion", "prior": 0.45},
                {"hypothesis": "Application logic regression from recent release", "prior": 0.35},
                {"hypothesis": "External dependency degradation", "prior": 0.20},
            ]
        return json.dumps({"hypotheses": hyps}, indent=2)

    # Confidence judge stage
    if "judge" in p or "logical coherence" in p or "review the reasoning" in p:
        return json.dumps({
            "verdict": "agrees",
            "summary": "Reasoning chain is logically grounded in retrieved context; recommended action aligns with known runbook for this incident class.",
            "flaws": [],
        }, indent=2)

    # Action plan / CoVe simulation
    if "propose" in p and "action" in p:
        if "connection pool" in p:
            return "Scale connection pool max from 50 to 100 and roll restart payments-service. Expected: pool utilization drops below 70% within 60s. Risk: brief request queueing during restart."
        if "oom" in p or "memory" in p:
            return "Roll back deployment to previous stable image and increase pod memory limit by 25%. Expected: crash loop resolves; RSS plateaus under new limit."
        if "p99" in p or "latency" in p:
            return "Scale gateway replicas from 4 to 8 and enable per-route circuit breaker on degraded upstream. Expected: P99 returns under SLO within 2 minutes."
        if "tls" in p or "cert" in p:
            return "Trigger manual cert renewal via cert-manager and verify ACME DNS challenge succeeds. Expected: new cert issued, expiry > 60 days."
        return "Apply standard remediation playbook for this incident class."

    # Policy summary
    if "policy" in p or "guardrail" in p:
        return "Action conforms to standard SRE remediation policy. No PII, PHI, or PCI-scoped data touched. RBAC: on-call role authorized."

    # Generic fallback
    return "Acknowledged. Proceeding with deterministic pipeline logic based on signal context."
