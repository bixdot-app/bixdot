# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Skill Sandbox Executor
Cross-platform subprocess sandbox (Windows + Mac + Linux).
"""
import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Any, Optional

# resource module is Unix-only
try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False  # Windows — resource limits handled differently

from core.agent.permissions import (
    Capability,
    PermissionStore,
    PermissionDeniedError,
)
from core.audit.logger import AuditLogger, AuditEvent
from core.config import settings


class SandboxViolationError(Exception):
    pass

class SandboxTimeoutError(Exception):
    pass


class SkillExecutor:
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

        self.audit.log(
            AuditEvent.SKILL_EXECUTED,
            {"capability": capability, "action": action,
             "params": self._sanitize_params(params)},
            user_id=user_id,
            skill_id=skill_id,
        )

        try:
            return self._run_sandboxed(skill_id, capability, action, params)
        except SandboxTimeoutError:
            self.audit.log(
                AuditEvent.SKILL_BLOCKED,
                {"reason": "timeout", "skill_id": skill_id},
                user_id=user_id,
                skill_id=skill_id,
            )
            raise

    def _run_sandboxed(self, skill_id, capability, action, params) -> Any:
        payload = json.dumps({
            "skill_id": skill_id,
            "capability": capability,
            "action": action,
            "params": params,
        })

        clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(Path(__file__).parent.parent.parent),
        }

        try:
            result = subprocess.run(
                [sys.executable, "-m", "core.sandbox.runner"],
                input=payload,
                capture_output=True,
                text=True,
                timeout=settings.sandbox_timeout_seconds,
                env=clean_env,
            )
        except subprocess.TimeoutExpired:
            raise SandboxTimeoutError(
                f"Skill '{skill_id}' exceeded timeout"
            )

        if result.returncode != 0:
            raise SandboxViolationError(
                f"Skill error: {result.stderr[:500]}"
            )

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            raise SandboxViolationError("Skill returned invalid output")

    @staticmethod
    def _sanitize_params(params: dict) -> dict:
        sensitive = {"password", "token", "secret", "api_key", "key", "auth"}
        return {
            k: "***" if any(s in k.lower() for s in sensitive) else v
            for k, v in params.items()
        }
