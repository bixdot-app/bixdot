# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BXD-004 — password change and recovery.
BXD-014 — bcrypt's 72-byte limit, and unbounded login fields.

Before v0.7 there was no way to change a password and no recovery path. A user
who mistyped their password into a manager during setup was permanently locked
out of their own local data — the single most likely way the first ten testers
were going to be lost, and one they would blame on themselves rather than
report.

Covers cases B9, B15, B16, C6, C7 and C8 of
docs/governance/07_USER_BASICS_ACCEPTANCE.md.
"""
import pytest

from core.auth.jwt import (
    BCRYPT_LEGACY,
    BCRYPT_SHA256,
    hash_password,
    verify_password,
)
from core.auth.recovery import (
    generate_recovery_code,
    hash_recovery_code,
    normalise_recovery_code,
    verify_recovery_code,
)

GOOD = "S3cur3P@ss!1"
NEW = "N3wP@ssw0rd!x"


@pytest.fixture()
def audit_log(monkeypatch):
    """
    The audit logger the auth routes actually write to.

    core/auth/routes.py binds `audit = get_audit_logger()` at import time, so
    conftest's singleton reset does not reach it and route events would land in
    whichever temp DB the first test created. Rebind before asserting.
    """
    import core.auth.routes as auth_routes
    from core.audit.logger import get_audit_logger

    logger = get_audit_logger()
    monkeypatch.setattr(auth_routes, "audit", logger)
    return logger


def _next_second():
    """
    Block until the wall clock crosses into the next whole second.

    JWT `iat` has one-second resolution (RFC 7519), so a token minted in the
    same second as a password change legitimately survives it — see the
    resolution caveat in core/auth/middleware.py. Crossing the boundary is what
    makes a revocation assertion meaningful rather than accidental.
    """
    import time
    start = int(time.time())
    while int(time.time()) == start:
        time.sleep(0.02)


# ─── BXD-014 — the 72-byte cliff ───────────────────────────────────────────────

def test_long_passphrase_beyond_72_bytes_actually_matters():
    """
    Case B9. Two 100-character passphrases differing only at character 80 must
    not authenticate interchangeably.

    Before the fix bcrypt saw only the first 72 bytes, so on bcrypt < 4.1 these
    two were the same password, and on bcrypt >= 4.1 hashing raised outright.
    """
    base = "Aa1!" + "x" * 76           # 80 chars
    one = base + "AAAAAAAAAAAAAAAAAAAA"
    two = base + "BBBBBBBBBBBBBBBBBBBB"
    assert len(one) == len(two) == 100

    stored = hash_password(one)
    assert verify_password(one, stored) is True
    assert verify_password(two, stored) is False, "bcrypt truncation still active"


def test_hashing_a_long_passphrase_does_not_raise():
    """bcrypt >= 4.1 raises past 72 bytes; setup returned a 500 on case B9."""
    assert hash_password("Aa1!" + "z" * 200)


@pytest.mark.parametrize("password", [
    "Pässwörd123!éàü",              # case B15 — accented
    "密碼Password123!",              # case B15 — CJK
    "Pass123!🔐🔐🔐secure",          # case B16 — emoji
])
def test_non_ascii_passwords_round_trip(password):
    """Accepted-then-unusable is the failure mode these cases exist to catch."""
    stored = hash_password(password)
    assert verify_password(password, stored) is True
    assert verify_password(password + "x", stored) is False


def test_legacy_scheme_still_verifies():
    """An existing v0.6.3 row must keep working, or the fix causes a lockout."""
    import bcrypt
    legacy = bcrypt.hashpw(GOOD.encode(), bcrypt.gensalt(rounds=4)).decode()
    assert verify_password(GOOD, legacy, BCRYPT_LEGACY) is True
    assert verify_password("wrong", legacy, BCRYPT_LEGACY) is False


def test_malformed_stored_hash_returns_false_not_raises():
    assert verify_password(GOOD, "not-a-bcrypt-hash") is False


def test_dummy_hash_is_a_real_bcrypt_hash():
    """
    Timing normalisation only works if the dummy actually costs a bcrypt round.
    The previous inline constant was malformed, so checkpw raised immediately.
    """
    from core.auth.jwt import dummy_hash
    assert dummy_hash().startswith("$2b$")
    assert verify_password("anything", dummy_hash()) is False


# ─── Login field bounds ────────────────────────────────────────────────────────

def test_login_rejects_oversized_password(client, auth_headers):
    r = client.post("/auth/login", json={"username": "testowner", "password": "x" * 10_000})
    assert r.status_code == 422, "LoginRequest still has no max_length — BXD-014"


def test_login_rejects_oversized_username(client, auth_headers):
    r = client.post("/auth/login", json={"username": "u" * 10_000, "password": GOOD})
    assert r.status_code == 422


# ─── Recovery code primitives ──────────────────────────────────────────────────

def test_recovery_code_shape_and_alphabet():
    code = generate_recovery_code()
    assert len(code.split("-")) == 4
    assert not (set(normalise_recovery_code(code)) & set("ILOU")), "ambiguous chars"


def test_recovery_codes_are_unique():
    assert len({generate_recovery_code() for _ in range(200)}) == 200


@pytest.mark.parametrize("variant", [
    "{code}", "{code_lower}", "{code_nodash}", " {code} ",
])
def test_recovery_code_normalisation_is_forgiving(variant):
    """The user is transcribing this off paper, probably in a hurry."""
    code = generate_recovery_code()
    stored = hash_recovery_code(code)
    submitted = variant.format(
        code=code, code_lower=code.lower(), code_nodash=code.replace("-", "")
    )
    assert verify_recovery_code(submitted, stored) is True


def test_wrong_recovery_code_rejected():
    stored = hash_recovery_code(generate_recovery_code())
    assert verify_recovery_code(generate_recovery_code(), stored) is False
    assert verify_recovery_code("", stored) is False


def test_recovery_code_hash_does_not_contain_the_code():
    code = generate_recovery_code()
    assert normalise_recovery_code(code) not in hash_recovery_code(code)


# ─── Setup issues a recovery code ──────────────────────────────────────────────

def test_setup_returns_a_recovery_code(client):
    r = client.post("/auth/setup", json={"username": "freshowner", "password": GOOD})
    assert r.status_code == 201
    assert r.json()["recovery_code"], "setup did not issue a recovery code — BXD-004"


def test_login_never_returns_a_recovery_code(client, auth_headers):
    r = client.post("/auth/login", json={"username": "testowner", "password": GOOD})
    assert r.status_code == 200
    assert r.json().get("recovery_code") is None


# ─── C6/C7 — change password ───────────────────────────────────────────────────

def test_change_password_requires_the_current_one(client, auth_headers):
    r = client.post("/auth/change-password",
                    json={"current_password": "WrongP@ss123", "new_password": NEW},
                    headers=auth_headers)
    assert r.status_code == 401
    # and the old password still works
    assert client.post("/auth/login",
                       json={"username": "testowner", "password": GOOD}).status_code == 200


def test_change_password_enforces_strength(client, auth_headers):
    r = client.post("/auth/change-password",
                    json={"current_password": GOOD, "new_password": "weak"},
                    headers=auth_headers)
    assert r.status_code == 422


def test_change_password_succeeds_and_old_password_stops_working(client, auth_headers):
    r = client.post("/auth/change-password",
                    json={"current_password": GOOD, "new_password": NEW},
                    headers=auth_headers)
    assert r.status_code == 204

    assert client.post("/auth/login",
                       json={"username": "testowner", "password": GOOD}).status_code == 401
    assert client.post("/auth/login",
                       json={"username": "testowner", "password": NEW}).status_code == 200


def test_change_password_revokes_every_other_session(client, auth_headers):
    """
    C6: all other sessions invalidated. A second session's access token must
    stop working immediately, not in fifteen minutes when it happens to expire.
    """
    second = client.post("/auth/login", json={"username": "testowner", "password": GOOD})
    other_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}
    assert client.get("/auth/me", headers=other_headers).status_code == 200

    _next_second()  # so the change is strictly later than the token's iat

    assert client.post("/auth/change-password",
                       json={"current_password": GOOD, "new_password": NEW},
                       headers=auth_headers).status_code == 204

    assert client.get("/auth/me", headers=other_headers).status_code == 401, (
        "a session issued before the password change survived it"
    )


def test_change_password_revokes_refresh_tokens(client, owner_tokens, auth_headers):
    _, refresh_token = owner_tokens
    assert client.post("/auth/change-password",
                       json={"current_password": GOOD, "new_password": NEW},
                       headers=auth_headers).status_code == 204
    assert client.post("/auth/refresh", json={"refresh_token": refresh_token}).status_code == 401


def test_change_password_is_audited(client, auth_headers, audit_log):
    logger = audit_log
    before = logger.count()

    client.post("/auth/change-password",
                json={"current_password": GOOD, "new_password": NEW},
                headers=auth_headers)

    assert logger.count() > before
    events = [e["event"] for e in logger.recent(10)]
    assert "auth.password.changed" in events
    assert logger.verify_chain()[0] is True


def test_change_password_never_logs_the_password(client, auth_headers, audit_log):
    client.post("/auth/change-password",
                json={"current_password": GOOD, "new_password": NEW},
                headers=auth_headers)
    blob = str(audit_log.recent(20))
    assert GOOD not in blob and NEW not in blob


def test_change_password_requires_auth(client):
    r = client.post("/auth/change-password",
                    json={"current_password": GOOD, "new_password": NEW})
    assert r.status_code in (401, 403)


# ─── C8 — recovery end to end ──────────────────────────────────────────────────

@pytest.fixture()
def owner_with_code(client):
    """A fresh owner plus the recovery code issued at setup."""
    r = client.post("/auth/setup", json={"username": "lockedout", "password": GOOD})
    assert r.status_code == 201
    return r.json()["recovery_code"]


def test_recovery_resets_the_password(client, owner_with_code):
    r = client.post("/auth/recover", json={
        "username": "lockedout", "recovery_code": owner_with_code, "new_password": NEW,
    })
    assert r.status_code == 200
    assert client.post("/auth/login",
                       json={"username": "lockedout", "password": NEW}).status_code == 200


def test_recovery_code_is_single_use(client, owner_with_code):
    assert client.post("/auth/recover", json={
        "username": "lockedout", "recovery_code": owner_with_code, "new_password": NEW,
    }).status_code == 200

    r = client.post("/auth/recover", json={
        "username": "lockedout", "recovery_code": owner_with_code,
        "new_password": "An0ther!Pass9",
    })
    assert r.status_code == 401, "a used recovery code still works"


def test_recovery_issues_a_fresh_code(client, owner_with_code):
    """The user must never be left without a way back in."""
    r = client.post("/auth/recover", json={
        "username": "lockedout", "recovery_code": owner_with_code, "new_password": NEW,
    })
    new_code = r.json()["recovery_code"]
    assert new_code and new_code != owner_with_code

    assert client.post("/auth/recover", json={
        "username": "lockedout", "recovery_code": new_code,
        "new_password": "Th1rdP@ssword!",
    }).status_code == 200


def test_recovery_rejects_a_wrong_code(client, owner_with_code):
    r = client.post("/auth/recover", json={
        "username": "lockedout", "recovery_code": generate_recovery_code(),
        "new_password": NEW,
    })
    assert r.status_code == 401
    assert client.post("/auth/login",
                       json={"username": "lockedout", "password": GOOD}).status_code == 200


def test_recovery_rejects_unknown_username(client, owner_with_code):
    r = client.post("/auth/recover", json={
        "username": "nobody", "recovery_code": owner_with_code, "new_password": NEW,
    })
    assert r.status_code == 401


def test_recovery_enforces_password_strength(client, owner_with_code):
    r = client.post("/auth/recover", json={
        "username": "lockedout", "recovery_code": owner_with_code, "new_password": "weak",
    })
    assert r.status_code == 422


def test_recovery_revokes_existing_sessions(client, owner_with_code):
    login = client.post("/auth/login", json={"username": "lockedout", "password": GOOD})
    stale = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/auth/me", headers=stale).status_code == 200

    _next_second()  # JWT iat has one-second resolution; cross the boundary
    client.post("/auth/recover", json={
        "username": "lockedout", "recovery_code": owner_with_code, "new_password": NEW,
    })
    assert client.get("/auth/me", headers=stale).status_code == 401


def test_recovery_is_audited_on_success_and_failure(client, owner_with_code, audit_log):
    logger = audit_log

    client.post("/auth/recover", json={
        "username": "lockedout", "recovery_code": generate_recovery_code(),
        "new_password": NEW,
    })
    assert "auth.recovery.failed" in [e["event"] for e in logger.recent(5)]

    client.post("/auth/recover", json={
        "username": "lockedout", "recovery_code": owner_with_code, "new_password": NEW,
    })
    assert "auth.recovery.used" in [e["event"] for e in logger.recent(5)]
    assert logger.verify_chain()[0] is True


def test_recovery_never_logs_the_code(client, owner_with_code, audit_log):
    client.post("/auth/recover", json={
        "username": "lockedout", "recovery_code": owner_with_code, "new_password": NEW,
    })
    blob = str(audit_log.recent(20))
    assert normalise_recovery_code(owner_with_code) not in blob
    assert NEW not in blob


def test_recovery_is_rate_limited(client, owner_with_code):
    """3/minute — the most tightly limited route in the product."""
    codes = [generate_recovery_code() for _ in range(5)]
    statuses = [
        client.post("/auth/recover", json={
            "username": "lockedout", "recovery_code": c, "new_password": NEW,
        }).status_code
        for c in codes
    ]
    assert 429 in statuses, f"no rate limit hit: {statuses}"


# ─── The scheme upgrade path ───────────────────────────────────────────────────

def test_legacy_row_logs_in_and_is_upgraded_in_place(client, auth_headers):
    """
    A v0.6.3 account must survive the upgrade. Rewrite the owner's row to the
    legacy scheme, log in, and confirm both that it works and that the scheme
    flipped.
    """
    import bcrypt
    from core.storage.db import get_connection

    legacy = bcrypt.hashpw(GOOD.encode(), bcrypt.gensalt(rounds=4)).decode()
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, password_scheme = ? WHERE username = ?",
            (legacy, BCRYPT_LEGACY, "testowner"),
        )

    assert client.post("/auth/login",
                       json={"username": "testowner", "password": GOOD}).status_code == 200

    with get_connection() as conn:
        row = conn.execute(
            "SELECT password_scheme FROM users WHERE username = ?", ("testowner",)
        ).fetchone()
    assert row["password_scheme"] == BCRYPT_SHA256, "legacy row was not upgraded"

    # and it still logs in after the rewrite
    assert client.post("/auth/login",
                       json={"username": "testowner", "password": GOOD}).status_code == 200
