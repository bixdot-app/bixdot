# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BXD-002 — mandatory auth must be a control, not a convention.

`PUBLIC_ROUTES` used to be dead data: nothing read it, auth was a per-route
dependency a developer had to remember, and 10 routes were unauthenticated
against a 3-entry allowlist. CVE-2026-25253 — the failure BixDot exists to
fix — was an unauthenticated endpoint.

The enumeration test below is the one that matters: it walks every registered
route and fails if any is neither authenticated nor explicitly allowlisted, so
"the next route added in a hurry at 1am" cannot ship unauthenticated.
"""
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from core.auth.middleware import (
    PUBLIC_PREFIXES,
    PUBLIC_ROUTES,
    STATE_AUTHENTICATED,
    AuthGateMiddleware,
    require_auth,
    require_owner,
)


def _has_auth_dependency(route: APIRoute) -> bool:
    """True if require_auth/require_owner appears anywhere in the chain."""
    guards = {require_auth, require_owner}
    seen, stack = set(), list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        if id(dep) in seen:
            continue
        seen.add(id(dep))
        if dep.call in guards:
            return True
        stack.extend(dep.dependencies)
    return False


def _api_routes() -> list[APIRoute]:
    from core.main import app
    return [r for r in app.routes if isinstance(r, APIRoute)]


# ─── C-3.1 — the enumeration test ──────────────────────────────────────────────

def test_every_route_is_authenticated_or_allowlisted():
    """
    Every route carries an auth dependency, or its path is deliberately public.

    If this fails, read the offending path: either add Depends(require_auth),
    or add it to PUBLIC_ROUTES with a justification comment and accept that
    test_public_routes_is_exactly will also need updating. Do not silence it.
    """
    unguarded = [
        f"{sorted(r.methods)} {r.path}"
        for r in _api_routes()
        if not _has_auth_dependency(r)
        and r.path not in PUBLIC_ROUTES
        and r.path not in STATE_AUTHENTICATED
        and not r.path.startswith(PUBLIC_PREFIXES)
    ]
    assert not unguarded, (
        "Unauthenticated routes outside the allowlist:\n  " + "\n  ".join(unguarded)
    )


def test_public_routes_is_exactly():
    """
    Frozen allowlist. A new public route fails CI until a human reviews it.
    Each entry carries a one-line justification in core/auth/middleware.py.
    """
    assert PUBLIC_ROUTES == {
        "/auth/login",
        "/auth/refresh",
        "/health",
        "/",
        "/auth/setup",
        "/auth/setup-status",
        "/auth/recover",
    }


def test_allowlist_is_exact_match_not_prefix():
    """
    /health is public; /health/onboarding must not inherit that.
    A startswith() allowlist would silently expose every /health/* route.
    """
    from core.auth.middleware import is_public_path
    assert is_public_path("/health") is True
    assert is_public_path("/health/onboarding") is False
    assert is_public_path("/auth/login") is True
    assert is_public_path("/auth/login/../me") is False


def test_static_assets_are_public_but_nothing_else_is():
    from core.auth.middleware import is_public_path
    assert is_public_path("/static/react.production.min.js") is True
    assert is_public_path("/agent/sessions") is False


# ─── C-3.3 — the middleware catches a route the dependency missed ──────────────

def test_middleware_denies_route_without_dependency():
    """
    The whole point of layer 1. A developer adds a route and forgets
    Depends(require_auth); the request must still be refused.

    Fails before the fix: without the middleware this returns 200.
    """
    app = FastAPI()
    app.add_middleware(AuthGateMiddleware)

    @app.get("/__forgot_the_dependency__")
    async def oops():
        return {"secret": "leaked"}

    with TestClient(app) as c:
        r = c.get("/__forgot_the_dependency__")
    assert r.status_code == 401, "an unguarded route was served without a token"


def test_middleware_allows_public_path_without_token():
    app = FastAPI()
    app.add_middleware(AuthGateMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    with TestClient(app) as c:
        assert c.get("/health").status_code == 200


def test_middleware_rejects_garbage_and_malformed_tokens(client):
    for header in ("Bearer not-a-jwt", "Basic abc123", "bearer", "Bearer "):
        r = client.get("/auth/me", headers={"Authorization": header})
        assert r.status_code in (401, 403), f"accepted {header!r}"


def test_middleware_does_not_break_authenticated_requests(client, auth_headers):
    assert client.get("/auth/me", headers=auth_headers).status_code == 200


def test_cors_preflight_survives_the_gate(client):
    """OPTIONS carries no Authorization header; the gate must not eat it."""
    r = client.options(
        "/agent/sessions",
        headers={
            "Origin": "http://localhost:8747",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code < 400, "CORS preflight was rejected by the auth gate"


# ─── /health/onboarding — no pre-auth host disclosure ──────────────────────────

def test_onboarding_requires_auth(client):
    """Was unauthenticated; disclosed Ollama URL, model names and platform."""
    assert client.get("/health/onboarding").status_code in (401, 403)


def test_onboarding_does_not_disclose_the_ollama_url(client, auth_headers):
    r = client.get("/health/onboarding", headers=auth_headers)
    assert r.status_code == 200
    assert "ollama_url" not in r.json(), "the resolved Ollama host is still exposed"


def test_health_stays_public(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ─── OAuth callbacks — state-token authenticated ───────────────────────────────

def test_oauth_callback_rejected_without_state(client):
    r = client.get("/calendar/oauth/callback", params={"code": "abc"})
    assert r.status_code == 401


def test_oauth_callback_rejected_with_unknown_state(client):
    r = client.get("/calendar/oauth/callback",
                   params={"code": "abc", "state": "never-issued"})
    assert r.status_code == 401


def test_oauth_callback_rejected_with_expired_state(client, monkeypatch):
    import time
    from core.skills.calendar import routes as cal

    monkeypatch.setitem(cal._oauth_states, "stale", {
        "code_verifier": "v", "client_id": "c", "client_secret": "s",
        "user_id": "u", "expires_at": time.monotonic() - 1,
    })
    r = client.get("/calendar/oauth/callback",
                   params={"code": "abc", "state": "stale"})
    assert r.status_code == 401


def test_oauth_callback_admitted_with_live_state(client, monkeypatch):
    """A live state must reach the handler — the flow still has to work."""
    import time
    from core.skills.calendar import routes as cal

    monkeypatch.setitem(cal._oauth_states, "live", {
        "code_verifier": "v", "client_id": "c", "client_secret": "s",
        "user_id": "u", "expires_at": time.monotonic() + 300,
    })
    r = client.get("/calendar/oauth/callback",
                   params={"code": "abc", "state": "live"})
    # The token exchange fails (no real Google), but the gate let it through —
    # that is what is under test here.
    assert r.status_code == 200
    assert "Connection failed" in r.text


def test_peek_does_not_consume_the_state(monkeypatch):
    """Single-use is preserved: the middleware peeks, the handler pops."""
    import time
    from core.skills.calendar import routes as cal

    monkeypatch.setitem(cal._oauth_states, "keepme", {
        "code_verifier": "v", "client_id": "c", "client_secret": "s",
        "user_id": "u", "expires_at": time.monotonic() + 300,
    })
    assert cal.peek_oauth_state("keepme") is True
    assert cal.peek_oauth_state("keepme") is True, "peek consumed the state"
    assert "keepme" in cal._oauth_states


@pytest.mark.parametrize("state", ["", "unknown"])
def test_peek_rejects_missing_and_unknown_states(state):
    from core.skills.calendar.routes import peek_oauth_state
    assert peek_oauth_state(state) is False


# ─── Streaming must not be buffered by the gate ────────────────────────────────

def test_streaming_response_passes_through_the_gate():
    """
    The gate is raw ASGI precisely so NDJSON progress streams are not buffered.
    A BaseHTTPMiddleware here would hold a multi-GB model pull in memory.
    """
    import json

    from starlette.responses import StreamingResponse

    app = FastAPI()
    app.add_middleware(AuthGateMiddleware)

    @app.get("/health")           # public, so no token needed for the test
    async def stream():
        async def gen():
            for i in range(3):
                yield json.dumps({"chunk": i}) + "\n"
        return StreamingResponse(gen(), media_type="application/x-ndjson")

    with TestClient(app) as c:
        with c.stream("GET", "/health") as r:
            chunks = [line for line in r.iter_lines() if line]
    assert len(chunks) == 3
