# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Calendar store — saves provider choice + OAuth tokens to ~/.bixdot/data.db
All data stays local. Tokens never leave the device.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.config import settings


def _db_path() -> Path:
    p = Path(settings.db_path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_calendar_db():
    """Create calendar_config table if missing. Safe to call multiple times."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS calendar_config (
                user_id     TEXT NOT NULL,
                provider    TEXT NOT NULL,
                config      TEXT NOT NULL DEFAULT '{}',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                PRIMARY KEY (user_id, provider)
            )
        """)
        conn.commit()


def save_provider(user_id: str, provider: str, config: dict):
    """Upsert calendar provider config (tokens, paths, etc.)."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute("""
            INSERT INTO calendar_config (user_id, provider, config, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, provider) DO UPDATE SET
                config = excluded.config,
                updated_at = excluded.updated_at
        """, (user_id, provider, json.dumps(config), now, now))
        conn.commit()


def load_provider(user_id: str, provider: str) -> Optional[dict]:
    """Load config dict for a provider. Returns None if not set up."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT config FROM calendar_config WHERE user_id=? AND provider=?",
            (user_id, provider)
        ).fetchone()
    return json.loads(row["config"]) if row else None


def load_active_provider(user_id: str) -> Optional[tuple[str, dict]]:
    """Return (provider_name, config) for whichever provider is set up, newest first."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT provider, config FROM calendar_config WHERE user_id=? ORDER BY updated_at DESC LIMIT 1",
            (user_id,)
        ).fetchone()
    if not row:
        return None
    return row["provider"], json.loads(row["config"])


def delete_provider(user_id: str, provider: str):
    """Disconnect a calendar provider."""
    with _connect() as conn:
        conn.execute(
            "DELETE FROM calendar_config WHERE user_id=? AND provider=?",
            (user_id, provider)
        )
        conn.commit()


def list_providers(user_id: str) -> list[str]:
    """List all connected providers for a user."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT provider FROM calendar_config WHERE user_id=?", (user_id,)
        ).fetchall()
    return [r["provider"] for r in rows]
