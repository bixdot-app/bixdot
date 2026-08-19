#!/usr/bin/env python3
# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BXD-005 — dependency licence gate for the Python (pip) tree.

Resolves the FULL transitive tree of currently-installed packages via
pip-licenses (it reads installed package metadata, so `pip install -r
requirements.txt` must already have happened in this environment) and fails
if any package's licence falls outside the allowlist in
docs/governance/03_GOVERNANCE.md section 4 AND has no reviewed exception in
docs/governance/LICENCE_ALLOWLIST.md.

BUSL-1.1 plus a paid commercial licence is incompatible with copyleft in the
dependency tree — see docs/governance/03_GOVERNANCE.md section 4 for why.

Usage:
    pip install -r requirements.txt
    pip install pip-licenses
    python scripts/check_licenses.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_DOC = ROOT / "docs" / "governance" / "LICENCE_ALLOWLIST.md"

# Mirrors docs/governance/03_GOVERNANCE.md section 4 exactly. Edit both together.
ALLOWED = {
    "MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC",
    "PSF-2.0", "HPND", "MIT-CMU", "Unlicense", "0BSD",
}

# Forbidden regardless of anything else — no exception overrides this.
FORBIDDEN_RE = re.compile(
    r"(?i)\b[AL]?GPL\b|GNU (LESSER |AFFERO )?GENERAL PUBLIC LICEN[SC]E"
    r"|\bSSPL\b|SERVER SIDE PUBLIC LICENSE|COMMONS CLAUSE|NON-?COMMERCIAL|-NC(\b|-)"
)

# Textual variants pip-licenses / importlib.metadata report for the SAME
# licence as one already in ALLOWED — normalisation, not a widened allowlist.
# Keys are matched case-insensitively (compared upper-cased).
SYNONYMS = {
    "MIT LICENSE": "MIT",
    "MIT-0": "MIT",                                    # MIT No Attribution
    "APACHE SOFTWARE LICENSE": "Apache-2.0",
    "APACHE LICENSE 2.0": "Apache-2.0",
    "APACHE 2.0": "Apache-2.0",
    "BSD LICENSE": "BSD-3-Clause",
    "3-CLAUSE BSD LICENSE": "BSD-3-Clause",
    "NEW BSD LICENSE": "BSD-3-Clause",
    "PYTHON SOFTWARE FOUNDATION LICENSE": "PSF-2.0",
    "HISTORICAL PERMISSION NOTICE AND DISCLAIMER (HPND)": "HPND",
    "ISC LICENSE (ISCL)": "ISC",
}

# Packages whose reported licence text does not literally normalise into
# ALLOWED but were reviewed and accepted — see docs/governance/
# LICENCE_ALLOWLIST.md for the human-readable justification each of these
# must also carry. Keys are lower-cased package names. Kept in sync with that
# doc by test_license_gate.py.
EXCEPTIONS = {
    "regex": "Apache-2.0 AND CNRI-Python",
    "numpy": "BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0",
    "pypdfium2": "BSD-3-Clause, Apache-2.0, dependency licenses",
    "tld": "MPL-1.1 OR GPL-2.0-only OR LGPL-2.1-or-later (MPL-1.1 option used)",
    "certifi": "Mozilla Public License 2.0 (MPL 2.0)",
}


def _normalise(token: str) -> str:
    token = token.strip()
    return SYNONYMS.get(token.upper(), token)


def _tokens(expr: str) -> list[str]:
    """Split a single (non- OR) licence expression on ';', ',' and ' AND '."""
    return [p.strip() for p in re.split(r"\s*(?:;|,|\bAND\b)\s*", expr) if p.strip()]


def _is_allowed(raw: str) -> bool:
    """
    True if every component of an AND-combination is allowed, or — for an
    OR-combination — at least one alternative is fully allowed (a licence
    choice only needs one acceptable option).
    """
    alternatives = re.split(r"\s+OR\s+", raw) if " OR " in raw else [raw]
    for alt in alternatives:
        tokens = _tokens(alt)
        if tokens and all(_normalise(t) in ALLOWED for t in tokens):
            return True
    return False


def get_packages() -> list[dict]:
    result = subprocess.run(
        [sys.executable, "-m", "piplicenses", "--format=json"],
        capture_output=True, text=True, check=True, shell=False,
    )
    return json.loads(result.stdout)


def check(packages: list[dict]) -> list[str]:
    failures = []
    for pkg in packages:
        name = pkg["Name"]
        raw = pkg["License"]

        if name.lower() in EXCEPTIONS:
            continue

        if _is_allowed(raw):
            continue

        if FORBIDDEN_RE.search(raw):
            failures.append(
                f"{name}: FORBIDDEN licence {raw!r} — see "
                f"docs/governance/03_GOVERNANCE.md section 4"
            )
        else:
            failures.append(
                f"{name}: licence {raw!r} is outside the allowlist and has no "
                f"reviewed exception in docs/governance/LICENCE_ALLOWLIST.md"
            )
    return failures


def check_exceptions_are_documented() -> list[str]:
    """Every EXCEPTIONS entry must have a matching row in the human-readable doc."""
    if not ALLOWLIST_DOC.exists():
        return [f"{ALLOWLIST_DOC.relative_to(ROOT)} does not exist"]
    text = ALLOWLIST_DOC.read_text(encoding="utf-8").lower()
    return [
        f"'{name}' is listed in scripts/check_licenses.py EXCEPTIONS but has no "
        f"row in {ALLOWLIST_DOC.relative_to(ROOT)}"
        for name in EXCEPTIONS
        if name.lower() not in text
    ]


def main() -> int:
    packages = get_packages()
    failures = check(packages) + check_exceptions_are_documented()

    if failures:
        print("Licence gate FAILED:\n")
        for f in failures:
            print(f"  - {f}")
        print(f"\n{len(packages)} packages scanned, {len(failures)} failure(s).")
        return 1

    print(f"Licence gate passed — {len(packages)} packages, all within allowlist or reviewed exceptions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
