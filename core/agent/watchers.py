# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Watchers (v0.6): event-triggered automations

Routines react to the clock; Watchers react to life:

- ``folder_new_file`` — "When a new file appears in <folder>, do <prompt>."
  Zero dependencies: each scheduler tick diffs a folder snapshot (name+mtime).
  The first tick only baselines — existing files never trigger a storm.
- ``meeting_soon`` — "<lead> minutes before each meeting, do <prompt>."
  Reads the connected calendar; each event fires at most once.

Security model (same as Routines): watcher runs are headless, so the user
pre-approves capabilities at creation in plain language; each firing grants
exactly those with a short TTL. Folder paths must live inside the user's home
directory. ``meeting_soon`` requires an explicit ``calendar:read`` approval
because the trigger check itself reads the calendar.
"""

import json
import fnmatch
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from core.storage.db import get_connection
from core.audit.logger import get_audit_logger, AuditEvent
from core.agent.permissions import Capability, get_permission_store
from core.agent.scheduler import enqueue_notification, RUN_GRANT_TTL_MINUTES

WATCHER_TYPES = {"folder_new_file", "meeting_soon"}
MAX_FIRES_PER_TICK = 3


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_watcher(row) -> dict:
    return {
        "watcher_id": row["watcher_id"],
        "user_id": row["user_id"],
        "persona_id": row["persona_id"] or "",
        "name": row["name"],
        "type": row["type"],
        "config": json.loads(row["config"]),
        "prompt": row["prompt"],
        "notify_desktop": bool(row["notify_desktop"]),
        "notify_telegram": bool(row["notify_telegram"]),
        "is_enabled": bool(row["is_enabled"]),
        "state": json.loads(row["state"]),
        "last_fired_at": row["last_fired_at"],
        "created_at": row["created_at"],
    }


# ─── Validation ────────────────────────────────────────────────────────────────

def validate_watcher(wtype: str, config: dict, capabilities: list[str]) -> None:
    if wtype not in WATCHER_TYPES:
        raise ValueError(f"type must be one of {sorted(WATCHER_TYPES)}")
    valid_caps = {c.value for c in Capability}
    for cap in capabilities:
        if cap not in valid_caps:
            raise ValueError(f"Unknown capability: {cap}")

    if wtype == "folder_new_file":
        folder = Path(str(config.get("folder", ""))).expanduser()
        if not folder.is_dir():
            raise ValueError("That folder doesn't exist.")
        try:
            folder.resolve().relative_to(Path.home())
        except ValueError:
            raise ValueError("Watched folders must be inside your home directory.")
    elif wtype == "meeting_soon":
        lead = int(config.get("lead_minutes", 15))
        if not 1 <= lead <= 240:
            raise ValueError("lead_minutes must be between 1 and 240.")
        if Capability.CALENDAR_READ.value not in capabilities:
            raise ValueError(
                "Meeting watchers need your approval to read the calendar "
                "(calendar:read) — the trigger itself checks your events."
            )


# ─── CRUD ──────────────────────────────────────────────────────────────────────

def create_watcher(user_id: str, *, name: str, wtype: str, config: dict,
                   prompt: str, persona_id: str = "",
                   notify_desktop: bool = True, notify_telegram: bool = False,
                   capabilities: Optional[list[str]] = None) -> dict:
    capabilities = capabilities or []
    validate_watcher(wtype, config, capabilities)
    watcher_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO watchers
               (watcher_id, user_id, persona_id, name, type, config, prompt,
                notify_desktop, notify_telegram, is_enabled, state, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '{}', ?)""",
            (watcher_id, user_id, persona_id or None, name, wtype,
             json.dumps(config), prompt, int(notify_desktop),
             int(notify_telegram), _now_utc()),
        )
        for cap in capabilities:
            conn.execute(
                "INSERT OR IGNORE INTO watcher_capability_grants "
                "(watcher_id, capability) VALUES (?, ?)",
                (watcher_id, cap),
            )
    return get_watcher(watcher_id)  # type: ignore[return-value]


def get_watcher(watcher_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM watchers WHERE watcher_id = ?", (watcher_id,)
        ).fetchone()
        if not row:
            return None
        caps = [r["capability"] for r in conn.execute(
            "SELECT capability FROM watcher_capability_grants WHERE watcher_id = ?",
            (watcher_id,),
        ).fetchall()]
    watcher = _row_to_watcher(row)
    watcher["capabilities"] = caps
    return watcher


def list_watchers(user_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT watcher_id FROM watchers WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [get_watcher(r["watcher_id"]) for r in rows]  # type: ignore[misc]


def set_watcher_enabled(watcher_id: str, enabled: bool) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE watchers SET is_enabled = ? WHERE watcher_id = ?",
                     (int(enabled), watcher_id))


def delete_watcher(watcher_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM watchers WHERE watcher_id = ?", (watcher_id,))


def watcher_belongs_to(watcher_id: str, user_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT user_id FROM watchers WHERE watcher_id = ?", (watcher_id,)
        ).fetchone()
    return row is not None and row["user_id"] == user_id


def _save_state(watcher_id: str, state: dict) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE watchers SET state = ? WHERE watcher_id = ?",
                     (json.dumps(state), watcher_id))


# ─── Trigger checks (called from the scheduler loop each tick) ─────────────────

def _folder_snapshot(folder: Path, pattern: str) -> dict[str, float]:
    snap = {}
    try:
        for entry in folder.iterdir():
            if entry.is_file() and fnmatch.fnmatch(entry.name.lower(), pattern.lower()):
                snap[entry.name] = entry.stat().st_mtime
    except OSError:
        pass
    return snap


def check_folder_watcher(watcher: dict) -> list[dict]:
    """Return a firing context per NEW file. First run baselines, never fires."""
    config = watcher["config"]
    folder = Path(str(config.get("folder", ""))).expanduser()
    pattern = config.get("pattern") or "*"
    snap = _folder_snapshot(folder, pattern)

    state = watcher["state"]
    if "known" not in state:
        _save_state(watcher["watcher_id"], {"known": snap})
        return []

    known = state["known"]
    new_files = [name for name in snap if name not in known]
    _save_state(watcher["watcher_id"], {"known": snap})

    return [{"file": str(folder / name)} for name in sorted(new_files)[:MAX_FIRES_PER_TICK]]


async def check_meeting_watcher(watcher: dict) -> list[dict]:
    """Return a firing context per meeting entering the lead window (once each)."""
    from core.skills.calendar.store import load_active_provider
    from core.skills.calendar.google_cal import GoogleCalendarProvider
    from core.skills.calendar.outlook_cal import OutlookCalendarProvider
    from core.skills.calendar.ical_cal import ICalProvider

    result = load_active_provider(watcher["user_id"])
    if not result:
        return []
    name, config = result
    provider = {"google": GoogleCalendarProvider, "outlook": OutlookCalendarProvider,
                "ical": ICalProvider}.get(name)
    if not provider:
        return []
    try:
        events = await provider(config).get_events(days_ahead=1)
    except Exception:
        return []

    lead = timedelta(minutes=int(watcher["config"].get("lead_minutes", 15)))
    now = datetime.now(timezone.utc)
    state = watcher["state"]
    notified = set(state.get("notified", []))

    contexts = []
    still_relevant = set()
    for event in events:
        start = event.start if event.start.tzinfo else event.start.replace(tzinfo=timezone.utc)
        event_id = f"{event.id or event.title}@{start.isoformat()}"
        if start <= now:
            continue
        still_relevant.add(event_id)
        if event_id in notified:
            continue
        if start - now <= lead:
            notified.add(event_id)
            when = start.astimezone().strftime("%H:%M")
            contexts.append({"event": f'"{event.title}" at {when}'})

    # Keep only ids still in the future — past meetings age out of the state.
    _save_state(watcher["watcher_id"], {"notified": sorted(notified & still_relevant)})
    return contexts[:MAX_FIRES_PER_TICK]


# ─── Firing ────────────────────────────────────────────────────────────────────

async def fire_watcher(watcher: dict, context: dict) -> dict:
    """Run the watcher's prompt with the trigger context substituted in."""
    from core.agent.runtime import AgentRuntime
    from core.agent import session_store

    audit = get_audit_logger()
    user_id = watcher["user_id"]

    prompt = watcher["prompt"]
    for key, value in context.items():
        prompt = prompt.replace("{" + key + "}", str(value))

    store = get_permission_store()
    for cap in watcher.get("capabilities", []):
        store.grant("builtin", Capability(cap), granted_by=user_id,
                    duration_minutes=RUN_GRANT_TTL_MINUTES)

    session_name = f"👀 {watcher['name']}"
    session = None
    for meta in session_store.list_sessions(user_id):
        if meta["name"] == session_name and not meta["is_private"]:
            session = session_store.load_session(meta["session_id"])
            break
    if session is None:
        meta = session_store.create_session(
            user_id, name=session_name, persona_id=watcher.get("persona_id", ""))
        session = session_store.load_session(meta["session_id"])

    try:
        response = await AgentRuntime().run(session, prompt)
        session_store.save_session(session)
        result_text = response.message
        if response.permissions_requested:
            result_text = ("This watcher needs a permission that wasn't approved: "
                           + ", ".join(response.permissions_requested)
                           + ". Edit the watcher to approve it.")
        audit.log(AuditEvent.WATCHER_FIRED,
                  {"watcher_id": watcher["watcher_id"], "context": context,
                   "session_id": session.session_id},
                  user_id=user_id)
        ok = True
    except Exception as e:
        result_text = f"Watcher failed: {e}"
        audit.log(AuditEvent.WATCHER_FAILED,
                  {"watcher_id": watcher["watcher_id"], "error": str(e)[:200]},
                  user_id=user_id)
        ok = False

    with get_connection() as conn:
        conn.execute("UPDATE watchers SET last_fired_at = ? WHERE watcher_id = ?",
                     (_now_utc(), watcher["watcher_id"]))
    if watcher["notify_desktop"]:
        enqueue_notification(user_id, watcher["name"], result_text[:300])
    if watcher["notify_telegram"]:
        try:
            from core.channels.telegram import send_to_paired_chats
            await send_to_paired_chats(user_id, f"👀 {watcher['name']}\n\n{result_text[:3500]}")
        except Exception:
            pass

    return {"ok": ok, "result": result_text, "session_id": session.session_id}


async def check_watchers() -> None:
    """Evaluate every enabled watcher once. Called from the scheduler tick."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT watcher_id FROM watchers WHERE is_enabled = 1"
        ).fetchall()
    for r in rows:
        watcher = get_watcher(r["watcher_id"])
        if not watcher:
            continue
        try:
            if watcher["type"] == "folder_new_file":
                contexts = check_folder_watcher(watcher)
            else:
                contexts = await check_meeting_watcher(watcher)
            for context in contexts:
                await fire_watcher(watcher, context)
        except Exception as e:  # one bad watcher must not stop the rest
            print(f"[BixDot] Watcher check error ({watcher['name']}): {e}")
