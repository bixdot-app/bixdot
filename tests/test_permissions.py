# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Permission system unit tests.

The agent starts with ZERO permissions. Every capability requires explicit grant.
Tests verify: grant, check, revoke, expiry, never-fails-open.
"""
import pytest
from datetime import datetime, timedelta, UTC
from core.agent.permissions import Capability, PermissionStore, PermissionDeniedError


@pytest.fixture()
def store():
    return PermissionStore()


# ── Zero permissions by default ─────────────────────────────────────────────────

def test_no_permissions_by_default(store):
    for cap in Capability:
        assert store.check("any-skill", cap) is False


def test_check_unknown_skill_returns_false(store):
    assert store.check("nonexistent-skill", Capability.FS_READ) is False


# ── Grant and check ─────────────────────────────────────────────────────────────

def test_grant_allows_check(store):
    store.grant("skill-a", Capability.FS_READ, granted_by="user-1")
    assert store.check("skill-a", Capability.FS_READ) is True


def test_grant_does_not_leak_to_other_skills(store):
    store.grant("skill-a", Capability.FS_READ, granted_by="user-1")
    assert store.check("skill-b", Capability.FS_READ) is False


def test_grant_does_not_leak_to_other_capabilities(store):
    store.grant("skill-a", Capability.FS_READ, granted_by="user-1")
    assert store.check("skill-a", Capability.FS_WRITE) is False


def test_multiple_capabilities_independent(store):
    store.grant("skill-a", Capability.FS_READ, granted_by="user-1")
    store.grant("skill-a", Capability.NET_FETCH, granted_by="user-1")
    assert store.check("skill-a", Capability.FS_READ) is True
    assert store.check("skill-a", Capability.NET_FETCH) is True
    assert store.check("skill-a", Capability.EXEC_SHELL) is False


# ── Revoke ──────────────────────────────────────────────────────────────────────

def test_revoke_single_capability(store):
    store.grant("skill-a", Capability.FS_READ, granted_by="user-1")
    store.grant("skill-a", Capability.FS_WRITE, granted_by="user-1")
    store.revoke("skill-a", Capability.FS_READ)
    assert store.check("skill-a", Capability.FS_READ) is False
    assert store.check("skill-a", Capability.FS_WRITE) is True


def test_revoke_all_capabilities(store):
    store.grant("skill-a", Capability.FS_READ, granted_by="user-1")
    store.grant("skill-a", Capability.NET_FETCH, granted_by="user-1")
    store.revoke("skill-a")  # Revoke all
    assert store.check("skill-a", Capability.FS_READ) is False
    assert store.check("skill-a", Capability.NET_FETCH) is False


def test_revoke_nonexistent_is_safe(store):
    """Revoking a skill that was never granted should not raise."""
    store.revoke("nonexistent-skill")
    store.revoke("nonexistent-skill", Capability.FS_READ)


# ── Expiry ──────────────────────────────────────────────────────────────────────

def test_grant_with_duration_expires(store):
    """A grant whose expires_at is in the past must be rejected."""
    store.grant("skill-a", Capability.FS_READ, granted_by="user-1", duration_minutes=60)
    grant = store._grants["skill-a"][Capability.FS_READ]
    # Force it to be already expired
    object.__setattr__(grant, "expires_at", datetime.now(UTC) - timedelta(seconds=1))
    assert store.check("skill-a", Capability.FS_READ) is False


def test_grant_without_duration_is_session_scoped(store):
    """No duration = session-scoped = never expires during the session."""
    store.grant("skill-a", Capability.FS_READ, granted_by="user-1")
    grant = store._grants["skill-a"][Capability.FS_READ]
    assert grant.expires_at is None
    assert grant.is_expired is False


def test_expired_grant_cleaned_up_on_check(store):
    """Expired grants must be removed from the store on check."""
    store.grant("skill-a", Capability.FS_READ, granted_by="user-1", duration_minutes=60)
    grant = store._grants["skill-a"][Capability.FS_READ]
    object.__setattr__(grant, "expires_at", datetime.now(UTC) - timedelta(seconds=1))
    store.check("skill-a", Capability.FS_READ)  # triggers cleanup
    assert Capability.FS_READ not in store._grants.get("skill-a", {})


# ── require() ───────────────────────────────────────────────────────────────────

def test_require_raises_when_no_permission(store):
    with pytest.raises(PermissionDeniedError):
        store.require("skill-a", Capability.EXEC_SHELL)


def test_require_passes_when_granted(store):
    store.grant("skill-a", Capability.EXEC_SHELL, granted_by="user-1")
    store.require("skill-a", Capability.EXEC_SHELL)  # Must not raise


def test_require_error_message_names_skill_and_capability(store):
    with pytest.raises(PermissionDeniedError) as exc_info:
        store.require("my-plugin", Capability.FS_DELETE)
    assert "my-plugin" in str(exc_info.value)
    assert "FS_DELETE" in str(exc_info.value) or "fs:delete" in str(exc_info.value)


# ── list_grants() ───────────────────────────────────────────────────────────────

def test_list_grants_empty_by_default(store):
    assert store.list_grants() == []


def test_list_grants_returns_active_grants(store):
    store.grant("skill-a", Capability.FS_READ, granted_by="user-1")
    store.grant("skill-b", Capability.NET_FETCH, granted_by="user-1")
    grants = store.list_grants()
    assert len(grants) == 2


def test_list_grants_filtered_by_skill(store):
    store.grant("skill-a", Capability.FS_READ, granted_by="user-1")
    store.grant("skill-b", Capability.NET_FETCH, granted_by="user-1")
    grants = store.list_grants("skill-a")
    assert len(grants) == 1
    assert grants[0].capability == Capability.FS_READ


def test_list_grants_excludes_expired(store):
    store.grant("skill-a", Capability.FS_READ, granted_by="user-1", duration_minutes=60)
    grant = store._grants["skill-a"][Capability.FS_READ]
    object.__setattr__(grant, "expires_at", datetime.now(UTC) - timedelta(seconds=1))
    grants = store.list_grants()
    assert len(grants) == 0


# ── Never-fails-open invariant ──────────────────────────────────────────────────

def test_check_never_returns_true_without_explicit_grant(store):
    """
    Exhaustive check: every capability for a fresh store must return False.
    The permission system must NEVER grant access by default.
    """
    for cap in Capability:
        result = store.check("builtin", cap)
        assert result is False, f"Capability {cap} was allowed without a grant!"
