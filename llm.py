"""
LLM client with three backends, in priority order:

  1. Groq    — if GROQ_API_KEY is set (great for hosted demos: free, fast)
  2. Ollama  — if reachable at OLLAMA_HOST and OLLAMA_MODEL is pulled
  3. Simulation — deterministic fallback so the pipeline always runs

Resolves credentials in this order:
  - Streamlit secrets (st.secrets) when available
  - Environment variables otherwise

Never log, print, or persist API keys.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests


# ----------------------------------------------------------------------
# Config helpers
# ----------------------------------------------------------------------
def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read from Streamlit secrets if running under Streamlit, else env."""
    try:
        import streamlit as st  # type: ignore
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


GROQ_API_KEY = _get_secret("GROQ_API_KEY")
GROQ_MODEL = _get_secret("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

OLLAMA_HOST = _get_secret("OLLAMA_HOST", "http://localhost:11434") or "http://localhost:11434"
OLLAMA_MODEL = _get_secret("OLLAMA_MODEL", "mistral:7b") or "mistral:7b"
OLLAMA_TIMEOUT = float(_get_secret("OLLAMA_TIMEOUT", "30") or "30")


@dataclass
class LLMResponse:
    text: str
    backend: str          # "groq" | "ollama" | "simulation"
    model: str
    latency_ms: int
    raw: Optional[dict] = None


# ======================================================================
# Client
# ======================================================================
class LLMClient:
    def __init__(
        self,
        host: str = OLLAMA_HOST,
        model: str = OLLAMA_MODEL,
        timeout: float = OLLAMA_TIMEOUT,
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._ollama_cache: Optional[bool] = None

    # ------------------------------------------------------------------
    # Backend availability
    # ------------------------------------------------------------------
    @property
    def has_groq(self) -> bool:
        return bool(GROQ_API_KEY)

    def is_available(self, refresh: bool = False) -> bool:
        """True if any real backend (Groq or Ollama) is reachable."""
        if self.has_groq:
            return True
        return self._ollama_available(refresh=refresh)

    def _ollama_available(self, refresh: bool = False) -> bool:
        if self._ollama_cache is not None and not refresh:
            return self._ollama_cache
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=2.0)
            if r.status_code != 200:
                self._ollama_cache = False
                return False
            tags = r.json().get("models", [])
            names = [t.get("name", "") for t in tags]
            ok = any(self.model in n or n.startswith(self.model.split(":")[0]) for n in names)
            self._ollama_cache = ok
            return ok
        except Exception:
            self._ollama_cache = False
            return False

    @property
    def active_backend(self) -> str:
        if self.has_groq:
            return "groq"
        if self._ollama_available():
            return "ollama"
        return "simulation"

    @property
    def active_model(self) -> str:
        if self.has_groq:
            return GROQ_MODEL
        if self._ollama_available():
            return self.model
        return "sim-mistral-7b"

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

        # ---- Backend 1: Groq ----
        if not force_simulation and self.has_groq:
            try:
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                r = requests.post(
                    GROQ_URL,
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": GROQ_MODEL,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    timeout=self.timeout,
                )
                r.raise_for_status()
                data = r.json()
                text = data["choices"][0]["message"]["content"].strip()
                return LLMResponse(
                    text=text,
                    backend="groq",
                    model=GROQ_MODEL,
                    latency_ms=int((time.time() - start) * 1000),
                    raw=data,
                )
            except Exception:
                pass  # fall through to next backend

        # ---- Backend 2: Ollama ----
        if not force_simulation and self._ollama_available():
            try:
                payload: dict[str, Any] = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                }
                if system:
                    payload["system"] = system
                r = requests.post(f"{self.host}/api/generate", json=payload, timeout=self.timeout)
                r.raise_for_status()
                data = r.json()
                return LLMResponse(
                    text=data.get("response", "").strip(),
                    backend="ollama",
                    model=self.model,
                    latency_ms=int((time.time() - start) * 1000),
                    raw=data,
                )
            except Exception:
                pass

        # ---- Backend 3: Simulation ----
        text = _simulate(prompt, system)
        return LLMResponse(
            text=text,
            backend="simulation",
            model="sim-mistral-7b",
            latency_ms=int((time.time() - start) * 1000),
            raw=None,
        )


# ======================================================================
# Deterministic simulation fallback (unchanged from prior version)
# ======================================================================
def _simulate(prompt: str, system: Optional[str] = None) -> str:
    import json as _json
    p = prompt.lower()

    if "hypothesis" in p or "root cause" in p:
        if "connection pool" in p or " db " in p or "pool exhausted" in p:
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
        return _json.dumps({"hypotheses": hyps}, indent=2)

    if "judge" in p or "logical coherence" in p or "review the reasoning" in p:
        return _json.dumps({
            "verdict": "agrees",
            "summary": "Reasoning chain is logically grounded; recommended action aligns with known runbook for this incident class.",
            "flaws": [],
        }, indent=2)

    if "propose" in p and "action" in p:
        if "connection pool" in p:
            return "Scale connection pool max from 50 to 100 and roll restart payments-service."
        if "oom" in p or "memory" in p:
            return "Roll back deployment to previous stable image and increase pod memory limit by 25%."
        if "p99" in p or "latency" in p:
            return "Scale gateway replicas from 4 to 8 and enable circuit breaker on degraded upstream."
        if "tls" in p or "cert" in p:
            return "Trigger manual cert renewal via cert-manager and verify ACME DNS challenge succeeds."
        return "Apply standard remediation playbook for this incident class."

    if "policy" in p or "guardrail" in p:
        return "Action conforms to standard SRE remediation policy. RBAC: on-call role authorized."

    return "Acknowledged. Proceeding with deterministic pipeline logic based on signal context."
