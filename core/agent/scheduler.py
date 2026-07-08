# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Scheduled Background Agents (v0.5)

Zero-dependency asyncio scheduler. Consumer-friendly schedules (no cron
strings): hourly / daily / weekdays / weekly at a local HH:MM.

Security model for headless runs:
- A scheduled run cannot show permission prompts, so the user pre-approves the
  capabilities a schedule needs AT CREATION TIME (stored in
  schedule_capability_grants). Each run grants exactly those capabilities into
  the permission store with a short TTL — zero-default-permissions preserved,
  approval is explicit and auditable.
- Results are appended to a dedicated, visible chat session (one per schedule)
  and queued as notifications so the user sees them in the app / as a toast.
"""

import re
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional

from core.storage.db import get_connection
from core.audit.logger import get_audit_logger, AuditEvent
from core.agent.permissions import Capability, get_permission_store

VALID_FREQUENCIES = {"hourly", "daily", "weekdays", "weekly"}
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
TICK_SECONDS = 30
RUN_GRANT_TTL_MINUTES = 10


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_schedule(row) -> dict:
    return {
        "schedule_id": row["schedule_id"],
        "user_id": row["user_id"],
        "persona_id": row["persona_id"] or "",
        "name": row["name"],
        "prompt": row["prompt"],
        "frequency": row["frequency"],
        "at_time": row["at_time"],
        "weekday": row["weekday"],
        "notify_desktop": bool(row["notify_desktop"]),
        "notify_telegram": bool(row["notify_telegram"]),
        "is_enabled": bool(row["is_enabled"]),
        "last_run_at": row["last_run_at"],
        "created_at": row["created_at"],
    }


# ─── Validation ────────────────────────────────────────────────────────────────

def validate_schedule(frequency: str, at_time: str, weekday: Optional[int],
                      capabilities: list[str]) -> None:
    if frequency not in VALID_FREQUENCIES:
        raise ValueError(f"frequency must be one of {sorted(VALID_FREQUENCIES)}")
    if not _TIME_RE.match(at_time):
        raise ValueError("at_time must be HH:MM (24-hour)")
    if frequency == "weekly" and (weekday is None or not 0 <= int(weekday) <= 6):
        raise ValueError("weekly schedules need weekday 0 (Mon) .. 6 (Sun)")
    valid_caps = {c.value for c in Capability}
    for cap in capabilities:
        if cap not in valid_caps:
            raise ValueError(f"Unknown capability: {cap}")


# ─── CRUD ──────────────────────────────────────────────────────────────────────

def create_schedule(user_id: str, *, name: str, prompt: str,
                    persona_id: str = "", frequency: str = "daily",
                    at_time: str = "07:00", weekday: Optional[int] = None,
                    notify_desktop: bool = True, notify_telegram: bool = False,
                    capabilities: Optional[list[str]] = None) -> dict:
    capabilities = capabilities or []
    validate_schedule(frequency, at_time, weekday, capabilities)
    schedule_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO scheduled_agents
               (schedule_id, user_id, persona_id, name, prompt, frequency,
                at_time, weekday, notify_desktop, notify_telegram, is_enabled,
                created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (schedule_id, user_id, persona_id or None, name, prompt, frequency,
             at_time, weekday, int(notify_desktop), int(notify_telegram),
             _now_utc()),
        )
        for cap in capabilities:
            conn.execute(
                "INSERT OR IGNORE INTO schedule_capability_grants "
                "(schedule_id, capability) VALUES (?, ?)",
                (schedule_id, cap),
            )
    return get_schedule(schedule_id)  # type: ignore[return-value]


def get_schedule(schedule_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM scheduled_agents WHERE schedule_id = ?", (schedule_id,)
        ).fetchone()
        if not row:
            return None
        caps = [r["capability"] for r in conn.execute(
            "SELECT capability FROM schedule_capability_grants WHERE schedule_id = ?",
            (schedule_id,),
        ).fetchall()]
    schedule = _row_to_schedule(row)
    schedule["capabilities"] = caps
    return schedule


def list_schedules(user_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT schedule_id FROM scheduled_agents WHERE user_id = ? "
            "ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [get_schedule(r["schedule_id"]) for r in rows]  # type: ignore[misc]


def set_schedule_enabled(schedule_id: str, enabled: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE scheduled_agents SET is_enabled = ? WHERE schedule_id = ?",
            (int(enabled), schedule_id),
        )


def delete_schedule(schedule_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM scheduled_agents WHERE schedule_id = ?",
                     (schedule_id,))


def schedule_belongs_to(schedule_id: str, user_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT user_id FROM scheduled_agents WHERE schedule_id = ?",
            (schedule_id,),
        ).fetchone()
    return row is not None and row["user_id"] == user_id


# ─── Notifications queue ───────────────────────────────────────────────────────

def enqueue_notification(user_id: str, title: str, body: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO notifications (user_id, title, body, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, title, body[:500], _now_utc()),
        )


def fetch_pending_notifications(user_id: str) -> list[dict]:
    """Return undelivered notifications and mark them delivered atomically."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, body, created_at FROM notifications "
            "WHERE user_id = ? AND delivered = 0 ORDER BY id ASC LIMIT 20",
            (user_id,),
        ).fetchall()
        if rows:
            ids = [r["id"] for r in rows]
            conn.execute(
                f"UPDATE notifications SET delivered = 1 "
                f"WHERE id IN ({','.join('?' * len(ids))})",  # noqa: S608  # nosec B608 — placeholders only
                ids,
            )
    return [{"id": r["id"], "title": r["title"], "body": r["body"],
             "created_at": r["created_at"]} for r in rows]


# ─── Due-time computation (pure, injectable clock → easily tested) ────────────

def is_due(schedule: dict, now_local: Optional[datetime] = None) -> bool:
    """
    True when the schedule should run at this local wall-clock moment.

    Slot semantics prevent double-runs: a daily/weekdays/weekly schedule runs
    at most once per local day; hourly at most once per hour — even though the
    loop ticks every 30 seconds.
    """
    if not schedule["is_enabled"]:
        return False
    now = now_local or datetime.now()
    hh, mm = (int(x) for x in schedule["at_time"].split(":"))

    last_local: Optional[datetime] = None
    if schedule["last_run_at"]:
        last = datetime.fromisoformat(schedule["last_run_at"])
        # Stored as UTC; compare in local wall-clock terms.
        last_local = last.astimezone().replace(tzinfo=None) if last.tzinfo else last

    freq = schedule["frequency"]
    if freq == "hourly":
        if now.minute < mm:
            return False
        slot = now.replace(minute=0, second=0, microsecond=0)
        return last_local is None or last_local < slot

    # daily / weekdays / weekly — day-based slots
    if freq == "weekdays" and now.weekday() > 4:
        return False
    if freq == "weekly" and now.weekday() != int(schedule["weekday"] or 0):
        return False
    if (now.hour, now.minute) < (hh, mm):
        return False
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return last_local is None or last_local < today


# ─── Headless run ──────────────────────────────────────────────────────────────

async def run_schedule(schedule: dict) -> dict:
    """
    Execute one scheduled run. Grants the pre-approved capabilities with a
    short TTL, runs the agent against the schedule's persona, appends the
    result to the schedule's visible chat session, and queues notifications.
    """
    from core.agent.runtime import AgentRuntime
    from core.agent import session_store

    audit = get_audit_logger()
    user_id = schedule["user_id"]

    # 1. Grant pre-approved capabilities for this run only (short TTL).
    store = get_permission_store()
    for cap in schedule.get("capabilities", []):
        store.grant("builtin", Capability(cap), granted_by=user_id,
                    duration_minutes=RUN_GRANT_TTL_MINUTES)

    # 2. Find or create the schedule's visible session (one per schedule).
    session_name = f"⏰ {schedule['name']}"
    session = None
    for meta in session_store.list_sessions(user_id):
        if meta["name"] == session_name and not meta["is_private"]:
            session = session_store.load_session(meta["session_id"])
            break
    if session is None:
        meta = session_store.create_session(
            user_id, name=session_name,
            persona_id=schedule.get("persona_id", ""),
        )
        session = session_store.load_session(meta["session_id"])

    # 3. Run headlessly.
    try:
        response = await AgentRuntime().run(session, schedule["prompt"])
        session_store.save_session(session)
        result_text = response.message
        if response.permissions_requested:
            result_text = (
                "This scheduled task needs a permission that wasn't approved: "
                + ", ".join(response.permissions_requested)
                + ". Edit the schedule to approve it."
            )
        audit.log(AuditEvent.SCHEDULE_RUN,
                  {"schedule_id": schedule["schedule_id"],
                   "session_id": session.session_id},
                  user_id=user_id)
        ok = True
    except Exception as e:
        result_text = f"Scheduled task failed: {e}"
        audit.log(AuditEvent.SCHEDULE_RUN_FAILED,
                  {"schedule_id": schedule["schedule_id"], "error": str(e)[:200]},
                  user_id=user_id)
        ok = False

    # 4. Record the run + notify.
    with get_connection() as conn:
        conn.execute(
            "UPDATE scheduled_agents SET last_run_at = ? WHERE schedule_id = ?",
            (_now_utc(), schedule["schedule_id"]),
        )
    if schedule["notify_desktop"]:
        enqueue_notification(user_id, schedule["name"], result_text[:300])
    if schedule["notify_telegram"]:
        try:
            from core.channels.telegram import send_to_paired_chats
            await send_to_paired_chats(user_id, f"⏰ {schedule['name']}\n\n{result_text[:3500]}")
        except Exception:
            pass  # Telegram optional — never break the run

    return {"ok": ok, "result": result_text, "session_id": session.session_id}


# ─── Background loop (started in the app lifespan) ─────────────────────────────

async def scheduler_loop() -> None:
    """Tick every TICK_SECONDS; run any due schedule. Cancelled on shutdown."""
    while True:
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT schedule_id FROM scheduled_agents WHERE is_enabled = 1"
                ).fetchall()
            for r in rows:
                schedule = get_schedule(r["schedule_id"])
                if schedule and is_due(schedule):
                    await run_schedule(schedule)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # never let one bad tick kill the loop
            print(f"[BixDot] Scheduler tick error: {e}")
        await asyncio.sleep(TICK_SECONDS)
