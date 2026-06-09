# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Sandbox executor unit tests.

Verifies SkillExecutor enforces permission checks before running any action,
logs to the audit trail, and raises appropriate errors on violations.
The subprocess runner itself is not tested here (that would require a full
integration harness) — these tests focus on the executor's guard layer.
"""
import pytest

from core.sandbox.executor import SkillExecutor, SandboxViolationError
from core.agent.permissions import Capability, PermissionStore
from core.audit.logger import AuditLogger, AuditEvent


@pytest.fixture()
def perm_store():
    return PermissionStore()


@pytest.fixture()
def audit(tmp_path):
    return AuditLogger(db_path=str(tmp_path / "sandbox_audit.db"))


@pytest.fixture()
def executor(perm_store, audit):
    return SkillExecutor(permission_store=perm_store, audit_logger=audit)


# ── Permission enforcement ───────────────────────────────────────────────────

def test_execute_raises_without_permission(executor):
    """Any execute() call without a grant must raise SandboxViolationError."""
    with pytest.raises(SandboxViolationError):
        executor.execute(
            skill_id="test-skill",
            capability=Capability.FS_READ,
            user_id="user-1",
            action="read_file",
            params={"path": "/tmp/x"},
        )


def test_execute_raises_for_every_capability_by_default(executor):
    """No capability is implicitly allowed — each one must be checked."""
    for cap in Capability:
        with pytest.raises(SandboxViolationError):
            executor.execute(
                skill_id="test-skill",
                capability=cap,
                user_id="user-1",
                action="action",
                params={},
            )


def test_permission_denied_logs_audit_event(executor, perm_store, audit):
    """A denied execution must produce a PERMISSION_DENIED audit entry."""
    with pytest.raises(SandboxViolationError):
        executor.execute(
            skill_id="bad-skill",
            capability=Capability.EXEC_SHELL,
            user_id="user-1",
            action="run",
            params={"cmd": "ls"},
        )
    recent = audit.recent(limit=1)
    assert recent[0]["event"] == AuditEvent.PERMISSION_DENIED.value


def test_permission_denied_does_not_log_skill_executed(executor, audit):
    """On denial, SKILL_EXECUTED must NOT appear — only PERMISSION_DENIED."""
    with pytest.raises(SandboxViolationError):
        executor.execute(
            skill_id="bad-skill",
            capability=Capability.FS_READ,
            user_id="user-1",
            action="read_file",
            params={},
        )
    entries = audit.recent(limit=10)
    events = [e["event"] for e in entries]
    assert AuditEvent.SKILL_EXECUTED.value not in events


# ── Param sanitisation ───────────────────────────────────────────────────────

def test_sanitize_params_masks_sensitive_keys():
    """Sensitive param keys must be masked before audit logging."""
    params = {
        "path": "/home/user/file.txt",
        "password": "s3cr3t",
        "api_key": "sk-abc123",
        "token": "tok-xyz",
        "visible_param": "visible",
    }
    sanitized = SkillExecutor._sanitize_params(params)
    assert sanitized["path"] == "/home/user/file.txt"
    assert sanitized["visible_param"] == "visible"
    assert sanitized["password"] == "***"
    assert sanitized["api_key"] == "***"
    assert sanitized["token"] == "***"


def test_sanitize_params_case_insensitive_masking():
    """Sensitive key check must be case-insensitive (PASSWORD, Token, etc.)."""
    params = {"PASSWORD": "secret", "TOKEN": "tok", "Auth": "bearer xyz"}
    sanitized = SkillExecutor._sanitize_params(params)
    for v in sanitized.values():
        assert v == "***"


def test_sanitize_params_empty_dict():
    assert SkillExecutor._sanitize_params({}) == {}


# ── Granted execution logs SKILL_EXECUTED ───────────────────────────────────

def test_granted_execute_logs_skill_executed(perm_store, audit, tmp_path, monkeypatch):
    """
    When permission is granted, execute() must log SKILL_EXECUTED before
    handing off to the subprocess runner.
    """
    perm_store.grant("test-skill", Capability.FS_READ, granted_by="user-1")
    executor = SkillExecutor(permission_store=perm_store, audit_logger=audit)

    # Stub out _run_sandboxed so we don't need a real subprocess
    monkeypatch.setattr(executor, "_run_sandboxed", lambda *a, **kw: {"ok": True})

    result = executor.execute(
        skill_id="test-skill",
        capability=Capability.FS_READ,
        user_id="user-1",
        action="read_file",
        params={"path": "/tmp/test.txt"},
    )

    assert result == {"ok": True}
    recent = audit.recent(limit=1)
    assert recent[0]["event"] == AuditEvent.SKILL_EXECUTED.value


def test_granted_execute_sanitizes_params_in_audit(perm_store, audit, monkeypatch):
    """Sensitive params must be masked in the SKILL_EXECUTED audit entry."""
    perm_store.grant("cred-skill", Capability.CRED_READ, granted_by="user-1")
    executor = SkillExecutor(permission_store=perm_store, audit_logger=audit)
    monkeypatch.setattr(executor, "_run_sandboxed", lambda *a, **kw: {})

    executor.execute(
        skill_id="cred-skill",
        capability=Capability.CRED_READ,
        user_id="user-1",
        action="read_cred",
        params={"key": "my-api-key", "token": "secret"},
    )

    recent = audit.recent(limit=1)
    logged_params = recent[0]["details"]["params"]
    assert logged_params["key"] == "***"
    assert logged_params["token"] == "***"
