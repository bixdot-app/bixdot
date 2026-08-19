# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
THIRD_PARTY_LICENSES.txt — MIT/BSD/Apache-2.0 all require reproducing a
dependency's copyright notice and licence text, and this was previously
missing entirely from the release pipeline. These tests check the generation
script logic directly (no real pip-licenses/cargo-about subprocess — that's
exercised by release.yml itself) and that the workflow/Tauri config actually
wire the result into both the release assets and the installer.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import generate_third_party_licenses as gtpl  # noqa: E402

yaml = pytest.importorskip("yaml")


def test_pip_section_includes_name_version_license_and_text(tmp_path):
    pip_json = tmp_path / "pip.json"
    pip_json.write_text(json.dumps([
        {"Name": "somepkg", "Version": "1.2.3", "License": "MIT",
         "Author": "Someone", "LicenseText": "MIT LICENSE TEXT HERE"},
    ]))
    section = gtpl._pip_section(pip_json)
    assert "somepkg 1.2.3" in section
    assert "Licence: MIT" in section
    assert "Someone" in section
    assert "MIT LICENSE TEXT HERE" in section


def test_pip_section_skips_unknown_author_and_text(tmp_path):
    pip_json = tmp_path / "pip.json"
    pip_json.write_text(json.dumps([
        {"Name": "somepkg", "Version": "1.0", "License": "MIT",
         "Author": "UNKNOWN", "LicenseText": "UNKNOWN"},
    ]))
    section = gtpl._pip_section(pip_json)
    assert "UNKNOWN" not in section


def test_cargo_section_includes_crate_names_and_license_text(tmp_path):
    cargo_json = tmp_path / "cargo.json"
    cargo_json.write_text(json.dumps({
        "licenses": [
            {
                "name": "MIT License", "id": "MIT",
                "text": "MIT LICENSE TEXT HERE",
                "used_by": [{"crate": {"name": "somecrate", "version": "0.1.0"}}],
            },
        ],
    }))
    section = gtpl._cargo_section(cargo_json)
    assert "somecrate 0.1.0" in section
    assert "MIT License (MIT)" in section
    assert "MIT LICENSE TEXT HERE" in section


def test_main_writes_combined_output(tmp_path, monkeypatch):
    pip_json = tmp_path / "pip.json"
    pip_json.write_text(json.dumps([
        {"Name": "pippkg", "Version": "1.0", "License": "MIT",
         "Author": "A", "LicenseText": "PIP TEXT"},
    ]))
    cargo_json = tmp_path / "cargo.json"
    cargo_json.write_text(json.dumps({
        "licenses": [
            {"name": "MIT License", "id": "MIT", "text": "CARGO TEXT",
             "used_by": [{"crate": {"name": "cratepkg", "version": "0.1"}}]},
        ],
    }))
    out = tmp_path / "THIRD_PARTY_LICENSES.txt"

    monkeypatch.setattr(sys, "argv", [
        "generate_third_party_licenses.py",
        "--pip", str(pip_json), "--cargo", str(cargo_json), "--out", str(out),
    ])
    assert gtpl.main() == 0
    text = out.read_text(encoding="utf-8")
    assert "pippkg" in text and "PIP TEXT" in text
    assert "cratepkg" in text and "CARGO TEXT" in text
    assert "Python dependencies" in text
    assert "Rust dependencies" in text


# ─── Wiring: the generated file must reach the installer, not just an asset ───

def test_third_party_licenses_placeholder_exists_for_local_dev_builds():
    """
    tauri.conf.json's bundle.resources references THIRD_PARTY_LICENSES.txt —
    a `cargo tauri build` run locally (without release.yml's generation step
    first) needs SOMETHING there or the resource glob fails.
    """
    assert (ROOT / "THIRD_PARTY_LICENSES.txt").is_file()


def test_tauri_bundle_resources_includes_third_party_licenses():
    conf = json.loads((ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    resources = conf["bundle"]["resources"]
    assert any("THIRD_PARTY_LICENSES.txt" in r for r in resources), (
        "THIRD_PARTY_LICENSES.txt is not bundled into the installer via "
        "tauri.conf.json bundle.resources"
    )


def _release_steps():
    spec = yaml.safe_load((ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"))
    return spec["jobs"]["build"]["steps"]


def test_release_generates_third_party_licenses_before_tauri_build():
    steps = _release_steps()
    gen_at = next((i for i, s in enumerate(steps) if "generate_third_party_licenses" in s.get("run", "")), None)
    build_at = next((i for i, s in enumerate(steps) if "cargo tauri build" in s.get("run", "")), None)
    assert gen_at is not None, "release.yml never generates THIRD_PARTY_LICENSES.txt"
    assert build_at is not None, "release.yml never runs cargo tauri build"
    assert gen_at < build_at, (
        "THIRD_PARTY_LICENSES.txt must be generated BEFORE cargo tauri build "
        "bundles it as a resource"
    )


def test_release_generates_third_party_licenses_on_every_platform_leg():
    """Not gated to ubuntu-only — every matrix leg runs cargo tauri build."""
    steps = _release_steps()
    gen_step = next(s for s in steps if "generate_third_party_licenses" in s.get("run", ""))
    assert "if" not in gen_step, (
        "THIRD_PARTY_LICENSES.txt generation must run on every platform leg, "
        f"not be gated — found condition: {gen_step.get('if')!r}"
    )


def test_release_ships_cargo_sbom_as_an_asset():
    steps = _release_steps()
    assert any("bixdot-cargo-sbom.json" in s.get("run", "") for s in steps), (
        "release.yml does not generate/stage a Rust-tree SBOM — BXD-006"
    )


def test_release_stages_third_party_licenses_and_both_sboms():
    steps = _release_steps()
    stage_step = next(s for s in steps if s.get("name") == "Stage installers (Linux)")
    run = stage_step["run"]
    for artifact in ("bixdot-sbom.json", "bixdot-cargo-sbom.json", "THIRD_PARTY_LICENSES.txt"):
        assert artifact in run, f"{artifact} is not staged as a release asset"
