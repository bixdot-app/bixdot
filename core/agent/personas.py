# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Agent Personas (v0.5)

A persona is a named agent with its own system prompt, default model, and tool
set. Personas are the foundational primitive of v0.5: chat sessions bind to a
persona, scheduled agents run a persona headlessly, and the Telegram bridge
routes each chat to a persona.

Design notes:
- Memory is deliberately SHARED across personas — one assistant that knows the
  user everywhere beats five assistants that each know a fifth of them.
- Built-in personas ship ready to use (zero setup for non-technical users).
  They can be edited but not deleted; custom personas can be both.
- `allowed_tools` is an allowlist of tool names ([] = all tools). It restricts
  which tools the runtime OFFERS the model; the permission system still gates
  every actual execution — personas never bypass permissions.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from core.storage.db import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Built-in personas ─────────────────────────────────────────────────────────
# Written for non-technical users: plain names, clear promises, safe tool sets.

BUILTIN_PERSONAS: list[dict] = [
    {
        "persona_id": "bixdot",
        "name": "BixDot",
        "icon": "🤖",
        "description": "Your everyday assistant. Can use every skill you allow.",
        "system_prompt": "",
        "model": "",
        "allowed_tools": [],  # all tools
    },
    {
        "persona_id": "day-planner",
        "name": "Day Planner",
        "icon": "📅",
        "description": "Keeps your day on track — calendar, plans, and reminders.",
        "system_prompt": (
            "You are Day Planner, a friendly personal organiser. Focus on the "
            "user's calendar, schedule, and plans. Keep answers short and "
            "actionable: what's next, what conflicts, what to prepare. When "
            "summarising a day, list events in time order with a one-line tip."
        ),
        "model": "",
        "allowed_tools": ["get_events", "create_event", "remember", "recall"],
    },
    {
        "persona_id": "researcher",
        "name": "Researcher",
        "icon": "🔎",
        "description": "Finds answers on the web and writes clear summaries.",
        "system_prompt": (
            "You are Researcher. Search the web when facts are needed and cite "
            "the source names in your answer. Prefer recent information. Write "
            "clear, structured summaries a busy person can skim."
        ),
        "model": "",
        "allowed_tools": ["web_search", "deep_research", "remember", "recall"],
    },
    {
        "persona_id": "writer",
        "name": "Writer",
        "icon": "✍️",
        "description": "Drafts and polishes messages, emails, and documents.",
        "system_prompt": (
            "You are Writer, a thoughtful writing partner. Draft, rewrite, and "
            "polish text in the tone the user asks for. Offer one improved "
            "version, not many options, unless asked. Never invent facts."
        ),
        "model": "",
        "allowed_tools": ["remember", "recall", "read_file", "write_file"],
    },
    {
        "persona_id": "file-helper",
        "name": "File Helper",
        "icon": "📁",
        "description": "Finds, reads, and organises files on your computer.",
        "system_prompt": (
            "You are File Helper. Help the user find, read, and organise their "
            "files. Always say exactly which files or folders you touched. "
            "Never delete anything — suggest moves and let the user decide."
        ),
        "model": "",
        "allowed_tools": ["read_file", "write_file", "list_directory",
                          "search_files", "list_documents", "search_document"],
    },
]


def _row_to_persona(row) -> dict:
    return {
        "persona_id": row["persona_id"],
        "name": row["name"],
        "icon": row["icon"],
        "description": row["description"],
        "system_prompt": row["system_prompt"],
        "model": row["model"],
        "allowed_tools": json.loads(row["allowed_tools"]),
        "is_builtin": bool(row["is_builtin"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def seed_builtin_personas() -> None:
    """Insert built-in personas if missing. Never overwrites user edits."""
    now = _now()
    with get_connection() as conn:
        for p in BUILTIN_PERSONAS:
            conn.execute(
                """INSERT OR IGNORE INTO personas
                   (persona_id, name, icon, description, system_prompt, model,
                    allowed_tools, is_builtin, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (p["persona_id"], p["name"], p["icon"], p["description"],
                 p["system_prompt"], p["model"],
                 json.dumps(p["allowed_tools"]), now, now),
            )


def list_personas() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM personas ORDER BY is_builtin DESC, name ASC"
        ).fetchall()
    return [_row_to_persona(r) for r in rows]


def get_persona(persona_id: str) -> Optional[dict]:
    if not persona_id:
        return None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM personas WHERE persona_id = ?", (persona_id,)
        ).fetchone()
    return _row_to_persona(row) if row else None


def create_persona(*, name: str, icon: str = "🤖", description: str = "",
                   system_prompt: str = "", model: str = "",
                   allowed_tools: Optional[list[str]] = None) -> dict:
    persona_id = str(uuid.uuid4())
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO personas
               (persona_id, name, icon, description, system_prompt, model,
                allowed_tools, is_builtin, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            (persona_id, name, icon, description, system_prompt, model,
             json.dumps(allowed_tools or []), now, now),
        )
    return get_persona(persona_id)  # type: ignore[return-value]


def update_persona(persona_id: str, **fields) -> Optional[dict]:
    """Update editable fields. Works for built-ins too (edit, not delete)."""
    editable = {"name", "icon", "description", "system_prompt", "model", "allowed_tools"}
    sets, params = [], []
    for key, value in fields.items():
        if key not in editable or value is None:
            continue
        if key == "allowed_tools":
            value = json.dumps(value)
        sets.append(f"{key} = ?")
        params.append(value)
    if sets:
        sets.append("updated_at = ?")
        params.append(_now())
        params.append(persona_id)
        with get_connection() as conn:
            # `sets` holds only hardcoded "<col> = ?" fragments; values are
            # parameterized. Safe despite the f-string.
            conn.execute(
                f"UPDATE personas SET {', '.join(sets)} WHERE persona_id = ?",  # noqa: S608  # nosec B608
                params,
            )
    return get_persona(persona_id)


def delete_persona(persona_id: str) -> bool:
    """Delete a custom persona. Built-ins cannot be deleted."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT is_builtin FROM personas WHERE persona_id = ?", (persona_id,)
        ).fetchone()
        if not row:
            return False
        if row["is_builtin"]:
            raise ValueError("Built-in personas cannot be deleted (edit them instead).")
        conn.execute("DELETE FROM personas WHERE persona_id = ?", (persona_id,))
    return True
