# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Skill Execution Sandbox

Third-party skills run as isolated child processes. The host never imports or
calls skill code directly. Communication is JSON over stdin/stdout.

Protocol:
  stdin:  {"capabilities": [...], "input": {...}}   (read once by the skill)
  stdout: {"success": bool, "output": ..., "error": ...}   (written once)
  stderr: captured for audit only — never returned to the user

Security:
  - shell=False always
  - env stripped to a minimal safe set — no secrets, no JWT, no DB paths
  - 30s wall-clock timeout, then the process is killed
  - stdout capped at 1MB — anything larger is rejected
"""
import json
import os
import sys
import subprocess
from pathlib import Path

SKILL_TIMEOUT_SECONDS = 30
MAX_OUTPUT_BYTES = 1_000_000  # 1MB


def _safe_env(granted_capabilities: list[str]) -> dict:
    """
    Build a minimal environment for the child. Constructed from scratch so no
    parent-process secret (JWT secret, DB path, API keys) can leak in.
    """
    # A minimal PATH is enough; we invoke the interpreter by absolute path.
    if os.name == "nt":
        default_path = os.environ.get("SystemRoot", r"C:\Windows") + r"\System32"
    else:
        default_path = "/usr/local/bin:/usr/bin:/bin"
    interp_dir = str(Path(sys.executable).parent)
    return {
        "PATH": interp_dir + os.pathsep + default_path,
        "HOME": str(Path.home()),
        "PYTHONPATH": "",
        "PYTHONIOENCODING": "utf-8",
        # The ONLY grant vector — the skill reads this to know what it may do.
        "BIXDOT_CAPABILITIES": json.dumps(granted_capabilities),
    }


def run_skill(
    entry_path,
    granted_capabilities: list[str],
    input_data: dict,
    timeout: int = SKILL_TIMEOUT_SECONDS,
) -> dict:
    """
    Execute a skill in a sandboxed subprocess and return its parsed result.
    Always returns a dict with at least {"success": bool}; never raises.
    """
    entry_path = Path(entry_path)
    if not entry_path.exists():
        return {"success": False, "error": "Skill entry file not found."}

    stdin_payload = json.dumps({
        "capabilities": granted_capabilities,
        "input": input_data,
    }).encode("utf-8")

    try:
        result = subprocess.run(
            [sys.executable, str(entry_path)],   # absolute interpreter, no shell
            input=stdin_payload,
            capture_output=True,
            timeout=timeout,
            env=_safe_env(granted_capabilities),
            shell=False,                          # NEVER True
            cwd=str(entry_path.parent),
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Skill timed out after {timeout} seconds"}
    except Exception as e:  # pragma: no cover - defensive
        return {"success": False, "error": f"Skill failed to run: {e}"}

    stdout = result.stdout or b""
    if len(stdout) > MAX_OUTPUT_BYTES:
        return {
            "success": False,
            "error": "Skill output exceeded the 1MB limit and was rejected.",
            "truncated": True,
        }

    try:
        return json.loads(stdout.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {"success": False, "error": "Skill returned invalid JSON."}
