# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Tests for v0.5 personas: built-in seeding, CRUD, session binding, and how a
persona shapes the runtime (system prompt + offered-tool filtering).
"""
import pytest

import core.agent.session_store as ss
from core.agent.personas import seed_builtin_personas, get_persona, BUILTIN_PERSONAS


@pytest.fixture(autouse=True)
def _no_ollama(monkeypatch):
    """Make model resolution succeed offline as a local FULL_AGENT model."""
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


# ─── Seeding + auth ────────────────────────────────────────────────────────────

def test_personas_requires_auth(client):
    assert client.get("/agent/personas").status_code == 401


def test_builtin_personas_seeded(client, auth_headers):
    listed = client.get("/agent/personas", headers=auth_headers).json()
    ids = [p["persona_id"] for p in listed]
    for builtin in BUILTIN_PERSONAS:
        assert builtin["persona_id"] in ids
    # All flagged as built-in
    assert all(p["is_builtin"] for p in listed if p["persona_id"] in
               [b["persona_id"] for b in BUILTIN_PERSONAS])


def test_seeding_is_idempotent_and_preserves_edits(client, auth_headers):
    # Edit a built-in, reseed, edit must survive
    r = client.put("/agent/personas/writer", json={"name": "Ghostwriter"},
                   headers=auth_headers)
    assert r.status_code == 200
    seed_builtin_personas()
    assert get_persona("writer")["name"] == "Ghostwriter"


# ─── CRUD ──────────────────────────────────────────────────────────────────────

def test_create_and_delete_custom_persona(client, auth_headers):
    r = client.post("/agent/personas", json={
        "name": "Chef", "icon": "🍳",
        "description": "Meal ideas",
        "system_prompt": "You suggest simple recipes.",
        "allowed_tools": ["web_search"],
    }, headers=auth_headers)
    assert r.status_code == 200
    pid = r.json()["persona_id"]
    assert r.json()["is_builtin"] is False

    r = client.delete(f"/agent/personas/{pid}", headers=auth_headers)
    assert r.status_code == 200
    assert get_persona(pid) is None


def test_builtin_persona_cannot_be_deleted(client, auth_headers):
    r = client.delete("/agent/personas/bixdot", headers=auth_headers)
    assert r.status_code == 400
    assert get_persona("bixdot") is not None


def test_create_persona_requires_name(client, auth_headers):
    assert client.post("/agent/personas", json={"name": "  "},
                       headers=auth_headers).status_code == 400


# ─── Session binding ───────────────────────────────────────────────────────────

def test_session_binds_persona(client, auth_headers):
    r = client.post("/agent/sessions",
                    json={"name": "Plan", "persona_id": "day-planner"},
                    headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["persona_id"] == "day-planner"
    sid = body["session_id"]
    # Runtime-facing session carries the persona
    assert ss.load_session(sid).persona_id == "day-planner"


def test_session_with_unknown_persona_404(client, auth_headers):
    r = client.post("/agent/sessions",
                    json={"name": "X", "persona_id": "no-such-persona"},
                    headers=auth_headers)
    assert r.status_code == 404


def test_persona_default_model_applies(client, auth_headers):
    client.put("/agent/personas/researcher", json={"model": "llama3.2:latest"},
               headers=auth_headers)
    r = client.post("/agent/sessions",
                    json={"name": "R", "persona_id": "researcher"},
                    headers=auth_headers)
    assert r.json()["model"] == "llama3.2:latest"


# ─── Runtime shaping ───────────────────────────────────────────────────────────

def test_system_prompt_includes_persona(client, auth_headers):
    from core.agent.runtime import get_system_prompt
    persona = get_persona("researcher")
    prompt = get_system_prompt(persona)
    assert "Researcher" in prompt
    assert "cite" in prompt.lower()
    # Base security prompt is still present
    assert "No data leaves this machine" in prompt


def test_persona_tool_filter_restricts_offered_tools(client, auth_headers):
    from core.agent.runtime import BUILTIN_TOOLS
    persona = get_persona("day-planner")
    allowed = set(persona["allowed_tools"])
    filtered = [t for t in BUILTIN_TOOLS if t["name"] in allowed]
    names = {t["name"] for t in filtered}
    assert "get_events" in names
    assert "run_command" not in names      # terminal never offered to Day Planner
    assert "web_search" not in names
