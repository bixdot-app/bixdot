# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Tests for the v0.6.1 signature-verified Ollama installer bootstrap.

All network and subprocess activity is mocked — no test downloads anything
or launches any process.
"""
import asyncio
import json
import zipfile
from types import SimpleNamespace

import httpx
import pytest

from core.services import ollama_installer as inst


# ── Shared fakes ───────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def tmp_download_dir(tmp_path, monkeypatch):
    """Never touch the real ~/.bixdot/downloads."""
    d = tmp_path / "downloads"
    monkeypatch.setattr(inst, "DOWNLOAD_DIR", d)
    return d


class _FakeResp:
    def __init__(self, chunks, headers=None):
        self._chunks = chunks
        self.headers = headers or {}

    def raise_for_status(self):
        pass

    async def aiter_bytes(self):
        for c in self._chunks:
            yield c


class _FakeStreamCtx:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *a):
        return False


def _fake_httpx_client(chunks, headers=None, seen_kwargs=None):
    """Replacement for httpx.AsyncClient that streams the given chunks."""
    class FakeClient:
        def __init__(self, **kwargs):
            if seen_kwargs is not None:
                seen_kwargs.append(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def stream(self, method, url):
            return _FakeStreamCtx(_FakeResp(chunks, headers))

    return FakeClient


def _probe_ollama_up(monkeypatch):
    async def _get(self, *a, **k):
        return SimpleNamespace(status_code=200)
    monkeypatch.setattr(httpx.AsyncClient, "get", _get)


def _probe_ollama_down(monkeypatch):
    async def _get(self, *a, **k):
        raise httpx.ConnectError("no ollama")
    monkeypatch.setattr(httpx.AsyncClient, "get", _get)


def _ndjson(resp_text):
    return [json.loads(ln) for ln in resp_text.splitlines() if ln.strip()]


# ── Route guards ───────────────────────────────────────────────────────────────

def test_route_requires_jwt(client):
    assert client.post("/agent/onboarding/download-ollama").status_code == 401


def test_route_400_when_ollama_already_running(client, auth_headers, monkeypatch):
    monkeypatch.setattr(inst, "platform_key", lambda: "windows")
    _probe_ollama_up(monkeypatch)
    r = client.post("/agent/onboarding/download-ollama", headers=auth_headers)
    assert r.status_code == 400
    assert "already running" in r.json()["detail"]


def test_route_400_on_unsupported_platform(client, auth_headers, monkeypatch):
    monkeypatch.setattr(inst, "platform_key", lambda: None)  # Linux
    r = client.post("/agent/onboarding/download-ollama", headers=auth_headers)
    assert r.status_code == 400
    assert "not available on this platform" in r.json()["detail"]


# ── Download hardening ─────────────────────────────────────────────────────────

def test_redirect_guard_blocks_untrusted_hosts(monkeypatch):
    """Redirect hops must stay on the official host allowlist — and the guard
    must be registered as a request hook on the download client."""
    assert inst._host_allowed("ollama.com")
    assert inst._host_allowed("cdn.ollama.com")
    assert inst._host_allowed("objects.githubusercontent.com")
    assert not inst._host_allowed("evilollama.com")          # no dot boundary
    assert not inst._host_allowed("ollama.com.evil.io")      # suffix spoof
    assert not inst._host_allowed("")

    bad_req = SimpleNamespace(url=SimpleNamespace(host="evil.example.com"))
    with pytest.raises(inst.InstallerError):
        asyncio.run(inst._check_request_host(bad_req))

    seen = []
    monkeypatch.setattr(inst, "platform_key", lambda: "windows")
    monkeypatch.setattr(httpx, "AsyncClient", _fake_httpx_client([b"x"], seen_kwargs=seen))
    asyncio.run(inst.download(lambda p: None))
    assert inst._check_request_host in seen[0]["event_hooks"]["request"]
    assert seen[0]["follow_redirects"] is True


def test_oversize_download_aborts_and_cleans_part(tmp_download_dir, monkeypatch):
    monkeypatch.setattr(inst, "platform_key", lambda: "windows")
    monkeypatch.setattr(inst, "MAX_BYTES", 10)
    # No content-length header — the streamed-byte counter must trip the cap.
    monkeypatch.setattr(httpx, "AsyncClient", _fake_httpx_client([b"a" * 8, b"b" * 8]))
    with pytest.raises(inst.InstallerError, match="safety size cap"):
        asyncio.run(inst.download(lambda p: None))
    assert list(tmp_download_dir.glob("*")) == []  # .part removed, nothing kept

    # Declared content-length beyond the cap aborts before writing anything.
    monkeypatch.setattr(httpx, "AsyncClient",
                        _fake_httpx_client([b"a"], headers={"content-length": "999999"}))
    with pytest.raises(inst.InstallerError, match="safety size cap"):
        asyncio.run(inst.download(lambda p: None))
    assert list(tmp_download_dir.glob("*")) == []


def test_record_net_setup_exactly_once_per_download(monkeypatch):
    from core.privacy import get_counters
    by_kind = {c["kind"]: c for c in get_counters()}
    assert by_kind["setup"]["count"] == 0  # full disclosure: visible at zero

    monkeypatch.setattr(inst, "platform_key", lambda: "windows")
    monkeypatch.setattr(httpx, "AsyncClient", _fake_httpx_client([b"data"]))
    asyncio.run(inst.download(lambda p: None))

    by_kind = {c["kind"]: c for c in get_counters()}
    assert by_kind["setup"]["count"] == 1
    assert by_kind["setup"]["category"] == "optin"


# ── Signature verification ─────────────────────────────────────────────────────

def test_windows_bad_signature_deletes_file_audits_and_streams_error(
    client, auth_headers, tmp_download_dir, monkeypatch
):
    monkeypatch.setattr(inst, "platform_key", lambda: "windows")
    _probe_ollama_down(monkeypatch)

    async def fake_download(cb):
        tmp_download_dir.mkdir(parents=True, exist_ok=True)
        f = tmp_download_dir / "OllamaSetup.exe"
        f.write_bytes(b"MZ not really signed")
        cb({"completed": 20, "total": 20})
        return f
    monkeypatch.setattr(inst, "download", fake_download)
    monkeypatch.setattr(
        inst.subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="NotSigned", stderr=""),
    )

    r = client.post("/agent/onboarding/download-ollama", headers=auth_headers)
    lines = _ndjson(r.text)
    assert any("error" in ln and "Signature verification failed" in ln["error"] for ln in lines)
    assert not (tmp_download_dir / "OllamaSetup.exe").exists()  # deleted on failure

    from core.audit.logger import get_audit_logger
    events = [e["details"].get("event") for e in get_audit_logger().recent(50)]
    assert "ollama_installer_rejected" in events
    assert "ollama_installer_launched" not in events


def test_macos_zip_with_path_traversal_rejected(tmp_download_dir, monkeypatch):
    monkeypatch.setattr(inst, "platform_key", lambda: "darwin")
    tmp_download_dir.mkdir(parents=True, exist_ok=True)
    zip_path = tmp_download_dir / "Ollama-darwin.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Ollama.app/Contents/Info.plist", "<plist/>")
        zf.writestr("../evil.txt", "escape attempt")

    ok, reason = inst.verify_signature(zip_path)
    assert ok is False
    assert "unsafe path" in reason
    assert not zip_path.exists()  # zip deleted, nothing extracted survives
    assert not inst._extract_dir().exists()


def test_happy_path_streams_and_audits_in_order(
    client, auth_headers, tmp_download_dir, monkeypatch
):
    monkeypatch.setattr(inst, "platform_key", lambda: "windows")
    _probe_ollama_down(monkeypatch)

    async def fake_download(cb):
        tmp_download_dir.mkdir(parents=True, exist_ok=True)
        f = tmp_download_dir / "OllamaSetup.exe"
        f.write_bytes(b"MZ officially signed")
        cb({"completed": 10, "total": 20})
        cb({"completed": 20, "total": 20})
        return f
    monkeypatch.setattr(inst, "download", fake_download)
    monkeypatch.setattr(
        inst.subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="Valid", stderr=""),
    )
    launched = []
    monkeypatch.setattr(inst, "launch", lambda p: launched.append(p))

    r = client.post("/agent/onboarding/download-ollama", headers=auth_headers)
    lines = _ndjson(r.text)
    assert any(ln.get("completed") is not None for ln in lines)      # progress
    statuses = [ln["status"] for ln in lines if "status" in ln]
    assert statuses == ["verifying", "launched"]
    assert not any("error" in ln for ln in lines)
    assert len(launched) == 1

    from core.audit.logger import get_audit_logger
    events = [e["details"].get("event") for e in get_audit_logger().recent(50)]
    flow = [e for e in reversed(events) if e and e.startswith("ollama_installer_")]
    assert flow == [
        "ollama_installer_download_started",
        "ollama_installer_verified",
        "ollama_installer_launched",
    ]
    verified = next(
        e["details"] for e in get_audit_logger().recent(50)
        if e["details"].get("event") == "ollama_installer_verified"
    )
    assert len(verified["sha256"]) == 64
    assert verified["signer_status"] == "Valid"


def test_all_subprocess_calls_are_arg_lists_with_shell_false(tmp_download_dir, monkeypatch):
    """Checklist §9: every subprocess call uses an argument list, shell=False,
    and never passes silent-install flags."""
    calls = []

    def fake_run(argv, **kw):
        calls.append((argv, kw))
        return SimpleNamespace(returncode=0, stdout="Valid", stderr="")

    def fake_popen(argv, **kw):
        calls.append((argv, kw))
        return SimpleNamespace(pid=12345)

    monkeypatch.setattr(inst.subprocess, "run", fake_run)
    monkeypatch.setattr(inst.subprocess, "Popen", fake_popen)
    tmp_download_dir.mkdir(parents=True, exist_ok=True)

    # Windows: Authenticode check + installer launch
    monkeypatch.setattr(inst, "platform_key", lambda: "windows")
    exe = tmp_download_dir / "OllamaSetup.exe"
    exe.write_bytes(b"MZ")
    ok, _ = inst.verify_signature(exe)
    assert ok
    inst.launch(exe)

    # macOS: codesign + spctl + open
    monkeypatch.setattr(inst, "platform_key", lambda: "darwin")
    zip_path = tmp_download_dir / "Ollama-darwin.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Ollama.app/Contents/Info.plist", "<plist/>")
    ok, _ = inst.verify_signature(zip_path)
    assert ok
    inst.launch(zip_path)

    assert len(calls) >= 5  # powershell, exe launch, codesign, spctl, open
    for argv, kw in calls:
        assert isinstance(argv, list), f"subprocess argv must be a list: {argv!r}"
        assert kw.get("shell") is False, f"shell must be explicitly False: {argv!r}"
        joined = " ".join(str(a) for a in argv).lower()
        assert "/s" not in argv and "--silent" not in joined and "/verysilent" not in joined
