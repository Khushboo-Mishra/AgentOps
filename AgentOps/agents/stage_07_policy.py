"""
Stage 7 — Policy / Guardrail Evaluation.

Checks the proposed action against organizational policies, compliance maps
(SOC 2, HIPAA, PCI-DSS), and basic RBAC. In the demo, policies are encoded
as plain Python rules; in production they'd live in OPA / Cedar / a registry.
"""

from __future__ import annotations

from typing import Any


# Demo policy registry — versioned for change management.
POLICY_VERSION = "1.4.0"

POLICIES = [
    {
        "id": "POL-001",
        "name": "No destructive verbs without HITL",
        "applies_to": "any",
        "denies_if": lambda action: any(v in action.lower() for v in ["delete", "drop table", "rm -rf", "truncate"]),
    },
    {
        "id": "POL-002",
        "name": "PCI-scoped services require dual approval",
        "applies_to": "pci",
        "denies_if": lambda action: False,
        "requires_amber": lambda gravity: gravity.get("pci", False),
    },
    {
        "id": "POL-003",
        "name": "PHI-scoped actions are HITL-only",
        "applies_to": "phi",
        "requires_amber": lambda gravity: gravity.get("phi", False),
    },
    {
        "id": "POL-004",
        "name": "Production rollbacks must reference a deploy version",
        "applies_to": "production",
        "warns_if": lambda action: "rollback" in action.lower() and not any(c.isdigit() for c in action),
    },
]


def run(scenario: dict[str, Any], stage4_out: dict[str, Any], stage6_out: dict[str, Any]) -> dict[str, Any]:
    action = stage4_out["proposed_action"]
    gravity = stage6_out["components"]["data_gravity"]

    denials: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    forces_amber: list[str] = []

    for pol in POLICIES:
        if "denies_if" in pol and pol["denies_if"](action):
            denials.append({"id": pol["id"], "name": pol["name"]})
        if "requires_amber" in pol and pol["requires_amber"](gravity):
            forces_amber.append(pol["id"])
        if "warns_if" in pol and pol["warns_if"](action):
            warnings.append({"id": pol["id"], "name": pol["name"]})

    compliance_tags = []
    if gravity.get("pci"):
        compliance_tags.append("PCI-DSS")
    if gravity.get("phi"):
        compliance_tags.append("HIPAA")
    if gravity.get("pii"):
        compliance_tags.append("SOC2-PII")

    rbac_authorized = True  # demo: on-call role pre-authorized

    return {
        "stage": "policy",
        "ok": len(denials) == 0,
        "policy_version": POLICY_VERSION,
        "denials": denials,
        "warnings": warnings,
        "forces_amber_policy_ids": forces_amber,
        "compliance_tags": compliance_tags,
        "rbac_authorized": rbac_authorized,
        "summary": (
            f"Policy v{POLICY_VERSION}: {len(denials)} deny, {len(warnings)} warn, "
            f"{len(forces_amber)} force-amber. Compliance: {','.join(compliance_tags) or 'none'}."
        ),
    }
