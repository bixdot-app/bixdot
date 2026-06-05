# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Auth Routes
Endpoints: /setup, /login, /refresh, /logout, /me

Security notes:
- /setup is only available before first user is created. Disabled permanently after.
- Login responses never reveal whether username or password was wrong (timing-safe).
- Refresh tokens are rotated on every use — old token immediately revoked.
- Logout revokes both access and refresh tokens.
- Rate limiting applied at the route level.
"""
import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status

from core.security import limiter
from core.auth.jwt import (
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from core.auth.middleware import require_auth
from core.auth.models import (
    LoginRequest,
    RefreshRequest,
    SetupRequest,
    SetupStatusResponse,
    TokenResponse,
    UserResponse,
)
from core.audit.logger import AuditEvent, get_audit_logger
from core.config import settings
from core.storage.db import get_connection, is_first_run

router = APIRouter(prefix="/auth", tags=["auth"])
audit = get_audit_logger()


# ─── Setup Wizard ─────────────────────────────────────────────────────────────

@router.get("/setup-status", response_model=SetupStatusResponse)
async def setup_status():
    """Check if first-run setup is needed. Safe to call unauthenticated."""
    first_run = is_first_run()
    return SetupStatusResponse(
        setup_complete=not first_run,
        message="Setup required" if first_run else "BixDot is ready",
    )


@router.post("/setup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def setup(request: SetupRequest, req: Request):
    """
    First-run owner account creation.
    This endpoint DISABLES itself permanently after the first user is created.
    Any call after setup is complete returns 410 Gone.
    """
    if not is_first_run():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Setup already complete. This endpoint is permanently disabled.",
        )

    user_id = str(uuid.uuid4())
    password_hash = hash_password(request.password)

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role)
               VALUES (?, ?, ?, 'owner')""",
            (user_id, request.username, password_hash),
        )

    audit.log(
        AuditEvent.AUTH_LOGIN_SUCCESS,
        {"event": "owner_account_created", "username": request.username,
         "ip": req.client.host if req.client else "unknown"},
        user_id=user_id,
    )

    tokens = create_token_pair(user_id, "owner")
    _store_refresh_token(tokens.refresh_token, user_id)

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        role="owner",
    )


# ─── Login ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest):
    """
    Authenticate with username + password.
    Returns a token pair on success.

    Timing-safe: identical response time for wrong username vs wrong password.
    Never reveals which field was incorrect.
    """
    user = _get_user_by_username(body.username)

    # Always run bcrypt — prevents timing attacks revealing valid usernames
    dummy_hash = "$2b$12$invalidhashfortimingnormalization000000000000000000000"
    stored_hash = user["password_hash"] if user else dummy_hash

    password_valid = verify_password(body.password, stored_hash)

    if not user or not password_valid or not user["is_active"]:
        audit.log(
            AuditEvent.AUTH_LOGIN_FAILURE,
            {"username": body.username, "ip": request.client.host if request.client else "unknown"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = datetime('now') WHERE id = ?",
            (user["id"],),
        )

    audit.log(
        AuditEvent.AUTH_LOGIN_SUCCESS,
        {"username": body.username, "ip": request.client.host if request.client else "unknown"},
        user_id=user["id"],
    )

    tokens = create_token_pair(user["id"], user["role"])
    _store_refresh_token(tokens.refresh_token, user["id"])

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        role=user["role"],
    )


# ─── Refresh ──────────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh(request: Request, body: RefreshRequest):
    """
    Exchange a valid refresh token for a new token pair.
    Old refresh token is immediately revoked (rotation).
    Replay of a revoked refresh token = all sessions for that user revoked.
    """
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    with get_connection() as conn:
        token_row = conn.execute(
            "SELECT * FROM refresh_tokens WHERE jti = ?", (payload.jti,)
        ).fetchone()

        if not token_row:
            raise HTTPException(status_code=401, detail="Token not found")

        if token_row["revoked"]:
            # Possible replay attack — revoke ALL tokens for this user
            conn.execute(
                "UPDATE refresh_tokens SET revoked=1, revoked_at=datetime('now') "
                "WHERE user_id = ? AND revoked = 0",
                (payload.sub,),
            )
            audit.log(
                AuditEvent.AUTH_LOGIN_FAILURE,
                {"event": "refresh_token_replay_detected", "jti": payload.jti},
                user_id=payload.sub,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token replay detected. All sessions revoked. Please log in again.",
            )

        # Revoke old refresh token
        conn.execute(
            "UPDATE refresh_tokens SET revoked=1, revoked_at=datetime('now') WHERE jti=?",
            (payload.jti,),
        )

    user = _get_user_by_id(payload.sub)
    if not user or not user["is_active"]:
        raise HTTPException(status_code=401, detail="User not found or deactivated")

    audit.log(
        AuditEvent.AUTH_TOKEN_REFRESH,
        {"old_jti": payload.jti},
        user_id=payload.sub,
    )

    tokens = create_token_pair(payload.sub, payload.role)
    _store_refresh_token(tokens.refresh_token, payload.sub)

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        role=payload.role,
    )


# ─── Logout ───────────────────────────────────────────────────────────────────

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: RefreshRequest,
    user=Depends(require_auth),
):
    """
    Revoke the current refresh token and blocklist the access token for immediate
    revocation — no waiting for the 15-minute expiry window.
    """
    # Blocklist the access token so it's rejected immediately by require_auth
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO token_blocklist (jti, expires_at) VALUES (?, ?)",
            (user.jti, user.exp.isoformat()),
        )

    try:
        payload = decode_token(request.refresh_token, expected_type="refresh")
        with get_connection() as conn:
            conn.execute(
                "UPDATE refresh_tokens SET revoked=1, revoked_at=datetime('now') "
                "WHERE jti=? AND user_id=?",
                (payload.jti, user.sub),
            )
    except jwt.InvalidTokenError:
        pass  # Token already invalid — logout is still successful

    audit.log(AuditEvent.AUTH_LOGOUT, {}, user_id=user.sub)


# ─── Current User ─────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def me(user=Depends(require_auth)):
    """Return current authenticated user's profile."""
    row = _get_user_by_id(user.sub)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=row["id"],
        username=row["username"],
        role=row["role"],
        created_at=row["created_at"],
        last_login_at=row["last_login_at"],
    )


# ─── Private Helpers ──────────────────────────────────────────────────────────

def _get_user_by_username(username: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.lower(),)
        ).fetchone()


def _get_user_by_id(user_id: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def _store_refresh_token(token: str, user_id: str) -> None:
    """Store a new refresh token in the registry."""
    payload = decode_token(token, expected_type="refresh")
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO refresh_tokens (jti, user_id, expires_at) VALUES (?, ?, ?)",
            (payload.jti, user_id, payload.exp.isoformat()),
        )
