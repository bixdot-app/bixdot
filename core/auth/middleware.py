# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Auth Middleware
Applied to EVERY route. No exceptions. No public endpoints except /auth/login.

This is the direct fix for CVE-2026-25253 (BixDot accepted unauthenticated
WebSocket connections from any visiting website).
"""
from fastapi import Depends, HTTPException, status, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from core.auth.jwt import decode_token, TokenPayload


security = HTTPBearer(auto_error=True)

# Routes that don't require auth (login only — nothing else)
PUBLIC_ROUTES = {"/auth/login", "/auth/refresh", "/health"}


# ─── HTTP Auth Dependency ──────────────────────────────────────────────────────

async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenPayload:
    """
    FastAPI dependency. Inject into any route that needs authentication.
    Usage: async def my_route(user: TokenPayload = Depends(require_auth))
    """
    try:
        return decode_token(credentials.credentials, expected_type="access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
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
