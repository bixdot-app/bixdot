# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Agent Routes
POST /agent/chat      — send a message, get a response
GET  /agent/sessions  — list active sessions
POST /agent/sessions  — create a new session
DELETE /agent/sessions/{id} — end a session
"""
import uuid
from typing import Literal, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from core.auth.middleware import require_auth
from core.agent.runtime import AgentRuntime, AgentSession, AgentResponse
from core.agent.permissions import get_permission_store, Capability
from core.agent.model_caps import ModelMode, classify_model
from core.audit.logger import get_audit_logger
from core.agent.session_store import (
    get_session_store,
    save_session,
    load_session,
    load_user_sessions,
    delete_session,
    session_belongs_to,
)

router = APIRouter(prefix="/agent", tags=["agent"])

# Initialise SQLite session store on first import
get_session_store()


# ─── Request / Response Models ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str


class NewSessionRequest(BaseModel):
    llm_backend: Literal["claude", "ollama"] = "ollama"  # Local-first default
    model: Optional[str] = None  # Override the persisted model for this session


class SessionResponse(BaseModel):
    session_id: str
    llm_backend: str
    message_count: int
    model_mode: str = ModelMode.FULL_AGENT.value


class ModelInfo(BaseModel):
    name: str
    size_gb: float
    mode: str
    supports_vision: bool
    is_cloud: bool
    is_default: bool


class PermissionGrantRequest(BaseModel):
    capability: str
    skill_id: str = "builtin"


class SetModelRequest(BaseModel):
    model: str


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: NewSessionRequest,
    user=Depends(require_auth),
):
    """Create a new agent session."""
    import httpx
    from core.config import settings as cfg
    from core.storage.db import get_setting

    # Resolve model_mode from Ollama capabilities
    model_mode = ModelMode.FULL_AGENT
    if request.llm_backend == "claude":
        model_mode = ModelMode.CLOUD
    else:
        model_name = request.model or get_setting("local_model") or cfg.local_model
        try:
            async with httpx.AsyncClient(base_url=cfg.ollama_url, timeout=5) as client:
                r = await client.get("/api/tags")
                r.raise_for_status()
                for m in r.json().get("models", []):
                    if m["name"] == model_name:
                        model_mode = classify_model(m.get("capabilities", []))
                        break
        except Exception:
            pass  # Ollama unreachable — default FULL_AGENT

    if model_mode == ModelMode.CLOUD:
        raise HTTPException(
            status_code=400,
            detail="Cloud models are blocked in local-first mode. "
                   "Use a local Ollama model.",
        )

    session_id = str(uuid.uuid4())
    session = AgentSession(
        session_id=session_id,
        user_id=user.sub,
        llm_backend=request.llm_backend,
        model_mode=model_mode.value,
    )
    save_session(session)  # persisted to SQLite

    return SessionResponse(
        session_id=session_id,
        llm_backend=request.llm_backend,
        message_count=0,
        model_mode=model_mode.value,
    )


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(user=Depends(require_auth)):
    """List all sessions for the current user (loaded from SQLite)."""
    sessions = load_user_sessions(user.sub)
    return [
        SessionResponse(
            session_id=s.session_id,
            llm_backend=s.llm_backend,
            message_count=len(s.messages),
        )
        for s in sessions
    ]


@router.delete("/sessions/{session_id}")
async def end_session(session_id: str, user=Depends(require_auth)):
    """End and delete a session."""
    if not session_belongs_to(session_id, user.sub):
        raise HTTPException(status_code=404, detail="Session not found")
    delete_session(session_id)
    return {"status": "ended", "session_id": session_id}


@router.post("/chat", response_model=AgentResponse)
async def chat(
    request: ChatRequest,
    user=Depends(require_auth),
):
    """
    Send a message to the agent and receive a response.
    Session is loaded from SQLite, updated after each message.
    """
    session = load_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Create a session first.")
    if session.user_id != user.sub:
        raise HTTPException(status_code=403, detail="Not your session")

    runtime = AgentRuntime()
    response = await runtime.run(session, request.message)

    # Persist updated session (with new messages) back to SQLite
    save_session(session)

    return response


@router.post("/permissions/grant")
async def grant_permission(
    request: PermissionGrantRequest,
    user=Depends(require_auth),
):
    """
    Grant a capability permission to a skill.
    Called when user approves a permission prompt in the UI.
    """
    try:
        capability = Capability(request.capability)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown capability: {request.capability}. "
                   f"Valid: {[c.value for c in Capability]}"
        )

    store = get_permission_store()
    grant = store.grant(
        skill_id=request.skill_id,
        capability=capability,
        granted_by=user.sub,
    )

    audit = get_audit_logger()
    from core.audit.logger import AuditEvent
    audit.log(
        AuditEvent.PERMISSION_GRANTED,
        {"capability": capability.value, "skill_id": request.skill_id},
        user_id=user.sub,
    )

    return {
        "granted": True,
        "capability": capability.value,
        "skill_id": request.skill_id,
        "granted_at": grant.granted_at.isoformat(),
    }


@router.get("/permissions")
async def list_permissions(user=Depends(require_auth)):
    """List all active permission grants."""
    store = get_permission_store()
    grants = store.list_grants()
    return [
        {
            "capability": g.capability.value,
            "skill_id": g.skill_id,
            "granted_at": g.granted_at.isoformat(),
            "expires_at": g.expires_at.isoformat() if g.expires_at else None,
        }
        for g in grants
    ]


@router.delete("/permissions/{capability}")
async def revoke_permission(
    capability: str,
    user=Depends(require_auth),
):
    """Revoke a specific capability permission."""
    try:
        cap = Capability(capability)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown capability: {capability}")

    store = get_permission_store()
    store.revoke("builtin", cap)

    audit = get_audit_logger()
    from core.audit.logger import AuditEvent
    audit.log(
        AuditEvent.PERMISSION_REVOKED,
        {"capability": capability},
        user_id=user.sub,
    )
    return {"revoked": True, "capability": capability}


@router.get("/models")
async def list_models(user=Depends(require_auth)):
    """
    Query Ollama for locally installed models, enriched with capability metadata.
    EMBEDDING models are filtered out. Results sorted: default first, then by name.
    Returns empty list gracefully if Ollama is not running.
    """
    import httpx
    from core.config import settings as cfg
    from core.storage.db import get_setting

    default_model = get_setting("local_model") or cfg.local_model
    try:
        async with httpx.AsyncClient(base_url=cfg.ollama_url, timeout=5) as client:
            r = await client.get("/api/tags")
            r.raise_for_status()
            raw_models = r.json().get("models", [])
    except Exception:
        return {"models": []}

    infos: list[ModelInfo] = []
    for m in raw_models:
        caps = m.get("capabilities", [])
        mode = classify_model(caps)
        if mode == ModelMode.EMBEDDING:
            continue  # hide embedding models from the chat picker
        infos.append(ModelInfo(
            name=m["name"],
            size_gb=round(m.get("size", 0) / 1e9, 2),
            mode=mode.value,
            supports_vision="vision" in caps,
            is_cloud=False,
            is_default=(m["name"] == default_model),
        ))

    # Sort: default model first, then alphabetically
    infos.sort(key=lambda x: (not x.is_default, x.name))
    return {"models": [i.model_dump() for i in infos]}


@router.get("/model")
async def get_model(user=Depends(require_auth)):
    """Return the currently selected local model (persistent setting)."""
    from core.storage.db import get_setting
    from core.config import settings as cfg
    model = get_setting("local_model") or cfg.local_model
    return {"model": model}


@router.post("/model")
async def set_model(request: SetModelRequest, user=Depends(require_auth)):
    """Persist the selected model so it survives restarts."""
    from core.storage.db import set_setting
    model = request.model.strip()
    if not model:
        raise HTTPException(status_code=400, detail="Model name cannot be empty")
    set_setting("local_model", model)
    return {"model": model}


@router.get("/audit")
async def get_audit_log(
    limit: int = 50,
    user=Depends(require_auth),
):
    """Return recent audit log entries."""
    audit = get_audit_logger()
    return audit.recent(limit=min(limit, 200))
