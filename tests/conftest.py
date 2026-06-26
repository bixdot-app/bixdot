# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Shared fixtures for the BixDot test suite.

Every test gets:
  - An isolated SQLite DB in a temp directory (no pollution between tests)
  - An isolated audit log in the same temp directory
  - A reset of all module-level singletons (audit logger, permission store)
  - A FastAPI TestClient wired to the temp DB
  - Helper functions for creating users and obtaining tokens
"""
import pytest
from fastapi.testclient import TestClient


# ── Isolated DB per test ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """
    Redirect all persistent state to a temp directory for this test.
    Resets module-level singletons so each test starts clean.
    """
    db_file    = tmp_path / "bixdot_test.db"
    audit_file = tmp_path / "audit_test.db"

    # Patch settings before any module reads them
    from core import config
    monkeypatch.setattr(config.settings, "db_path",        str(db_file))
    monkeypatch.setattr(config.settings, "audit_log_path", str(audit_file))

    # Patch the module-level DB_PATH constant (computed at import time)
    import core.storage.db as db_mod
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)

    # Reset singletons so they re-initialise against the patched paths
    import core.audit.logger as audit_mod
    import core.agent.permissions as perm_mod
    monkeypatch.setattr(audit_mod, "_audit_logger", None)
    monkeypatch.setattr(perm_mod, "_permission_store", None)

    # Initialise schema
    from core.storage.db import init_db
    init_db()

    # Reset session store: clear in-memory private sessions and force re-init
    import core.agent.session_store as ss_mod
    monkeypatch.setattr(ss_mod, "_initialized", False)
    ss_mod._reset_for_tests()

    # Reset rate limiter storage so tests don't accumulate counts and hit 429
    from core.security import limiter
    limiter.reset()

    yield

    limiter.reset()


# ── Test client ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def client():
    """FastAPI TestClient with a live app instance."""
    from core.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── Auth helpers ────────────────────────────────────────────────────────────────

@pytest.fixture()
def owner_tokens(client):
    """
    Create the owner account and return (access_token, refresh_token).
    Skips setup if already done.
    """
    r = client.post("/auth/setup", json={"username": "testowner", "password": "S3cur3P@ss!1"})
    assert r.status_code in (201, 410), f"Unexpected setup status: {r.status_code}"
    if r.status_code == 201:
        data = r.json()
        return data["access_token"], data["refresh_token"]
    # Already set up — log in
    r = client.post("/auth/login", json={"username": "testowner", "password": "S3cur3P@ss!1"})
    assert r.status_code == 200
    data = r.json()
    return data["access_token"], data["refresh_token"]


@pytest.fixture()
def auth_headers(owner_tokens):
    """Authorization header dict for authenticated requests."""
    access_token, _ = owner_tokens
    return {"Authorization": f"Bearer {access_token}"}
