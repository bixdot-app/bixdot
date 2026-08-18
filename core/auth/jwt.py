# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Authentication
JWT implementation with zero bypass paths.

Design decisions (directly addressing BixDot CVEs):
- senderIsOwner is ALWAYS derived from the authenticated token.
  Never from a client-provided header, body param, or query string.
- Access tokens expire in 15 minutes.
- Refresh tokens rotate on every use (replay detection built in).
- No debug/admin backdoor that skips validation.
"""
import base64
import hashlib
import secrets
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
#
# BXD-014: bcrypt only considers the first 72 bytes of a password. Depending on
# the library version it either silently truncates (bcrypt < 4.1 — two different
# long passphrases then authenticate interchangeably) or raises ValueError
# (bcrypt >= 4.1 — /auth/setup returns a 500 on a long passphrase). Our floor is
# bcrypt>=4.2.0, so both behaviours exist in the field. SetupRequest allows 128
# characters, so either way the promise was false.
#
# Pre-hashing with SHA-256 and base64-encoding the digest gives a fixed 44-byte
# input that preserves the entropy of the whole passphrase. Base64 rather than
# hex or the raw digest because bcrypt stops at the first NUL byte, and base64
# output contains none.

BCRYPT_SHA256 = "sha256-bcrypt"   # current scheme
BCRYPT_LEGACY = "bcrypt-legacy"   # pre-v0.7 rows: raw password into bcrypt

_BCRYPT_ROUNDS = 12


def _prehash(password: str) -> bytes:
    """SHA-256 → base64. 44 bytes, no NULs, full passphrase entropy retained."""
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def _password_input(password: str, scheme: str) -> bytes:
    if scheme == BCRYPT_LEGACY:
        # Reproduce the old behaviour exactly so existing accounts still verify.
        return password.encode("utf-8")[:72]
    return _prehash(password)


def hash_password(password: str) -> str:
    """bcrypt cost 12 over the SHA-256 pre-hash. Always the current scheme."""
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def verify_password(password: str, hashed: str, scheme: str = BCRYPT_SHA256) -> bool:
    """
    Check a password against a stored hash under the given scheme.

    Exactly one bcrypt operation runs on either path, which is what keeps the
    login timing-normalisation in auth/routes.py honest — trying both schemes
    in sequence would make a legacy row measurably slower than a miss.
    """
    try:
        return bcrypt.checkpw(_password_input(password, scheme), hashed.encode())
    except ValueError:
        # Malformed stored hash, or a legacy row whose bytes bcrypt rejects.
        return False


def dummy_hash() -> str:
    """
    A real bcrypt hash of random bytes, for timing normalisation on login.

    Computed once and cached. The previous inline constant was not a valid
    bcrypt hash, so checkpw raised ValueError immediately instead of doing the
    work — the wrong-username path was therefore much faster than the
    wrong-password path, defeating the normalisation it existed to provide.
    Lazy so that importing this module stays cheap.
    """
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = bcrypt.hashpw(
            _prehash(secrets.token_urlsafe(32)), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
        ).decode()
    return _DUMMY_HASH


_DUMMY_HASH: str | None = None
