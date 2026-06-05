# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Permission System
Agent starts with ZERO permissions. Every capability must be explicitly granted.

This is the core architectural fix for BixDot's biggest design flaw:
"The agent has the same rights as the user, connected to all their services."

Here, the agent has NO rights until the user grants them — one at a time,
with full visibility of what each grant allows.
"""
from enum import Enum
from typing import Optional
from datetime import datetime, timedelta, UTC
from pydantic import BaseModel


# ─── Capability Definitions ────────────────────────────────────────────────────

class Capability(str, Enum):
    """
    Every action the agent can take maps to a declared capability.
    Skills must declare required capabilities in their manifest.
    Any undeclared capability attempted at runtime = immediate sandbox kill.
    """
    # Filesystem
    FS_READ = "fs:read"               # Read files from granted paths only
    FS_WRITE = "fs:write"             # Write files to granted paths only
    FS_DELETE = "fs:delete"           # Delete files (requires explicit grant)

    # Network
    NET_OUTBOUND = "net:outbound"     # Make HTTP requests
    NET_FETCH = "net:fetch"           # Read-only web fetch

    # Execution
    EXEC_SHELL = "exec:shell"         # Run shell commands (allowlist only)
    EXEC_PYTHON = "exec:python"       # Run Python in sandbox

    # Data / Credentials
    CRED_READ = "cred:read"           # Read stored credentials
    CRED_WRITE = "cred:write"         # Store credentials

    # Integrations
    TELEGRAM_SEND = "telegram:send"   # Send Telegram messages
    DISCORD_SEND = "discord:send"     # Send Discord messages
    GITHUB_READ = "github:read"       # Read GitHub repos/issues
    GITHUB_WRITE = "github:write"     # Create PRs, issues (explicit)

    # Calendar
    CALENDAR_READ = "calendar:read"   # Read calendar events
    CALENDAR_WRITE = "calendar:write" # Create/modify calendar events

    # LLM
    LLM_CLOUD = "llm:cloud"          # Use cloud LLM (data leaves machine)
    LLM_LOCAL = "llm:local"          # Use local Ollama (always allowed)


# ─── Permission Grant Model ────────────────────────────────────────────────────

class PermissionGrant(BaseModel):
    capability: Capability
    skill_id: str                         # Which skill requested this
    granted_at: datetime
    expires_at: Optional[datetime] = None # None = session-scoped
    scope: Optional[dict] = None          # e.g. {"paths": ["/home/user/docs"]}
    granted_by: str                       # User ID who approved

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at


# ─── Permission Store ──────────────────────────────────────────────────────────

class PermissionStore:
    """
    In-memory permission store for the current session.
    Persisted to encrypted DB for named sessions.
    """

    def __init__(self):
        # {skill_id: {capability: PermissionGrant}}
        self._grants: dict[str, dict[Capability, PermissionGrant]] = {}

    def grant(
        self,
        skill_id: str,
        capability: Capability,
        granted_by: str,
        duration_minutes: Optional[int] = None,
        scope: Optional[dict] = None,
    ) -> PermissionGrant:
        """Grant a capability to a skill. Called only after user confirmation."""
        expires_at = None
        if duration_minutes:
            expires_at = datetime.now(UTC) + timedelta(minutes=duration_minutes)

        grant = PermissionGrant(
            capability=capability,
            skill_id=skill_id,
            granted_at=datetime.now(UTC),
            expires_at=expires_at,
            scope=scope,
            granted_by=granted_by,
        )

        if skill_id not in self._grants:
            self._grants[skill_id] = {}
        self._grants[skill_id][capability] = grant
        return grant

    def revoke(self, skill_id: str, capability: Optional[Capability] = None):
        """Revoke one capability or all capabilities for a skill."""
        if skill_id not in self._grants:
            return
        if capability is None:
            del self._grants[skill_id]  # Revoke all
        else:
            self._grants[skill_id].pop(capability, None)

    def check(self, skill_id: str, capability: Capability) -> bool:
        """
        Check if a skill has a valid, non-expired grant for a capability.
        Returns False for any ambiguity — never fails open.
        """
        skill_grants = self._grants.get(skill_id, {})
        grant = skill_grants.get(capability)
        if grant is None:
            return False
        if grant.is_expired:
            # Clean up expired grant
            self.revoke(skill_id, capability)
            return False
        return True

    def require(self, skill_id: str, capability: Capability):
        """
        Assert that a skill has permission. Raises PermissionDeniedError if not.
        Called inside the sandbox before every privileged operation.
        """
        if not self.check(skill_id, capability):
            raise PermissionDeniedError(
                f"Skill '{skill_id}' attempted '{capability}' without permission. "
                f"This action has been blocked and logged."
            )

    def list_grants(self, skill_id: Optional[str] = None) -> list[PermissionGrant]:
        """List all active grants, optionally filtered by skill."""
        grants = []
        targets = [skill_id] if skill_id else list(self._grants.keys())
        for sid in targets:
            for cap, grant in self._grants.get(sid, {}).items():
                if not grant.is_expired:
                    grants.append(grant)
        return grants


class PermissionDeniedError(Exception):
    """Raised when a skill attempts an action it has no permission for."""
    pass


# ─── Global permission store (per-session singleton) ──────────────────────────
_permission_store: Optional[PermissionStore] = None


def get_permission_store() -> PermissionStore:
    global _permission_store
    if _permission_store is None:
        _permission_store = PermissionStore()
    return _permission_store
