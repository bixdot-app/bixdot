# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Tests for the v0.4 multi-session API and private-session enforcement.

Cloud-model resolution hits Ollama; every test patches httpx so creation
resolves to a local FULL_AGENT mode without a live Ollama instance.
"""
import json
import pytest

from core.storage.db import get_connection
import core.agent.session_store as ss


@pytest.fixture(autouse=True)
def _no_ollama(monkeypatch):
    """Make model resolution succeed offline as a local (non-cloud) model."""
    import httpx

    class _Resp:
        def raise_for_status(self): pass
        def json(self):
            return {"models": [
                {"name": "llama3.2:latest", "size": 2_000_000_000, "capabilities": ["tools"]},
            ]}

    async def _get(self, *a, **k):
        return _Resp()

    monkeypatch.setattr(httpx.AsyncClient, "get", _get)


def _db_session_count(session_id: str) -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()[0]


# ─── Auth ──────────────────────────────────────────────────────────────────────

def test_sessions_requires_auth(client):
    assert client.get("/agent/sessions").status_code == 401


def test_create_session_requires_auth(client):
    assert client.post("/agent/sessions", json={"name": "x"}).status_code == 401


# ─── Regular sessions persist ──────────────────────────────────────────────────

def test_create_regular_session_persisted(client, auth_headers):
    r = client.post("/agent/sessions", json={"name": "Work"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Work"
    assert body["is_private"] is False
    assert _db_session_count(body["session_id"]) == 1


def test_regular_session_messages_returned(client, auth_headers):
    r = client.post("/agent/sessions", json={"name": "Chat"}, headers=auth_headers)
    sid = r.json()["session_id"]

    # Persist a couple of messages via the store (no live LLM needed)
    sess = ss.load_session(sid)
    from core.agent.runtime import Message
    sess.messages = [Message(role="user", content="hello"),
                     Message(role="assistant", content="hi there")]
    ss.save_session(sess)

    r = client.get(f"/agent/sessions/{sid}/messages", headers=auth_headers)
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "agent"]
    assert msgs[1]["content"] == "hi there"


# ─── Private sessions: in-memory only ──────────────────────────────────────────

def test_create_private_session_not_in_db(client, auth_headers):
    r = client.post("/agent/sessions",
                    json={"name": "Secret", "is_private": True}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["is_private"] is True
    # Zero trace in the database
    assert _db_session_count(body["session_id"]) == 0
    # But visible in the live list (served from memory)
    listed = client.get("/agent/sessions", headers=auth_headers).json()
    assert body["session_id"] in [s["session_id"] for s in listed]


def test_private_session_messages_gone_after_restart(client, auth_headers):
    r = client.post("/agent/sessions",
                    json={"name": "Secret", "is_private": True}, headers=auth_headers)
    sid = r.json()["session_id"]

    sess = ss.load_session(sid)
    from core.agent.runtime import Message
    sess.messages = [Message(role="user", content="classified")]
    ss.save_session(sess)
    assert ss.get_messages(sid)  # present in memory now

    # Simulate an app restart — in-memory state is wiped
    ss._reset_for_tests()

    # No trace anywhere
    assert _db_session_count(sid) == 0
    assert client.get(f"/agent/sessions/{sid}/messages", headers=auth_headers).status_code == 404


def test_private_session_no_message_content_in_audit(client, auth_headers):
    r = client.post("/agent/sessions",
                    json={"name": "Secret", "is_private": True}, headers=auth_headers)
    sid = r.json()["session_id"]
    from core.audit.logger import get_audit_logger
    entries = get_audit_logger().recent(limit=20)
    started = [e for e in entries if e["event"] == "session.private_started"]
    assert started, "private_session_started must be audited"
    # The audit entry must carry no session name and no message content
    details = started[0]["details"]
    assert details["session_id"] == sid
    assert "Secret" not in json.dumps(details)


def test_delete_private_session_hard_delete(client, auth_headers):
    r = client.post("/agent/sessions",
                    json={"name": "Secret", "is_private": True}, headers=auth_headers)
    sid = r.json()["session_id"]
    r = client.delete(f"/agent/sessions/{sid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"
    # Gone from the list, no DB trace
    listed = client.get("/agent/sessions", headers=auth_headers).json()
    assert sid not in [s["session_id"] for s in listed]
    assert _db_session_count(sid) == 0


# ─── Archive + rename ──────────────────────────────────────────────────────────

def test_archive_regular_session(client, auth_headers):
    sid = client.post("/agent/sessions", json={"name": "Old"},
                      headers=auth_headers).json()["session_id"]
    # Delete on a regular session = archive (recoverable)
    r = client.delete(f"/agent/sessions/{sid}", headers=auth_headers)
    assert r.json()["status"] == "archived"

    active = client.get("/agent/sessions", headers=auth_headers).json()
    assert sid not in [s["session_id"] for s in active]

    archived = client.get("/agent/sessions?include_archived=true",
                          headers=auth_headers).json()
    assert sid in [s["session_id"] for s in archived]


def test_rename_session_audits_old_and_new(client, auth_headers):
    sid = client.post("/agent/sessions", json={"name": "First"},
                      headers=auth_headers).json()["session_id"]
    r = client.put(f"/agent/sessions/{sid}", json={"name": "Second"},
                   headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Second"

    from core.audit.logger import get_audit_logger
    renamed = [e for e in get_audit_logger().recent(limit=20)
               if e["event"] == "session.renamed"]
    assert renamed
    assert renamed[0]["details"]["old_name"] == "First"
    assert renamed[0]["details"]["new_name"] == "Second"


# ─── Cross-user isolation ──────────────────────────────────────────────────────

def test_user_cannot_access_other_users_session(client, auth_headers):
    sid = client.post("/agent/sessions", json={"name": "Mine"},
                      headers=auth_headers).json()["session_id"]

    from core.auth.jwt import create_access_token
    other = create_access_token("attacker-user-id", "owner")
    other_headers = {"Authorization": f"Bearer {other}"}

    assert client.get(f"/agent/sessions/{sid}", headers=other_headers).status_code in (403, 404)
    assert client.delete(f"/agent/sessions/{sid}", headers=other_headers).status_code in (403, 404)
    assert client.put(f"/agent/sessions/{sid}", json={"name": "hax"},
                      headers=other_headers).status_code in (403, 404)


# ─── Cloud block at creation ───────────────────────────────────────────────────

def test_cloud_backend_blocked_at_creation(client, auth_headers):
    r = client.post("/agent/sessions",
                    json={"name": "Cloud", "llm_backend": "claude"}, headers=auth_headers)
    assert r.status_code == 400
    assert "local-first" in r.json()["detail"].lower()
