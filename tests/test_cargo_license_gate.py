# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BXD-005/BXD-006 — the cargo (Rust/Tauri) tree gets the same licence and
advisory gate as the pip tree, via `cargo deny check advisories licenses`
against src-tauri/deny.toml.

These tests read deny.toml as data (tomllib, stdlib in 3.11+) rather than
shelling out to `cargo deny` — running the real tool needs the full crate
registry and network access, which is exercised separately by the
`cargo-deny` CI job. What's checked here is structural: the config exists,
the allowlist matches project policy, and every reviewed exception/ignore
is cross-referenced in the human-readable governance docs so the two cannot
silently drift apart.
"""
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DENY_TOML = ROOT / "src-tauri" / "deny.toml"
ALLOWLIST_DOC = ROOT / "docs" / "governance" / "LICENCE_ALLOWLIST.md"
FINDINGS_REGISTER = ROOT / "docs" / "governance" / "01_FINDINGS_REGISTER.md"

# The core allowlist shared with the pip gate (scripts/check_licenses.py).
CORE_ALLOWED = {
    "MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC",
    "HPND", "MIT-CMU", "Unlicense", "0BSD",
}


def _load_deny_toml() -> dict:
    assert DENY_TOML.is_file(), "src-tauri/deny.toml must exist — BXD-005/BXD-006"
    return tomllib.loads(DENY_TOML.read_text(encoding="utf-8"))


def test_deny_toml_advisories_and_licenses_sections_present():
    spec = _load_deny_toml()
    assert "advisories" in spec, "deny.toml has no [advisories] section — BXD-006"
    assert "licenses" in spec, "deny.toml has no [licenses] section — BXD-005"


def test_cargo_allowlist_is_a_superset_of_the_core_allowlist():
    """The cargo gate must not be more permissive than the pip gate's core policy."""
    spec = _load_deny_toml()
    allowed = set(spec["licenses"]["allow"])
    missing = CORE_ALLOWED - allowed
    assert not missing, f"deny.toml's allow list is missing core entries: {missing}"


def test_cargo_allowlist_forbids_nothing_copyleft():
    spec = _load_deny_toml()
    allowed = {a.upper() for a in spec["licenses"]["allow"]}
    for forbidden in ("GPL", "AGPL", "LGPL", "SSPL"):
        assert not any(forbidden in a for a in allowed), (
            f"deny.toml's allow list contains something matching {forbidden!r}"
        )


def test_every_cargo_license_exception_is_documented():
    """Every [[licenses.exceptions]] crate must have a row in LICENCE_ALLOWLIST.md."""
    spec = _load_deny_toml()
    exceptions = spec["licenses"].get("exceptions", [])
    doc_text = ALLOWLIST_DOC.read_text(encoding="utf-8")
    undocumented = [
        exc["crate"] for exc in exceptions
        if exc["crate"] not in doc_text
    ]
    assert not undocumented, (
        f"Cargo licence exceptions missing from docs/governance/"
        f"LICENCE_ALLOWLIST.md: {undocumented}"
    )


def test_every_ignored_advisory_has_a_named_reason():
    """
    A bare RUSTSEC ID with no reason is exactly the kind of silent suppression
    this project's governance model rejects — see BXD-018's postmortem on
    unverified claims.
    """
    spec = _load_deny_toml()
    ignored = spec["advisories"].get("ignore", [])
    for entry in ignored:
        assert isinstance(entry, dict) and entry.get("reason"), (
            f"Ignored advisory {entry!r} has no documented reason"
        )
        assert "id" in entry and entry["id"].startswith("RUSTSEC-"), (
            f"Malformed advisory ignore entry: {entry!r}"
        )


def test_ignored_advisories_are_logged_in_the_findings_register():
    """BXD-019 must exist and reference every RUSTSEC ID cargo-deny ignores."""
    spec = _load_deny_toml()
    ignored_ids = [e["id"] for e in spec["advisories"].get("ignore", [])]
    assert ignored_ids, "expected at least one ignored advisory to exist"

    register_text = FINDINGS_REGISTER.read_text(encoding="utf-8")
    assert "BXD-019" in register_text, (
        "The findings register has no BXD-019 entry for the ignored RustSec advisories"
    )
    missing = [rid for rid in ignored_ids if rid not in register_text]
    assert not missing, (
        f"RUSTSEC IDs ignored in deny.toml but not mentioned in the findings "
        f"register: {missing}"
    )
