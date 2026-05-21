# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.dev
# Security disclosures: security@bixdot.dev
# See LICENSE in the project root for full terms.

"""
BixDot — Authentication
JWT implementation with zero bypass paths.

Design decisions (directly addressing OpenClaw CVEs):
- senderIsOwner is ALWAYS derived from the authenticated token.
  Never from a client-provided header, body param, or query string.
- Access tokens expire in 15 minutes.
- Refresh tokens rotate on every use (replay detection built in).
- No debug/admin backdoor that skips validation.
"""
from datetime import datetime, timedelta, UTC
from typing import Literal
import jwt
import bcrypt
from pydantic import BaseModel

from core.config import settings


# ─── Token Models ──────────────────────────────────────────────────────────────

class TokenPayload(BaseModel):
    sub: str                              # User ID
    role: Literal["owner", "operator"]   # Privilege level — server-derived ONLY
    token_type: Literal["access", "refresh"]
    exp: datetime
    iat: datetime
    jti: str                              # Unique token ID for revocation


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = settings.jwt_access_token_expire_minutes * 60


# ─── Token Generation ──────────────────────────────────────────────────────────

def create_access_token(user_id: str, role: Literal["owner", "operator"]) -> str:
    """
    Create a short-lived access token.
    Role is set HERE on the server — never accepted from the client.
    """
    import uuid
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,               # Server-authoritative. Full stop.
        "token_type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str, role: Literal["owner", "operator"]) -> str:
    """Refresh tokens are longer-lived but rotated on every use."""
    import uuid
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "role": role,
        "token_type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_token_expire_days),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_token_pair(user_id: str, role: Literal["owner", "operator"]) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id, role),
        refresh_token=create_refresh_token(user_id, role),
    )


# ─── Token Validation ──────────────────────────────────────────────────────────

def decode_token(token: str, expected_type: Literal["access", "refresh"] = "access") -> TokenPayload:
    """
    Decode and fully validate a JWT.
    Raises jwt.InvalidTokenError on any failure — callers must handle.
    """
    try:
        raw = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "role", "token_type", "exp", "iat", "jti"]},
        )
    except jwt.ExpiredSignatureError:
        raise jwt.ExpiredSignatureError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise jwt.InvalidTokenError(f"Invalid token: {e}")

    if raw.get("token_type") != expected_type:
        raise jwt.InvalidTokenError(
            f"Expected {expected_type} token, got {raw.get('token_type')}"
        )

    return TokenPayload(**raw)


# ─── Password Hashing ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """bcrypt with cost factor 12."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())
