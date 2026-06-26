# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Tests for the v0.4 skill plugin API: manifest validation, SHA-256 integrity,
capability gating, the execution sandbox, and the routes.
"""
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from core.skills import plugin_manager as pm
from core.skills import registry
from core.skills.sandbox import run_skill
from core.storage.db import get_connection


# ─── Helpers ───────────────────────────────────────────────────────────────────

_VALID_ENTRY = (
    "import sys, json\n"
    "payload = json.loads(sys.stdin.read() or '{}')\n"
    "print(json.dumps({'success': True, 'output': payload.get('input', {})}))\n"
)


def _make_skill_zip(tmp_path: Path, *, skill_id="com.example.demo",
                    capabilities=None, license="MIT", entry_code=_VALID_ENTRY,
                    sha_override=None, name="Demo Skill") -> Path:
    capabilities = capabilities if capabilities is not None else ["web.search"]
    src = tmp_path / f"src_{skill_id}"
    src.mkdir(parents=True, exist_ok=True)
    entry_name = "skill.py"
    (src / entry_name).write_text(entry_code, encoding="utf-8")
    sha = sha_override or hashlib.sha256((src / entry_name).read_bytes()).hexdigest()
    manifest = {
        "id": skill_id,
        "name": name,
        "version": "1.0.0",
        "description": "A demo skill.",
        "author": "Tester",
        "license": license,
        "entry": entry_name,
        "capabilities": capabilities,
        "trigger": "Use this skill to echo input.",
        "sha256": sha,
    }
    (src / "bixdot-skill.json").write_text(json.dumps(manifest), encoding="utf-8")
    zip_path = tmp_path / f"{skill_id}.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.write(src / "bixdot-skill.json", "bixdot-skill.json")
        z.write(src / entry_name, entry_name)
    return zip_path


def _installed_count(skill_id: str) -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM installed_skills WHERE skill_id = ?", (skill_id,)
        ).fetchone()[0]


# ─── Install validation ────────────────────────────────────────────────────────

def test_install_valid_skill(tmp_path):
    zip_path = _make_skill_zip(tmp_path)
    manifest = pm.install_skill(zip_path, approved_by="user-1")
    assert manifest["id"] == "com.example.demo"
    assert _installed_count("com.example.demo") == 1
    # Capability grants recorded
    assert "web.search" in registry.get_skill_grants("com.example.demo")


def test_install_forbidden_capability_rejected(tmp_path):
    zip_path = _make_skill_zip(tmp_path, skill_id="com.example.bad",
                               capabilities=["shell.execute"])
    with pytest.raises(ValueError):
        pm.install_skill(zip_path, approved_by="user-1")
    assert _installed_count("com.example.bad") == 0


def test_install_unknown_capability_rejected(tmp_path):
    zip_path = _make_skill_zip(tmp_path, skill_id="com.example.unknown",
                               capabilities=["filesystem.delete"])
    with pytest.raises(ValueError):
        pm.install_skill(zip_path, approved_by="user-1")
    assert _installed_count("com.example.unknown") == 0


def test_install_agpl_license_rejected(tmp_path):
    zip_path = _make_skill_zip(tmp_path, skill_id="com.example.agpl", license="AGPL-3.0")
    with pytest.raises(ValueError):
        pm.install_skill(zip_path, approved_by="user-1")
    assert _installed_count("com.example.agpl") == 0


def test_install_sha_mismatch_rejected(tmp_path):
    zip_path = _make_skill_zip(tmp_path, skill_id="com.example.tamper",
                               sha_override="deadbeef" * 8)
    with pytest.raises(ValueError):
        pm.install_skill(zip_path, approved_by="user-1")
    assert _installed_count("com.example.tamper") == 0


# ─── Integrity verification ────────────────────────────────────────────────────

def test_tampered_file_detected_and_disabled(tmp_path):
    zip_path = _make_skill_zip(tmp_path, skill_id="com.example.live")
    pm.install_skill(zip_path, approved_by="user-1")

    # Tamper with the installed entry file
    skill = registry.get_skill("com.example.live")
    Path(skill["entry_file"]).write_text("print('evil')\n", encoding="utf-8")

    assert pm.verify_skill_integrity("com.example.live") is False
    assert registry.get_skill("com.example.live")["is_enabled"] is False

    from core.audit.logger import get_audit_logger
    events = [e["event"] for e in get_audit_logger().recent(limit=20)]
    assert "skill.verify_failed" in events


def test_load_enabled_skills_excludes_tampered(tmp_path):
    pm.install_skill(_make_skill_zip(tmp_path, skill_id="com.example.ok"),
                     approved_by="user-1")
    pm.install_skill(_make_skill_zip(tmp_path, skill_id="com.example.bad2"),
                     approved_by="user-1")
    Path(registry.get_skill("com.example.bad2")["entry_file"]).write_text("x=1\n")

    enabled = pm.load_enabled_skills()
    ids = [s["skill_id"] for s in enabled]
    assert "com.example.ok" in ids
    assert "com.example.bad2" not in ids


# ─── Uninstall ─────────────────────────────────────────────────────────────────

def test_uninstall_removes_db_and_files(tmp_path):
    pm.install_skill(_make_skill_zip(tmp_path, skill_id="com.example.gone"),
                     approved_by="user-1")
    install_dir = pm.plugins_dir() / "com.example.gone"
    assert install_dir.exists()

    pm.uninstall_skill("com.example.gone", "user-1")
    assert _installed_count("com.example.gone") == 0
    assert not install_dir.exists()


# ─── Sandbox ───────────────────────────────────────────────────────────────────

def test_run_skill_basic_roundtrip(tmp_path):
    entry = tmp_path / "skill.py"
    entry.write_text(_VALID_ENTRY, encoding="utf-8")
    result = run_skill(entry, ["web.search"], {"q": "hello"})
    assert result["success"] is True
    assert result["output"] == {"q": "hello"}


def test_run_skill_timeout(tmp_path):
    entry = tmp_path / "slow.py"
    entry.write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
    result = run_skill(entry, [], {}, timeout=1)
    assert result["success"] is False
    assert "timed out" in result["error"].lower()


def test_run_skill_output_capped(tmp_path):
    entry = tmp_path / "big.py"
    entry.write_text("import sys\nsys.stdout.write('x' * 1_000_001)\n", encoding="utf-8")
    result = run_skill(entry, [], {})
    assert result["success"] is False
    assert "1mb" in result["error"].lower()


def test_run_skill_invalid_json(tmp_path):
    entry = tmp_path / "bad.py"
    entry.write_text("print('not json')\n", encoding="utf-8")
    result = run_skill(entry, [], {})
    assert result["success"] is False
    assert "invalid json" in result["error"].lower()


def test_run_skill_env_has_no_secrets(tmp_path):
    entry = tmp_path / "env.py"
    entry.write_text(
        "import os, json\n"
        "print(json.dumps({'success': True, 'output': dict(os.environ)}))\n",
        encoding="utf-8",
    )
    result = run_skill(entry, ["web.search"], {})
    env = result["output"]
    serialized = json.dumps(env)
    from core.config import settings
    assert "BIXDOT_JWT_SECRET" not in env
    assert "DATABASE_URL" not in env
    assert settings.jwt_secret not in serialized
    assert settings.db_path not in serialized
    # The capability grant vector IS present
    assert "BIXDOT_CAPABILITIES" in env


# ─── Routes ────────────────────────────────────────────────────────────────────

def test_skills_list_requires_auth(client):
    assert client.get("/agent/skills").status_code == 401


def test_skills_install_and_list_via_api(client, auth_headers, tmp_path):
    zip_path = _make_skill_zip(tmp_path, skill_id="com.example.api")
    with open(zip_path, "rb") as f:
        r = client.post("/agent/skills/install",
                        files={"file": ("skill.zip", f, "application/zip")},
                        headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["skill_id"] == "com.example.api"
    assert "web.search" in body["granted_capabilities"]

    listed = client.get("/agent/skills", headers=auth_headers).json()
    assert "com.example.api" in [s["skill_id"] for s in listed]


# ─── Runtime dispatch (C7) ─────────────────────────────────────────────────────

def test_third_party_tools_lists_enabled_skill(tmp_path):
    from core.agent.runtime import third_party_tools
    pm.install_skill(_make_skill_zip(tmp_path, skill_id="com.example.tool"),
                     approved_by="user-1")
    tool_defs, tool_map = third_party_tools()
    names = [t["name"] for t in tool_defs]
    assert any("com_example_tool" in n for n in names)
    # The map points back to the skill record
    skill = list(tool_map.values())[0]
    assert skill["skill_id"] == "com.example.tool"


def test_dispatch_skill_runs_in_sandbox(tmp_path):
    import asyncio
    from core.agent.runtime import AgentRuntime, third_party_tools
    pm.install_skill(_make_skill_zip(tmp_path, skill_id="com.example.run"),
                     approved_by="user-1")
    _, tool_map = third_party_tools()
    skill = list(tool_map.values())[0]
    result = asyncio.run(AgentRuntime()._dispatch_skill(skill, "hello", "user-1"))
    assert "hello" in result


def test_dispatch_tampered_skill_blocked(tmp_path):
    import asyncio
    from core.agent.runtime import AgentRuntime, third_party_tools
    pm.install_skill(_make_skill_zip(tmp_path, skill_id="com.example.evil"),
                     approved_by="user-1")
    _, tool_map = third_party_tools()
    skill = list(tool_map.values())[0]
    Path(skill["entry_file"]).write_text("print('evil')\n", encoding="utf-8")
    result = asyncio.run(AgentRuntime()._dispatch_skill(skill, "x", "user-1"))
    assert "integrity check" in result.lower()


def test_skills_install_rejects_bad_license_via_api(client, auth_headers, tmp_path):
    zip_path = _make_skill_zip(tmp_path, skill_id="com.example.gpl", license="GPL-3.0")
    with open(zip_path, "rb") as f:
        r = client.post("/agent/skills/install",
                        files={"file": ("skill.zip", f, "application/zip")},
                        headers=auth_headers)
    assert r.status_code == 400
