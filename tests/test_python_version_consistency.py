# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BXD-008 — one Python version, declared once, used everywhere.

Before the fix, `ci.yml` and `daily-security-audit.yml` pinned Python 3.12
while `release.yml` built the shipped artefact on 3.11. A dependency floor or
CVE fix validated on 3.12 can resolve to a different, unscanned wheel on 3.11
— audits were green against an interpreter the product does not ship.

`.python-version` is now the single source of truth. These tests read the
workflow files as data (matching tests/test_workflow_audit.py's approach) so a
future edit that re-introduces a hardcoded, diverging version fails CI instead
of shipping a silent mismatch.
"""
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
PYTHON_VERSION_FILE = ROOT / ".python-version"
WORKFLOWS = [
    ROOT / ".github" / "workflows" / "ci.yml",
    ROOT / ".github" / "workflows" / "daily-security-audit.yml",
    ROOT / ".github" / "workflows" / "release.yml",
]


def test_python_version_file_exists_and_is_pinned():
    assert PYTHON_VERSION_FILE.is_file(), ".python-version must exist — BXD-008"
    version = PYTHON_VERSION_FILE.read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"3\.\d+", version), (
        f".python-version must pin major.minor exactly, got {version!r}"
    )


def _setup_python_steps(workflow: Path) -> list[dict]:
    spec = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    steps = []
    for job in spec.get("jobs", {}).values():
        for step in job.get("steps", []):
            if step.get("uses", "").startswith("actions/setup-python"):
                steps.append(step)
    return steps


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda p: p.name)
def test_every_setup_python_step_references_the_pinned_file(workflow):
    steps = _setup_python_steps(workflow)
    assert steps, f"{workflow.name} has no actions/setup-python step to check"
    for step in steps:
        with_block = step.get("with", {}) or {}
        assert with_block.get("python-version-file") == ".python-version", (
            f"{workflow.name} step {step.get('name')!r} does not read "
            f".python-version — got {with_block!r}. A hardcoded python-version "
            "here is exactly the drift BXD-008 fixed."
        )
        assert "python-version" not in with_block, (
            f"{workflow.name} step {step.get('name')!r} still hardcodes "
            "python-version alongside python-version-file"
        )


def test_no_workflow_hardcodes_a_python_version():
    """Belt-and-braces: no stray `python-version: "3.1x"` anywhere in the three."""
    pattern = re.compile(r"python-version\s*:\s*['\"]?3\.\d+")
    for workflow in WORKFLOWS:
        text = workflow.read_text(encoding="utf-8")
        assert not pattern.search(text), (
            f"{workflow.name} hardcodes a Python version outside .python-version"
        )
