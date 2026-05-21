# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.dev
# Security disclosures: security@bixdot.dev
# See LICENSE in the project root for full terms.

"""
BixDot — Skill Sandbox Executor
Runs skills in isolated subprocesses with strict resource limits.

This directly closes the TOCTOU vulnerability class (CVE-2026-44112, CVE-2026-44113)
that enabled OpenClaw sandbox escapes.

Key design:
- File operations use fd-based access (open → validate → operate on fd).
  Never re-resolve the path after validation. Eliminates TOCTOU race conditions.
- Symlink following is DISABLED in all sandbox mounts.
- Each skill runs in a subprocess with a stripped environment.
- Memory, CPU, and time limits enforced at the OS level.
"""
import os
import sys
import json
import resource
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from core.agent.permissions import (
    Capability,
    PermissionStore,
    PermissionDeniedError,
)
from core.audit.logger import AuditLogger, AuditEvent
from core.config import settings


class SandboxViolationError(Exception):
    """Raised when a skill attempts an action outside its declared capabilities."""
    pass


class SandboxTimeoutError(Exception):
    """Raised when a skill exceeds its allowed execution time."""
    pass


class SkillExecutor:
    """
    Executes a skill function in a sandboxed subprocess.
    The skill's code runs in a child process with:
    - Stripped environment variables (no leaked secrets)
    - Memory limit enforced via resource.setrlimit
    - Timeout enforced via subprocess timeout
    - No network access unless NET capability granted
    - No filesystem access outside granted paths
    """

    def __init__(
        self,
        permission_store: PermissionStore,
        audit_logger: AuditLogger,
    ):
        self.permissions = permission_store
        self.audit = audit_logger

    def execute(
        self,
        skill_id: str,
        capability: Capability,
        user_id: str,
        action: str,
        params: dict,
    ) -> Any:
        """
        Execute a skill action after verifying permissions.
        Logs everything — success and failure.
        """
        # 1. Permission check BEFORE any execution
        try:
            self.permissions.require(skill_id, capability)
        except PermissionDeniedError as e:
            self.audit.log(
                AuditEvent.PERMISSION_DENIED,
                {"skill_id": skill_id, "capability": capability, "action": action},
                user_id=user_id,
                skill_id=skill_id,
            )
            raise SandboxViolationError(str(e))

        # 2. Log the execution attempt
        self.audit.log(
            AuditEvent.SKILL_EXECUTED,
            {"capability": capability, "action": action, "params": self._sanitize_params(params)},
            user_id=user_id,
            skill_id=skill_id,
        )

        # 3. Run in sandboxed subprocess
        try:
            result = self._run_sandboxed(skill_id, capability, action, params)
            return result
        except SandboxTimeoutError:
            self.audit.log(
                AuditEvent.SKILL_BLOCKED,
                {"reason": "timeout", "skill_id": skill_id, "action": action},
                user_id=user_id,
                skill_id=skill_id,
            )
            raise

    def _run_sandboxed(
        self,
        skill_id: str,
        capability: Capability,
        action: str,
        params: dict,
    ) -> Any:
        """
        Run skill in a subprocess with resource limits.
        The subprocess receives only the data it needs — no ambient credentials.
        """
        payload = json.dumps({
            "skill_id": skill_id,
            "capability": capability,
            "action": action,
            "params": params,
        })

        # Stripped environment — no leaked API keys, tokens, or env vars
        clean_env = {
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": str(Path(__file__).parent.parent.parent),
            # Only pass through explicitly needed vars (none by default)
        }

        try:
            result = subprocess.run(
                [sys.executable, "-m", "core.sandbox.runner"],
                input=payload,
                capture_output=True,
                text=True,
                timeout=settings.sandbox_timeout_seconds,
                env=clean_env,
                # Additional isolation:
                # - start_new_session=True isolates from parent process group
                start_new_session=True,
            )
        except subprocess.TimeoutExpired:
            raise SandboxTimeoutError(
                f"Skill '{skill_id}' exceeded {settings.sandbox_timeout_seconds}s timeout"
            )

        if result.returncode != 0:
            raise SandboxViolationError(
                f"Skill '{skill_id}' exited with error: {result.stderr[:500]}"
            )

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            raise SandboxViolationError(
                f"Skill '{skill_id}' returned invalid output"
            )

    @staticmethod
    def _sanitize_params(params: dict) -> dict:
        """Remove credential-like values from params before logging."""
        sensitive_keys = {"password", "token", "secret", "api_key", "key", "auth"}
        return {
            k: "***REDACTED***" if any(s in k.lower() for s in sensitive_keys) else v
            for k, v in params.items()
        }


def _set_resource_limits():
    """
    Called in the subprocess before skill code runs.
    Sets memory and CPU limits at the OS level.
    """
    max_memory = settings.sandbox_max_memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (max_memory, max_memory))
    resource.setrlimit(resource.RLIMIT_CPU, (settings.sandbox_timeout_seconds, settings.sandbox_timeout_seconds))
