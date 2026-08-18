# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Auth Middleware

Auth is DENY-BY-DEFAULT at the framework level, enforced in two independent
layers:

  1. AuthGateMiddleware — a raw ASGI middleware that rejects any request whose
     path is not explicitly allowlisted and does not carry a valid JWT. This
     runs before routing, so a route added without an auth dependency is still
     refused.
  2. Depends(require_auth) / Depends(require_owner) — per-route dependencies
     that additionally carry role checks.

Layer 2 alone was the entire protection until v0.7 (BXD-002). That is a
convention — "the developer remembers to inject the dependency" — and it is
precisely the protection OpenClaw had when CVE-2026-25253 shipped an
unauthenticated endpoint. Layer 1 turns it into a control.

tests/test_route_auth.py enumerates app.routes and fails CI if any route is
neither authenticated nor allowlisted, so this cannot silently regress.

Also the direct fix for CVE-2026-25253 (BixDot accepted unauthenticated
WebSocket connections from any visiting website) via ws_require_auth.
"""
from fastapi import Depends, HTTPException, status, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.responses import JSONResponse
import jwt

from core.auth.jwt import decode_token, TokenPayload
from core.storage.db import get_connection


security = HTTPBearer(auto_error=True)

# ─── The allowlist ─────────────────────────────────────────────────────────────
# Every entry needs a reason. Matched EXACTLY — never by prefix — so that
# /health is public while /health/onboarding is not.
#
# tests/test_route_auth.py::test_public_routes_is_exactly freezes this set. A
# new entry fails CI until someone reviews it. That is the point.
PUBLIC_ROUTES = {
    "/auth/login",         # pre-auth by definition — issues the first token
    "/auth/refresh",       # exchanges a refresh token; validates its own credential
    "/health",             # liveness probe for the Tauri shell watchdog
    "/",                   # static login shell; contains no user data
    "/auth/setup",         # first run only — returns 410 Gone once an owner exists
    "/auth/setup-status",  # tells the shell whether to render setup or login
}

# Asset prefixes for the unauthenticated login shell. Kept separate from
# PUBLIC_ROUTES so the allowlist above stays an exact, reviewable set of pages.
PUBLIC_PREFIXES = ("/static/",)

# Routes authenticated by a short-lived, single-use, user-bound state token
# rather than a JWT.
#
# These are top-level browser redirects from Google/Microsoft: the browser
# cannot attach an Authorization header, and BixDot stores its JWT in JS rather
# than a cookie, so no bearer credential can reach them. The `state` parameter
# is already a 128-bit secret minted by an authenticated /calendar/connect/*
# call, bound to a user_id, single-use, and expiring in 5 minutes — a capability
# in every meaningful sense. The middleware verifies one is live before the
# request reaches the route; the route still pops it, preserving single use.
#
# The paths are pinned in Google/Microsoft console configuration and in
# user-facing setup instructions — they cannot be renamed without breaking
# every existing connection.
STATE_AUTHENTICATED = {
    "/calendar/oauth/callback",
    "/calendar/oauth/microsoft/callback",
}


# ─── Shared validation ─────────────────────────────────────────────────────────

class InvalidAccessToken(Exception):
    """Raised by _validate_access_token. Carries a user-safe reason."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _validate_access_token(token: str) -> TokenPayload:
    """
    Full validation of an access token: signature, expiry, type, and revocation.

    One implementation shared by the middleware and the route dependency so the
    two layers can never drift apart on what "valid" means.
    """
    try:
        payload = decode_token(token, expected_type="access")
    except jwt.ExpiredSignatureError:
        raise InvalidAccessToken("Token expired")
    except jwt.InvalidTokenError as e:
        raise InvalidAccessToken(str(e))

    # Blocklist (populated on logout for immediate revocation)
    with get_connection() as conn:
        blocked = conn.execute(
            "SELECT 1 FROM token_blocklist WHERE jti = ? AND expires_at > datetime('now')",
            (payload.jti,),
        ).fetchone()
    if blocked:
        raise InvalidAccessToken("Token has been revoked")

    return payload


def is_public_path(path: str) -> bool:
    """True if `path` may be served without any credential."""
    return path in PUBLIC_ROUTES or path.startswith(PUBLIC_PREFIXES)


# ─── Layer 1 — deny-by-default ASGI middleware ─────────────────────────────────

class AuthGateMiddleware:
    """
    Reject every request that is neither allowlisted nor authenticated, before
    routing happens.

    Deliberately a raw ASGI middleware rather than BaseHTTPMiddleware: `send` is
    passed straight through, so the NDJSON progress streams on
    /agent/models/pull and /agent/onboarding/download-ollama are not buffered.
    Those can run for many minutes and carry multiple gigabytes.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # CORS preflight carries no Authorization header by design. CORSMiddleware
        # is mounted outside this one and answers it; never reject it here.
        if scope.get("method") == "OPTIONS":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")

        if is_public_path(path):
            return await self.app(scope, receive, send)

        if path in STATE_AUTHENTICATED:
            if _has_live_oauth_state(scope):
                return await self.app(scope, receive, send)
            return await self._deny(scope, receive, send,
                                    "Invalid or expired authorization state")

        token = _bearer_from_scope(scope)
        if not token:
            return await self._deny(scope, receive, send, "Not authenticated")
        try:
            _validate_access_token(token)
        except InvalidAccessToken as e:
            return await self._deny(scope, receive, send, e.reason)

        return await self.app(scope, receive, send)

    @staticmethod
    async def _deny(scope, receive, send, detail: str):
        response = JSONResponse(
            {"detail": detail},
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )
        await response(scope, receive, send)


def _bearer_from_scope(scope) -> str:
    """Extract a Bearer token from the raw ASGI header list."""
    for name, value in scope.get("headers", []):
        if name == b"authorization":
            raw = value.decode("latin-1").strip()
            scheme, _, token = raw.partition(" ")
            if scheme.lower() == "bearer":
                return token.strip()
            return ""
    return ""


def _has_live_oauth_state(scope) -> bool:
    """
    Non-destructive check that the OAuth `state` in the query string is live.

    Peeks only — the route handler still pops the entry, so a state token
    remains single-use.
    """
    from urllib.parse import parse_qs

    qs = parse_qs(scope.get("query_string", b"").decode("latin-1"))
    state = (qs.get("state") or [""])[0]
    if not state:
        return False
    try:
        from core.skills.calendar.routes import peek_oauth_state
        return peek_oauth_state(state)
    except Exception:
        return False


# ─── Layer 2 — HTTP Auth Dependency ────────────────────────────────────────────

async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenPayload:
    """
    FastAPI dependency. Inject into any route that needs authentication.
    Usage: async def my_route(user: TokenPayload = Depends(require_auth))

    Kept alongside AuthGateMiddleware as defence in depth, and because it is
    what supplies the authenticated user object and the role checks.
    """
    try:
        return _validate_access_token(credentials.credentials)
    except InvalidAccessToken as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.reason,
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_owner(user: TokenPayload = Depends(require_auth)) -> TokenPayload:
    """
    Require owner-level privilege.
    Role is always derived from the authenticated JWT — never from client input.
    This directly closes CVE-2026-44118 (senderIsOwner header spoofing).
    """
    if user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner privilege required",
        )
    return user


# ─── WebSocket Auth ────────────────────────────────────────────────────────────

async def ws_require_auth(websocket: WebSocket) -> TokenPayload:
    """
    WebSocket authentication via query param token.
    Validates Origin header before accepting the connection.

    This directly closes CVE-2026-25253 (cross-site WebSocket hijacking).
    BixDot trusted any WebSocket connection to its localhost server.
    We validate origin AND require a valid JWT on every WebSocket upgrade.
    """
    from core.config import settings

    # 1. Validate Origin header — reject any non-allowlisted origin
    origin = websocket.headers.get("origin", "")
    if origin and origin not in settings.allowed_origins:
        await websocket.close(code=4001, reason="Origin not allowed")
        raise HTTPException(status_code=403, detail="Origin not allowed")

    # 2. Require token in query params (can't set Authorization header in WS)
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="No token provided")
        raise HTTPException(status_code=401, detail="No token provided")

    # 3. Validate the token exactly like HTTP routes
    try:
        return decode_token(token, expected_type="access")
    except jwt.InvalidTokenError as e:
        await websocket.close(code=4001, reason="Invalid token")
        raise HTTPException(status_code=401, detail=str(e))
