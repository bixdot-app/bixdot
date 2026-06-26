# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Skill Plugin Manager

Installs, verifies, and manages third-party skills. Security model:

1. Every skill declares its required capabilities in bixdot-skill.json.
2. The user approves each capability at install time (no silent grants).
3. The entry file is SHA-256 verified against the manifest at install and at
   every startup — a tampered file auto-disables the skill.
4. Skills run only in the subprocess sandbox (core/skills/sandbox.py) — never
   in-process.
5. Manifest capabilities use a dotted vocabulary (filesystem.read) that maps
   onto BixDot's first-party Capability enum (fs:read) so there is ONE
   permission and audit system.
"""
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from core.config import settings
from core.audit.logger import get_audit_logger, AuditEvent
from core.agent.permissions import Capability
from core.skills import registry


# ─── Capability vocabulary ─────────────────────────────────────────────────────
# Dotted manifest capability → first-party Capability enum (single audit system).
SKILL_CAPABILITY_MAP: dict[str, Capability] = {
    "filesystem.read":  Capability.FS_READ,
    "filesystem.write": Capability.FS_WRITE,
    "filesystem.list":  Capability.FS_READ,
    "web.search":       Capability.NET_FETCH,
    "web.fetch":        Capability.NET_FETCH,
    "memory.read":      Capability.MEMORY_READ,
    "memory.write":     Capability.MEMORY_WRITE,
    "calendar.read":    Capability.CALENDAR_READ,
    "calendar.write":   Capability.CALENDAR_WRITE,
    "github.read":      Capability.GITHUB_READ,
    "terminal.execute": Capability.EXEC_SHELL,
    "documents.read":   Capability.DOCS_READ,
}

ALLOWED_CAPABILITIES = set(SKILL_CAPABILITY_MAP.keys())

# Capabilities that are too broad / unsafe — rejected at install.
FORBIDDEN_CAPABILITY_PREFIXES = ("network.", "shell.", "database.", "auth.")

_REQUIRED_MANIFEST_FIELDS = (
    "id", "name", "version", "description", "author",
    "license", "entry", "capabilities", "trigger", "sha256",
)


def plugins_dir() -> Path:
    """Install root, derived from the data dir so tests are isolated."""
    d = Path(settings.db_path).expanduser().parent / "plugins"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ─── Validation helpers ────────────────────────────────────────────────────────

def _license_allowed(license_str: str) -> bool:
    """Only MIT, BSD, and Apache 2.0 are permitted (matches BixDot policy)."""
    s = (license_str or "").strip().lower()
    if not s:
        return False
    # Reject copyleft explicitly even if substring-matched elsewhere
    if "agpl" in s or "gpl" in s or "lgpl" in s:
        return False
    return ("mit" in s) or s.startswith("bsd") or ("bsd" in s) or ("apache" in s)


def _validate_capabilities(capabilities: list[str]) -> None:
    if not isinstance(capabilities, list):
        raise ValueError("Manifest 'capabilities' must be a list.")
    for cap in capabilities:
        for prefix in FORBIDDEN_CAPABILITY_PREFIXES:
            if cap.startswith(prefix):
                raise ValueError(
                    f"Capability '{cap}' is too broad and is not permitted. "
                    f"Forbidden prefixes: {', '.join(FORBIDDEN_CAPABILITY_PREFIXES)}"
                )
        if cap not in ALLOWED_CAPABILITIES:
            raise ValueError(
                f"Capability '{cap}' is not in the allowed set. "
                f"Allowed: {', '.join(sorted(ALLOWED_CAPABILITIES))}"
            )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _validate_manifest(manifest: dict) -> None:
    missing = [f for f in _REQUIRED_MANIFEST_FIELDS if f not in manifest]
    if missing:
        raise ValueError(f"Manifest is missing required fields: {', '.join(missing)}")
    if not isinstance(manifest["id"], str) or not manifest["id"].strip():
        raise ValueError("Manifest 'id' must be a non-empty string.")
    _validate_capabilities(manifest["capabilities"])
    if not _license_allowed(manifest["license"]):
        raise ValueError(
            f"License '{manifest['license']}' is not allowed. "
            "Only MIT, BSD, and Apache 2.0 skills may be installed."
        )


def mapped_capabilities(dotted: list[str]) -> list[Capability]:
    """Translate manifest dotted capabilities to first-party Capability enums."""
    return [SKILL_CAPABILITY_MAP[c] for c in dotted if c in SKILL_CAPABILITY_MAP]


# ─── Inspect (validate without installing) ─────────────────────────────────────

def inspect_skill(zip_path: Path) -> dict:
    """
    Extract and fully validate a skill archive WITHOUT installing it. Used to
    show the user the capability-approval screen before they commit. Raises
    ValueError on any validation failure; returns the validated manifest.
    """
    zip_path = Path(zip_path)
    if not zip_path.exists() or not zipfile.is_zipfile(zip_path):
        raise ValueError("Skill archive is not a valid zip file.")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.namelist():
                dest = (tmp_path / member).resolve()
                if not str(dest).startswith(str(tmp_path.resolve())):
                    raise ValueError("Skill archive contains an unsafe path.")
            zf.extractall(tmp_path)
        manifest_path = tmp_path / "bixdot-skill.json"
        if not manifest_path.exists():
            candidates = list(tmp_path.glob("*/bixdot-skill.json"))
            if len(candidates) == 1:
                manifest_path = candidates[0]
        if not manifest_path.exists():
            raise ValueError("bixdot-skill.json not found at the archive root.")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"bixdot-skill.json is not valid JSON: {e}")
        _validate_manifest(manifest)
        entry_path = manifest_path.parent / manifest["entry"]
        if not entry_path.exists():
            raise ValueError(f"Entry file '{manifest['entry']}' not found in archive.")
        if _sha256_file(entry_path).lower() != str(manifest["sha256"]).lower():
            raise ValueError("SHA-256 of the entry file does not match the manifest.")
    return manifest


# ─── Install ───────────────────────────────────────────────────────────────────

def install_skill(zip_path: Path, approved_by: str) -> dict:
    """
    Install a skill from a zip file. Returns the manifest dict on success.
    Raises ValueError with a clear message on any validation failure; nothing
    is written to the registry or filesystem unless every check passes.
    """
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise ValueError(f"Skill archive not found: {zip_path}")
    if not zipfile.is_zipfile(zip_path):
        raise ValueError("Skill archive is not a valid zip file.")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.namelist():
                # Prevent zip-slip path traversal
                dest = (tmp_path / member).resolve()
                if not str(dest).startswith(str(tmp_path.resolve())):
                    raise ValueError("Skill archive contains an unsafe path.")
            zf.extractall(tmp_path)

        # The manifest may be at the root or inside a single top-level folder.
        manifest_path = tmp_path / "bixdot-skill.json"
        if not manifest_path.exists():
            candidates = list(tmp_path.glob("*/bixdot-skill.json"))
            if len(candidates) == 1:
                manifest_path = candidates[0]
        if not manifest_path.exists():
            raise ValueError("bixdot-skill.json not found at the archive root.")

        root = manifest_path.parent
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"bixdot-skill.json is not valid JSON: {e}")

        _validate_manifest(manifest)

        entry_path = root / manifest["entry"]
        if not entry_path.exists() or not entry_path.is_file():
            raise ValueError(f"Entry file '{manifest['entry']}' not found in archive.")

        actual_hash = _sha256_file(entry_path)
        if actual_hash.lower() != str(manifest["sha256"]).lower():
            raise ValueError(
                "SHA-256 of the entry file does not match the manifest. "
                "The skill may have been tampered with and was NOT installed."
            )

        # All checks passed — copy into the install root.
        dest_dir = plugins_dir() / manifest["id"]
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        shutil.copytree(root, dest_dir)
        installed_entry = dest_dir / manifest["entry"]

    registry.register_skill(
        manifest,
        entry_file=str(installed_entry),
        entry_sha256=actual_hash,
        approved_by=approved_by,
    )
    registry.grant_capabilities(manifest["id"], approved_by, manifest["capabilities"])

    get_audit_logger().log(
        AuditEvent.SKILL_INSTALLED,
        {"skill_id": manifest["id"], "version": manifest["version"],
         "capabilities": manifest["capabilities"], "approved_by": approved_by},
        user_id=approved_by,
        skill_id=manifest["id"],
    )
    return manifest


# ─── Verify / lifecycle ────────────────────────────────────────────────────────

def verify_skill_integrity(skill_id: str) -> bool:
    """
    Recompute the entry file's SHA-256 and compare to the stored hash.
    On mismatch (or missing file) the skill is auto-disabled and audit-logged.
    """
    skill = registry.get_skill(skill_id)
    if not skill:
        return False
    entry = Path(skill["entry_file"])
    if not entry.exists():
        _auto_disable(skill_id, "entry file missing")
        return False
    if _sha256_file(entry).lower() != skill["entry_sha256"].lower():
        _auto_disable(skill_id, "sha256 mismatch")
        return False
    return True


def _auto_disable(skill_id: str, reason: str) -> None:
    registry.set_enabled(skill_id, False)
    get_audit_logger().log(
        AuditEvent.SKILL_VERIFY_FAILED,
        {"skill_id": skill_id, "reason": reason},
        skill_id=skill_id,
    )


def load_enabled_skills() -> list[dict]:
    """
    Return all enabled skills whose integrity verifies. Tampered skills are
    auto-disabled as a side effect. Called at startup and by the runtime.
    """
    verified = []
    for skill in registry.list_enabled_skills():
        if verify_skill_integrity(skill["skill_id"]):
            verified.append(skill)
    return verified


def set_enabled(skill_id: str, enabled: bool, user_id: str) -> None:
    if not registry.get_skill(skill_id):
        raise KeyError(f"Skill '{skill_id}' is not installed.")
    registry.set_enabled(skill_id, enabled)
    get_audit_logger().log(
        AuditEvent.SKILL_TOGGLED,
        {"skill_id": skill_id, "enabled": enabled},
        user_id=user_id, skill_id=skill_id,
    )


def disable_skill(skill_id: str, reason: str, user_id: str) -> None:
    registry.set_enabled(skill_id, False)
    get_audit_logger().log(
        AuditEvent.SKILL_DISABLED,
        {"skill_id": skill_id, "reason": reason},
        user_id=user_id, skill_id=skill_id,
    )


def uninstall_skill(skill_id: str, user_id: str) -> None:
    if not registry.get_skill(skill_id):
        raise KeyError(f"Skill '{skill_id}' is not installed.")
    registry.remove_skill(skill_id)
    dest_dir = plugins_dir() / skill_id
    if dest_dir.exists():
        shutil.rmtree(dest_dir, ignore_errors=True)
    get_audit_logger().log(
        AuditEvent.SKILL_REMOVED,
        {"skill_id": skill_id},
        user_id=user_id, skill_id=skill_id,
    )


def verify_all_on_startup() -> list[str]:
    """Verify every enabled skill at startup. Returns ids that were disabled."""
    disabled: list[str] = []
    for skill in registry.list_enabled_skills():
        if not verify_skill_integrity(skill["skill_id"]):
            disabled.append(skill["skill_id"])
    return disabled
