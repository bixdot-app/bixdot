# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BXD-005 — dependency licence gate.

`scripts/check_licenses.py` resolves the full pip transitive tree and fails
on any licence outside docs/governance/03_GOVERNANCE.md section 4's
allowlist, unless the package has a reviewed exception in
docs/governance/LICENCE_ALLOWLIST.md. These tests exercise the classification
logic directly (no real pip-licenses subprocess — that would require the full
dependency tree to be installed and is covered separately by the CI job
itself), and cross-check the doc against the code so the two cannot drift.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_licenses as cl  # noqa: E402


def _pkg(name, license_str):
    return {"Name": name, "License": license_str}


# ─── Straightforward allowed licences ──────────────────────────────────────────

@pytest.mark.parametrize("license_str", [
    "MIT", "MIT License", "BSD-3-Clause", "BSD-2-Clause", "BSD License",
    "Apache-2.0", "Apache Software License", "PSF-2.0",
    "Python Software Foundation License", "MIT-CMU", "MIT-0", "Unlicense",
    "0BSD", "ISC",
])
def test_known_permissive_licenses_pass(license_str):
    assert cl.check([_pkg("somepkg", license_str)]) == []


@pytest.mark.parametrize("license_str", [
    "Apache Software License; BSD License",
    "Apache Software License; MIT License",
    "Apache-2.0 OR BSD-2-Clause",
    "Apache-2.0 OR BSD-3-Clause",
    "MIT OR Apache-2.0",
])
def test_multi_license_combinations_pass_when_every_option_or_component_allowed(license_str):
    assert cl.check([_pkg("somepkg", license_str)]) == []


# ─── Forbidden licences — no exception can rescue these ───────────────────────

@pytest.mark.parametrize("license_str", [
    "GPL-3.0", "GNU General Public License v3", "AGPL-3.0",
    "GNU Affero General Public License", "LGPL-2.1",
    "GNU Lesser General Public License", "SSPL-1.0",
    "Server Side Public License",
])
def test_forbidden_licenses_fail(license_str):
    failures = cl.check([_pkg("badpkg", license_str)])
    assert len(failures) == 1
    assert "badpkg" in failures[0]
    assert "FORBIDDEN" in failures[0]


def test_forbidden_license_cannot_be_rescued_by_a_permissive_and_partner():
    """AND means both apply — a permissive co-licence does not launder a GPL one."""
    failures = cl.check([_pkg("badpkg", "MIT AND GPL-3.0")])
    assert failures, "MIT AND GPL-3.0 must still fail — AND requires all components"


def test_gpl_option_in_or_choice_is_fine_if_a_permissive_alternative_exists():
    """This is exactly the tld case: choosing the permissive option is legitimate."""
    assert cl.check([_pkg("choosy", "MIT OR GPL-3.0")]) == []


# ─── Unknown / unrecognised — needs review, not an automatic pass ─────────────

def test_unrecognised_license_fails_without_an_exception():
    failures = cl.check([_pkg("mysterypkg", "Some Bespoke Licence 1.0")])
    assert len(failures) == 1
    assert "mysterypkg" in failures[0]
    assert "reviewed exception" in failures[0]


def test_unrecognised_license_passes_with_a_recorded_exception(monkeypatch):
    monkeypatch.setitem(cl.EXCEPTIONS, "mysterypkg", "reviewed for the test")
    assert cl.check([_pkg("mysterypkg", "Some Bespoke Licence 1.0")]) == []


# ─── The real EXCEPTIONS dict, exercised against its actual entries ───────────

@pytest.mark.parametrize("name,license_str", [
    ("regex", "Apache-2.0 AND CNRI-Python"),
    ("numpy", "BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0"),
    ("pypdfium2", "BSD-3-Clause, Apache-2.0, dependency licenses"),
    ("tld", "MPL-1.1 OR GPL-2.0-only OR LGPL-2.1-or-later"),
    ("certifi", "Mozilla Public License 2.0 (MPL 2.0)"),
])
def test_documented_exceptions_pass_with_their_real_reported_license(name, license_str):
    assert cl.check([_pkg(name, license_str)]) == []


def test_every_exception_has_a_documented_row():
    """docs/governance/LICENCE_ALLOWLIST.md and EXCEPTIONS must stay in sync."""
    assert cl.check_exceptions_are_documented() == []


def test_ddgs_and_icalendar_are_annotated_in_requirements():
    """
    BXD-005: these were the two production deps with no licence comment.
    ddgs is MIT, icalendar is BSD-2-Clause — confirmed via pip-licenses
    against the resolved tree.
    """
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip().startswith("ddgs"):
            assert "MIT" in line, "ddgs is missing its licence annotation"
        if line.strip().startswith("icalendar"):
            assert "BSD-2-Clause" in line, "icalendar is missing its licence annotation"
