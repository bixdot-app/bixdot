# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Auth route integration tests.

Verifies the full authentication flow via HTTP:
- Setup wizard (one-time, permanently disabled after first user)
- Login (timing-safe, no username enumeration)
- Token refresh (rotation, replay detection)
- Logout (immediate access token revocation via blocklist)
- Protected routes enforce auth
- Role is always server-derived
"""
import pytest
from fastapi.testclient import TestClient


# ── /health — unauthenticated ───────────────────────────────────────────────────

def test_health_no_auth_required(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_returns_version(client):
    from core.config import settings
    r = client.get("/health")
    assert r.json()["version"] == settings.version


# ── /auth/setup ─────────────────────────────────────────────────────────────────

def test_setup_creates_owner_account(client):
    r = client.post("/auth/setup", json={"username": "admin", "password": "SecureP@ss1!"})
    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["role"] == "owner"


def test_setup_permanently_disabled_after_first_use(client):
    client.post("/auth/setup", json={"username": "admin", "password": "SecureP@ss1!"})
    r = client.post("/auth/setup", json={"username": "admin2", "password": "AnotherP@ss1"})
    assert r.status_code == 410  # Gone — endpoint permanently disabled


def test_setup_status_before_setup(client):
    r = client.get("/auth/setup-status")
    assert r.status_code == 200
    assert r.json()["setup_complete"] is False


def test_setup_status_after_setup(client):
    client.post("/auth/setup", json={"username": "admin", "password": "SecureP@ss1!"})
    r = client.get("/auth/setup-status")
    assert r.json()["setup_complete"] is True


# ── /auth/login ─────────────────────────────────────────────────────────────────

def test_login_success(client):
    client.post("/auth/setup", json={"username": "admin", "password": "SecureP@ss1!"})
    r = client.post("/auth/login", json={"username": "admin", "password": "SecureP@ss1!"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["role"] == "owner"


def test_login_wrong_password(client):
    client.post("/auth/setup", json={"username": "admin", "password": "SecureP@ss1!"})
    r = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_nonexistent_username(client):
    client.post("/auth/setup", json={"username": "admin", "password": "SecureP@ss1!"})
    r = client.post("/auth/login", json={"username": "nobody", "password": "SecureP@ss1!"})
    assert r.status_code == 401


def test_login_error_message_does_not_reveal_field(client):
    """The error detail must be the same regardless of whether username or password is wrong."""
    client.post("/auth/setup", json={"username": "admin", "password": "SecureP@ss1!"})
    r_bad_pass = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    r_bad_user = client.post("/auth/login", json={"username": "nobody", "password": "wrong"})
    # Both return the same generic message — no username enumeration
    assert r_bad_pass.json()["detail"] == r_bad_user.json()["detail"]


def test_login_username_case_insensitive(client):
    """Usernames are stored lowercase — login with uppercase must work."""
    client.post("/auth/setup", json={"username": "Admin", "password": "SecureP@ss1!"})
    r = client.post("/auth/login", json={"username": "ADMIN", "password": "SecureP@ss1!"})
    assert r.status_code == 200


# ── Protected routes ────────────────────────────────────────────────────────────

def test_protected_route_requires_auth(client):
    r = client.get("/auth/me")
    assert r.status_code in (401, 403)  # HTTPBearer returns 403 or 401 for missing credentials


def test_protected_route_invalid_token(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_protected_route_valid_token(client, auth_headers):
    r = client.get("/auth/me", headers=auth_headers)
    assert r.status_code == 200


def test_me_returns_correct_user(client, auth_headers):
    r = client.get("/auth/me", headers=auth_headers)
    data = r.json()
    assert data["username"] == "testowner"
    assert data["role"] == "owner"


def test_role_is_server_derived(client):
    """Role in the returned token must always match what the server assigned, not client input."""
    client.post("/auth/setup", json={"username": "admin", "password": "SecureP@ss1!"})
    r = client.post("/auth/login", json={"username": "admin", "password": "SecureP@ss1!"})
    assert r.json()["role"] == "owner"

    from core.auth.jwt import decode_token
    payload = decode_token(r.json()["access_token"], expected_type="access")
    assert payload.role == "owner"  # Server-set, not client-controlled


# ── /auth/logout — access token blocklist ──────────────────────────────────────

def test_logout_invalidates_access_token(client, owner_tokens):
    access, refresh = owner_tokens
    headers = {"Authorization": f"Bearer {access}"}

    # Token works before logout
    assert client.get("/auth/me", headers=headers).status_code == 200

    # Logout
    r = client.post("/auth/logout", json={"refresh_token": refresh}, headers=headers)
    assert r.status_code == 204

    # Same access token must now be rejected immediately (blocklist)
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 401


# ── /auth/refresh — token rotation ─────────────────────────────────────────────

def test_refresh_returns_new_token_pair(client, owner_tokens):
    _, refresh = owner_tokens
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # New refresh token must be different
    assert data["refresh_token"] != refresh


def test_refresh_old_token_revoked_after_rotation(client, owner_tokens):
    """After refresh, the original refresh token must be rejected."""
    _, refresh = owner_tokens
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200

    # Try to use the old refresh token again
    r2 = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 401


def test_refresh_replay_revokes_all_sessions(client, owner_tokens):
    """
    Replaying a revoked refresh token signals a possible attack.
    BixDot must revoke ALL sessions for that user.
    """
    _, refresh = owner_tokens

    # First rotation — legitimate
    r1 = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r1.status_code == 200
    new_refresh = r1.json()["refresh_token"]

    # Replay the original (revoked) token — should trigger full revocation
    r2 = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 401

    # New refresh token from the legitimate rotation must also now be rejected
    r3 = client.post("/auth/refresh", json={"refresh_token": new_refresh})
    assert r3.status_code == 401


def test_invalid_refresh_token_rejected(client):
    r = client.post("/auth/refresh", json={"refresh_token": "totally-fake-token"})
    assert r.status_code == 401


def test_access_token_rejected_as_refresh(client, owner_tokens):
    """An access token must not be accepted at the refresh endpoint."""
    access, _ = owner_tokens
    r = client.post("/auth/refresh", json={"refresh_token": access})
    assert r.status_code == 401
