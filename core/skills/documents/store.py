# Copyright (c) 2026 DigiTect Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""Document metadata storage (SQLite) and file management."""

import uuid
from datetime import datetime, UTC
from pathlib import Path
from core.storage.db import get_connection

DOCS_DIR = Path.home() / ".bixdot" / "documents"


def init_documents_db():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id           TEXT PRIMARY KEY,
                user_id      TEXT NOT NULL,
                filename     TEXT NOT NULL,
                file_path    TEXT NOT NULL,
                mime_type    TEXT NOT NULL,
                size_bytes   INTEGER NOT NULL,
                text_content TEXT NOT NULL,
                created_at   TEXT NOT NULL
            )
        """)


def save_document(user_id: str, filename: str, file_path: str,
                  mime_type: str, size_bytes: int, text_content: str) -> str:
    doc_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO documents (id, user_id, filename, file_path, mime_type, size_bytes, text_content, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (doc_id, user_id, filename, file_path, mime_type, size_bytes, text_content, now),
        )
    return doc_id


def load_documents(user_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, filename, mime_type, size_bytes, created_at FROM documents WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [{"id": r[0], "filename": r[1], "mime_type": r[2], "size_bytes": r[3], "created_at": r[4]} for r in rows]


def load_document(doc_id: str, user_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, filename, file_path, mime_type, size_bytes, text_content, created_at FROM documents WHERE id=? AND user_id=?",
            (doc_id, user_id),
        ).fetchone()
    if not row:
        return None
    return {"id": row[0], "filename": row[1], "file_path": row[2], "mime_type": row[3],
            "size_bytes": row[4], "text_content": row[5], "created_at": row[6]}


def delete_document(doc_id: str, user_id: str) -> bool:
    doc = load_document(doc_id, user_id)
    if not doc:
        return False
    try:
        Path(doc["file_path"]).unlink(missing_ok=True)
    except Exception:
        pass
    with get_connection() as conn:
        conn.execute("DELETE FROM documents WHERE id=? AND user_id=?", (doc_id, user_id))
    return True
