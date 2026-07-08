# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Tests for v0.5 scheduled background agents: due-time logic, validation,
pre-approved capability grants, headless runs, and the notification queue.
"""
from datetime import datetime

import pytest

import core.agent.runtime as rt
from core.agent import scheduler
from core.agent.scheduler import is_due, validate_schedule


class FakeLLM:
    def __init__(self, backend="ollama", user_id=None, model=None):
        pass

    async def chat(self, messages, system="", tools=None, max_tokens=4096):
        return {"content": [{"type": "text", "text": "Here is your briefing."}],
                "stop_reason": "end_turn", "usage": {}}


@pytest.fixture()
def fake_llm(monkeypatch):
    monkeypatch.setattr(rt, "LLMAdapter", FakeLLM)


def _sched(**kw) -> dict:
    base = dict(schedule_id="s1", user_id="u1", persona_id="", name="Brief",
                prompt="p", frequency="daily", at_time="07:00", weekday=None,
                notify_desktop=True, notify_telegram=False, is_enabled=True,
                last_run_at=None, created_at="2026-06-26T00:00:00+00:00",
                capabilities=[])
    base.update(kw)
    return base


# ─── is_due (pure clock logic) ─────────────────────────────────────────────────

def test_daily_not_due_before_time():
    assert not is_due(_sched(), datetime(2026, 6, 26, 6, 59))

def test_daily_due_at_time():
    assert is_due(_sched(), datetime(2026, 6, 26, 7, 0))

def test_daily_due_late_same_day():
    # App was closed at 07:00; opened at 09:30 → still runs today
    assert is_due(_sched(), datetime(2026, 6, 26, 9, 30))

def test_daily_not_due_twice_same_day():
    s = _sched(last_run_at="2026-06-26T07:00:05")  # naive = local in tests
    assert not is_due(s, datetime(2026, 6, 26, 7, 1))

def test_daily_due_again_next_day():
    s = _sched(last_run_at="2026-06-26T07:00:05")
    assert is_due(s, datetime(2026, 6, 27, 7, 0))

def test_weekdays_skips_weekend():
    s = _sched(frequency="weekdays")
    assert not is_due(s, datetime(2026, 6, 27, 8, 0))   # Saturday
    assert is_due(s, datetime(2026, 6, 29, 8, 0))       # Monday

def test_weekly_only_on_chosen_day():
    s = _sched(frequency="weekly", weekday=2)           # Wednesday
    assert not is_due(s, datetime(2026, 6, 26, 8, 0))   # Friday
    assert is_due(s, datetime(2026, 6, 24, 8, 0))       # Wednesday

def test_hourly_once_per_hour():
    s = _sched(frequency="hourly", at_time="00:15")
    assert not is_due(s, datetime(2026, 6, 26, 9, 10))
    assert is_due(s, datetime(2026, 6, 26, 9, 20))
    s2 = _sched(frequency="hourly", at_time="00:15",
                last_run_at="2026-06-26T09:15:30")
    assert not is_due(s2, datetime(2026, 6, 26, 9, 40))
    assert is_due(s2, datetime(2026, 6, 26, 10, 16))

def test_disabled_never_due():
    assert not is_due(_sched(is_enabled=False), datetime(2026, 6, 26, 8, 0))


# ─── Validation ────────────────────────────────────────────────────────────────

def test_validate_rejects_bad_frequency():
    with pytest.raises(ValueError):
        validate_schedule("fortnightly", "07:00", None, [])

def test_validate_rejects_bad_time():
    with pytest.raises(ValueError):
        validate_schedule("daily", "25:99", None, [])

def test_validate_weekly_needs_weekday():
    with pytest.raises(ValueError):
        validate_schedule("weekly", "07:00", None, [])

def test_validate_rejects_unknown_capability():
    with pytest.raises(ValueError):
        validate_schedule("daily", "07:00", None, ["root:everything"])


# ─── API + headless run ────────────────────────────────────────────────────────

def test_schedules_require_auth(client):
    assert client.get("/agent/schedules").status_code == 401

def test_create_schedule_stores_capabilities(client, auth_headers):
    r = client.post("/agent/schedules", json={
        "name": "Morning Briefing",
        "prompt": "Summarise my calendar and the news.",
        "frequency": "daily", "at_time": "07:00",
        "capabilities": ["net:fetch", "calendar:read"],
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert sorted(body["capabilities"]) == ["calendar:read", "net:fetch"]
    assert body["is_enabled"] is True

def test_cross_user_schedule_isolated(client, auth_headers):
    sid = client.post("/agent/schedules", json={
        "name": "Mine", "prompt": "p",
    }, headers=auth_headers).json()["schedule_id"]
    from core.auth.jwt import create_access_token
    other = {"Authorization": f"Bearer {create_access_token('intruder', 'owner')}"}
    assert client.delete(f"/agent/schedules/{sid}", headers=other).status_code == 404

def test_run_now_produces_session_and_notification(client, auth_headers, fake_llm):
    sid = client.post("/agent/schedules", json={
        "name": "Test Brief", "prompt": "Say hello.",
        "capabilities": ["net:fetch"],
    }, headers=auth_headers).json()["schedule_id"]

    r = client.post(f"/agent/schedules/{sid}/run-now", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert "briefing" in body["result"].lower()

    # Result is visible in a dedicated chat session
    sessions = client.get("/agent/sessions", headers=auth_headers).json()
    assert any(s["name"] == "⏰ Test Brief" for s in sessions)

    # Pre-approved capability was granted for the run
    from core.agent.permissions import get_permission_store, Capability
    assert get_permission_store().check("builtin", Capability.NET_FETCH)

    # Notification queued, delivered once, then gone
    n = client.get("/agent/notifications/pending", headers=auth_headers).json()
    assert any(x["title"] == "Test Brief" for x in n["notifications"])
    n2 = client.get("/agent/notifications/pending", headers=auth_headers).json()
    assert n2["notifications"] == []

def test_run_now_reuses_schedule_session(client, auth_headers, fake_llm):
    sid = client.post("/agent/schedules", json={
        "name": "Daily", "prompt": "Say hello.",
    }, headers=auth_headers).json()["schedule_id"]
    client.post(f"/agent/schedules/{sid}/run-now", headers=auth_headers)
    client.post(f"/agent/schedules/{sid}/run-now", headers=auth_headers)
    sessions = client.get("/agent/sessions", headers=auth_headers).json()
    assert len([s for s in sessions if s["name"] == "⏰ Daily"]) == 1

def test_toggle_and_delete_schedule(client, auth_headers):
    sid = client.post("/agent/schedules", json={
        "name": "Toggle", "prompt": "p",
    }, headers=auth_headers).json()["schedule_id"]
    r = client.put(f"/agent/schedules/{sid}", json={"is_enabled": False},
                   headers=auth_headers)
    assert r.json()["is_enabled"] is False
    client.delete(f"/agent/schedules/{sid}", headers=auth_headers)
    assert scheduler.get_schedule(sid) is None
