# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
BixDot — SQLite Session Store

Persists agent sessions (message history) across server restarts.
Stored at ~/.bixdot/data.db — local only, never leaves the device.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from core.agent.runtime import AgentSession, Message
from core.config import settings


def _db_path() -> Path:
    p = Path(settings.db_path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


REQUIRED_COLUMNS = {"session_id", "user_id", "llm_backend", "messages", "created_at", "updated_at"}


def init_db():
    """
    Create sessions table if it doesn't exist.
    If the table exists but has a stale schema (missing columns),
    drop and recreate it so server always starts cleanly.
    """
    with _connect() as conn:
        # Check if table exists already
        existing = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
        ).fetchone()

        if existing:
            # Check columns match expected schema
            cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
            if not REQUIRED_COLUMNS.issubset(cols):
                # Stale schema — drop and recreate
                conn.execute("DROP TABLE sessions")
                print("⚠️  BixDot: sessions table had stale schema — recreated cleanly.")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                user_id      TEXT NOT NULL,
                llm_backend  TEXT NOT NULL DEFAULT 'ollama',
                messages     TEXT NOT NULL DEFAULT '[]',
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            )
        """)
        conn.commit()


# ─── CRUD ─────────────────────────────────────────────────────────────────────

def save_session(session: AgentSession):
    """Insert or update a session."""
    now = datetime.now(timezone.utc).isoformat()
    messages_json = json.dumps([m.dict() for m in session.messages])
    with _connect() as conn:
        conn.execute("""
            INSERT INTO sessions (session_id, user_id, llm_backend, messages, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                messages   = excluded.messages,
                updated_at = excluded.updated_at
        """, (
            session.session_id,
            session.user_id,
            session.llm_backend,
            messages_json,
            now,
            now,
        ))
        conn.commit()


def load_session(session_id: str) -> Optional[AgentSession]:
    """Load a session by ID. Returns None if not found."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()

    if not row:
        return None

    messages = [Message(**m) for m in json.loads(row["messages"])]
    return AgentSession(
        session_id=row["session_id"],
        user_id=row["user_id"],
        llm_backend=row["llm_backend"],
        messages=messages,
    )


def load_user_sessions(user_id: str) -> list[AgentSession]:
    """Load all sessions for a user, newest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,)
        ).fetchall()

    sessions = []
    for row in rows:
        messages = [Message(**m) for m in json.loads(row["messages"])]
        sessions.append(AgentSession(
            session_id=row["session_id"],
            user_id=row["user_id"],
            llm_backend=row["llm_backend"],
            messages=messages,
        ))
    return sessions


def delete_session(session_id: str):
    """Delete a session permanently."""
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()


def session_belongs_to(session_id: str, user_id: str) -> bool:
    """Security check — verify session belongs to user before any operation."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT user_id FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    return row is not None and row["user_id"] == user_id


# ─── Singleton init guard ──────────────────────────────────────────────────────

_initialized = False

def get_session_store():
    """Call once at startup to ensure DB is ready."""
    global _initialized
    if not _initialized:
        init_db()
        _initialized = True
