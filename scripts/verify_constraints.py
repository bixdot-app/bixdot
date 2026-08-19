#!/usr/bin/env python3
# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Constraint Verification

Runs every control in docs/governance/02_SECURITY_CONTROLS.md (implemented
as tests/test_constraints.py) and prints the enforcement report that
document specifies, grouped by control family. This is the artefact to
attach to an enterprise security questionnaire or paste into a release.

Runs entirely offline: it executes tests/test_constraints.py, which reads
source, config, and workflow files as data and never issues a live network
call (no live pip-audit / cargo-audit / npm-audit run — those need network
for their advisory databases; this script instead verifies the CI wiring
that runs them is structurally correct — see the module docstring in
tests/test_constraints.py).

Usage:
    python scripts/verify_constraints.py

Exit code: 0 if every control passes, 1 otherwise. This is also wired as a
required step in ci.yml and as a release gate in release.yml — a version
that fails this script does not ship.
"""
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_FILE = ROOT / "tests" / "test_constraints.py"

# Group label -> (regex matching that group's control ids, human name).
# Order matters for the printed report.
GROUPS = [
    ("C-1", re.compile(r"^C_1_\d+$"), "Local-first"),
    ("C-2", re.compile(r"^C_2_\d+$"), "Loopback only"),
    ("C-3", re.compile(r"^C_3_\d+$"), "Mandatory auth"),
    ("C-4", re.compile(r"^C_4_\d+$"), "Zero default permissions"),
    ("C-5", re.compile(r"^C_5_\d+$"), "Tamper-evident audit"),
    ("C-6", re.compile(r"^C_6_\d+$"), "No shell"),
    ("S",   re.compile(r"^S_\d+$"),   "Supply chain"),
]

# Matches the C-x-y / S-x control id at the start of a test function name,
# e.g. "test_C_1_6_all_record_net_kinds_registered" -> "C_1_6",
# "test_S_3_cargo_audit_gates_build" -> "S_3".
CONTROL_ID_RE = re.compile(r"^test_(C_\d+_\d+|S_\d+)_")


def _control_id(nodeid: str) -> str | None:
    """Extract the control id from a pytest nodeid's function name, ignoring parametrisation."""
    func_name = nodeid.split("::")[-1].split("[")[0]
    m = CONTROL_ID_RE.match(func_name)
    return m.group(1) if m else None


def run_tests() -> dict[str, bool]:
    """
    Run tests/test_constraints.py in-process via pytest's Python API and
    return {control_id: all_passed}.

    A small local plugin collects each test's outcome via the
    pytest_runtest_logreport hook — no --report-log (that flag moved out of
    pytest core into the separate pytest-reportlog plugin, which is not a
    project dependency) and no dependency on pytest's terminal output
    format, which is exactly the kind of thing that breaks silently across
    pytest versions.
    """
    import pytest

    outcomes: dict[str, bool] = defaultdict(lambda: True)
    seen: set[str] = set()

    class _Collector:
        def pytest_runtest_logreport(self, report):
            if report.when != "call":
                return
            control_id = _control_id(report.nodeid)
            if control_id is None:
                return
            seen.add(control_id)
            outcomes[control_id] = outcomes[control_id] and report.passed

    pytest.main(
        [str(TEST_FILE), "-q", "--tb=line", "-p", "no:cacheprovider"],
        plugins=[_Collector()],
    )

    return {cid: outcomes[cid] for cid in seen}


def main() -> int:
    if not TEST_FILE.is_file():
        print(f"FATAL: {TEST_FILE} does not exist.", file=sys.stderr)
        return 1

    results = run_tests()
    if not results:
        print(
            "FATAL: tests/test_constraints.py produced no recognisable "
            "C-x.y / S-x results — the report log parser or the test file "
            "itself may be broken.",
            file=sys.stderr,
        )
        return 1

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        from core.config import settings
        version = settings.version
    except Exception:
        version = "unknown"

    print(f"BixDot Constraint Verification — v{version} — {timestamp}")

    all_ok = True
    total_pass = total_all = 0
    for label, pattern, name in GROUPS:
        ids = sorted(
            (cid for cid in results if pattern.match(cid)),
            key=lambda c: [int(x) for x in c.split("_")[1:]],
        )
        passed = sum(1 for cid in ids if results[cid])
        total = len(ids)
        total_pass += passed
        total_all += total
        status = "PASS" if passed == total and total > 0 else "FAIL"
        if status == "FAIL":
            all_ok = False
        label_text = f"{label} {name}"
        dots = "." * max(1, 34 - len(label_text))
        print(f"{label_text} {dots} {passed}/{total}  {status}")
        if status == "FAIL":
            for cid in ids:
                if not results[cid]:
                    print(f"    ✗ {cid.replace('_', '-', 1).replace('_', '.')}")

    print()
    if all_ok and total_pass == total_all:
        print("ALL CONSTRAINTS VERIFIED")
        return 0
    else:
        print(f"CONSTRAINT VERIFICATION FAILED — {total_pass}/{total_all} controls passing")
        return 1


if __name__ == "__main__":
    sys.exit(main())
