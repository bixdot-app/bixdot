# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Tests for the v0.5 Telegram bridge: pairing security, message routing, and
routes. No network — the HTTP seam and keyring are mocked.
"""
import asyncio
from datetime import timedelta

import pytest

import core.agent.runtime as rt
import core.channels.telegram as tg
from core.storage.db import get_connection, set_setting


class FakeLLM:
    def __init__(self, backend="ollama", user_id=None, model=None):
        pass

    async def chat(self, messages, system="", tools=None, max_tokens=4096):
        return {"content": [{"type": "text", "text": "Agent reply."}],
                "stop_reason": "end_turn", "usage": {}}


@pytest.fixture(autouse=True)
def telegram_env(monkeypatch):
    """Fake keyring + captured sends + reset module state for every test."""
    fake_keys: dict[str, str] = {}
    sent: list[tuple[str, str]] = []

    monkeypatch.setattr(tg, "get_api_key", lambda svc: fake_keys.get(svc))
    monkeypatch.setattr(tg, "store_api_key", lambda svc, k: fake_keys.__setitem__(svc, k))
    monkeypatch.setattr(tg, "delete_api_key", lambda svc: fake_keys.pop(svc, None))

    async def _fake_send(chat_id, text):
        sent.append((str(chat_id), text))
    monkeypatch.setattr(tg, "_send", _fake_send)
    monkeypatch.setattr(tg, "start_poller", lambda: None)  # never spin the loop
    monkeypatch.setattr(tg, "_active_pairing", None)
    monkeypatch.setattr(rt, "LLMAdapter", FakeLLM)

    yield {"keys": fake_keys, "sent": sent}


def _enable(env):
    env["keys"][tg.KEYRING_SERVICE] = "123456:FAKE"
    set_setting("telegram_enabled", "1")


def _pairings() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM telegram_pairings").fetchone()[0]


# ─── Routes / auth ─────────────────────────────────────────────────────────────

def test_status_requires_auth(client):
    assert client.get("/agent/telegram/status").status_code == 401


def test_connect_rejects_bad_token(client, auth_headers, monkeypatch):
    import httpx

    class _Resp:
        status_code = 200
        def json(self): return {"ok": False}

    async def _post(self, *a, **k):
        return _Resp()
    monkeypatch.setattr(httpx.AsyncClient, "post", _post)

    r = client.post("/agent/telegram/connect", json={"token": "123:bad"},
                    headers=auth_headers)
    assert r.status_code == 400


def test_connect_stores_token_and_enables(client, auth_headers, monkeypatch, telegram_env):
    import httpx

    class _Resp:
        status_code = 200
        def json(self): return {"ok": True, "result": {"username": "bixdot_bot"}}

    async def _post(self, *a, **k):
        return _Resp()
    monkeypatch.setattr(httpx.AsyncClient, "post", _post)

    r = client.post("/agent/telegram/connect", json={"token": "123456:GOOD"},
                    headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["bot_username"] == "bixdot_bot"
    assert telegram_env["keys"][tg.KEYRING_SERVICE] == "123456:GOOD"

    s = client.get("/agent/telegram/status", headers=auth_headers).json()
    assert s["enabled"] is True
    assert s["bot_username"] == "bixdot_bot"


def test_pair_requires_connected_bot(client, auth_headers):
    r = client.post("/agent/telegram/pair", json={}, headers=auth_headers)
    assert r.status_code == 400


def test_disconnect_clears_everything(client, auth_headers, telegram_env):
    _enable(telegram_env)
    with get_connection() as conn:
        conn.execute("INSERT INTO telegram_pairings (chat_id, user_id, paired_at) "
                     "VALUES ('99', 'u1', 'now')")
    r = client.post("/agent/telegram/disconnect", headers=auth_headers)
    assert r.status_code == 200
    assert tg.KEYRING_SERVICE not in telegram_env["keys"]
    assert _pairings() == 0


# ─── Pairing security ──────────────────────────────────────────────────────────

def test_pairing_code_pairs_chat(telegram_env):
    _enable(telegram_env)
    code = tg.start_pairing("user-1")["code"]
    assert len(code) == 6

    asyncio.run(tg.handle_update(
        {"message": {"chat": {"id": 42}, "text": code}}))
    assert _pairings() == 1
    assert "Paired" in telegram_env["sent"][-1][1]


def test_wrong_code_does_not_pair(telegram_env):
    _enable(telegram_env)
    tg.start_pairing("user-1")
    asyncio.run(tg.handle_update(
        {"message": {"chat": {"id": 42}, "text": "000000"}}))
    assert _pairings() == 0
    assert "private" in telegram_env["sent"][-1][1].lower()


def test_expired_code_rejected(telegram_env, monkeypatch):
    _enable(telegram_env)
    tg.start_pairing("user-1")
    tg._active_pairing["expires"] = tg._now() - timedelta(seconds=1)
    asyncio.run(tg.handle_update(
        {"message": {"chat": {"id": 42}, "text": tg._active_pairing["code"] if tg._active_pairing else ""}}))
    assert _pairings() == 0


def test_unpaired_chat_rejected_and_audited(telegram_env):
    _enable(telegram_env)
    asyncio.run(tg.handle_update(
        {"message": {"chat": {"id": 7}, "text": "hello?"}}))
    assert _pairings() == 0
    from core.audit.logger import get_audit_logger
    events = [e["event"] for e in get_audit_logger().recent(limit=10)]
    assert "telegram.rejected" in events


# ─── Paired message flow ───────────────────────────────────────────────────────

def test_paired_message_runs_agent_and_replies(telegram_env):
    _enable(telegram_env)
    code = tg.start_pairing("user-1")["code"]
    asyncio.run(tg.handle_update({"message": {"chat": {"id": 42}, "text": code}}))

    asyncio.run(tg.handle_update(
        {"message": {"chat": {"id": 42}, "text": "what's the plan today?"}}))
    assert telegram_env["sent"][-1] == ("42", "Agent reply.")

    # Conversation is visible in a dedicated session
    from core.agent import session_store
    names = [m["name"] for m in session_store.list_sessions("user-1")]
    assert "📱 Telegram" in names


def test_send_to_paired_chats(telegram_env):
    _enable(telegram_env)
    with get_connection() as conn:
        conn.execute("INSERT INTO telegram_pairings (chat_id, user_id, paired_at) "
                     "VALUES ('1', 'user-1', 'now')")
        conn.execute("INSERT INTO telegram_pairings (chat_id, user_id, paired_at) "
                     "VALUES ('2', 'user-1', 'now')")
        conn.execute("INSERT INTO telegram_pairings (chat_id, user_id, paired_at) "
                     "VALUES ('3', 'other', 'now')")
    sent = asyncio.run(tg.send_to_paired_chats("user-1", "briefing text"))
    assert sent == 2
    chats = [c for c, _ in telegram_env["sent"]]
    assert "1" in chats and "2" in chats and "3" not in chats


def test_unpair_removes_chat(client, auth_headers, telegram_env):
    _enable(telegram_env)
    code = tg.start_pairing("user-1")["code"]
    asyncio.run(tg.handle_update({"message": {"chat": {"id": 42}, "text": code}}))
    assert tg.unpair("42", "user-1") is True
    assert _pairings() == 0
