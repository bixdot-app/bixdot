# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""Persistent memory store using SQLite FTS5."""

import uuid
from datetime import datetime, UTC
from core.storage.db import get_connection

VALID_CATEGORIES = {"general", "preference", "fact", "task", "person", "project"}


def init_memory_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                content     TEXT NOT NULL,
                category    TEXT NOT NULL DEFAULT 'general',
                source      TEXT NOT NULL DEFAULT 'user',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
            USING fts5(content, id UNINDEXED, user_id UNINDEXED,
                       tokenize='porter unicode61')
        """)


def save_memory(user_id: str, content: str, category: str = "general", source: str = "user") -> str:
    if category not in VALID_CATEGORIES:
        category = "general"
    mem_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO memories (id, user_id, content, category, source, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (mem_id, user_id, content, category, source, now, now),
        )
        conn.execute(
            "INSERT INTO memories_fts (content, id, user_id) VALUES (?,?,?)",
            (content, mem_id, user_id),
        )
    return mem_id


def search_memories(user_id: str, query: str, limit: int = 10) -> list[dict]:
    safe_query = query.replace('"', '').replace("'", "").strip()
    if not safe_query:
        return load_all_memories(user_id, limit=limit)
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT m.id, m.content, m.category, m.source, m.created_at
                FROM memories_fts f
                JOIN memories m ON m.id = f.id
                WHERE f.memories_fts MATCH ? AND f.user_id = ?
                ORDER BY rank
                LIMIT ?
                """,
                (safe_query, user_id, limit),
            ).fetchall()
        return [{"id": r[0], "content": r[1], "category": r[2], "source": r[3], "created_at": r[4]} for r in rows]
    except Exception:
        # FTS5 query syntax error — fall back to LIKE search
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, content, category, source, created_at FROM memories "
                    "WHERE user_id=? AND LOWER(content) LIKE ? ORDER BY created_at DESC LIMIT ?",
                    (user_id, f"%{query.lower()}%", limit),
                ).fetchall()
            return [{"id": r[0], "content": r[1], "category": r[2], "source": r[3], "created_at": r[4]} for r in rows]
        except Exception:
            return []


def load_all_memories(user_id: str, limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, content, category, source, created_at FROM memories WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [{"id": r[0], "content": r[1], "category": r[2], "source": r[3], "created_at": r[4]} for r in rows]


def delete_memory(mem_id: str, user_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM memories WHERE id=? AND user_id=?", (mem_id, user_id)
        )
        if cur.rowcount:
            conn.execute("DELETE FROM memories_fts WHERE id=?", (mem_id,))
            return True
    return False
