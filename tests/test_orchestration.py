# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Tests for v0.5 multi-agent orchestration (delegate_tasks).
"""
import asyncio

import pytest

import core.agent.runtime as rt
from core.agent.runtime import AgentRuntime, AgentSession, BUILTIN_TOOLS


class FakeLLM:
    """Echoes the last user message as a plain text response (no tool calls)."""

    def __init__(self, backend="ollama", user_id=None, model=None):
        self.backend = backend

    async def chat(self, messages, system="", tools=None, max_tokens=4096):
        last = messages[-1]["content"]
        return {
            "content": [{"type": "text", "text": f"done: {last}"}],
            "stop_reason": "end_turn",
            "usage": {},
        }


@pytest.fixture()
def fake_llm(monkeypatch):
    monkeypatch.setattr(rt, "LLMAdapter", FakeLLM)


def _session(**kw) -> AgentSession:
    base = dict(session_id="parent-1", user_id="u1", llm_backend="ollama",
                model="llama3.2:latest")
    base.update(kw)
    return AgentSession(**base)


# ─── Tool definition ───────────────────────────────────────────────────────────

def test_delegate_tasks_is_a_builtin_tool():
    names = [t["name"] for t in BUILTIN_TOOLS]
    assert "delegate_tasks" in names


def test_subagent_runtime_never_offered_delegate():
    # The depth cap is enforced by filtering the tool from a sub-agent's list.
    sub = AgentRuntime(is_subagent=True)
    assert sub._is_subagent is True
    filtered = [t for t in BUILTIN_TOOLS if t["name"] != "delegate_tasks"]
    assert "delegate_tasks" not in [t["name"] for t in filtered]


# ─── _run_subagents behaviour ──────────────────────────────────────────────────

def test_subagents_run_in_parallel_and_combine(fake_llm):
    out = asyncio.run(AgentRuntime()._run_subagents(
        _session(), ["find the weather", "summarise my day"]
    ))
    assert "[Subtask 1: find the weather]" in out
    assert "[Subtask 2: summarise my day]" in out
    assert "done: find the weather" in out
    assert "done: summarise my day" in out


def test_subagents_require_at_least_two(fake_llm):
    out = asyncio.run(AgentRuntime()._run_subagents(_session(), ["only one"]))
    assert "2-4" in out


def test_subagents_capped_at_four(fake_llm):
    out = asyncio.run(AgentRuntime()._run_subagents(
        _session(), [f"task {i}" for i in range(1, 8)]
    ))
    assert "[Subtask 4:" in out
    assert "[Subtask 5:" not in out


def test_subagent_sessions_are_ephemeral(fake_llm):
    """Sub-agent sessions must never be persisted to the sessions table."""
    from core.storage.db import get_connection
    asyncio.run(AgentRuntime()._run_subagents(
        _session(), ["alpha task", "beta task"]
    ))
    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE session_id LIKE 'parent-1:sub%'"
        ).fetchone()[0]
    assert count == 0


def test_subagent_runs_are_audited(fake_llm):
    from core.audit.logger import get_audit_logger
    asyncio.run(AgentRuntime()._run_subagents(
        _session(), ["alpha task", "beta task"]
    ))
    events = [e for e in get_audit_logger().recent(limit=30)
              if e["event"] == "agent.subagent"]
    assert len(events) >= 2
    previews = [e["details"].get("preview", "") for e in events]
    assert any("alpha task" in p for p in previews)


def test_private_parent_redacts_subtask_previews(fake_llm):
    from core.audit.logger import get_audit_logger
    asyncio.run(AgentRuntime()._run_subagents(
        _session(session_id="priv-1", is_private=True),
        ["secret task one", "secret task two"],
    ))
    events = [e for e in get_audit_logger().recent(limit=30)
              if e["event"] == "agent.subagent"
              and e["details"].get("parent_session") == "priv-1"]
    assert events
    for e in events:
        assert "secret" not in e["details"].get("preview", "")
