# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BXD-001 — the privacy dashboard must not be able to state a falsehood.

The cloud-*model* door was locked while the cloud-*transport* window was open:
`ollama_url` was an unvalidated settings field, `privacy.py` hardcoded
"127.0.0.1 — this computer", and `llm.py` wrote `data_leaves_device: False` as
a literal. Pointing Ollama at a remote host therefore produced a hash chain
that verified perfectly over a false statement.

These tests assert the three halves of the fix: the URL is validated, the
ledger derives its disclosure, and the audit event derives its claim.
"""
import asyncio

import pytest
from pydantic import ValidationError

from core.config import Settings, host_of, is_loopback_host


# ─── Host resolution ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "127.0.0.5"])
def test_loopback_hosts_recognised(host):
    assert is_loopback_host(host) is True


@pytest.mark.parametrize(
    "host",
    ["192.168.1.5", "10.0.0.1", "ollama.com", "", "0.0.0.0"],  # noqa: S104 — asserting this IS rejected
)
def test_non_loopback_hosts_rejected(host):
    assert is_loopback_host(host) is False


def test_host_of_strips_ipv6_brackets():
    assert host_of("http://[::1]:11434") == "::1"


# ─── C-1.1 — ollama_url must be loopback ───────────────────────────────────────

@pytest.mark.parametrize("url", [
    "http://localhost:11434",
    "http://127.0.0.1:11434",
    "http://[::1]:11434",
])
def test_loopback_ollama_url_accepted(url):
    assert Settings(ollama_url=url).ollama_is_local is True


@pytest.mark.parametrize("url", [
    "http://192.168.1.5:11434",   # a LAN box
    "http://10.0.0.1:11434",      # a cloud VM
    "https://ollama.com",         # Ollama's hosted endpoint
])
def test_non_loopback_ollama_url_fails_startup(url):
    """This is the finding: today any of these silently exfiltrated prompts."""
    with pytest.raises(ValidationError, match="loopback"):
        Settings(ollama_url=url)


def test_remote_ollama_url_without_acknowledgement_fails_startup():
    """Both settings are required. One alone must not start the server."""
    with pytest.raises(ValidationError, match="acknowledged"):
        Settings(remote_ollama_url="http://192.168.1.5:11434")


def test_remote_ollama_url_with_acknowledgement_is_allowed():
    s = Settings(remote_ollama_url="http://192.168.1.5:11434",
                 remote_ollama_acknowledged=True)
    assert s.effective_ollama_url == "http://192.168.1.5:11434"
    assert s.ollama_host == "192.168.1.5"
    assert s.ollama_is_local is False


def test_unacknowledged_remote_url_is_not_used():
    """A remote URL that never got acknowledged cannot leak in via the resolver."""
    s = Settings(ollama_url="http://127.0.0.1:11434")
    assert s.effective_ollama_url == "http://127.0.0.1:11434"
    assert s.ollama_is_local is True


def test_malformed_remote_url_rejected():
    with pytest.raises(ValidationError):
        Settings(remote_ollama_url="not-a-url", remote_ollama_acknowledged=True)


# ─── C-1.2 — the ledger reports the real host ──────────────────────────────────

@pytest.fixture()
def remote_ollama(monkeypatch):
    """Point the live settings singleton at an acknowledged remote host."""
    from core.config import settings
    monkeypatch.setattr(settings, "remote_ollama_url", "http://192.168.1.5:11434")
    monkeypatch.setattr(settings, "remote_ollama_acknowledged", True)
    return "192.168.1.5"


def test_local_ollama_is_reported_as_local():
    """The default configuration must still say local — this is the honest case."""
    from core.privacy import get_counters
    row = {c["kind"]: c for c in get_counters()}["ollama"]
    assert row["category"] == "local"
    assert "127.0.0.1" in row["where"]


def test_remote_ollama_is_reported_as_cloud_with_real_host(remote_ollama):
    """
    The dashboard must not claim 127.0.0.1 when prompts are going to a LAN box.
    Fails before the fix: the label was a hardcoded constant.
    """
    from core.privacy import get_counters
    row = {c["kind"]: c for c in get_counters()}["ollama"]
    assert row["category"] == "cloud"
    assert remote_ollama in row["where"]
    assert "127.0.0.1" not in row["where"]


def test_remote_ollama_counts_toward_cloud_total(remote_ollama):
    """A remote call must move the 'cloud' number the user is reading."""
    from core.privacy import record_net, get_report
    record_net("ollama")
    report = get_report()
    assert report["totals"]["cloud"] == 1
    assert report["totals"]["local"] == 0


# ─── C-1.3 — the audit event is derived, not literal ───────────────────────────

def _run_chat(monkeypatch):
    """Drive LLMAdapter.chat with Ollama stubbed out, returning audit entries."""
    import httpx
    import core.agent.llm as llm_mod
    from core.audit.logger import get_audit_logger

    # llm.py binds `audit` at import time, so conftest's singleton reset does
    # not reach it. Rebind or the entries land in whichever DB was first seen.
    logger = get_audit_logger()
    monkeypatch.setattr(llm_mod, "audit", logger)

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"message": {"content": "hi"}}

    async def _post(self, *a, **k): return _Resp()
    monkeypatch.setattr(httpx.AsyncClient, "post", _post)

    asyncio.run(llm_mod.LLMAdapter(backend="ollama").chat(
        [{"role": "user", "content": "x"}]
    ))
    return [e for e in logger.recent(20) if e["event"] == "agent.query"]


def test_local_inference_audits_data_stays_on_device(monkeypatch):
    entries = _run_chat(monkeypatch)
    assert entries, "no agent.query event was written"
    details = entries[0]["details"]
    assert details["local"] is True
    assert details["data_leaves_device"] is False


def test_remote_inference_audits_data_leaving_device(monkeypatch, remote_ollama):
    """
    The core of BXD-001. Before the fix these were the literals True/False and
    this event claimed the data stayed home while it was crossing the network.
    """
    entries = _run_chat(monkeypatch)
    assert entries, "no agent.query event was written"
    details = entries[0]["details"]
    assert details["local"] is False
    assert details["data_leaves_device"] is True
    assert details["ollama_host"] == remote_ollama


def test_audit_chain_still_verifies_after_remote_inference(monkeypatch, remote_ollama):
    """An honest record is still a tamper-evident one."""
    from core.audit.logger import get_audit_logger
    _run_chat(monkeypatch)
    assert get_audit_logger().verify_chain()[0] is True
