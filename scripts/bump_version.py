# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot version bump script.

Atomically updates the version string across all 10 required files.
Performs a dry-run preview first, then applies on confirmation.

Usage:
    python scripts/bump_version.py 0.2.0 0.3.0
    python scripts/bump_version.py 0.2.0 0.3.0 --yes   # skip confirmation
"""

import sys
import re
from pathlib import Path
from datetime import date

ROOT = Path(__file__).parent.parent


def _replace_in_file(path: Path, old: str, new: str) -> tuple[bool, int]:
    """Replace all occurrences of old with new in a file. Returns (changed, count)."""
    text = path.read_text(encoding="utf-8")
    new_text = text.replace(old, new)
    count = text.count(old)
    if count:
        path.write_text(new_text, encoding="utf-8")
    return count > 0, count


def _build_replacements(old: str, new: str) -> list[tuple[Path, str, str, str]]:
    """
    Return list of (file_path, find_string, replace_string, description) tuples.
    All replacements use literal string matching — no regex.
    """
    today = date.today().isoformat()
    return [
        # ── Core version files ─────────────────────────────────────────────────
        (
            ROOT / "core" / "config.py",
            f'version: str = "{old}"',
            f'version: str = "{new}"',
            "core/config.py — version field",
        ),
        (
            ROOT / "src-tauri" / "tauri.conf.json",
            f'"version": "{old}"',
            f'"version": "{new}"',
            "src-tauri/tauri.conf.json — version field",
        ),
        (
            ROOT / "src-tauri" / "Cargo.toml",
            f'version = "{old}"',
            f'version = "{new}"',
            "src-tauri/Cargo.toml — version field",
        ),
        (
            ROOT / "pyproject.toml",
            f'version = "{old}"',
            f'version = "{new}"',
            "pyproject.toml — version field",
        ),
        # ── Documentation / marketing ──────────────────────────────────────────
        (
            ROOT / "README.md",
            f"version-{old}-green",
            f"version-{new}-green",
            "README.md — version badge",
        ),
        (
            ROOT / "README.md",
            f"/releases/tag/v{old}",
            f"/releases/tag/v{new}",
            "README.md — release tag URL",
        ),
        (
            ROOT / "README.md",
            f"Download BixDot v{old}",
            f"Download BixDot v{new}",
            "README.md — download link text",
        ),
        (
            ROOT / "CLAUDE.md",
            f"**Version:** v{old}",
            f"**Version:** v{new}",
            "CLAUDE.md — version line",
        ),
        (
            ROOT / "CLAUDE.md",
            f"## Current Status — v{old} ✅ SHIPPED",
            f"## Current Status — v{new} ✅ SHIPPED",
            "CLAUDE.md — status table header",
        ),
        (
            ROOT / "CLAUDE.md",
            f"RELEASE_NOTES_v{old}.md",
            f"RELEASE_NOTES_v{new}.md",
            "CLAUDE.md — release notes filename",
        ),
        (
            ROOT / "CLAUDE.md",
            f"*Last updated: {_get_claude_md_date()} | v{old}*",
            f"*Last updated: {today} | v{new}*",
            "CLAUDE.md — last updated footer",
        ),
    ]


def _get_claude_md_date() -> str:
    """Extract the current date from CLAUDE.md's last-updated footer."""
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    m = re.search(r"\*Last updated: (\d{4}-\d{2}-\d{2})", text)
    return m.group(1) if m else date.today().isoformat()


def _get_current_version() -> str:
    """Read the authoritative version from core/config.py."""
    text = (ROOT / "core" / "config.py").read_text(encoding="utf-8")
    m = re.search(r'version: str = "([^"]+)"', text)
    if not m:
        raise RuntimeError("Could not find version in core/config.py")
    return m.group(1)


def main():
    args = sys.argv[1:]
    skip_confirm = "--yes" in args
    args = [a for a in args if not a.startswith("--")]

    if len(args) == 1:
        old = _get_current_version()
        new = args[0]
        print(f"Auto-detected current version: {old}")
    elif len(args) == 2:
        old, new = args
    else:
        print(__doc__)
        sys.exit(1)

    # Validate semver-ish format
    if not re.match(r"^\d+\.\d+\.\d+$", new):
        print(f"ERROR: '{new}' is not a valid version (expected X.Y.Z)")
        sys.exit(1)

    print(f"\nBumping version: {old} -> {new}\n")

    replacements = _build_replacements(old, new)

    # Dry-run preview
    print("Files to update:")
    all_found = True
    for path, find, replace, desc in replacements:
        if not path.exists():
            print(f"  [MISSING]  {desc} ({path.relative_to(ROOT)})")
            all_found = False
            continue
        count = path.read_text(encoding="utf-8").count(find)
        if count:
            print(f"  [OK]  {count}x  {desc}")
        else:
            print(f"  [--]  NOT FOUND  {desc}  (pattern: {find!r})")

    if not all_found:
        print("\nSome files are missing. Aborting.")
        sys.exit(1)

    print()
    if not skip_confirm:
        answer = input(f"Apply {len(replacements)} replacements? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    # Apply
    total = 0
    for path, find, replace, desc in replacements:
        changed, count = _replace_in_file(path, find, replace)
        if changed:
            total += count
            print(f"  [UPDATED] {desc}")

    print(f"\n[DONE] {total} occurrences replaced.")
    print("\nNext steps:")
    print(f"  1. Create .github/RELEASE_NOTES_v{new}.md")
    print(f"  2. Add ## [{new}] section to CHANGELOG.md")
    print("  3. Update docs/THREAT_MODEL.md version header")
    print("  4. Update bixdot-website/index.html (hero badge + all 6 download links)")
    print(f"  5. git add -A && git commit -m 'chore: bump version to v{new}'")
    print(f"  6. git tag v{new} && git push origin main v{new}")


if __name__ == "__main__":
    main()
