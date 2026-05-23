# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
BixDot — Terminal Skill Routes

POST /terminal/run     — execute a sandboxed command
GET  /terminal/allowed — list allowed executables
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth.middleware import require_auth
from core.audit.logger import get_audit_logger, AuditEvent
from core.skills.terminal.sandbox import run_command, ALLOWED_EXECUTABLES

router = APIRouter(prefix="/terminal", tags=["terminal"])


class RunRequest(BaseModel):
    command: str
    cwd: str | None = None


class RunResponse(BaseModel):
    ok: bool
    command: str
    stdout: str
    stderr: str
    exit_code: int
    blocked: str | None


@router.post("/run", response_model=RunResponse)
async def terminal_run(req: RunRequest, user=Depends(require_auth)):
    """Execute a sandboxed, allowlisted terminal command."""
    audit = get_audit_logger()
    audit.log(
        AuditEvent.AGENT_TOOL_CALL,
        {"tool": "terminal", "command": req.command, "cwd": req.cwd},
        user_id=user.sub,
    )

    result = run_command(req.command, req.cwd)

    # Log blocked attempts
    if result["blocked"]:
        audit.log(
            AuditEvent.AGENT_TOOL_CALL,
            {"tool": "terminal", "blocked": result["blocked"], "command": req.command},
            user_id=user.sub,
        )

    return RunResponse(
        ok        = result["ok"],
        command   = result["command"],
        stdout    = result["stdout"],
        stderr    = result["stderr"],
        exit_code = result["exit"],
        blocked   = result["blocked"],
    )


@router.get("/allowed")
async def list_allowed(user=Depends(require_auth)):
    """Return the list of allowed executables."""
    return {"allowed": sorted(ALLOWED_EXECUTABLES)}
