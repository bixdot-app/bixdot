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


def test_unresolved_cve_is_explicitly_reverified_and_fails_the_job():
    """
    BXD-015: `--fix`'s own exit code is not trusted as the sole gate. A
    dedicated step must re-run pip-audit and a dedicated step must fail the
    job on its output — mirroring the bandit HIGH pattern above.
    """
    steps = _steps()
    verify = next((s for s in steps if s.get("id") == "pip_audit_verify"), None)
    assert verify is not None, "No pip-audit re-verification step (id: pip_audit_verify)"
    assert re.search(r"(?:^|[\s;&|])pip-audit\s", verify.get("run", "")), (
        "pip_audit_verify step does not actually invoke pip-audit"
    )

    assert any(
        "pip_audit_verify" in str(s.get("if", "")) and "unresolved" in str(s.get("if", ""))
        and "exit 1" in s.get("run", "")
        for s in steps
    ), "No step fails the job when pip_audit_verify reports an unresolved CVE — BXD-015"


def test_notification_step_runs_independent_of_job_failure():
    """
    BXD-015: a passing check does not mean clean, and GitHub's failure email
    only fires on job failure. A notification step must run via `if: always()`
    so a clean run still leaves a human-visible record.
    """
    steps = _steps()
    always_steps = [s for s in steps if str(s.get("if", "")).strip() == "always()"]
    assert always_steps, "No step runs unconditionally via `if: always()` — BXD-015"
    assert any("gh issue comment" in s.get("run", "") for s in always_steps), (
        "The always() step must actually post a notification, not just exist"
    )


def test_workflow_notes_60_day_schedule_inactivity_risk():
    """
    GitHub disables `schedule` triggers after 60 days of repository inactivity.
    This can't be tested at runtime, so the risk must be documented in the
    workflow itself where the next person touching this file will see it.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "60 days" in text and "inactiv" in text.lower(), (
        "The 60-day scheduled-workflow inactivity risk is not documented in "
        "daily-security-audit.yml — BXD-015"
    )


# ─── Permissions ───────────────────────────────────────────────────────────────

def test_workflow_can_open_pull_requests():
    assert _permissions().get("pull-requests") == "write", (
        "The audit job needs pull-requests: write to open a PR"
    )


def test_licence_gate_runs_isolated_from_dev_dependencies():
    """
    BXD-029: this job installs requirements-dev.txt earlier (for pytest),
    which pulls in semgrep/pyinstaller and their transitive deps
    (face, peewee, ...) — correctly dev-only tools that never ship. Running
    check_licenses.py against the job's shared interpreter fails the same
    production gate ci.yml passes, on packages ci.yml never even installs.
    The gate must install requirements.txt into an isolated venv instead.
    """
    gate_step = next(
        (s for s in _steps() if "check_licenses.py" in s.get("run", "")), None
    )
    assert gate_step is not None, "No step invokes scripts/check_licenses.py"
    run = gate_step["run"]
    assert re.search(r"\bvenv\b", run), (
        "The licence gate must install requirements.txt into an isolated venv, "
        "not reuse the job's shared environment polluted by requirements-dev.txt — BXD-029"
    )
    assert "requirements-dev.txt" not in run, (
        "The licence gate's isolated environment must not also install requirements-dev.txt — BXD-029"
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
