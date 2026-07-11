# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Tests for v0.6 Watchers: folder triggers (baseline semantics, new-file
detection, fire caps), validation, firing, and routes.
"""
import asyncio

import pytest

import core.agent.runtime as rt
from core.agent import watchers as w


class FakeLLM:
    def __init__(self, backend="ollama", user_id=None, model=None):
        pass

    async def chat(self, messages, system="", tools=None, max_tokens=4096):
        return {"content": [{"type": "text", "text": "Watcher handled it."}],
                "stop_reason": "end_turn", "usage": {}}


@pytest.fixture()
def fake_llm(monkeypatch):
    monkeypatch.setattr(rt, "LLMAdapter", FakeLLM)


@pytest.fixture()
def home_folder(tmp_path, monkeypatch):
    """A watchable folder that passes the inside-home security check."""
    from pathlib import Path
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    folder = tmp_path / "Downloads"
    folder.mkdir()
    return folder


# ─── Validation ────────────────────────────────────────────────────────────────

def test_validate_rejects_unknown_type():
    with pytest.raises(ValueError):
        w.validate_watcher("full_moon", {}, [])


def test_validate_rejects_folder_outside_home(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    (tmp_path / "home").mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    with pytest.raises(ValueError, match="home"):
        w.validate_watcher("folder_new_file", {"folder": str(outside)}, [])


def test_validate_meeting_requires_calendar_read(home_folder):
    with pytest.raises(ValueError, match="calendar:read"):
        w.validate_watcher("meeting_soon", {"lead_minutes": 15}, [])
    w.validate_watcher("meeting_soon", {"lead_minutes": 15}, ["calendar:read"])


# ─── Folder trigger semantics ──────────────────────────────────────────────────

def test_first_check_baselines_without_firing(home_folder):
    (home_folder / "existing.pdf").write_text("old")
    watcher = w.create_watcher("u1", name="Inbox", wtype="folder_new_file",
                               config={"folder": str(home_folder), "pattern": "*.pdf"},
                               prompt="Summarise {file}")
    assert w.check_folder_watcher(w.get_watcher(watcher["watcher_id"])) == []


def test_new_file_fires_once(home_folder):
    watcher = w.create_watcher("u1", name="Inbox", wtype="folder_new_file",
                               config={"folder": str(home_folder), "pattern": "*.pdf"},
                               prompt="Summarise {file}")
    w.check_folder_watcher(w.get_watcher(watcher["watcher_id"]))  # baseline

    (home_folder / "report.pdf").write_text("new")
    contexts = w.check_folder_watcher(w.get_watcher(watcher["watcher_id"]))
    assert len(contexts) == 1
    assert contexts[0]["file"].endswith("report.pdf")

    # Same file must not fire again
    assert w.check_folder_watcher(w.get_watcher(watcher["watcher_id"])) == []


def test_pattern_filters_and_fire_cap(home_folder):
    watcher = w.create_watcher("u1", name="Inbox", wtype="folder_new_file",
                               config={"folder": str(home_folder), "pattern": "*.pdf"},
                               prompt="Summarise {file}")
    w.check_folder_watcher(w.get_watcher(watcher["watcher_id"]))  # baseline

    (home_folder / "notes.txt").write_text("x")          # filtered out
    for i in range(5):
        (home_folder / f"doc{i}.pdf").write_text("x")
    contexts = w.check_folder_watcher(w.get_watcher(watcher["watcher_id"]))
    assert len(contexts) == w.MAX_FIRES_PER_TICK          # capped at 3
    assert all(c["file"].endswith(".pdf") for c in contexts)


# ─── Firing ────────────────────────────────────────────────────────────────────

def test_fire_substitutes_context_and_notifies(home_folder, fake_llm):
    watcher = w.create_watcher("u1", name="Inbox Watch", wtype="folder_new_file",
                               config={"folder": str(home_folder)},
                               prompt="Summarise {file} for me",
                               capabilities=["fs:read"])
    result = asyncio.run(w.fire_watcher(w.get_watcher(watcher["watcher_id"]),
                                        {"file": "C:/x/report.pdf"}))
    assert result["ok"] is True

    # Pre-approved capability granted for the run
    from core.agent.permissions import get_permission_store, Capability
    assert get_permission_store().check("builtin", Capability.FS_READ)

    # Visible session + notification
    from core.agent import session_store
    names = [m["name"] for m in session_store.list_sessions("u1")]
    assert "👀 Inbox Watch" in names
    from core.agent.scheduler import fetch_pending_notifications
    notes = fetch_pending_notifications("u1")
    assert any(n["title"] == "Inbox Watch" for n in notes)

    # Audited
    from core.audit.logger import get_audit_logger
    events = [e["event"] for e in get_audit_logger().recent(limit=10)]
    assert "watcher.fired" in events


# ─── Routes ────────────────────────────────────────────────────────────────────

def test_watchers_require_auth(client):
    assert client.get("/agent/watchers").status_code == 401


def test_create_list_toggle_delete_via_api(client, auth_headers, home_folder):
    r = client.post("/agent/watchers", json={
        "name": "Downloads watch", "type": "folder_new_file",
        "prompt": "Summarise {file}",
        "config": {"folder": str(home_folder), "pattern": "*"},
        "capabilities": ["fs:read"],
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    wid = r.json()["watcher_id"]
    assert r.json()["capabilities"] == ["fs:read"]

    listed = client.get("/agent/watchers", headers=auth_headers).json()
    assert wid in [x["watcher_id"] for x in listed]

    r = client.put(f"/agent/watchers/{wid}", json={"is_enabled": False},
                   headers=auth_headers)
    assert r.json()["is_enabled"] is False

    client.delete(f"/agent/watchers/{wid}", headers=auth_headers)
    assert w.get_watcher(wid) is None


def test_create_watcher_rejects_bad_folder_via_api(client, auth_headers):
    r = client.post("/agent/watchers", json={
        "name": "Bad", "type": "folder_new_file",
        "prompt": "x", "config": {"folder": "Z:/no/such/dir"},
    }, headers=auth_headers)
    assert r.status_code == 400


def test_cross_user_watcher_isolated(client, auth_headers, home_folder):
    wid = client.post("/agent/watchers", json={
        "name": "Mine", "type": "folder_new_file", "prompt": "x",
        "config": {"folder": str(home_folder)},
    }, headers=auth_headers).json()["watcher_id"]
    from core.auth.jwt import create_access_token
    other = {"Authorization": f"Bearer {create_access_token('intruder', 'owner')}"}
    assert client.delete(f"/agent/watchers/{wid}", headers=other).status_code == 404
