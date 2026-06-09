# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot Plugin Loader

Plugins live in ~/.bixdot/plugins/<plugin-id>/
Each plugin directory must contain a manifest.json.

Manifest schema (v1):
{
  "schema_version": 1,
  "id": "com.example.myplugin",       -- reverse-domain unique ID
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "Does something useful",
  "author": "Developer Name",
  "capabilities": ["fs:read"],        -- declared capabilities (subset of Capability enum)
  "entry": "main.py",                 -- entry point (reserved for future execution)
  "homepage": "https://example.com",  -- optional
  "license": "MIT"                    -- optional
}

This foundation release handles discovery, validation, install/uninstall,
and enable/disable. Plugin execution (loading entry point code) is v0.3.0.
"""

import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.storage.db import get_connection

# ─── Constants ────────────────────────────────────────────────────────────────

PLUGINS_DIR = Path("~/.bixdot/plugins").expanduser()
MANIFEST_FILE = "manifest.json"
SCHEMA_VERSION = 1

# Valid capability values (mirrors Capability enum in permissions.py)
VALID_CAPABILITIES = {
    "fs:read", "fs:write", "fs:delete",
    "net:outbound", "net:fetch",
    "exec:shell", "exec:python",
    "cred:read", "cred:write",
    "calendar:read", "calendar:write",
    "llm:cloud", "llm:local",
}

# Plugin ID must be reverse-domain style, letters/digits/dots/hyphens
_ID_RE = re.compile(r'^[a-z0-9][a-z0-9.\-]{2,63}$')


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class PluginManifest:
    id: str
    name: str
    version: str
    description: str
    author: str
    capabilities: list[str]
    entry: str
    schema_version: int = 1
    homepage: Optional[str] = None
    license: Optional[str] = None


@dataclass
class PluginRecord:
    id: str
    name: str
    version: str
    description: str
    author: str
    capabilities: list[str]
    is_enabled: bool
    install_path: str
    installed_at: str


# ─── Database helpers ─────────────────────────────────────────────────────────

def _ensure_plugins_table() -> None:
    """Create the plugins table if it doesn't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS plugins (
                id           TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                version      TEXT NOT NULL,
                description  TEXT,
                author       TEXT,
                capabilities TEXT NOT NULL DEFAULT '[]',
                is_enabled   INTEGER NOT NULL DEFAULT 1,
                install_path TEXT NOT NULL,
                installed_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


def _upsert_plugin(manifest: PluginManifest, install_path: Path) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO plugins (id, name, version, description, author,
                                  capabilities, install_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                version=excluded.version,
                description=excluded.description,
                author=excluded.author,
                capabilities=excluded.capabilities,
                install_path=excluded.install_path,
                installed_at=datetime('now')
            """,
            (
                manifest.id,
                manifest.name,
                manifest.version,
                manifest.description,
                manifest.author,
                json.dumps(manifest.capabilities),
                str(install_path),
            ),
        )


def _delete_plugin(plugin_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM plugins WHERE id = ?", (plugin_id,))


def _set_enabled(plugin_id: str, enabled: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE plugins SET is_enabled = ? WHERE id = ?",
            (1 if enabled else 0, plugin_id),
        )


def list_plugins() -> list[PluginRecord]:
    _ensure_plugins_table()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, version, description, author, capabilities, "
            "is_enabled, install_path, installed_at FROM plugins ORDER BY name"
        ).fetchall()
    records = []
    for r in rows:
        records.append(PluginRecord(
            id=r["id"],
            name=r["name"],
            version=r["version"],
            description=r["description"] or "",
            author=r["author"] or "",
            capabilities=json.loads(r["capabilities"] or "[]"),
            is_enabled=bool(r["is_enabled"]),
            install_path=r["install_path"],
            installed_at=r["installed_at"],
        ))
    return records


def get_plugin(plugin_id: str) -> Optional[PluginRecord]:
    _ensure_plugins_table()
    with get_connection() as conn:
        r = conn.execute(
            "SELECT id, name, version, description, author, capabilities, "
            "is_enabled, install_path, installed_at FROM plugins WHERE id = ?",
            (plugin_id,),
        ).fetchone()
    if not r:
        return None
    return PluginRecord(
        id=r["id"],
        name=r["name"],
        version=r["version"],
        description=r["description"] or "",
        author=r["author"] or "",
        capabilities=json.loads(r["capabilities"] or "[]"),
        is_enabled=bool(r["is_enabled"]),
        install_path=r["install_path"],
        installed_at=r["installed_at"],
    )


# ─── Manifest validation ──────────────────────────────────────────────────────

def _validate_manifest(data: dict) -> PluginManifest:
    """Validate a raw manifest dict and return a typed PluginManifest."""
    required = ("id", "name", "version", "description", "author", "capabilities", "entry")
    missing  = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"Manifest missing required fields: {missing}")

    plugin_id = str(data["id"]).strip()
    if not _ID_RE.match(plugin_id):
        raise ValueError(
            f"Invalid plugin ID '{plugin_id}'. "
            "Use reverse-domain format: com.example.myplugin"
        )

    caps = data["capabilities"]
    if not isinstance(caps, list):
        raise ValueError("capabilities must be a JSON array")
    invalid_caps = [c for c in caps if c not in VALID_CAPABILITIES]
    if invalid_caps:
        raise ValueError(
            f"Unknown capabilities: {invalid_caps}. "
            f"Valid: {sorted(VALID_CAPABILITIES)}"
        )

    return PluginManifest(
        id=plugin_id,
        name=str(data["name"]).strip(),
        version=str(data["version"]).strip(),
        description=str(data["description"]).strip(),
        author=str(data["author"]).strip(),
        capabilities=caps,
        entry=str(data.get("entry", "main.py")).strip(),
        schema_version=int(data.get("schema_version", 1)),
        homepage=data.get("homepage"),
        license=data.get("license"),
    )


# ─── Install / uninstall ──────────────────────────────────────────────────────

def install_from_directory(source_path: Path) -> PluginManifest:
    """
    Install a plugin from a local directory that contains manifest.json.
    Copies the directory to ~/.bixdot/plugins/<id>/ and registers it in DB.
    """
    _ensure_plugins_table()
    manifest_path = source_path / MANIFEST_FILE
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.json found in {source_path}")

    with open(manifest_path, encoding="utf-8") as f:
        raw = json.load(f)
    manifest = _validate_manifest(raw)

    dest = PLUGINS_DIR / manifest.id
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source_path, dest)

    _upsert_plugin(manifest, dest)
    return manifest


def install_from_zip(zip_path: Path) -> PluginManifest:
    """
    Install a plugin from a .zip archive.
    The zip must contain manifest.json at its root or inside a single directory.
    """
    _ensure_plugins_table()
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_path)

        # Support both flat zip (manifest.json at root) and single-folder zip
        if (tmp_path / MANIFEST_FILE).exists():
            source = tmp_path
        else:
            dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
            if len(dirs) == 1 and (dirs[0] / MANIFEST_FILE).exists():
                source = dirs[0]
            else:
                raise FileNotFoundError(
                    "manifest.json not found in zip root or single subdirectory"
                )

        return install_from_directory(source)


def uninstall_plugin(plugin_id: str) -> None:
    """Remove a plugin from disk and from the DB."""
    _ensure_plugins_table()
    record = get_plugin(plugin_id)
    if not record:
        raise KeyError(f"Plugin '{plugin_id}' is not installed")

    dest = Path(record.install_path)
    if dest.exists():
        shutil.rmtree(dest)

    _delete_plugin(plugin_id)


def set_plugin_enabled(plugin_id: str, enabled: bool) -> None:
    _ensure_plugins_table()
    if not get_plugin(plugin_id):
        raise KeyError(f"Plugin '{plugin_id}' is not installed")
    _set_enabled(plugin_id, enabled)


# ─── Scan on startup ──────────────────────────────────────────────────────────

def scan_plugins_dir() -> int:
    """
    Scan ~/.bixdot/plugins/ for directories with manifest.json that aren't
    yet registered in the DB. Registers any new ones found.
    Returns the count of newly registered plugins.
    """
    _ensure_plugins_table()
    if not PLUGINS_DIR.exists():
        return 0

    count = 0
    for entry in PLUGINS_DIR.iterdir():
        if not entry.is_dir():
            continue
        manifest_path = entry / MANIFEST_FILE
        if not manifest_path.exists():
            continue
        try:
            with open(manifest_path, encoding="utf-8") as f:
                raw = json.load(f)
            manifest = _validate_manifest(raw)
            existing = get_plugin(manifest.id)
            if not existing:
                _upsert_plugin(manifest, entry)
                count += 1
        except Exception:
            pass  # Skip invalid plugin directories silently
    return count
