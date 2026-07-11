# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Audit Logger
Every agent action is logged. The log is append-only and hash-chained.
Any deletion or modification of an entry breaks the chain — detectable immediately.

This is not optional. Audit logging cannot be disabled in production.
(Directly addresses BixDot having zero audit logging by default.)
"""
import hashlib
import json
import sqlite3
from datetime import datetime, UTC
from enum import Enum
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

from core.config import settings


class AuditEvent(str, Enum):
    # Auth
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILURE = "auth.login.failure"
    AUTH_TOKEN_REFRESH = "auth.token.refresh"
    AUTH_LOGOUT = "auth.logout"

    # Permissions
    PERMISSION_GRANTED = "permission.granted"
    PERMISSION_REVOKED = "permission.revoked"
    PERMISSION_DENIED = "permission.denied"    # Blocked attempt logged here

    # Skills
    SKILL_INSTALLED = "skill.installed"
    SKILL_REMOVED = "skill.removed"
    SKILL_EXECUTED = "skill.executed"
    SKILL_BLOCKED = "skill.blocked"            # Sandbox kill logged here
    SKILL_DISABLED = "skill.disabled"          # Integrity failure / user disable
    SKILL_VERIFY_FAILED = "skill.verify_failed"  # SHA-256 mismatch at startup
    SKILL_TOGGLED = "skill.toggled"

    # Sessions (v0.4 multi-session). For private sessions, NEVER log content.
    SESSION_CREATED = "session.created"
    SESSION_RENAMED = "session.renamed"
    SESSION_ARCHIVED = "session.archived"
    SESSION_DELETED = "session.deleted"
    PRIVATE_SESSION_STARTED = "session.private_started"
    PRIVATE_SESSION_ENDED = "session.private_ended"

    # Models
    CLOUD_MODEL_BLOCKED = "model.cloud_blocked"

    # Personas (v0.5)
    PERSONA_CREATED = "persona.created"
    PERSONA_UPDATED = "persona.updated"
    PERSONA_DELETED = "persona.deleted"

    # Scheduled agents (v0.5)
    SCHEDULE_CREATED = "schedule.created"
    SCHEDULE_UPDATED = "schedule.updated"
    SCHEDULE_DELETED = "schedule.deleted"
    SCHEDULE_RUN = "schedule.run"
    SCHEDULE_RUN_FAILED = "schedule.run_failed"

    # Ask My Files (v0.6) — local knowledge base
    KNOWLEDGE_FOLDER_ADDED = "knowledge.folder_added"
    KNOWLEDGE_FOLDER_REMOVED = "knowledge.folder_removed"
    KNOWLEDGE_SEARCH = "knowledge.search"

    # Watchers (v0.6) — event-triggered automations
    WATCHER_CREATED = "watcher.created"
    WATCHER_UPDATED = "watcher.updated"
    WATCHER_DELETED = "watcher.deleted"
    WATCHER_FIRED = "watcher.fired"
    WATCHER_FAILED = "watcher.failed"

    # Telegram bridge (v0.5) — outbound long-polling only, localhost preserved
    TELEGRAM_ENABLED = "telegram.enabled"
    TELEGRAM_DISABLED = "telegram.disabled"
    TELEGRAM_PAIRED = "telegram.paired"
    TELEGRAM_UNPAIRED = "telegram.unpaired"
    TELEGRAM_MESSAGE = "telegram.message"
    TELEGRAM_REJECTED = "telegram.rejected"   # message from unpaired chat

    # Agent
    AGENT_QUERY = "agent.query"
    AGENT_TOOL_CALL = "agent.tool_call"
    AGENT_RESPONSE = "agent.response"
    AGENT_SUBAGENT = "agent.subagent"         # multi-agent orchestration (v0.5)

    # Data
    FILE_READ = "data.file_read"
    FILE_WRITE = "data.file_write"
    FILE_DELETE = "data.file_delete"
    NET_REQUEST = "data.net_request"
    CRED_ACCESS = "data.cred_access"


class AuditEntry(BaseModel):
    id: Optional[int] = None
    timestamp: datetime
    event: AuditEvent
    user_id: Optional[str]
    skill_id: Optional[str]
    details: dict
    entry_hash: str       # SHA-256 of this entry's content
    prev_hash: str        # SHA-256 of the previous entry (chain link)


class AuditLogger:
    def __init__(self, db_path: str = settings.audit_log_path):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT NOT NULL,
                    event       TEXT NOT NULL,
                    user_id     TEXT,
                    skill_id    TEXT,
                    details     TEXT NOT NULL,
                    entry_hash  TEXT NOT NULL,
                    prev_hash   TEXT NOT NULL
                )
            """)
            # Append-only: no DELETE or UPDATE triggers
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS no_delete
                BEFORE DELETE ON audit_log
                BEGIN
                    SELECT RAISE(ABORT, 'Audit log is append-only. Deletions are not permitted.');
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS no_update
                BEFORE UPDATE ON audit_log
                BEGIN
                    SELECT RAISE(ABORT, 'Audit log is append-only. Updates are not permitted.');
                END
            """)

    def _conn(self):
        return sqlite3.connect(str(self.db_path))

    def _last_hash(self) -> str:
        """Get the hash of the most recent entry for chain linking."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return row[0] if row else "GENESIS"

    def _compute_hash(self, entry_data: dict) -> str:
        canonical = json.dumps(entry_data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def log(
        self,
        event: AuditEvent,
        details: dict,
        user_id: Optional[str] = None,
        skill_id: Optional[str] = None,
    ) -> AuditEntry:
        """Append an entry to the audit log. Thread-safe via SQLite locking."""
        prev_hash = self._last_hash()
        timestamp = datetime.now(UTC)

        entry_data = {
            "timestamp": timestamp.isoformat(),
            "event": event.value,
            "user_id": user_id,
            "skill_id": skill_id,
            "details": details,
            "prev_hash": prev_hash,
        }
        entry_hash = self._compute_hash(entry_data)

        with self._conn() as conn:
            cursor = conn.execute(
                """INSERT INTO audit_log
                   (timestamp, event, user_id, skill_id, details, entry_hash, prev_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    timestamp.isoformat(),
                    event.value,
                    user_id,
                    skill_id,
                    json.dumps(details, default=str),
                    entry_hash,
                    prev_hash,
                ),
            )

        return AuditEntry(
            id=cursor.lastrowid,
            timestamp=timestamp,
            event=event,
            user_id=user_id,
            skill_id=skill_id,
            details=details,
            entry_hash=entry_hash,
            prev_hash=prev_hash,
        )

    def verify_chain(self) -> tuple[bool, Optional[int]]:
        """
        Verify the full hash chain. Returns (is_valid, first_broken_id).
        Call this on startup and periodically.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, timestamp, event, user_id, skill_id, details, entry_hash, prev_hash "
                "FROM audit_log ORDER BY id ASC"
            ).fetchall()

        prev_hash = "GENESIS"
        for row in rows:
            id_, timestamp, event, user_id, skill_id, details_str, stored_hash, stored_prev = row

            if stored_prev != prev_hash:
                return False, id_  # Chain broken at this entry

            entry_data = {
                "timestamp": timestamp,
                "event": event,
                "user_id": user_id,
                "skill_id": skill_id,
                "details": json.loads(details_str),
                "prev_hash": stored_prev,
            }
            computed = self._compute_hash(entry_data)
            if computed != stored_hash:
                return False, id_  # Entry tampered

            prev_hash = stored_hash

        return True, None

    def count(self) -> int:
        """Total number of audit entries (for the Privacy dashboard)."""
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]

    def recent(self, limit: int = 50) -> list[dict]:
        """Fetch recent audit entries for the UI."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, timestamp, event, user_id, skill_id, details "
                "FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r[0], "timestamp": r[1], "event": r[2],
                "user_id": r[3], "skill_id": r[4],
                "details": json.loads(r[5]),
            }
            for r in rows
        ]


# ─── Module-level singleton ────────────────────────────────────────────────────
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
