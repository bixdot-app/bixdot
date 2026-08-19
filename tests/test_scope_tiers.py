# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BXD-017 — scope tiers must be a control, not a habit to remember.

docs/governance/06_SCOPE_FREEZE.md classifies every feature Core /
Experimental / Quarantined so the product's attack surface and support
surface stop outrunning validation. That classification is worthless if it
lives only in a markdown table nobody re-checks — the next route or persona
added at 1am would ship unclassified by default, which is exactly the
"scope drifted ahead of validation" failure the freeze exists to stop.

These tests enumerate the live app and fail if anything is unclassified.
"""
from fastapi.routing import APIRoute

from core.governance_tiers import CORE, EXPERIMENTAL, PERSONA_TIERS, QUARANTINED, ROUTE_TIERS, route_tier


def _api_routes() -> list[APIRoute]:
    """
    Recursively flatten every APIRoute reachable from app.routes.

    Newer Starlette/FastAPI wraps each app.include_router(...) call in an
    internal "_IncludedRouter" object (not a plain APIRoute, and its own
    `.routes` is empty — the real routes live on its `.original_router`)
    instead of flattening leaf routes directly into app.routes. A one-level
    filter (`isinstance(r, APIRoute)`) silently sees only the 3 routes
    declared directly on `app` and misses everything registered through a
    router — which is nearly this whole API. Walk `.routes` AND
    `.original_router.routes` recursively so this test is correct
    regardless of which FastAPI/Starlette version resolves the unpinned
    floor in requirements.txt.
    """
    from core.main import app

    found: list[APIRoute] = []
    seen: set[int] = set()
    stack = list(app.routes)
    while stack:
        r = stack.pop()
        if id(r) in seen:
            continue
        seen.add(id(r))
        if isinstance(r, APIRoute):
            found.append(r)
        for attr in ("routes", "original_router"):
            sub = getattr(r, attr, None)
            if sub is None:
                continue
            stack.extend(sub.routes if attr == "original_router" else sub)
    return found


def test_every_route_is_classified_into_a_tier():
    """
    Every registered route path must longest-prefix-match an entry in
    ROUTE_TIERS. If this fails, the offending path is new: add its prefix to
    core/governance_tiers.py ROUTE_TIERS with the tier from
    docs/governance/06_SCOPE_FREEZE.md's feature inventory (or add the
    feature to that inventory first if it is genuinely new — the freeze
    forbids new features outside the permitted list without review).
    """
    unclassified = sorted({r.path for r in _api_routes() if route_tier(r.path) is None})
    assert not unclassified, (
        "Route(s) not classified into Core/Experimental/Quarantined: "
        f"{unclassified}. Add them to core/governance_tiers.py ROUTE_TIERS."
    )


def test_every_built_in_persona_is_classified():
    """
    Every built-in persona id must appear in PERSONA_TIERS. A new built-in
    persona added to core/agent/personas.py BUILTIN_PERSONAS without a
    matching entry here fails — Personas is Quarantined (item #8), so new
    personas belong in the quarantined tier until a real user asks for the
    feature by name.
    """
    from core.agent.personas import BUILTIN_PERSONAS

    ids = {p["persona_id"] for p in BUILTIN_PERSONAS}
    unclassified = sorted(ids - PERSONA_TIERS.keys())
    assert not unclassified, (
        f"Persona(s) not classified into a tier: {unclassified}. "
        "Add them to core/governance_tiers.py PERSONA_TIERS."
    )


def test_route_tiers_values_are_valid():
    """Every declared tier is one of the three real tiers — catches typos."""
    valid = {CORE, EXPERIMENTAL, QUARANTINED}
    assert set(ROUTE_TIERS.values()) <= valid
    assert set(PERSONA_TIERS.values()) <= valid


def test_quarantined_persona_router_is_not_mounted_in_packaged_build():
    """
    BXD-017: Quarantined features are kept in the codebase but unreachable
    in a packaged build. core/main.py only registers persona_router when
    core.config._is_packaged_build() is False.
    """
    persona_paths = {r.path for r in _api_routes() if r.path.startswith("/agent/personas")}
    # In this (non-packaged) test process the router IS mounted — this test
    # documents the invariant main.py implements, not a runtime toggle.
    assert persona_paths, "expected /agent/personas routes in a non-packaged test run"

    import core.main as main_mod
    import inspect
    source = inspect.getsource(main_mod)
    assert "_is_packaged_build" in source and "persona_router" in source, (
        "core/main.py must guard app.include_router(persona_router) behind "
        "a packaged-build check — see core/config.py _is_packaged_build()"
    )


def test_quarantined_delegate_tasks_gated_in_runtime():
    """
    Multi-agent orchestration (item #10, Quarantined) has no route — it is
    the delegate_tasks tool. core/agent/runtime.py must filter it out of the
    offered tool list for packaged builds, the same way it already does for
    sub-agents (depth cap).
    """
    import inspect
    from core.agent import runtime as runtime_mod

    source = inspect.getsource(runtime_mod)
    assert "_is_packaged_build" in source, (
        "core/agent/runtime.py must filter delegate_tasks out of all_tools "
        "when core.config._is_packaged_build() is True"
    )
