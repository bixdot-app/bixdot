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

-- Agent sessions
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id),
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at    TEXT,
    llm_backend TEXT NOT NULL DEFAULT 'claude',
    message_count INTEGER NOT NULL DEFAULT 0
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
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
"""


def init_db() -> None:
    """
    Initialise the database. Safe to call on every startup.
    Creates tables if they don't exist, runs pending migrations.
    """
    with get_connection() as conn:
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
