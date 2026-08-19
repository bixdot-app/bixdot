#!/usr/bin/env python3
# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
Generates THIRD_PARTY_LICENSES.txt — the attribution document MIT/BSD/
Apache-2.0 require: reproducing each dependency's copyright notice and
licence text. Run from release.yml, after the pip and cargo trees have both
been resolved.

Inputs (both produced earlier in the release job):
  - pip:   `python -m piplicenses --format=json --with-license-file
            --no-license-path` piped to a file
  - cargo: `cargo about generate --format json -o <file>` (run in src-tauri/,
            using src-tauri/about.toml)

Usage:
    python -m piplicenses --format=json --with-authors --with-license-file \\
        --no-license-path > pip-licenses.json
    (cd src-tauri && cargo about generate --format json -o cargo-about.json)
    python scripts/generate_third_party_licenses.py \\
        --pip pip-licenses.json --cargo src-tauri/cargo-about.json \\
        --out THIRD_PARTY_LICENSES.txt
"""
import argparse
import json
from pathlib import Path

HEADER = """\
BixDot — Third-Party Licences
==============================

BixDot (c) 2026 DigiTech Business Pte. Ltd. is licensed under the Business
Source License 1.1 — see LICENSE in the project root.

BixDot is built on the open-source packages listed below. Each package
remains under its own licence; the copyright notice and licence text for
each is reproduced as required by its terms. This file is generated —
see scripts/generate_third_party_licenses.py.
"""

SEPARATOR = "\n" + "-" * 78 + "\n"


def _pip_section(pip_json: Path) -> str:
    packages = json.loads(pip_json.read_text(encoding="utf-8"))
    lines = ["\n\nPython dependencies\n===================\n"]
    for pkg in sorted(packages, key=lambda p: p["Name"].lower()):
        lines.append(SEPARATOR)
        lines.append(f"{pkg['Name']} {pkg['Version']}")
        lines.append(f"Licence: {pkg['License']}")
        if pkg.get("Author") and pkg["Author"] != "UNKNOWN":
            lines.append(f"Author: {pkg['Author']}")
        text = (pkg.get("LicenseText") or "").strip()
        if text and text != "UNKNOWN":
            lines.append("")
            lines.append(text)
    return "\n".join(lines)


def _cargo_section(cargo_json: Path) -> str:
    data = json.loads(cargo_json.read_text(encoding="utf-8"))
    lines = ["\n\nRust dependencies\n=================\n"]
    for licence in sorted(data["licenses"], key=lambda l: l["name"].lower()):
        crates = sorted(
            f"{u['crate']['name']} {u['crate']['version']}" for u in licence["used_by"]
        )
        lines.append(SEPARATOR)
        lines.append(f"Licence: {licence['name']} ({licence['id']})")
        lines.append(f"Used by: {', '.join(crates)}")
        text = (licence.get("text") or "").strip()
        if text:
            lines.append("")
            lines.append(text)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pip", type=Path, required=True)
    parser.add_argument("--cargo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    out = HEADER + _pip_section(args.pip) + _cargo_section(args.cargo) + "\n"
    args.out.write_text(out, encoding="utf-8")
    print(f"Wrote {args.out} ({len(out):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
