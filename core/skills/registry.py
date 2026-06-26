# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Skill Registry (data access)

Thin data-access layer over the installed_skills and skill_capability_grants
tables (schema owned by core.storage.db). Used by the plugin manager and the
agent runtime to discover, enable/disable, and capability-gate third-party
skills. All rows are local — nothing leaves the device.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from core.storage.db import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_skill(row) -> dict:
    return {
        "skill_id": row["skill_id"],
        "name": row["name"],
        "version": row["version"],
        "description": row["description"],
        "author": row["author"],
        "license": row["license"],
        "entry_file": row["entry_file"],
        "capabilities": json.loads(row["capabilities"]),
        "trigger": row["trigger_text"],
        "entry_sha256": row["entry_sha256"],
        "is_enabled": bool(row["is_enabled"]),
        "installed_at": row["installed_at"],
        "approved_by": row["approved_by"],
    }


def register_skill(manifest: dict, *, entry_file: str, entry_sha256: str,
                   approved_by: str) -> None:
    """Insert (or replace) an installed skill row."""
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO installed_skills
               (skill_id, name, version, description, author, license,
                entry_file, capabilities, trigger_text, entry_sha256,
                is_enabled, installed_at, approved_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
               ON CONFLICT(skill_id) DO UPDATE SET
                 name=excluded.name, version=excluded.version,
                 description=excluded.description, author=excluded.author,
                 license=excluded.license, entry_file=excluded.entry_file,
                 capabilities=excluded.capabilities,
                 trigger_text=excluded.trigger_text,
                 entry_sha256=excluded.entry_sha256,
                 is_enabled=1, installed_at=excluded.installed_at,
                 approved_by=excluded.approved_by""",
            (
                manifest["id"], manifest["name"], manifest["version"],
                manifest["description"], manifest["author"], manifest["license"],
                entry_file, json.dumps(manifest["capabilities"]),
                manifest["trigger"], entry_sha256, _now(), approved_by,
            ),
        )


def grant_capabilities(skill_id: str, user_id: str, capabilities: list[str]) -> None:
    """Record the user's approval of each declared capability for a skill."""
    now = _now()
    with get_connection() as conn:
        for cap in capabilities:
            conn.execute(
                "INSERT OR IGNORE INTO skill_capability_grants "
                "(skill_id, user_id, capability, granted_at) VALUES (?, ?, ?, ?)",
                (skill_id, user_id, cap, now),
            )


def list_skills() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM installed_skills ORDER BY name ASC"
        ).fetchall()
    return [_row_to_skill(r) for r in rows]


def list_enabled_skills() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM installed_skills WHERE is_enabled = 1 ORDER BY name ASC"
        ).fetchall()
    return [_row_to_skill(r) for r in rows]


def get_skill(skill_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM installed_skills WHERE skill_id = ?", (skill_id,)
        ).fetchone()
    return _row_to_skill(row) if row else None


def get_skill_grants(skill_id: str) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT capability FROM skill_capability_grants WHERE skill_id = ?",
            (skill_id,),
        ).fetchall()
    return [r["capability"] for r in rows]


def set_enabled(skill_id: str, enabled: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE installed_skills SET is_enabled = ? WHERE skill_id = ?",
            (1 if enabled else 0, skill_id),
        )


def remove_skill(skill_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM installed_skills WHERE skill_id = ?", (skill_id,))
