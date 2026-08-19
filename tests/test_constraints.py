# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Security Constraints

One dedicated module implementing every control in
docs/governance/02_SECURITY_CONTROLS.md, named with that document's C-x.y /
S-x IDs so the mapping from control to enforcement is mechanical, not a
cross-reference exercise, for an external reviewer handed this one file.

Principle (docs/governance/02_SECURITY_CONTROLS.md): a control is not
satisfied by correct code. It is satisfied by correct code plus a test that
fails when the code changes.

This file is deliberately self-contained rather than importing test
functions from the finding-scoped modules (test_route_auth.py,
test_ollama_transport.py, etc.) — those keep their detailed regression
coverage; this module is the flat, reviewable index over the same
guarantees, run by ci.yml, daily-security-audit.yml, and as a release gate
in release.yml (via scripts/verify_constraints.py).

Supply-chain controls (S-1..S-8) assert the CI wiring is structurally
correct — reading workflow YAML and config files as data, never issuing a
live network call — mirroring tests/test_workflow_audit.py and
tests/test_python_version_consistency.py. They must pass with no network
access, same as scripts/verify_constraints.py.
"""
import ast
import asyncio
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"

yaml = pytest.importorskip("yaml")


# ════════════════════════════════════════════════════════════════════════════
# C-1 — Local-first always
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("url", [
    "http://192.168.1.5:11434",   # a LAN box
    "http://10.0.0.1:11434",      # a cloud VM
    "https://ollama.com",         # Ollama's hosted endpoint
])
def test_C_1_1_non_loopback_ollama_url_fails_startup(url):
    """BXD-001: ollama_url must resolve to loopback or startup must fail."""
    from core.config import Settings
    with pytest.raises(ValidationError, match="loopback"):
        Settings(ollama_url=url)


@pytest.fixture()
def _remote_ollama_acknowledged(monkeypatch):
    from core.config import settings
    monkeypatch.setattr(settings, "remote_ollama_url", "http://192.168.1.5:11434")
    monkeypatch.setattr(settings, "remote_ollama_acknowledged", True)
    return "192.168.1.5"


def test_C_1_2_remote_ollama_is_reported_as_cloud_with_real_host(_remote_ollama_acknowledged):
    """BXD-001: an acknowledged remote host is disclosed as cloud, honestly."""
    from core.privacy import get_counters
    row = {c["kind"]: c for c in get_counters()}["ollama"]
    assert row["category"] == "cloud"
    assert _remote_ollama_acknowledged in row["where"]
    assert "127.0.0.1" not in row["where"]


def test_C_1_3_remote_inference_audits_data_leaving_device(monkeypatch, _remote_ollama_acknowledged):
    """BXD-001: the audit event's local/data_leaves_device fields are derived, never literal."""
    import httpx
    import core.agent.llm as llm_mod
    from core.audit.logger import get_audit_logger

    logger = get_audit_logger()
    monkeypatch.setattr(llm_mod, "audit", logger)

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"message": {"content": "hi"}}

    async def _post(self, *a, **k): return _Resp()
    monkeypatch.setattr(httpx.AsyncClient, "post", _post)

    asyncio.run(llm_mod.LLMAdapter(backend="ollama").chat([{"role": "user", "content": "x"}]))
    entries = [e for e in logger.recent(20) if e["event"] == "agent.query"]
    assert entries, "no agent.query event was written"
    details = entries[0]["details"]
    assert details["local"] is False
    assert details["data_leaves_device"] is True
    # BXD-009: the resolved host itself is on the record too, so the ledger
    # reflects reality even if a local model alias fools name-based classification.
    assert details["ollama_host"] == _remote_ollama_acknowledged


def test_C_1_4_cloud_models_rejected(monkeypatch):
    """Cloud models are blocked at session/model resolution, not just by name heuristic."""
    from core.agent.model_caps import classify_model, ModelMode
    assert classify_model(["cloud"]) == ModelMode.CLOUD
    assert classify_model([], "gpt-oss-120b-cloud") == ModelMode.CLOUD
    assert classify_model(["tools"], "minimax-m3:cloud") == ModelMode.CLOUD

    from core.agent.routes import _resolve_model_and_mode
    from core.audit.logger import get_audit_logger
    from fastapi import HTTPException

    logger_before = get_audit_logger().count()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_resolve_model_and_mode("claude", "claude-sonnet-4-6", "test-user"))
    assert exc.value.status_code == 400
    entries = get_audit_logger().recent(5)
    assert any(e["event"] == "model.cloud_blocked" for e in entries)
    assert get_audit_logger().count() > logger_before


def test_C_1_5_cloud_llm_off_by_default():
    """cloud_llm_enabled defaults False; constructing a cloud adapter without it raises."""
    from core.config import settings
    from core.agent.llm import LLMAdapter
    assert settings.cloud_llm_enabled is False
    with pytest.raises(RuntimeError):
        LLMAdapter(backend="cloud")


_RECORD_NET_CALL = re.compile(r"record_net\(\s*[\"']([^\"']+)[\"']\s*\)")


def _record_net_literals() -> set[str]:
    """Every string literal passed to record_net(...) anywhere in core/."""
    literals = set()
    for path in CORE.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        literals.update(_RECORD_NET_CALL.findall(text))
    return literals


def test_C_1_6_all_record_net_kinds_registered():
    """BXD-010: every record_net("x") literal call site is a registered NET_KINDS entry."""
    from core.privacy import NET_KINDS
    literals = _record_net_literals()
    assert literals, "source scan found no record_net(...) call sites — scan is broken"
    unregistered = literals - set(NET_KINDS)
    assert not unregistered, (
        f"record_net() called with unregistered kind(s): {sorted(unregistered)} — "
        "add them to core/privacy.py NET_KINDS"
    )


def test_C_1_7_unknown_egress_is_loud():
    """BXD-010: an unregistered kind surfaces as 'unknown' in category cloud, never 'research'."""
    from core.privacy import record_net, get_counters
    record_net("some_new_call_site_nobody_registered")
    by_kind = {c["kind"]: c for c in get_counters()}
    assert by_kind["unknown"]["count"] == 1
    assert by_kind["unknown"]["category"] == "cloud"
    assert by_kind["research"]["count"] == 0, "unknown egress was folded into a real, disclosed purpose"


# ════════════════════════════════════════════════════════════════════════════
# C-2 — Loopback binding only
# ════════════════════════════════════════════════════════════════════════════

def test_C_2_1_non_loopback_host_always_rejected():
    """BXD-007: host=0.0.0.0 fails even with debug=True — the check must not depend on debug."""
    from core.config import Settings
    with pytest.raises(ValidationError, match="does not depend on debug"):
        Settings(debug=True, host="0.0.0.0")  # noqa: S104 — asserting this IS rejected


def test_C_2_2_debug_not_env_settable_in_packaged_build(monkeypatch):
    """BXD-007: a packaged (frozen) build ignores DEBUG from the environment entirely."""
    import sys
    from core.config import Settings
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert Settings(debug=True).debug is False


def test_C_2_3_openapi_disabled():
    """/docs, /redoc, /openapi.json are off in the default (non-debug) configuration."""
    from core.main import app
    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None


# ════════════════════════════════════════════════════════════════════════════
# C-3 — Mandatory JWT auth
# ════════════════════════════════════════════════════════════════════════════

def test_C_3_1_every_route_is_authenticated_or_allowlisted():
    """BXD-002: every registered route carries an auth dependency or is deliberately public."""
    from fastapi.routing import APIRoute
    from core.auth.middleware import (
        PUBLIC_PREFIXES, PUBLIC_ROUTES, STATE_AUTHENTICATED, require_auth, require_owner,
    )
    from core.main import app

    guards = {require_auth, require_owner}

    def _has_auth_dependency(route: APIRoute) -> bool:
        seen, stack = set(), list(route.dependant.dependencies)
        while stack:
            dep = stack.pop()
            if id(dep) in seen:
                continue
            seen.add(id(dep))
            if dep.call in guards:
                return True
            stack.extend(dep.dependencies)
        return False

    unguarded = [
        f"{sorted(r.methods)} {r.path}"
        for r in app.routes
        if isinstance(r, APIRoute)
        and not _has_auth_dependency(r)
        and r.path not in PUBLIC_ROUTES
        and r.path not in STATE_AUTHENTICATED
        and not r.path.startswith(PUBLIC_PREFIXES)
    ]
    assert not unguarded, "Unauthenticated routes outside the allowlist:\n  " + "\n  ".join(unguarded)


def test_C_3_2_public_routes_is_exactly():
    """BXD-002: the allowlist is frozen at exactly 7 reviewed paths."""
    from core.auth.middleware import PUBLIC_ROUTES
    assert PUBLIC_ROUTES == {
        "/auth/login",
        "/auth/refresh",
        "/health",
        "/",
        "/auth/setup",
        "/auth/setup-status",
        "/auth/recover",
    }


def test_C_3_3_middleware_denies_route_without_dependency():
    """BXD-002: a route with no Depends(require_auth) is still refused by the middleware."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from core.auth.middleware import AuthGateMiddleware

    app = FastAPI()
    app.add_middleware(AuthGateMiddleware)

    @app.get("/__forgot_the_dependency__")
    async def oops():
        return {"secret": "leaked"}

    with TestClient(app) as c:
        r = c.get("/__forgot_the_dependency__")
    assert r.status_code == 401


def test_C_3_4_role_never_from_client_input(client, auth_headers):
    """Role is always derived from the JWT server-side — a spoofed header cannot elevate."""
    r = client.get("/auth/me", headers={**auth_headers, "X-Role": "owner", "senderIsOwner": "true"})
    assert r.status_code == 200
    # Role comes back correctly regardless — it was never read from the header at all.
    assert r.json()["role"] == "owner"


def test_C_3_5_setup_disabled_after_first_run(client):
    """A second POST /auth/setup returns 410 Gone — the endpoint self-disables."""
    r1 = client.post("/auth/setup", json={"username": "first", "password": "S3cur3P@ss!1"})
    assert r1.status_code == 201
    r2 = client.post("/auth/setup", json={"username": "second", "password": "S3cur3P@ss!1"})
    assert r2.status_code == 410


def test_C_3_6_revoked_token_rejected(client, owner_tokens):
    """A blocklisted access token is rejected immediately, not after its natural expiry."""
    access_token, refresh_token = owner_tokens
    headers = {"Authorization": f"Bearer {access_token}"}
    assert client.get("/auth/me", headers=headers).status_code == 200
    r = client.post("/auth/logout", json={"refresh_token": refresh_token}, headers=headers)
    assert r.status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401


# ════════════════════════════════════════════════════════════════════════════
# C-4 — Zero default permissions
# ════════════════════════════════════════════════════════════════════════════

def test_C_4_1_fresh_user_has_no_permissions():
    """The permission store starts empty — nothing is granted implicitly."""
    from core.agent.permissions import get_permission_store
    assert get_permission_store().list_grants() == []


def test_C_4_2_every_tool_requires_named_capability():
    """Every builtin tool the model can be offered maps to a named Capability."""
    from core.agent.runtime import BUILTIN_TOOLS, TOOL_CAPABILITY_MAP
    from core.agent.permissions import get_permission_store

    # delegate_tasks is an orchestration control tool, not a privileged action —
    # it is gated by the depth cap (sub-agents never receive it), not a
    # Capability grant. Every other builtin tool must be mapped.
    names = [t["name"] for t in BUILTIN_TOOLS if t["name"] != "delegate_tasks"]
    missing = [n for n in names if n not in TOOL_CAPABILITY_MAP]
    assert not missing, f"Builtin tools with no capability gate: {missing}"

    store = get_permission_store()
    for cap in set(TOOL_CAPABILITY_MAP.values()):
        assert store.check("builtin", cap) is False, f"{cap} was granted on a fresh store"


def test_C_4_3_no_capability_implies_another():
    """Granting one capability never yields another, related or not."""
    from core.agent.permissions import PermissionStore, Capability
    store = PermissionStore()
    store.grant("builtin", Capability.FS_READ, granted_by="owner")
    assert store.check("builtin", Capability.FS_READ) is True
    for cap in (
        Capability.FS_WRITE, Capability.FS_DELETE,
        Capability.NET_FETCH, Capability.NET_OUTBOUND,
        Capability.CALENDAR_READ, Capability.CALENDAR_WRITE,
        Capability.EXEC_SHELL, Capability.CRED_READ,
    ):
        assert store.check("builtin", cap) is False, f"granting fs:read implied {cap}"


def test_C_4_4_oauth_scopes_are_least_privilege():
    """
    BXD-012: Google's scope is the events-only grant, not full calendar
    management. Microsoft's scope was audited the same way and found to
    already be Graph's finest-grained events scope — nothing to narrow.

    Not calendar.events.readonly / Calendars.Read alone: both providers ship
    a real, capability-gated (calendar:write) create_event() feature
    (core/agent/runtime.py TOOL_CAPABILITY_MAP, POST /calendar/events) —
    a readonly scope would break shipped functionality. Least scope that
    still works, not least scope that breaks the product.
    """
    from core.skills.calendar.google_cal import SCOPES as GOOGLE_SCOPES
    from core.skills.calendar.outlook_cal import SCOPES as MS_SCOPES

    assert GOOGLE_SCOPES == "https://www.googleapis.com/auth/calendar.events"
    assert GOOGLE_SCOPES != "https://www.googleapis.com/auth/calendar", (
        "regressed to the full calendar-management scope"
    )

    ms_scopes = set(MS_SCOPES.split())
    assert ms_scopes == {"Calendars.Read", "Calendars.ReadWrite", "offline_access", "User.Read"}
    # No directory, mail, or admin-level Graph scope has crept in.
    forbidden_substrings = ("Mail.", "Directory.", "User.ReadWrite.All", "Application")
    assert not any(f in MS_SCOPES for f in forbidden_substrings)


def test_C_4_5_revocation_is_immediate(client, auth_headers):
    """After DELETE /agent/permissions/{cap}, the next check is denied — no caching."""
    from core.agent.permissions import get_permission_store, Capability
    store = get_permission_store()
    store.grant("builtin", Capability.FS_READ, granted_by="owner")
    assert store.check("builtin", Capability.FS_READ) is True

    r = client.delete("/agent/permissions/fs:read", headers=auth_headers)
    assert r.status_code == 200
    assert store.check("builtin", Capability.FS_READ) is False


# ════════════════════════════════════════════════════════════════════════════
# C-5 — Tamper-evident audit log
# ════════════════════════════════════════════════════════════════════════════

def test_C_5_1_chain_verified_on_startup():
    """
    A mutated audit row breaks chain verification — core/main.py's lifespan
    raises RuntimeError and refuses to start the server when this is False.
    """
    import sqlite3
    from core.audit.logger import get_audit_logger, AuditEvent

    logger = get_audit_logger()
    logger.log(AuditEvent.AGENT_QUERY, {"e": 1})
    logger.log(AuditEvent.AGENT_QUERY, {"e": 2})

    valid_before, _ = logger.verify_chain()
    assert valid_before is True

    # The append-only triggers block UPDATE at the application layer; simulate
    # an attacker with raw filesystem access to the SQLite file, which is
    # exactly the threat this control defends against.
    with sqlite3.connect(str(logger.db_path)) as conn:
        conn.execute("DROP TRIGGER IF EXISTS no_update")
        conn.execute("UPDATE audit_log SET details = ? WHERE id = 1", ('{"tampered": true}',))
        conn.commit()

    valid_after, broken_at = logger.verify_chain()
    assert valid_after is False
    assert broken_at is not None


def test_C_5_2_no_config_flag_disables_audit():
    """BXD-011: audit_log_enabled is gone — no settings field can suppress writes."""
    from core.config import Settings
    assert "audit_log_enabled" not in Settings.model_fields

    from core.audit.logger import get_audit_logger, AuditEvent
    logger = get_audit_logger()
    before = logger.count()
    logger.log(AuditEvent.AGENT_QUERY, {"e": "still writes"})
    assert logger.count() == before + 1


def test_C_5_3_every_route_writes_an_event(client, owner_tokens, monkeypatch):
    """
    State-changing authenticated routes each produce at least one audit
    entry. Scoped to mutating routes, not every GET — a read that writes
    nothing to change is not a gap in this control (audit records actions
    that change or reveal state, not idempotent reads of already-audited
    resources).
    """
    from core.audit.logger import get_audit_logger
    import core.auth.routes as auth_routes_mod
    access_token, refresh_token = owner_tokens
    headers = {"Authorization": f"Bearer {access_token}"}
    logger = get_audit_logger()

    # core/auth/routes.py binds `audit = get_audit_logger()` at MODULE import
    # time (unlike core/agent/routes.py, which resolves it per-call), so
    # conftest's per-test singleton reset never reaches it — same caveat
    # documented in tests/test_ollama_transport.py for core/agent/llm.py.
    # Rebind it to this test's logger rather than asserting against the
    # wrong instance's count.
    monkeypatch.setattr(auth_routes_mod, "audit", logger)

    def _count():
        return logger.count()

    before = _count()
    r = client.post("/agent/permissions/grant", json={"capability": "fs:read"}, headers=headers)
    assert r.status_code == 200
    assert _count() > before

    before = _count()
    r = client.delete("/agent/permissions/fs:read", headers=headers)
    assert r.status_code == 200
    assert _count() > before

    before = _count()
    r = client.post("/auth/logout", json={"refresh_token": refresh_token}, headers=headers)
    assert r.status_code == 204
    assert _count() > before


def test_C_5_4_privacy_report_reverifies_chain(client, auth_headers, monkeypatch):
    """GET /agent/privacy/report calls verify_chain() live — it is not a cached boolean."""
    from core.audit import logger as audit_mod

    calls = {"n": 0}
    real_verify = audit_mod.AuditLogger.verify_chain

    def _counting_verify(self):
        calls["n"] += 1
        return real_verify(self)

    monkeypatch.setattr(audit_mod.AuditLogger, "verify_chain", _counting_verify)

    r1 = client.get("/agent/privacy/report", headers=auth_headers)
    r2 = client.get("/agent/privacy/report", headers=auth_headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert calls["n"] == 2, "verify_chain() was not called on every request — looks cached"


# ════════════════════════════════════════════════════════════════════════════
# C-6 — shell=False always
# ════════════════════════════════════════════════════════════════════════════

def _core_py_files():
    return [p for p in CORE.rglob("*.py") if "__pycache__" not in p.parts]


def test_C_6_1_no_shell_true_in_core():
    """No shell=True, os.system, os.popen, or subprocess.getoutput anywhere in core/ CODE."""
    forbidden = re.compile(r"shell\s*=\s*True|os\.system\(|os\.popen\(|subprocess\.getoutput\(")
    hits = []
    for path in _core_py_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            code = line.split("#", 1)[0]  # a comment explaining "NEVER shell=True" is not a violation
            if forbidden.search(code):
                hits.append(f"{path.relative_to(ROOT)}:{lineno}")
    assert not hits, f"Forbidden subprocess pattern found in: {hits}"


def _is_string_like(node: ast.AST) -> bool:
    """True for a literal string, f-string, or string concatenation — never a real argv."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.JoinedStr):  # f-string
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _is_string_like(node.left) or _is_string_like(node.right)
    return False


def test_C_6_2_subprocess_calls_use_arg_lists():
    """
    Every subprocess.{run,call,check_call,check_output,Popen} call's first
    argument is never a raw string (literal, f-string, or concatenation) — a
    shell=True-shaped command line, which subprocess.run(..., shell=False)
    would otherwise treat as a single program name rather than an argv list.

    A Name/List/Tuple/Subscript is accepted: proving a variable's runtime
    type is a list is dataflow analysis this AST scan does not attempt (e.g.
    terminal/sandbox.py's `argv` is shlex.split(...) built two lines above
    the call) — the structural invariant this guards is "never a bare
    command string", which every real call site in core/ already avoids.
    """
    targets = {"run", "call", "check_call", "check_output", "Popen"}
    violations = []
    for path in _core_py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_subprocess_call = (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess"
                and func.attr in targets
            )
            if not is_subprocess_call or not node.args:
                continue
            first_arg = node.args[0]
            if _is_string_like(first_arg):
                violations.append(
                    f"{path.relative_to(ROOT)}:{node.lineno} subprocess.{func.attr}() "
                    f"first argument is a raw string, not an argv list"
                )
    assert not violations, "\n".join(violations)


# ════════════════════════════════════════════════════════════════════════════
# S — Supply chain (cross-cutting, structural / offline only)
# ════════════════════════════════════════════════════════════════════════════

def test_S_1_license_allowlist():
    """BXD-005: the pip licence gate script exists and its exceptions are documented."""
    import importlib
    import sys as _sys
    sys_path_added = str(ROOT / "scripts")
    if sys_path_added not in _sys.path:
        _sys.path.insert(0, sys_path_added)
    check_licenses = importlib.import_module("check_licenses")
    assert check_licenses.check_exceptions_are_documented() == []

    deny_toml = ROOT / "src-tauri" / "deny.toml"
    assert deny_toml.is_file()
    text = deny_toml.read_text(encoding="utf-8")
    assert "[licenses]" in text and "[advisories]" in text


def test_S_2_pip_audit_not_swallowed():
    """BXD-003/BXD-015: pip-audit's exit code is never swallowed by `|| true` in CI."""
    for wf in ("ci.yml", "daily-security-audit.yml"):
        text = (ROOT / ".github" / "workflows" / wf).read_text(encoding="utf-8")
        invocation = re.compile(r"(?:^|[\s;&|])pip-audit\s")
        for line in text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if invocation.search(line) and "--dry-run" not in line and "--fix" not in line:
                assert "|| true" not in line, f"{wf}: pip-audit failure swallowed: {line.strip()}"


def test_S_3_cargo_audit_gates_build():
    """BXD-006: cargo-deny (advisories + licenses) is a required CI job."""
    spec = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    assert "cargo-deny" in spec["jobs"]
    run_text = " ".join(s.get("run", "") for s in spec["jobs"]["cargo-deny"]["steps"])
    assert "cargo deny check advisories licenses" in run_text


def test_S_4_npm_audit_gates_build():
    """BXD-006: an npm audit gate exists (currently a documented no-op — no package.json yet)."""
    spec = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    assert "npm-audit" in spec["jobs"]


def test_S_5_pyinstaller_quarantine():
    """PyInstaller must never reach the production dependency manifest."""
    prod = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    dev = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8").lower()
    assert "pyinstaller" not in prod
    assert "pyinstaller" in dev


def test_S_6_single_python_version():
    """BXD-008: one declared Python version, referenced (never hardcoded) by every workflow."""
    version_file = ROOT / ".python-version"
    assert version_file.is_file()
    assert re.fullmatch(r"3\.\d+", version_file.read_text(encoding="utf-8").strip())

    for wf in ("ci.yml", "daily-security-audit.yml", "release.yml"):
        spec = yaml.safe_load((ROOT / ".github" / "workflows" / wf).read_text(encoding="utf-8"))
        found = False
        for job in spec.get("jobs", {}).values():
            for step in job.get("steps", []):
                if step.get("uses", "").startswith("actions/setup-python"):
                    found = True
                    with_block = step.get("with", {}) or {}
                    assert with_block.get("python-version-file") == ".python-version", (
                        f"{wf} step {step.get('name')!r} does not reference .python-version"
                    )
        assert found, f"{wf} has no actions/setup-python step"


def test_S_7_sbom_completeness():
    """BXD-006: CycloneDX SBOM generation covers both the Python and Rust trees."""
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "cyclonedx-py" in text or "cyclonedx-bom" in text
    assert "cargo-cyclonedx" in text or "cargo cyclonedx" in text


def test_S_8_boot_test():
    """The packaged backend must prove it boots and answers /health before upload."""
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "Smoke test backend bundle" in text
    assert "curl -sf http://127.0.0.1:8747/health" in text


# ════════════════════════════════════════════════════════════════════════════
# Meta — this module and its runner are actually wired into the pipeline.
#
# Not itself a numbered C-x.y/S-x control (scripts/verify_constraints.py's
# grouping regex intentionally does not match these names, so they don't
# skew the enforcement report's counts) — this just closes the loop the
# governance doc asks for: "wire it into ci.yml and as a release gate in
# release.yml."
# ════════════════════════════════════════════════════════════════════════════

def test_meta_verify_constraints_script_exists():
    assert (ROOT / "scripts" / "verify_constraints.py").is_file()


def test_meta_ci_runs_verify_constraints():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "scripts/verify_constraints.py" in text


def test_meta_release_gates_on_verify_constraints():
    spec = yaml.safe_load((ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"))
    jobs = spec["jobs"]
    assert "verify-constraints" in jobs
    verify_text = " ".join(s.get("run", "") for s in jobs["verify-constraints"]["steps"])
    assert "scripts/verify_constraints.py" in verify_text

    build_needs = jobs["build"].get("needs")
    build_needs = [build_needs] if isinstance(build_needs, str) else (build_needs or [])
    assert "verify-constraints" in build_needs, (
        "the build job does not depend on verify-constraints — a failing "
        "control would not block the release build"
    )
