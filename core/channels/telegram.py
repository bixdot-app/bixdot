# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Telegram Bridge (v0.5)

Talk to your BixDot agent from any phone via a Telegram bot — WITHOUT exposing
anything. The backend makes OUTBOUND long-polling calls to api.telegram.org
(plain httpx, no webhook, no inbound port, no new dependencies). The backend
stays bound to 127.0.0.1 exactly as before.

Security model:
- The bot token lives in the OS keyring — never in the DB, config, or audit log.
- Only PAIRED chats may talk to the agent. Pairing requires a 6-digit code
  displayed inside the app (5-minute TTL) — possession of the app, not just the
  bot handle, is required.
- Messages from unpaired chats are rejected and audited (chat id only).
- Note for the threat model: Telegram messages traverse Telegram's servers by
  definition. Enabling this bridge is an explicit, per-user opt-in.
"""

import asyncio
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from core.storage.db import (
    get_connection, get_setting, set_setting,
    store_api_key, get_api_key, delete_api_key,
)
from core.audit.logger import get_audit_logger, AuditEvent

KEYRING_SERVICE = "telegram_bot"
PAIRING_TTL_MINUTES = 5
MAX_UPDATES_PER_TICK = 10
REPLY_MAX_CHARS = 3900          # Telegram hard limit is 4096

# ── Module state ───────────────────────────────────────────────────────────────
_poller_task: Optional[asyncio.Task] = None
# One active pairing code at a time: {"code", "user_id", "persona_id", "expires"}
_active_pairing: Optional[dict] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Telegram HTTP seam (single point, easily mocked in tests) ────────────────

async def _api(method: str, payload: dict | None = None, *, timeout: float = 60) -> dict:
    """Call a Telegram Bot API method. Raises on transport errors."""
    from core.privacy import record_net
    record_net("telegram")
    token = get_api_key(KEYRING_SERVICE)
    if not token:
        raise RuntimeError("Telegram bot token not configured.")
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            f"https://api.telegram.org/bot{token}/{method}",
            json=payload or {},
        )
        r.raise_for_status()
        return r.json()


async def _send(chat_id: str, text: str) -> None:
    for start in range(0, max(len(text), 1), REPLY_MAX_CHARS):
        await _api("sendMessage", {
            "chat_id": chat_id, "text": text[start:start + REPLY_MAX_CHARS],
        }, timeout=30)


# ─── Configuration ─────────────────────────────────────────────────────────────

async def connect(token: str, user_id: str) -> dict:
    """Validate the token via getMe, store it in the keyring, start polling."""
    token = token.strip()
    if not token or ":" not in token:
        raise ValueError("That doesn't look like a Telegram bot token.")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"https://api.telegram.org/bot{token}/getMe")
        data = r.json() if r.status_code == 200 else {}
    if not data.get("ok"):
        raise ValueError("Telegram rejected this token. Create a bot with @BotFather "
                         "and paste the token it gives you.")
    bot = data["result"]
    store_api_key(KEYRING_SERVICE, token)
    set_setting("telegram_enabled", "1")
    set_setting("telegram_bot_username", bot.get("username", ""))
    get_audit_logger().log(AuditEvent.TELEGRAM_ENABLED,
                           {"bot_username": bot.get("username", "")},
                           user_id=user_id)
    start_poller()
    return {"bot_username": bot.get("username", "")}


def disconnect(user_id: str) -> None:
    """Stop polling, forget the token, and clear all pairings."""
    stop_poller()
    delete_api_key(KEYRING_SERVICE)
    set_setting("telegram_enabled", "0")
    with get_connection() as conn:
        conn.execute("DELETE FROM telegram_pairings")
    get_audit_logger().log(AuditEvent.TELEGRAM_DISABLED, {}, user_id=user_id)


def is_enabled() -> bool:
    return get_setting("telegram_enabled") == "1" and bool(get_api_key(KEYRING_SERVICE))


def status() -> dict:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT chat_id, user_id, persona_id, paired_at FROM telegram_pairings"
        ).fetchall()
    return {
        "enabled": is_enabled(),
        "bot_username": get_setting("telegram_bot_username") or "",
        "pairings": [
            {"chat_id": r["chat_id"], "persona_id": r["persona_id"] or "",
             "paired_at": r["paired_at"]}
            for r in rows
        ],
    }


# ─── Pairing ───────────────────────────────────────────────────────────────────

def start_pairing(user_id: str, persona_id: str = "") -> dict:
    """Create a 6-digit pairing code shown in the app. One active code at a time."""
    global _active_pairing
    code = f"{secrets.randbelow(1_000_000):06d}"
    _active_pairing = {
        "code": code,
        "user_id": user_id,
        "persona_id": persona_id,
        "expires": _now() + timedelta(minutes=PAIRING_TTL_MINUTES),
    }
    return {"code": code, "expires_in_seconds": PAIRING_TTL_MINUTES * 60}


def _try_pair(chat_id: str, text: str) -> bool:
    """If the message is the active pairing code, pair this chat."""
    global _active_pairing
    if not _active_pairing:
        return False
    if _now() > _active_pairing["expires"]:
        _active_pairing = None
        return False
    if text.strip() != _active_pairing["code"]:
        return False
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO telegram_pairings "
            "(chat_id, user_id, persona_id, paired_at) VALUES (?, ?, ?, ?)",
            (str(chat_id), _active_pairing["user_id"],
             _active_pairing["persona_id"] or None, _now().isoformat()),
        )
    get_audit_logger().log(AuditEvent.TELEGRAM_PAIRED,
                           {"chat_id": str(chat_id)},
                           user_id=_active_pairing["user_id"])
    _active_pairing = None
    return True


def unpair(chat_id: str, user_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM telegram_pairings WHERE chat_id = ? AND user_id = ?",
            (str(chat_id), user_id),
        )
        removed = cur.rowcount > 0
    if removed:
        get_audit_logger().log(AuditEvent.TELEGRAM_UNPAIRED,
                               {"chat_id": str(chat_id)}, user_id=user_id)
    return removed


def _get_pairing(chat_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM telegram_pairings WHERE chat_id = ?", (str(chat_id),)
        ).fetchone()
    if not row:
        return None
    return {"chat_id": row["chat_id"], "user_id": row["user_id"],
            "persona_id": row["persona_id"] or ""}


# ─── Message handling ──────────────────────────────────────────────────────────

async def handle_update(update: dict) -> None:
    """Process one Telegram update. Never raises — the poller must survive."""
    audit = get_audit_logger()
    try:
        message = update.get("message") or {}
        chat_id = str((message.get("chat") or {}).get("id", ""))
        text = (message.get("text") or "").strip()
        if not chat_id or not text:
            return

        pairing = _get_pairing(chat_id)
        if pairing is None:
            if _try_pair(chat_id, text):
                await _send(chat_id, "✅ Paired with BixDot! Send me anything — "
                                     "your agent runs on your own computer.")
            else:
                audit.log(AuditEvent.TELEGRAM_REJECTED, {"chat_id": chat_id})
                await _send(chat_id, "🔒 This BixDot is private. Open BixDot on "
                                     "your computer, go to Settings → Telegram, "
                                     "and send me the 6-digit pairing code.")
            return

        # Paired chat → run the agent
        from core.agent.runtime import AgentRuntime
        from core.agent import session_store

        user_id = pairing["user_id"]
        audit.log(AuditEvent.TELEGRAM_MESSAGE,
                  {"chat_id": chat_id, "preview": text[:100]}, user_id=user_id)

        session_name = "📱 Telegram"
        session = None
        for meta in session_store.list_sessions(user_id):
            if meta["name"] == session_name and not meta["is_private"]:
                session = session_store.load_session(meta["session_id"])
                break
        if session is None:
            meta = session_store.create_session(
                user_id, name=session_name,
                persona_id=pairing.get("persona_id", ""),
            )
            session = session_store.load_session(meta["session_id"])

        response = await AgentRuntime().run(session, text)
        session_store.save_session(session)
        reply = response.message
        if response.permissions_requested:
            reply = ("I need a permission I don't have yet: "
                     + ", ".join(response.permissions_requested)
                     + ". Please grant it in the BixDot app, then ask me again.")
        await _send(chat_id, reply or "Done.")
    except Exception as e:
        try:
            get_audit_logger().log(AuditEvent.TELEGRAM_REJECTED,
                                   {"error": str(e)[:200]})
        except Exception:
            pass


async def send_to_paired_chats(user_id: str, text: str) -> int:
    """Push a message (e.g. a scheduled briefing) to every chat this user paired."""
    if not is_enabled():
        return 0
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT chat_id FROM telegram_pairings WHERE user_id = ?", (user_id,)
        ).fetchall()
    sent = 0
    for r in rows:
        try:
            await _send(r["chat_id"], text)
            sent += 1
        except Exception:
            pass
    return sent


# ─── Long-poll loop ────────────────────────────────────────────────────────────

async def _poll_loop() -> None:
    offset = 0
    while True:
        try:
            data = await _api("getUpdates", {
                "offset": offset, "timeout": 50,
                "allowed_updates": ["message"],
            })
            updates = data.get("result", [])[:MAX_UPDATES_PER_TICK]
            for update in updates:
                offset = max(offset, update.get("update_id", 0) + 1)
                await handle_update(update)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(5)  # transient network error — retry calmly


def start_poller() -> None:
    """Start the long-poll task if configured and not already running."""
    global _poller_task
    if _poller_task and not _poller_task.done():
        return
    if not is_enabled():
        return
    _poller_task = asyncio.get_event_loop().create_task(_poll_loop())


def stop_poller() -> None:
    global _poller_task
    if _poller_task and not _poller_task.done():
        _poller_task.cancel()
    _poller_task = None
