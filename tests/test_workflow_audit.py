# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BXD-003 — the nightly security audit must never author production code.

Governance rule (docs/governance/03_GOVERNANCE.md section 2):
    "No automation pushes to main. Bots open pull requests."

These tests read the workflow as data, so a future edit that reintroduces a
direct push, an auto-fix over core/, or a swallowed CVE fails CI rather than
shipping silently overnight.
"""
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "daily-security-audit.yml"


def _steps() -> list[dict]:
    """Every step of the audit job, in declaration order."""
    spec = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return spec["jobs"]["audit"]["steps"]


def _runs() -> list[str]:
    return [s.get("run", "") for s in _steps()]


def _permissions() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["permissions"]


# ─── The push ──────────────────────────────────────────────────────────────────

def test_audit_job_never_pushes_to_main():
    """The bot may push a branch. It may never push the default branch."""
    for run in _runs():
        assert not re.search(r"git\s+push\s+\S*\s*origin\s+main\b", run), (
            "daily-security-audit.yml pushes directly to main — BXD-003"
        )


def test_audit_job_opens_a_pull_request():
    """Fixes reach main through review, or they do not reach main."""
    assert any("gh pr create" in run for run in _runs()), (
        "The audit job must open a PR instead of committing to main"
    )


def test_audit_branch_is_dated_and_namespaced():
    """PRs land on security/audit-YYYY-MM-DD, never on a long-lived branch."""
    assert any(re.search(r"security/audit-", run) for run in _runs()), (
        "The audit job must work on a security/audit-<date> branch"
    )


# ─── Never author product code ─────────────────────────────────────────────────

def test_audit_job_does_not_autofix_core():
    """
    `ruff --fix` is not always semantically neutral — removing an 'unused'
    import removes its side effects. Lint is reported, never auto-applied.
    """
    for run in _runs():
        assert not re.search(r"ruff\s+check[^\n]*--fix", run), (
            "The audit job auto-edits source with `ruff --fix` — BXD-003"
        )


def test_audit_job_only_stages_dependency_manifests():
    """The bot's commit surface is dependency pins — never core/, tests/, docs/."""
    for run in _runs():
        for match in re.finditer(r"git\s+add\s+([^\n]+)", run):
            staged = match.group(1).split("#")[0].replace("|| true", "").split()
            forbidden = {"core/", "tests/", "scripts/", "docs/", "ruff.toml"}
            assert not (forbidden & set(staged)), (
                f"The audit job stages product code: {sorted(forbidden & set(staged))}"
            )


# ─── Gates ─────────────────────────────────────────────────────────────────────

def test_audit_job_runs_tests_before_commit():
    """No green tests, no PR. A dependency bump is a code change."""
    runs = _runs()
    pytest_at = next((i for i, r in enumerate(runs) if re.search(r"\bpytest\b", r)), None)
    commit_at = next((i for i, r in enumerate(runs) if re.search(r"git\s+commit", r)), None)

    assert pytest_at is not None, "The audit job never runs the test suite — BXD-003"
    assert commit_at is not None, "Expected a commit step to exist"
    assert pytest_at < commit_at, "The test suite must run BEFORE anything is committed"


def test_pip_audit_failure_is_not_swallowed():
    """
    An unresolvable CVE must fail the job, not produce a green run.

    Matches `pip-audit` only as an invoked command (trailing whitespace), so
    the `pip-audit-report.json` filename is not mistaken for a call. The
    `--dry-run` preview is informational and may stay soft-failed.
    """
    invocation = re.compile(r"(?:^|[\s;&|])pip-audit\s")
    for run in _runs():
        for line in run.splitlines():
            if line.lstrip().startswith("#"):
                continue  # shell comment, not a command
            if invocation.search(line) and "--dry-run" not in line:
                assert "|| true" not in line, (
                    f"pip-audit failure is swallowed by `|| true`: {line.strip()} — BXD-003/BXD-015"
                )


def test_bandit_high_still_fails_the_job():
    """The one failure condition that already worked stays working."""
    spec = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = spec["jobs"]["audit"]["steps"]
    assert any(
        "bandit_issues" in str(s.get("if", "")) and "exit 1" in s.get("run", "")
        for s in steps
    ), "The bandit HIGH severity gate was removed"


# ─── Permissions ───────────────────────────────────────────────────────────────

def test_workflow_can_open_pull_requests():
    assert _permissions().get("pull-requests") == "write", (
        "The audit job needs pull-requests: write to open a PR"
    )


def test_contents_permission_is_documented_as_branch_only():
    """
    Creating a commit requires contents: write — no token scope avoids that.
    The control is that the bot pushes only to security/audit-*, backed by
    branch protection on main (docs/governance/03_GOVERNANCE.md section 2).
    Assert the justification is present so the scope is never widened silently.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r"contents:\s*write", text)
    assert "branch" in text.lower().split("contents: write")[1][:200].lower(), (
        "contents: write must carry an inline comment scoping it to branch pushes"
    )
