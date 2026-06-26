# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot pre-release validation script.

Runs before every tag to ensure the repo is in a releasable state:
- All version strings are consistent across all files
- Tests pass
- Lint + security gate: ruff (core/ and full repo), bandit, pip-audit all clean
- No uncommitted changes
- CHANGELOG has an entry for this version
- Release notes file exists

Tools are invoked via ``python -m`` so they work on Windows and Linux alike.

Usage:
    python scripts/pre_release.py              # validates against current version
    python scripts/pre_release.py 0.3.0        # validates against a specific version
"""

import re
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent
PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run(cmd: list) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return r.returncode, (r.stdout + r.stderr).strip()


def check_version_consistency(version: str) -> list[str]:
    """Verify version appears correctly in all required files."""
    failures = []
    checks = [
        (ROOT / "core" / "config.py",          f'version: str = "{version}"'),
        (ROOT / "src-tauri" / "tauri.conf.json", f'"version": "{version}"'),
        (ROOT / "src-tauri" / "Cargo.toml",     f'version = "{version}"'),
        (ROOT / "pyproject.toml",               f'version = "{version}"'),
        (ROOT / "README.md",                    f"version-{version}-green"),
        (ROOT / "CLAUDE.md",                    f"**Version:** v{version}"),
    ]
    for path, pattern in checks:
        if not path.exists():
            failures.append(f"{FAIL} {path.relative_to(ROOT)} — file not found")
        elif pattern not in _read(path):
            failures.append(f"{FAIL} {path.relative_to(ROOT)} — pattern not found: {pattern!r}")
        else:
            print(f"  {PASS} {path.relative_to(ROOT)}")
    return failures


def check_changelog(version: str) -> list[str]:
    text = _read(ROOT / "CHANGELOG.md")
    # Must be the FIRST version entry (newest at top)
    first_entry = re.search(r"## \[(\d+\.\d+\.\d+)\]", text)
    if not first_entry:
        return [f"{FAIL} CHANGELOG.md — no version entries found"]
    if first_entry.group(1) != version:
        return [f"{FAIL} CHANGELOG.md — first entry is [{first_entry.group(1)}], expected [{version}]"]
    print(f"  {PASS} CHANGELOG.md — [{version}] is the top entry")
    return []


def check_release_notes(version: str) -> list[str]:
    path = ROOT / ".github" / f"RELEASE_NOTES_v{version}.md"
    if not path.exists():
        return [f"{FAIL} .github/RELEASE_NOTES_v{version}.md — not found"]
    print(f"  {PASS} .github/RELEASE_NOTES_v{version}.md")
    return []


def check_tests() -> list[str]:
    print("  Running pytest...")
    code, output = _run([sys.executable, "-m", "pytest", "tests/", "-q", "--tb=line"])
    if code != 0:
        lines = [l for l in output.splitlines() if l.strip()][-5:]
        return [f"{FAIL} Tests failed:\n    " + "\n    ".join(lines)]
    # Extract summary line
    summary = [l for l in output.splitlines() if "passed" in l]
    print(f"  {PASS} Tests — {summary[-1].strip() if summary else 'all passed'}")
    return []


def check_lint() -> list[str]:
    """ruff must be clean on core/ (CI gate) AND the full repo (success bar)."""
    failures = []
    for target in ("core/", "."):
        code, output = _run([sys.executable, "-m", "ruff", "check", target])
        if code != 0:
            tail = "\n    ".join([ln for ln in output.splitlines() if ln.strip()][-6:])
            failures.append(f"{FAIL} ruff check {target} — issues:\n    {tail}")
        else:
            print(f"  {PASS} ruff check {target}")
    return failures


def check_bandit() -> list[str]:
    """bandit must report no medium+ severity issues in core/ (matches CI flags)."""
    code, output = _run([
        sys.executable, "-m", "bandit", "-r", "core/",
        "-ll", "-ii", "--skip", "B101,B603,B607", "-q",
    ])
    if code != 0:
        tail = "\n    ".join([ln for ln in output.splitlines() if ln.strip()][-8:])
        return [f"{FAIL} bandit (medium+ severity) — issues:\n    {tail}"]
    print(f"  {PASS} bandit — no medium+ severity issues")
    return []


def check_pip_audit() -> list[str]:
    """pip-audit must find zero CVEs (scoped to requirements.txt — never bare)."""
    code, output = _run([sys.executable, "-m", "pip_audit", "-r", "requirements.txt"])
    if code != 0:
        tail = "\n    ".join([ln for ln in output.splitlines() if ln.strip()][-8:])
        return [f"{FAIL} pip-audit — CVE(s) or error:\n    {tail}"]
    print(f"  {PASS} pip-audit — zero CVEs")
    return []


def check_clean_working_tree() -> list[str]:
    code, output = _run(["git", "status", "--porcelain"])
    if output:
        return [f"{WARN} Uncommitted changes present (commit before tagging):\n    {output[:200]}"]
    print(f"  {PASS} Working tree clean")
    return []


def check_tag_does_not_exist(version: str) -> list[str]:
    code, output = _run(["git", "tag", "-l", f"v{version}"])
    if output.strip():
        return [f"{FAIL} Tag v{version} already exists"]
    print(f"  {PASS} Tag v{version} does not yet exist")
    return []


def get_current_version() -> str:
    text = _read(ROOT / "core" / "config.py")
    m = re.search(r'version: str = "([^"]+)"', text)
    if not m:
        raise RuntimeError("Cannot detect current version from core/config.py")
    return m.group(1)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    version = args[0] if args else get_current_version()

    print(f"\nPre-release validation for v{version}\n")

    failures = []
    warnings = []

    print("Version consistency:")
    failures += check_version_consistency(version)

    print("\nChangelog:")
    failures += check_changelog(version)

    print("\nRelease notes:")
    failures += check_release_notes(version)

    print("\nTest suite:")
    failures += check_tests()

    print("\nLint + security gate:")
    failures += check_lint()
    failures += check_bandit()
    failures += check_pip_audit()

    print("\nGit state:")
    w = check_clean_working_tree()
    for item in w:
        if item.startswith(WARN):
            warnings.append(item)
            print(f"  {item}")
        else:
            failures.append(item)
    failures += check_tag_does_not_exist(version)

    print()
    if failures:
        print(f"BLOCKED — {len(failures)} issue(s) must be fixed before releasing:\n")
        for f in failures:
            print(f"  {f}")
        sys.exit(1)
    elif warnings:
        print(f"READY WITH WARNINGS — {len(warnings)} warning(s):\n")
        for w in warnings:
            print(f"  {w}")
        print(f"\nTo release:\n  git tag v{version} && git push origin v{version}")
    else:
        print("READY — all checks passed.")
        print(f"\nTo release:\n  git tag v{version} && git push origin v{version}")


if __name__ == "__main__":
    main()
