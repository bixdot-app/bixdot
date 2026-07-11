# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Database Layer
SQLite with full schema, migrations, and keyring-backed secret storage.

Design decisions:
- Secrets (JWT key, API keys) stored in OS keyring — never in the DB or .env
- DB is a single file in ~/.bixdot/ — fully local, user-owned
- Schema versioned from day one — no painful migrations later
- Audit log in a SEPARATE db file — tamper isolation
"""
import sqlite3
import secrets
from pathlib import Path
from contextlib import contextmanager
from typing import Optional
import keyring

from core.config import settings

# ─── Constants ────────────────────────────────────────────────────────────────
APP_NAME   = "BixDot"
KEYRING_JWT_KEY  = "bixdot_jwt_secret"
KEYRING_DB_KEY   = "bixdot_db_key"
SCHEMA_VERSION   = 1

DB_PATH = Path(settings.db_path).expanduser()


# ─── Secret Management ────────────────────────────────────────────────────────

def get_or_create_jwt_secret() -> str:
    """
    Retrieve JWT secret from OS keyring.
    Generate and store on first run.
    Never stored in env files or DB.
    """
    secret = keyring.get_password(APP_NAME, KEYRING_JWT_KEY)
    if not secret:
        secret = secrets.token_urlsafe(64)
        keyring.set_password(APP_NAME, KEYRING_JWT_KEY, secret)
    return secret


def store_api_key(service: str, key: str) -> None:
    """Store an API key in the OS keyring."""
    keyring.set_password(APP_NAME, f"apikey_{service}", key)


def get_api_key(service: str) -> Optional[str]:
    """Retrieve an API key from OS keyring."""
    return keyring.get_password(APP_NAME, f"apikey_{service}")


def delete_api_key(service: str) -> None:
    """Remove an API key from OS keyring."""
    try:
        keyring.delete_password(APP_NAME, f"apikey_{service}")
    except keyring.errors.PasswordDeleteError:
        pass


# ─── Database Setup ───────────────────────────────────────────────────────────

def get_db_path() -> Path:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH


@contextmanager
def get_connection(db_path: Optional[Path] = None):
    """Context manager for database connections."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row          # Dict-like row access
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent read performance
    conn.execute("PRAGMA foreign_keys=ON")   # Enforce FK constraints
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── Schema ───────────────────────────────────────────────────────────────────

SCHEMA = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Users
-- Only owner role can manage skills, permissions, and agent config
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,           -- UUID
    username        TEXT UNIQUE NOT NULL,
    email           TEXT,                       -- optional; used for license detection
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'operator'
                    CHECK(role IN ('owner', 'operator')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at   TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1
);

-- Refresh token registry (for revocation)
-- jti = JWT ID, checked on every token use
CREATE TABLE IF NOT EXISTS refresh_tokens (
    jti         TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    issued_at   TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT NOT NULL,
    revoked     INTEGER NOT NULL DEFAULT 0,
    revoked_at  TEXT
);

-- Blocklist for revoked access tokens (until expiry)
CREATE TABLE IF NOT EXISTS token_blocklist (
    jti         TEXT PRIMARY KEY,
    revoked_at  TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT NOT NULL     -- Auto-clean after this time
);

-- Installed skills
CREATE TABLE IF NOT EXISTS skills (
    id              TEXT PRIMARY KEY,       -- e.g. 'com.bixdot.filesystem'
    name            TEXT NOT NULL,
    version         TEXT NOT NULL,
    description     TEXT,
    author          TEXT,
    manifest        TEXT NOT NULL,          -- JSON: declared capabilities
    signature       TEXT,                   -- Sigstore/cosign signature
    installed_at    TEXT NOT NULL DEFAULT (datetime('now')),
    installed_by    TEXT REFERENCES users(id),
    is_enabled      INTEGER NOT NULL DEFAULT 1,
    is_verified     INTEGER NOT NULL DEFAULT 0  -- Marketplace-vetted
);

-- Permission grants (per skill, per capability)
CREATE TABLE IF NOT EXISTS permission_grants (
    id              TEXT PRIMARY KEY,
    skill_id        TEXT NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    capability      TEXT NOT NULL,
    granted_by      TEXT NOT NULL REFERENCES users(id),
    granted_at      TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at      TEXT,                   -- NULL = session only
    scope           TEXT,                   -- JSON: e.g. {"paths": ["/home/user/docs"]}
    is_active       INTEGER NOT NULL DEFAULT 1
);

-- Agent sessions (v0.4 multi-session schema)
-- Private sessions (is_private=1) are NEVER written here — they live only in
-- memory in session_store and vanish on restart. Only regular sessions persist.
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    name         TEXT NOT NULL DEFAULT 'New Chat',
    model        TEXT NOT NULL DEFAULT '',
    model_mode   TEXT NOT NULL DEFAULT 'FULL_AGENT',
    llm_backend  TEXT NOT NULL DEFAULT 'ollama',
    is_private   INTEGER NOT NULL DEFAULT 0,
    is_archived  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Per-session chat history (regular sessions only — never private)
CREATE TABLE IF NOT EXISTS session_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    role         TEXT NOT NULL,   -- 'user' | 'assistant' | 'system'
    content      TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

-- Installed third-party skills registry (v0.4 skill plugin API)
CREATE TABLE IF NOT EXISTS installed_skills (
    skill_id      TEXT PRIMARY KEY,        -- e.g. com.example.my-skill
    name          TEXT NOT NULL,
    version       TEXT NOT NULL,
    description   TEXT NOT NULL,
    author        TEXT NOT NULL,
    license       TEXT NOT NULL,
    entry_file    TEXT NOT NULL,           -- absolute path to entry script
    capabilities  TEXT NOT NULL,           -- JSON array (dotted manifest caps)
    trigger_text  TEXT NOT NULL,
    entry_sha256  TEXT NOT NULL,           -- verified at install and every startup
    is_enabled    INTEGER NOT NULL DEFAULT 1,
    installed_at  TEXT NOT NULL,
    approved_by   TEXT NOT NULL            -- user_id who approved the install
);

CREATE TABLE IF NOT EXISTS skill_capability_grants (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id      TEXT NOT NULL,
    user_id       TEXT NOT NULL,
    capability    TEXT NOT NULL,
    granted_at    TEXT NOT NULL,
    UNIQUE(skill_id, user_id, capability),
    FOREIGN KEY (skill_id) REFERENCES installed_skills(skill_id) ON DELETE CASCADE
);

-- Agent personas (v0.5): named agents with their own prompt, model, and tool set.
-- Memory is deliberately shared across personas (one assistant that knows you).
CREATE TABLE IF NOT EXISTS personas (
    persona_id    TEXT PRIMARY KEY,       -- slug for built-ins, uuid for custom
    name          TEXT NOT NULL,
    icon          TEXT NOT NULL DEFAULT '🤖',
    description   TEXT NOT NULL DEFAULT '',
    system_prompt TEXT NOT NULL DEFAULT '',
    model         TEXT NOT NULL DEFAULT '',   -- default model for new sessions ('' = global)
    allowed_tools TEXT NOT NULL DEFAULT '[]', -- JSON list of tool names; [] = all tools
    is_builtin    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Scheduled background agents (v0.5): cron-lite, consumer-friendly schedules.
CREATE TABLE IF NOT EXISTS scheduled_agents (
    schedule_id     TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    persona_id      TEXT,                    -- NULL = default assistant
    name            TEXT NOT NULL,
    prompt          TEXT NOT NULL,
    frequency       TEXT NOT NULL,           -- 'hourly' | 'daily' | 'weekdays' | 'weekly'
    at_time         TEXT NOT NULL DEFAULT '07:00',  -- HH:MM local time
    weekday         INTEGER,                 -- 0=Mon..6=Sun, for 'weekly'
    notify_desktop  INTEGER NOT NULL DEFAULT 1,
    notify_telegram INTEGER NOT NULL DEFAULT 0,
    is_enabled      INTEGER NOT NULL DEFAULT 1,
    last_run_at     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Capabilities the user pre-approved for a schedule at creation time.
-- Headless runs cannot show permission prompts, so approval happens up front.
CREATE TABLE IF NOT EXISTS schedule_capability_grants (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id  TEXT NOT NULL,
    capability   TEXT NOT NULL,
    UNIQUE(schedule_id, capability),
    FOREIGN KEY (schedule_id) REFERENCES scheduled_agents(schedule_id) ON DELETE CASCADE
);

-- Notification queue: backend enqueues, frontend polls and shows native toasts.
CREATE TABLE IF NOT EXISTS notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    delivered   INTEGER NOT NULL DEFAULT 0
);

-- Telegram chat pairings (v0.5): only paired chat_ids may talk to the agent.
CREATE TABLE IF NOT EXISTS telegram_pairings (
    chat_id     TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    persona_id  TEXT,                        -- persona that answers this chat
    paired_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Network ledger (v0.6 Privacy Proof): aggregate counters of every outbound
-- connection BixDot initiates, by purpose. Self-accounting for the dashboard;
-- the audit log holds the per-event trail.
CREATE TABLE IF NOT EXISTS net_ledger (
    kind     TEXT PRIMARY KEY,
    count    INTEGER NOT NULL DEFAULT 0,
    last_at  TEXT
);

-- App settings (non-secret config persisted across restarts)
CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_permission_grants_skill ON permission_grants(skill_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_session ON session_messages(session_id, id ASC);
CREATE INDEX IF NOT EXISTS idx_skill_grants_skill ON skill_capability_grants(skill_id);
CREATE INDEX IF NOT EXISTS idx_schedules_user ON scheduled_agents(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, delivered);
"""


def _premigrate_sessions(conn) -> None:
    """
    Idempotent pre-migration: if a pre-v0.4 `sessions` table exists (old schema
    with an `id` PK or a `messages` blob column), drop it so the v0.4 schema can
    be created cleanly. Chat history in old sessions is ephemeral and safe to
    reset — this mirrors the prior drop-on-stale-schema behaviour.
    """
    cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
    if not cols:
        return  # table doesn't exist yet — nothing to migrate
    required = {"session_id", "name", "model_mode", "is_private", "is_archived"}
    if not required.issubset(cols):
        conn.execute("DROP TABLE IF EXISTS session_messages")
        conn.execute("DROP TABLE IF EXISTS sessions")


def init_db() -> None:
    """
    Initialise the database. Safe to call on every startup.
    Creates tables if they don't exist, runs pending migrations.
    """
    with get_connection() as conn:
        _premigrate_sessions(conn)
        conn.executescript(SCHEMA)
        conn.executescript(INDEXES)

        # Record schema version
        existing = conn.execute(
            "SELECT version FROM schema_version WHERE version = ?",
            (SCHEMA_VERSION,)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,)
            )

        # Migration: add email column to existing users tables (idempotent)
        try:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        except Exception:
            pass  # Column already exists — safe to ignore

        # Migration (v0.5): sessions gain an optional persona binding (idempotent)
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN persona_id TEXT")
        except Exception:
            pass  # Column already exists — safe to ignore


# ─── First-Run Detection ──────────────────────────────────────────────────────

def is_first_run() -> bool:
    """True if no users exist — setup wizard must run."""
    try:
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            return count == 0
    except sqlite3.OperationalError:
        return True  # Tables don't exist yet


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieve a persisted app setting."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    """Persist an app setting."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
            "updated_at=datetime('now')",
            (key, value)
        )
