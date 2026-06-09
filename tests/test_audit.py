# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Audit log tests.

The audit log is tamper-evident via SHA-256 hash chaining.
Tests verify: entries are logged, chain is valid, tampering is detected,
and the append-only triggers prevent deletion and modification.
"""
import json
import sqlite3
import pytest

from core.audit.logger import AuditLogger, AuditEvent


@pytest.fixture()
def logger(tmp_path):
    """Fresh AuditLogger pointing at a temp file."""
    return AuditLogger(db_path=str(tmp_path / "audit_test.db"))


# ── Logging ─────────────────────────────────────────────────────────────────────

def test_log_appends_entry(logger):
    entry = logger.log(AuditEvent.AUTH_LOGIN_SUCCESS, {"user": "test"}, user_id="user-1")
    assert entry.id is not None
    assert entry.event == AuditEvent.AUTH_LOGIN_SUCCESS
    assert entry.user_id == "user-1"


def test_log_returns_entry_with_hash(logger):
    entry = logger.log(AuditEvent.AGENT_QUERY, {})
    assert entry.entry_hash
    assert len(entry.entry_hash) == 64  # SHA-256 hex


def test_first_entry_has_genesis_prev_hash(logger):
    entry = logger.log(AuditEvent.AUTH_LOGIN_SUCCESS, {})
    assert entry.prev_hash == "GENESIS"


def test_second_entry_links_to_first(logger):
    e1 = logger.log(AuditEvent.AUTH_LOGIN_SUCCESS, {})
    e2 = logger.log(AuditEvent.AUTH_LOGOUT, {})
    assert e2.prev_hash == e1.entry_hash


def test_chain_links_across_multiple_entries(logger):
    entries = [
        logger.log(AuditEvent.AUTH_LOGIN_SUCCESS, {"n": i})
        for i in range(5)
    ]
    for i in range(1, 5):
        assert entries[i].prev_hash == entries[i - 1].entry_hash


def test_details_are_persisted(logger):
    logger.log(AuditEvent.FILE_READ, {"path": "/home/user/doc.txt"}, user_id="u1")
    recent = logger.recent(limit=1)
    assert recent[0]["details"]["path"] == "/home/user/doc.txt"


# ── Chain verification ──────────────────────────────────────────────────────────

def test_verify_empty_chain_is_valid(logger):
    valid, broken_at = logger.verify_chain()
    assert valid is True
    assert broken_at is None


def test_verify_single_entry_chain(logger):
    logger.log(AuditEvent.AUTH_LOGIN_SUCCESS, {})
    valid, broken_at = logger.verify_chain()
    assert valid is True
    assert broken_at is None


def test_verify_multi_entry_chain(logger):
    for i in range(10):
        logger.log(AuditEvent.AGENT_QUERY, {"i": i})
    valid, broken_at = logger.verify_chain()
    assert valid is True
    assert broken_at is None


def test_tamper_detection_modified_details(logger, tmp_path):
    """Modifying an entry's details field must break the chain."""
    logger.log(AuditEvent.AUTH_LOGIN_SUCCESS, {"legit": True})
    logger.log(AuditEvent.AGENT_QUERY, {})

    # Directly modify the DB — bypass the append-only trigger via raw sqlite
    db_path = str(tmp_path / "audit_test.db")
    conn = sqlite3.connect(db_path)
    # Disable the no_update trigger temporarily by re-creating without it
    conn.execute("DROP TRIGGER IF EXISTS no_update")
    conn.execute(
        "UPDATE audit_log SET details = ? WHERE id = 1",
        (json.dumps({"legit": False, "tampered": True}),)
    )
    conn.commit()
    conn.close()

    valid, broken_at = logger.verify_chain()
    assert valid is False
    assert broken_at == 1


def test_tamper_detection_modified_prev_hash(logger, tmp_path):
    """Modifying a prev_hash link must break the chain."""
    logger.log(AuditEvent.AUTH_LOGIN_SUCCESS, {})
    logger.log(AuditEvent.AUTH_LOGOUT, {})

    db_path = str(tmp_path / "audit_test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("DROP TRIGGER IF EXISTS no_update")
    conn.execute(
        "UPDATE audit_log SET prev_hash = 'fakehash' WHERE id = 2"
    )
    conn.commit()
    conn.close()

    valid, broken_at = logger.verify_chain()
    assert valid is False
    assert broken_at == 2


# ── Append-only enforcement ─────────────────────────────────────────────────────

def test_delete_trigger_blocks_deletion(logger):
    """DELETE on audit_log must raise — the trigger enforces append-only."""
    logger.log(AuditEvent.AUTH_LOGIN_SUCCESS, {})

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn = sqlite3.connect(str(logger.db_path))
        conn.execute("DELETE FROM audit_log WHERE id = 1")
        conn.commit()
        conn.close()


def test_update_trigger_blocks_modification(logger):
    """UPDATE on audit_log must raise — the trigger enforces append-only."""
    logger.log(AuditEvent.AUTH_LOGIN_SUCCESS, {})

    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        conn = sqlite3.connect(str(logger.db_path))
        conn.execute("UPDATE audit_log SET event = 'hacked' WHERE id = 1")
        conn.commit()
        conn.close()


# ── recent() ───────────────────────────────────────────────────────────────────

def test_recent_returns_latest_first(logger):
    for i in range(5):
        logger.log(AuditEvent.AGENT_QUERY, {"seq": i})
    recent = logger.recent(limit=5)
    seqs = [r["details"]["seq"] for r in recent]
    assert seqs == [4, 3, 2, 1, 0]  # Newest first


def test_recent_respects_limit(logger):
    for _ in range(20):
        logger.log(AuditEvent.AGENT_QUERY, {})
    recent = logger.recent(limit=5)
    assert len(recent) == 5
