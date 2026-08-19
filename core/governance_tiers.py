# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — feature support tier map (BXD-017, docs/governance/06_SCOPE_FREEZE.md)

Every route prefix registered in core/main.py, and every built-in persona in
core/agent/personas.py, must be classified into exactly one of the three
tiers below. tests/test_scope_tiers.py enumerates the live app.routes and
BUILTIN_PERSONAS against these maps and fails on anything unclassified —
that is the anti-sprawl control the scope freeze exists to enforce. It must
not depend on anyone remembering to update this file by convention alone:
add a route or a persona without adding it here, and CI fails.

Tier definitions (docs/governance/06_SCOPE_FREEZE.md):
- CORE — in the pitch, in the demo, fully tested, constraint-verified,
  supported. Breaking one is a release blocker.
- EXPERIMENTAL — shipped, off by default, behind an explicit warning naming
  any third party involved. Absent from demos and the website's feature
  list. May break. May be removed.
- QUARANTINED — code retained, not reachable in a packaged build
  (core.config._is_packaged_build()). Revisit only when a real user asks.

Multi-agent orchestration (item #10 in the scope freeze inventory,
Quarantined) has no dedicated route — it is the `delegate_tasks` tool,
filtered out of the offered tool list directly in core/agent/runtime.py for
packaged builds. It has nothing to register here.
"""

CORE = "Core"
EXPERIMENTAL = "Experimental"
QUARANTINED = "Quarantined"

# Matched by exact path, or by "path startswith prefix + '/'" — longest
# prefix wins. A registered FastAPI route whose path matches none of these
# keys is, by definition, unclassified and fails test_scope_tiers.py.
ROUTE_TIERS: dict[str, str] = {
    # ── Core — core/main.py's own routes ────────────────────────────────
    "/": CORE,
    "/health": CORE,
    "/health/onboarding": CORE,
    "/static": CORE,
    # ── Core — auth flow (item #3) ──────────────────────────────────────
    "/auth": CORE,
    # ── Core — agent runtime, permissions, sessions, models (items #1,2,5,6) ─
    # /agent/notifications is the toast queue every Core surface reads from
    # (including Experimental routines/watchers results) — it is Core
    # infrastructure, not the Experimental feature that populates it.
    "/agent/notifications": CORE,
    "/agent": CORE,  # chat, sessions, permissions, models, model, audit, onboarding download
    # ── Core — privacy proof / network ledger (item #13) ────────────────
    "/agent/privacy": CORE,
    # ── Core — Ask My Files (item #15) ──────────────────────────────────
    "/agent/knowledge": CORE,
    # ── Core — hardware check (item #20) ────────────────────────────────
    "/system": CORE,
    # ── Core — first-party skills shipped since v0.1.0-v0.3.0 ───────────
    "/calendar": CORE,
    "/terminal": CORE,
    "/memory": CORE,
    "/documents": CORE,
    "/github": CORE,
    "/research": CORE,

    # ── Experimental (item #7) — network isolation queued, not shipped ──
    "/agent/skills": EXPERIMENTAL,
    # ── Experimental (item #9) — acts while the user is absent ──────────
    "/agent/schedules": EXPERIMENTAL,
    # ── Experimental (item #14) — same class as Routines ────────────────
    "/agent/watchers": EXPERIMENTAL,
    # ── Experimental (item #11) — routes conversation through api.telegram.org ─
    "/agent/telegram": EXPERIMENTAL,

    # ── Quarantined (item #8) — zero users have asked; pure surface area ─
    "/agent/personas": QUARANTINED,
}

# Built-in persona ids (core/agent/personas.py BUILTIN_PERSONAS). The whole
# Personas feature is Quarantined (item #8) — a new built-in persona is
# still part of that quarantined feature, but must be added here explicitly
# so a persona can never be added silently.
PERSONA_TIERS: dict[str, str] = {
    "bixdot": QUARANTINED,
    "day-planner": QUARANTINED,
    "researcher": QUARANTINED,
    "writer": QUARANTINED,
    "file-helper": QUARANTINED,
}


def route_tier(path: str) -> str | None:
    """Longest-prefix-match a route path against ROUTE_TIERS. None if unmatched."""
    best_prefix = None
    best_tier = None
    for prefix, tier in ROUTE_TIERS.items():
        # "/" is the literal root route only — it must never act as a
        # catch-all prefix, or every unclassified route would silently
        # match it and the anti-sprawl test below would never fail.
        matches = path == "/" if prefix == "/" else (path == prefix or path.startswith(prefix + "/"))
        if matches and (best_prefix is None or len(prefix) > len(best_prefix)):
            best_prefix, best_tier = prefix, tier
    return best_tier
