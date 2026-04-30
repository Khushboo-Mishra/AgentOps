"""
Stage 3 — Pre-processing & Validation.

Cleans aggregated context, masks PII / secrets, validates completeness,
and emits a sanitized context object ready for the reasoning engine.
"""

from __future__ import annotations

import re
from typing import Any


# Deliberately conservative regexes — false positives are safer than leaks.
_PATTERNS = [
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "[REDACTED_IP]"),
    (re.compile(r"\b(?:Bearer|bearer)\s+[A-Za-z0-9._\-]+"), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"(?i)(password|passwd|secret|api[_-]?key)\s*[=:]\s*\S+"), r"\1=[REDACTED_SECRET]"),
    (re.compile(r"\b\d{16}\b"), "[REDACTED_CARD]"),
]


def _scrub(text: str) -> tuple[str, list[str]]:
    flags: list[str] = []
    out = text
    for pat, replacement in _PATTERNS:
        if pat.search(out):
            flags.append(pat.pattern)
            out = pat.sub(replacement, out)
    return out, flags


def _scrub_logs(logs: list[str]) -> tuple[list[str], list[str]]:
    scrubbed = []
    all_flags: list[str] = []
    for line in logs:
        new_line, flags = _scrub(line)
        # Trim very long lines
        if len(new_line) > 500:
            new_line = new_line[:480] + "... [TRUNCATED]"
        scrubbed.append(new_line)
        all_flags.extend(flags)
    return scrubbed, all_flags


def run(stage2_out: dict[str, Any]) -> dict[str, Any]:
    ctx_in = stage2_out["context"]
    ctx_out = dict(ctx_in)

    # 1. Scrub logs
    scrubbed_logs, log_flags = _scrub_logs(ctx_in.get("recent_logs", []))
    ctx_out["recent_logs"] = scrubbed_logs

    # 2. Validate required fields
    required = ["signal", "recent_logs", "system_health"]
    missing = [k for k in required if k not in ctx_out or ctx_out[k] in (None, [], {})]
    context_incomplete = len(missing) > 0

    # 3. Note compliance tags from scenario tuning if available downstream
    redactions_applied = sorted(set(log_flags))

    summary = (
        f"Pre-processing complete: {len(redactions_applied)} redaction rule(s) triggered, "
        f"context_incomplete={context_incomplete}."
    )

    return {
        "stage": "preprocessing",
        "ok": True,
        "context": ctx_out,
        "redactions_applied": redactions_applied,
        "context_incomplete": context_incomplete,
        "missing_fields": missing,
        "summary": summary,
    }
