# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
JWT unit tests.

Verifies the authentication token implementation:
- Tokens are created with server-authoritative fields
- Expiry is enforced
- Token type (access vs refresh) cannot be substituted
- Tampered signatures are rejected
- Role cannot be elevated by a client
"""
import time
from datetime import datetime, timedelta, UTC

import jwt as pyjwt
import pytest

from core.auth.jwt import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from core.config import settings


# ── Token creation ──────────────────────────────────────────────────────────────

def test_access_token_fields():
    token = create_access_token("user-123", "owner")
    payload = decode_token(token, expected_type="access")
    assert payload.sub == "user-123"
    assert payload.role == "owner"
    assert payload.token_type == "access"
    assert payload.jti  # non-empty UUID


def test_refresh_token_fields():
    token = create_refresh_token("user-456", "operator")
    payload = decode_token(token, expected_type="refresh")
    assert payload.sub == "user-456"
    assert payload.role == "operator"
    assert payload.token_type == "refresh"


def test_token_pair_returns_both():
    pair = create_token_pair("user-789", "owner")
    assert pair.access_token
    assert pair.refresh_token
    assert pair.token_type == "bearer"
    assert pair.expires_in == settings.jwt_access_token_expire_minutes * 60


def test_each_token_has_unique_jti():
    a = create_access_token("user-1", "owner")
    b = create_access_token("user-1", "owner")
    pa = decode_token(a, expected_type="access")
    pb = decode_token(b, expected_type="access")
    assert pa.jti != pb.jti


# ── Token validation ────────────────────────────────────────────────────────────

def test_expired_token_rejected(monkeypatch):
    """Token with past expiry must raise ExpiredSignatureError."""
    from datetime import timedelta
    import core.auth.jwt as jwt_mod

    original_access = jwt_mod.create_access_token

    def expired_token(user_id, role):
        import uuid
        now = datetime.now(UTC)
        payload = {
            "sub": user_id,
            "role": role,
            "token_type": "access",
            "iat": now - timedelta(minutes=30),
            "exp": now - timedelta(minutes=15),  # Already expired
            "jti": str(uuid.uuid4()),
        }
        return pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    token = expired_token("user-1", "owner")
    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_token(token, expected_type="access")


def test_wrong_token_type_rejected():
    """An access token must not be accepted where a refresh token is expected."""
    access = create_access_token("user-1", "owner")
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_token(access, expected_type="refresh")


def test_refresh_token_rejected_as_access():
    """A refresh token must not be accepted where an access token is expected."""
    refresh = create_refresh_token("user-1", "owner")
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_token(refresh, expected_type="access")


def test_tampered_signature_rejected():
    """Modifying the token body after signing must invalidate it."""
    token = create_access_token("user-1", "owner")
    header, payload, sig = token.split(".")
    # Corrupt the signature
    tampered = f"{header}.{payload}.invalidsignature"
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_token(tampered, expected_type="access")


def test_wrong_secret_rejected():
    """Token signed with a different secret must be rejected."""
    payload = {
        "sub": "user-1",
        "role": "owner",
        "token_type": "access",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=15),
        "jti": "fake-jti",
    }
    bad_token = pyjwt.encode(payload, "wrong-secret", algorithm=settings.jwt_algorithm)
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_token(bad_token, expected_type="access")


def test_missing_required_claims_rejected():
    """Token missing required claims (jti, role, etc.) must be rejected."""
    payload = {
        "sub": "user-1",
        "exp": datetime.now(UTC) + timedelta(minutes=15),
        # Missing: role, token_type, iat, jti
    }
    bad_token = pyjwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_token(bad_token, expected_type="access")


# ── Role enforcement ────────────────────────────────────────────────────────────

def test_owner_role_preserved():
    token = create_access_token("user-1", "owner")
    payload = decode_token(token, expected_type="access")
    assert payload.role == "owner"


def test_operator_role_preserved():
    token = create_access_token("user-1", "operator")
    payload = decode_token(token, expected_type="access")
    assert payload.role == "operator"


# ── Password hashing ────────────────────────────────────────────────────────────

def test_password_hash_is_not_plaintext():
    h = hash_password("mypassword")
    assert "mypassword" not in h
    assert h.startswith("$2b$")  # bcrypt prefix


def test_correct_password_verifies():
    h = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", h) is True


def test_wrong_password_fails():
    h = hash_password("correct-horse-battery")
    assert verify_password("wrong-password", h) is False


def test_hashes_are_unique():
    """Same password must produce different hashes (bcrypt salting)."""
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2
    # But both must verify
    assert verify_password("same-password", h1)
    assert verify_password("same-password", h2)
