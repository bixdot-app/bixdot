# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
BixDot — Session Store (v0.4 multi-session)

Persists agent sessions and their chat history to ~/.bixdot/data.db.

Private sessions (is_private=1) are held ENTIRELY in memory — never written to
the `sessions` or `session_messages` tables. They appear in the session list
while the process is running and vanish on restart or delete, leaving zero
trace in the database. The audit log records only the event type for private
sessions, never message content.

The schema is owned by core.storage.db (single source of truth); this module
is a thin data-access layer over it.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from core.agent.runtime import AgentSession, Message
from core.agent.model_caps import ModelMode
from core.storage.db import get_connection, init_db as _init_core_db

# ── In-memory store for private sessions ───────────────────────────────────────
# session_id -> AgentSession (messages live here, never touch the DB)
_private_sessions: dict[str, AgentSession] = {}
# session_id -> metadata dict (name, model, model_mode, llm_backend, timestamps)
_private_meta: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Internal memory-context messages injected by the runtime — hidden from the UI.
def _is_visible(role: str, content: str) -> bool:
    if content.startswith("[MEMORY CONTEXT]"):
        return False
    if role == "assistant" and content == "Noted, I have that context.":
        return False
    return True


# ─── Schema init (delegates to core.storage.db) ────────────────────────────────

_initialized = False


def init_db() -> None:
    """Ensure the shared schema exists. Idempotent."""
    _init_core_db()


def get_session_store():
    """Call once at startup to ensure the DB schema is ready."""
    global _initialized
    if not _initialized:
        init_db()
        _initialized = True


# ─── Metadata helpers ──────────────────────────────────────────────────────────

def _meta_from_row(row, *, message_count: int, last_preview: Optional[str]) -> dict:
    return {
        "session_id": row["session_id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "model": row["model"],
        "model_mode": row["model_mode"],
        "llm_backend": row["llm_backend"],
        "is_private": bool(row["is_private"]),
        "is_archived": bool(row["is_archived"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "message_count": message_count,
        "last_message_preview": last_preview,
    }


def _private_meta_view(session_id: str) -> dict:
    meta = dict(_private_meta[session_id])
    sess = _private_sessions.get(session_id)
    visible = [m for m in (sess.messages if sess else []) if _is_visible(m.role, m.content)]
    meta["message_count"] = len(visible)
    meta["last_message_preview"] = (visible[-1].content[:80] if visible else None)
    return meta


# ─── Create ────────────────────────────────────────────────────────────────────

def create_session(
    user_id: str,
    *,
    name: str = "New Chat",
    model: str = "",
    model_mode: str = ModelMode.FULL_AGENT.value,
    llm_backend: str = "ollama",
    is_private: bool = False,
) -> dict:
    """Create a session. Returns its metadata dict."""
    session_id = str(uuid.uuid4())
    now = _now()

    if is_private:
        _private_sessions[session_id] = AgentSession(
            session_id=session_id,
            user_id=user_id,
            llm_backend=llm_backend,
            model=model,
            model_mode=model_mode,
            is_private=True,
        )
        _private_meta[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "name": name,
            "model": model,
            "model_mode": model_mode,
            "llm_backend": llm_backend,
            "is_private": True,
            "is_archived": False,
            "created_at": now,
            "updated_at": now,
            "started_monotonic": datetime.now(timezone.utc),
        }
        return _private_meta_view(session_id)

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO sessions
               (session_id, user_id, name, model, model_mode, llm_backend,
                is_private, is_archived, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?)""",
            (session_id, user_id, name, model, model_mode, llm_backend, now, now),
        )
    return get_session_meta(session_id)  # type: ignore[return-value]


# ─── Read ──────────────────────────────────────────────────────────────────────

def get_session_meta(session_id: str) -> Optional[dict]:
    """Return session metadata (incl. message_count + last preview), or None."""
    if session_id in _private_meta:
        return _private_meta_view(session_id)

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        agg = conn.execute(
            "SELECT COUNT(*) AS c FROM session_messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        last = conn.execute(
            "SELECT role, content FROM session_messages "
            "WHERE session_id = ? ORDER BY id DESC LIMIT 5",
            (session_id,),
        ).fetchall()
    preview = None
    for r in last:  # newest first — first visible one is the latest message
        if _is_visible(r["role"], r["content"]):
            preview = r["content"][:80]
            break
    return _meta_from_row(row, message_count=agg["c"], last_preview=preview)


def list_sessions(user_id: str, include_archived: bool = False) -> list[dict]:
    """List a user's sessions, newest first. Private (in-memory) sessions merged in."""
    metas: list[dict] = []

    with get_connection() as conn:
        q = "SELECT * FROM sessions WHERE user_id = ?"
        if not include_archived:
            q += " AND is_archived = 0"
        q += " ORDER BY updated_at DESC"
        rows = conn.execute(q, (user_id,)).fetchall()
        for row in rows:
            agg = conn.execute(
                "SELECT COUNT(*) AS c FROM session_messages WHERE session_id = ?",
                (row["session_id"],),
            ).fetchone()
            last = conn.execute(
                "SELECT role, content FROM session_messages "
                "WHERE session_id = ? ORDER BY id DESC LIMIT 5",
                (row["session_id"],),
            ).fetchall()
            preview = None
            for r in last:
                if _is_visible(r["role"], r["content"]):
                    preview = r["content"][:80]
                    break
            metas.append(_meta_from_row(row, message_count=agg["c"], last_preview=preview))

    # Merge in-memory private sessions for this user (not archived by definition)
    private = [
        _private_meta_view(sid)
        for sid, m in _private_meta.items()
        if m["user_id"] == user_id
    ]
    metas.extend(private)
    metas.sort(key=lambda m: m["updated_at"], reverse=True)
    return metas


def get_messages(
    session_id: str, limit: int = 50, before_id: Optional[int] = None
) -> list[dict]:
    """
    Return visible chat messages for a session, oldest-first.
    `before_id` paginates: returns messages with id < before_id.
    Private sessions return their in-memory history (no ids).
    """
    if session_id in _private_sessions:
        msgs = _private_sessions[session_id].messages
        visible = [
            {"role": m.role, "content": m.content}
            for m in msgs
            if _is_visible(m.role, m.content)
        ]
        return visible[-limit:]

    with get_connection() as conn:
        if before_id is not None:
            rows = conn.execute(
                "SELECT id, role, content, created_at FROM session_messages "
                "WHERE session_id = ? AND id < ? ORDER BY id DESC LIMIT ?",
                (session_id, before_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, role, content, created_at FROM session_messages "
                "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
    out = []
    for r in reversed(rows):  # back to oldest-first
        if _is_visible(r["role"], r["content"]):
            out.append({
                "id": r["id"], "role": r["role"],
                "content": r["content"], "created_at": r["created_at"],
            })
    return out


# ─── Update ────────────────────────────────────────────────────────────────────

def update_session(
    session_id: str,
    *,
    name: Optional[str] = None,
    is_archived: Optional[bool] = None,
) -> Optional[dict]:
    """Rename and/or archive a session. Returns updated metadata."""
    if session_id in _private_meta:
        # Private sessions can be renamed in memory; archiving is a no-op.
        if name is not None:
            _private_meta[session_id]["name"] = name
            _private_meta[session_id]["updated_at"] = _now()
        return _private_meta_view(session_id)

    sets, params = [], []
    if name is not None:
        sets.append("name = ?")
        params.append(name)
    if is_archived is not None:
        sets.append("is_archived = ?")
        params.append(1 if is_archived else 0)
    if sets:
        sets.append("updated_at = ?")
        params.append(_now())
        params.append(session_id)
        with get_connection() as conn:
            # `sets` contains only hardcoded "<col> = ?" fragments; every value
            # is parameterized via `params`. Safe despite the f-string. noqa S608.
            conn.execute(
                f"UPDATE sessions SET {', '.join(sets)} WHERE session_id = ?",  # noqa: S608  # nosec B608
                params,
            )
    return get_session_meta(session_id)


# ─── Delete ────────────────────────────────────────────────────────────────────

def delete_session(session_id: str) -> None:
    """Hard delete a session and its messages (or drop a private session)."""
    if session_id in _private_sessions:
        _private_sessions.pop(session_id, None)
        _private_meta.pop(session_id, None)
        return
    with get_connection() as conn:
        # ON DELETE CASCADE removes session_messages
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))


def session_belongs_to(session_id: str, user_id: str) -> bool:
    """Security check — verify a session belongs to the user."""
    if session_id in _private_meta:
        return _private_meta[session_id]["user_id"] == user_id
    with get_connection() as conn:
        row = conn.execute(
            "SELECT user_id FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    return row is not None and row["user_id"] == user_id


def is_private(session_id: str) -> bool:
    return session_id in _private_sessions


# ─── AgentSession bridge (for the runtime) ─────────────────────────────────────

def load_session(session_id: str) -> Optional[AgentSession]:
    """Load an AgentSession (with messages) for the runtime. Private = in-memory."""
    if session_id in _private_sessions:
        return _private_sessions[session_id]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        msg_rows = conn.execute(
            "SELECT role, content FROM session_messages "
            "WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    messages = [Message(role=r["role"], content=r["content"]) for r in msg_rows]
    return AgentSession(
        session_id=row["session_id"],
        user_id=row["user_id"],
        llm_backend=row["llm_backend"],
        model=row["model"],
        model_mode=row["model_mode"],
        messages=messages,
    )


def save_session(session: AgentSession) -> None:
    """
    Persist a session's messages after a runtime turn.

    Private sessions are kept in memory only. For regular sessions the message
    list is rewritten (replace-all) into session_messages and updated_at bumped.
    """
    if session.session_id in _private_sessions:
        _private_sessions[session.session_id] = session
        if session.session_id in _private_meta:
            _private_meta[session.session_id]["updated_at"] = _now()
        return

    now = _now()
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?", (session.session_id,)
        ).fetchone()
        if not exists:
            # Session row missing (e.g. legacy caller) — create a minimal one.
            conn.execute(
                """INSERT INTO sessions
                   (session_id, user_id, name, model, model_mode, llm_backend,
                    is_private, is_archived, created_at, updated_at)
                   VALUES (?, ?, 'New Chat', '', ?, ?, 0, 0, ?, ?)""",
                (session.session_id, session.user_id, session.model_mode,
                 session.llm_backend, now, now),
            )
        conn.execute("DELETE FROM session_messages WHERE session_id = ?",
                     (session.session_id,))
        conn.executemany(
            "INSERT INTO session_messages (session_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            [(session.session_id, m.role, m.content, now) for m in session.messages],
        )
        conn.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                     (now, session.session_id))


def load_user_sessions(user_id: str) -> list[AgentSession]:
    """Legacy helper — load all regular AgentSessions for a user, newest first."""
    out = []
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT session_id FROM sessions WHERE user_id = ? AND is_archived = 0 "
            "ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    for r in rows:
        s = load_session(r["session_id"])
        if s:
            out.append(s)
    return out


# ─── Test isolation helper ─────────────────────────────────────────────────────

def _reset_for_tests() -> None:
    """Clear in-memory private session state between tests."""
    _private_sessions.clear()
    _private_meta.clear()
