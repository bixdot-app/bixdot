# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Tests for the v0.6 Privacy Proof network ledger and report.
"""
from core.privacy import record_net, get_counters, get_report, NET_KINDS


# ─── Ledger ────────────────────────────────────────────────────────────────────

def test_all_kinds_visible_at_zero():
    """Full disclosure: every known purpose appears even with zero calls."""
    counters = get_counters()
    assert {c["kind"] for c in counters} == set(NET_KINDS.keys())
    assert all(c["count"] == 0 for c in counters)


def test_record_increments_and_timestamps():
    record_net("ollama")
    record_net("ollama")
    record_net("telegram")
    by_kind = {c["kind"]: c for c in get_counters()}
    assert by_kind["ollama"]["count"] == 2
    assert by_kind["ollama"]["last_at"] is not None
    assert by_kind["telegram"]["count"] == 1
    assert by_kind["websearch"]["count"] == 0


def test_unknown_kind_never_raises_and_is_visible():
    record_net("mystery_exfil")  # must not raise; surfaces in a visible bucket
    total = sum(c["count"] for c in get_counters())
    assert total == 1


def test_categories_are_correct():
    by_kind = {c["kind"]: c for c in get_counters()}
    assert by_kind["ollama"]["category"] == "local"
    assert by_kind["cloud_llm"]["category"] == "cloud"
    for k in ("telegram", "websearch", "research", "github", "calendar"):
        assert by_kind[k]["category"] == "optin"


# ─── Report ────────────────────────────────────────────────────────────────────

def test_report_shape_and_totals():
    record_net("ollama")
    record_net("websearch")
    report = get_report()
    assert report["totals"]["local"] == 1
    assert report["totals"]["optin"] == 1
    assert report["totals"]["cloud"] == 0
    assert report["config"]["bind_host"] == "127.0.0.1"
    assert report["config"]["cloud_llm_enabled"] is False
    assert report["audit"]["chain_valid"] is True
    assert isinstance(report["audit"]["entries"], int)


def test_report_detects_broken_chain(monkeypatch):
    """The dashboard must not show a green seal on a tampered log."""
    from core.audit.logger import get_audit_logger, AuditEvent
    logger = get_audit_logger()
    logger.log(AuditEvent.AGENT_QUERY, {"e": 1})
    monkeypatch.setattr(type(logger), "verify_chain", lambda self: (False, 1))
    report = get_report()
    assert report["audit"]["chain_valid"] is False
    assert report["audit"]["broken_at"] == 1


# ─── Route ─────────────────────────────────────────────────────────────────────

def test_report_requires_auth(client):
    assert client.get("/agent/privacy/report").status_code == 401


def test_report_via_api(client, auth_headers):
    r = client.get("/agent/privacy/report", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["config"]["bind_host"] == "127.0.0.1"
    assert "counters" in body and "totals" in body


# ─── Instrumentation seams ─────────────────────────────────────────────────────

def test_ollama_chat_records(monkeypatch):
    """The LLM adapter records a local call before talking to Ollama."""
    import asyncio
    import httpx
    from core.agent.llm import LLMAdapter

    class _Resp:
        def raise_for_status(self): pass
        def json(self):
            return {"message": {"content": "hi"}}

    async def _post(self, *a, **k):
        return _Resp()
    monkeypatch.setattr(httpx.AsyncClient, "post", _post)

    asyncio.run(LLMAdapter(backend="ollama").chat([{"role": "user", "content": "x"}]))
    by_kind = {c["kind"]: c for c in get_counters()}
    assert by_kind["ollama"]["count"] == 1
