# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Plugin loader unit tests.

Verifies manifest validation, install/uninstall lifecycle, enable/disable,
and the startup scanner. Tests use a temp directory for the plugins dir —
real ~/.bixdot/plugins/ is never touched.
"""
import json
import pytest
from pathlib import Path

from core.plugins.loader import (
    _validate_manifest,
    install_from_directory,
    install_from_zip,
    uninstall_plugin,
    set_plugin_enabled,
    list_plugins,
    get_plugin,
    scan_plugins_dir,
    PLUGINS_DIR,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

VALID_MANIFEST = {
    "schema_version": 1,
    "id": "com.example.myplugin",
    "name": "My Plugin",
    "version": "1.0.0",
    "description": "Does something useful",
    "author": "Dev",
    "capabilities": ["fs:read"],
    "entry": "main.py",
}


@pytest.fixture()
def plugin_dir(tmp_path, monkeypatch):
    """Redirect PLUGINS_DIR to tmp_path and return a helper that creates plugin dirs."""
    plugins_root = tmp_path / "plugins"
    plugins_root.mkdir()
    monkeypatch.setattr("core.plugins.loader.PLUGINS_DIR", plugins_root)

    def _make_plugin(manifest: dict) -> Path:
        src = tmp_path / "src" / manifest["id"]
        src.mkdir(parents=True, exist_ok=True)
        (src / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (src / "main.py").write_text("# entry point", encoding="utf-8")
        return src

    return _make_plugin


# ── Manifest validation ───────────────────────────────────────────────────────

def test_valid_manifest_parses():
    m = _validate_manifest(VALID_MANIFEST)
    assert m.id == "com.example.myplugin"
    assert m.name == "My Plugin"
    assert m.capabilities == ["fs:read"]
    assert m.schema_version == 1


def test_valid_manifest_all_capabilities():
    caps = [
        "fs:read", "fs:write", "fs:delete",
        "net:outbound", "net:fetch",
        "exec:shell", "exec:python",
        "cred:read", "cred:write",
        "calendar:read", "calendar:write",
        "llm:cloud", "llm:local",
    ]
    data = {**VALID_MANIFEST, "capabilities": caps}
    m = _validate_manifest(data)
    assert set(m.capabilities) == set(caps)


def test_missing_required_field_raises():
    for field in ("id", "name", "version", "description", "author", "capabilities", "entry"):
        data = {k: v for k, v in VALID_MANIFEST.items() if k != field}
        with pytest.raises(ValueError, match="missing required fields"):
            _validate_manifest(data)


def test_invalid_id_format_raises():
    bad_ids = [
        "UPPERCASE",
        "has spaces",
        "x",          # too short (< 3 chars)
        "-starts-with-dash",
        "",
    ]
    for bad_id in bad_ids:
        data = {**VALID_MANIFEST, "id": bad_id}
        with pytest.raises(ValueError, match="Invalid plugin ID"):
            _validate_manifest(data)


def test_valid_id_formats():
    valid_ids = [
        "com.example.plugin",
        "my-plugin",
        "abc",
        "org.bixdot.example-plugin",
        "plugin123",
    ]
    for pid in valid_ids:
        data = {**VALID_MANIFEST, "id": pid}
        m = _validate_manifest(data)
        assert m.id == pid


def test_unknown_capability_raises():
    data = {**VALID_MANIFEST, "capabilities": ["fs:read", "net:hack"]}
    with pytest.raises(ValueError, match="Unknown capabilities"):
        _validate_manifest(data)


def test_capabilities_must_be_list():
    data = {**VALID_MANIFEST, "capabilities": "fs:read"}
    with pytest.raises(ValueError, match="must be a JSON array"):
        _validate_manifest(data)


def test_empty_capabilities_is_valid():
    data = {**VALID_MANIFEST, "capabilities": []}
    m = _validate_manifest(data)
    assert m.capabilities == []


def test_optional_fields_default_to_none():
    data = {k: v for k, v in VALID_MANIFEST.items() if k not in ("homepage", "license")}
    m = _validate_manifest(data)
    assert m.homepage is None
    assert m.license is None


# ── Install / uninstall ───────────────────────────────────────────────────────

def test_install_from_directory(plugin_dir):
    src = plugin_dir(VALID_MANIFEST)
    m = install_from_directory(src)
    assert m.id == VALID_MANIFEST["id"]

    record = get_plugin(m.id)
    assert record is not None
    assert record.name == VALID_MANIFEST["name"]
    assert record.is_enabled is True


def test_install_missing_manifest_raises(tmp_path, monkeypatch):
    plugins_root = tmp_path / "plugins"
    plugins_root.mkdir()
    monkeypatch.setattr("core.plugins.loader.PLUGINS_DIR", plugins_root)

    src = tmp_path / "empty_plugin"
    src.mkdir()
    with pytest.raises(FileNotFoundError, match="manifest.json"):
        install_from_directory(src)


def test_install_updates_existing(plugin_dir):
    src = plugin_dir(VALID_MANIFEST)
    install_from_directory(src)

    updated = {**VALID_MANIFEST, "version": "2.0.0"}
    src2 = src.parent / (VALID_MANIFEST["id"] + "_v2")
    src2.mkdir()
    (src2 / "manifest.json").write_text(json.dumps(updated), encoding="utf-8")

    m2 = install_from_directory(src2)
    assert m2.version == "2.0.0"
    assert get_plugin(m2.id).version == "2.0.0"


def test_uninstall_removes_record(plugin_dir):
    src = plugin_dir(VALID_MANIFEST)
    m = install_from_directory(src)
    uninstall_plugin(m.id)
    assert get_plugin(m.id) is None


def test_uninstall_nonexistent_raises(plugin_dir):
    with pytest.raises(KeyError, match="not installed"):
        uninstall_plugin("com.does.not.exist")


def test_install_from_zip(tmp_path, monkeypatch):
    import zipfile
    plugins_root = tmp_path / "plugins"
    plugins_root.mkdir()
    monkeypatch.setattr("core.plugins.loader.PLUGINS_DIR", plugins_root)

    src = tmp_path / "plugin_src"
    src.mkdir()
    (src / "manifest.json").write_text(json.dumps(VALID_MANIFEST), encoding="utf-8")
    (src / "main.py").write_text("", encoding="utf-8")

    zip_path = tmp_path / "plugin.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(src / "manifest.json", "manifest.json")
        zf.write(src / "main.py", "main.py")

    m = install_from_zip(zip_path)
    assert m.id == VALID_MANIFEST["id"]


# ── Enable / disable ──────────────────────────────────────────────────────────

def test_set_plugin_enabled_false(plugin_dir):
    src = plugin_dir(VALID_MANIFEST)
    m = install_from_directory(src)
    set_plugin_enabled(m.id, False)
    assert get_plugin(m.id).is_enabled is False


def test_set_plugin_enabled_true_after_disable(plugin_dir):
    src = plugin_dir(VALID_MANIFEST)
    m = install_from_directory(src)
    set_plugin_enabled(m.id, False)
    set_plugin_enabled(m.id, True)
    assert get_plugin(m.id).is_enabled is True


def test_set_enabled_nonexistent_raises():
    with pytest.raises(KeyError):
        set_plugin_enabled("com.ghost.plugin", True)


# ── list_plugins / get_plugin ─────────────────────────────────────────────────

def test_list_plugins_empty_initially():
    assert list_plugins() == []


def test_list_plugins_returns_all_installed(plugin_dir):
    for i in range(3):
        manifest = {**VALID_MANIFEST, "id": f"com.example.plugin{i}", "name": f"Plugin {i}"}
        install_from_directory(plugin_dir(manifest))
    assert len(list_plugins()) == 3


def test_get_plugin_unknown_returns_none():
    assert get_plugin("com.unknown.plugin") is None


# ── scan_plugins_dir ──────────────────────────────────────────────────────────

def test_scan_discovers_unregistered_plugin(tmp_path, monkeypatch):
    plugins_root = tmp_path / "plugins"
    plugins_root.mkdir()
    monkeypatch.setattr("core.plugins.loader.PLUGINS_DIR", plugins_root)

    # Write a plugin directly to the plugins dir (not via install_from_directory)
    plugin_path = plugins_root / "com.example.scanned"
    plugin_path.mkdir()
    (plugin_path / "manifest.json").write_text(
        json.dumps({**VALID_MANIFEST, "id": "com.example.scanned"}),
        encoding="utf-8",
    )

    count = scan_plugins_dir()
    assert count == 1
    assert get_plugin("com.example.scanned") is not None


def test_scan_skips_invalid_manifests(tmp_path, monkeypatch):
    plugins_root = tmp_path / "plugins"
    plugins_root.mkdir()
    monkeypatch.setattr("core.plugins.loader.PLUGINS_DIR", plugins_root)

    bad_dir = plugins_root / "bad-plugin"
    bad_dir.mkdir()
    (bad_dir / "manifest.json").write_text('{"id": "BAD ID!!!"}', encoding="utf-8")

    count = scan_plugins_dir()
    assert count == 0


def test_scan_skips_already_registered(tmp_path, monkeypatch):
    plugins_root = tmp_path / "plugins"
    plugins_root.mkdir()
    monkeypatch.setattr("core.plugins.loader.PLUGINS_DIR", plugins_root)

    src = tmp_path / "src" / "com.example.myplugin"
    src.mkdir(parents=True)
    (src / "manifest.json").write_text(json.dumps(VALID_MANIFEST), encoding="utf-8")
    install_from_directory(src)

    # scan_plugins_dir should not double-register
    count = scan_plugins_dir()
    assert count == 0
    assert len(list_plugins()) == 1
