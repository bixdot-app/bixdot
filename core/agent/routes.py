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
from typing import Literal, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from core.auth.middleware import require_auth
from core.agent.runtime import AgentRuntime, AgentResponse
from core.agent.permissions import get_permission_store, Capability
from core.agent.model_caps import ModelMode, classify_model
from core.audit.logger import get_audit_logger, AuditEvent
from core.agent.session_store import (
    get_session_store,
    create_session as store_create_session,
    get_session_meta,
    list_sessions as store_list_sessions,
    update_session as store_update_session,
    get_messages as store_get_messages,
    load_session,
    save_session,
    delete_session,
    session_belongs_to,
    is_private as store_is_private,
)

router = APIRouter(prefix="/agent", tags=["agent"])

# Initialise SQLite session store on first import
get_session_store()


# ─── Request / Response Models ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str


class CreateSessionRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    name: str = "New Chat"
    model: str = ""               # empty = persona default, then global default
    is_private: bool = False
    llm_backend: Literal["claude", "ollama"] = "ollama"
    persona_id: str = ""          # persona this session speaks as


class UpdateSessionRequest(BaseModel):
    name: Optional[str] = None
    is_archived: Optional[bool] = None


class SessionSummary(BaseModel):
    model_config = {"protected_namespaces": ()}
    session_id: str
    name: str
    model: str
    model_mode: str
    persona_id: str = ""
    is_private: bool
    is_archived: bool = False
    created_at: str
    updated_at: str
    last_message_preview: Optional[str] = None
    message_count: int = 0
    # Legacy field kept for older frontend builds
    llm_backend: str = "ollama"


class MessageItem(BaseModel):
    role: str
    content: str


class SessionDetail(SessionSummary):
    messages: list[MessageItem] = []


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


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _resolve_model_and_mode(
    llm_backend: str, model: str, user_id: str
) -> tuple[str, ModelMode]:
    """
    Resolve the effective model name and its ModelMode from live Ollama
    capabilities. Raises HTTP 400 (and audits cloud_model_blocked) for cloud
    models — they transmit data off-device, violating the local-first guarantee.
    """
    import httpx
    from core.config import settings as cfg
    from core.storage.db import get_setting

    model_name = model or get_setting("local_model") or cfg.local_model
    model_mode = ModelMode.FULL_AGENT

    if llm_backend == "claude":
        model_mode = ModelMode.CLOUD
    else:
        try:
            async with httpx.AsyncClient(base_url=cfg.ollama_url, timeout=5) as client:
                r = await client.get("/api/tags")
                r.raise_for_status()
                for m in r.json().get("models", []):
                    if m["name"].split(":")[0] == model_name.split(":")[0]:
                        model_mode = classify_model(m.get("capabilities", []), m["name"])
                        break
            # If the chosen name itself carries a cloud tag, classify it as cloud
            # even when Ollama is unreachable or didn't list it.
            if model_name.lower().endswith((":cloud", "-cloud")):
                model_mode = ModelMode.CLOUD
        except Exception:
            pass  # Ollama unreachable — default to FULL_AGENT

    if model_mode == ModelMode.CLOUD:
        get_audit_logger().log(
            AuditEvent.CLOUD_MODEL_BLOCKED,
            {"model_name": model_name},
            user_id=user_id,
        )
        raise HTTPException(
            status_code=400,
            detail=(
                "Cloud models transmit data to external servers, violating "
                "BixDot's local-first guarantee. Pull a local model instead: "
                "ollama pull <model-name>"
            ),
        )
    return model_name, model_mode


def _summary(meta: dict) -> SessionSummary:
    return SessionSummary(
        session_id=meta["session_id"],
        name=meta["name"],
        model=meta["model"],
        model_mode=meta["model_mode"],
        persona_id=meta.get("persona_id", ""),
        is_private=meta["is_private"],
        is_archived=meta.get("is_archived", False),
        created_at=meta["created_at"],
        updated_at=meta["updated_at"],
        last_message_preview=meta.get("last_message_preview"),
        message_count=meta.get("message_count", 0),
        llm_backend=meta.get("llm_backend", "ollama"),
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/sessions", response_model=SessionSummary)
async def create_session(
    request: CreateSessionRequest,
    user=Depends(require_auth),
):
    """
    Create a new agent session (regular or private), optionally bound to a
    persona. Cloud models are blocked with HTTP 400 (local-first guarantee).
    """
    # Persona: resolve first so its default model applies when none is chosen.
    requested_model = request.model
    if request.persona_id:
        from core.agent.personas import get_persona
        persona = get_persona(request.persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")
        if not requested_model and persona["model"]:
            requested_model = persona["model"]

    model_name, model_mode = await _resolve_model_and_mode(
        request.llm_backend, requested_model, user.sub
    )

    meta = store_create_session(
        user.sub,
        name=request.name or "New Chat",
        model=model_name,
        model_mode=model_mode.value,
        llm_backend=request.llm_backend,
        is_private=request.is_private,
        persona_id=request.persona_id,
    )

    audit = get_audit_logger()
    if request.is_private:
        # NEVER record name or message content for private sessions.
        audit.log(
            AuditEvent.PRIVATE_SESSION_STARTED,
            {"session_id": meta["session_id"], "model": model_name},
            user_id=user.sub,
        )
    else:
        audit.log(
            AuditEvent.SESSION_CREATED,
            {"session_id": meta["session_id"], "name": meta["name"],
             "model": model_name, "is_private": False},
            user_id=user.sub,
        )
    return _summary(meta)


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(
    include_archived: bool = False,
    user=Depends(require_auth),
):
    """List the current user's sessions (non-archived, newest first by default)."""
    return [_summary(m) for m in store_list_sessions(user.sub, include_archived=include_archived)]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, user=Depends(require_auth)):
    """Return session metadata plus the last 50 messages."""
    if not session_belongs_to(session_id, user.sub):
        raise HTTPException(status_code=404, detail="Session not found")
    meta = get_session_meta(session_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Session not found")
    msgs = store_get_messages(session_id, limit=50)
    detail = SessionDetail(**_summary(meta).model_dump())
    detail.messages = [MessageItem(role=m["role"], content=m["content"]) for m in msgs]
    return detail


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = 50,
    before: Optional[int] = None,
    user=Depends(require_auth),
):
    """
    Paginated message history (oldest-first within the page). Roles are mapped
    to the UI vocabulary ('assistant' -> 'agent'); internal memory-context
    messages are already filtered by the store.
    """
    if not session_belongs_to(session_id, user.sub):
        raise HTTPException(status_code=404, detail="Session not found")
    msgs = store_get_messages(session_id, limit=min(limit, 200), before_id=before)
    return {
        "messages": [
            {"id": m.get("id"),
             "role": "user" if m["role"] == "user" else "agent",
             "content": m["content"]}
            for m in msgs
        ]
    }


@router.put("/sessions/{session_id}", response_model=SessionSummary)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    user=Depends(require_auth),
):
    """Rename and/or archive a session."""
    if not session_belongs_to(session_id, user.sub):
        raise HTTPException(status_code=404, detail="Session not found")
    before = get_session_meta(session_id)
    meta = store_update_session(session_id, name=request.name, is_archived=request.is_archived)
    if not meta:
        raise HTTPException(status_code=404, detail="Session not found")

    audit = get_audit_logger()
    if request.name is not None and not meta["is_private"]:
        audit.log(
            AuditEvent.SESSION_RENAMED,
            {"session_id": session_id,
             "old_name": before["name"] if before else None,
             "new_name": request.name},
            user_id=user.sub,
        )
    if request.is_archived:
        audit.log(AuditEvent.SESSION_ARCHIVED, {"session_id": session_id}, user_id=user.sub)
    return _summary(meta)


@router.delete("/sessions/{session_id}")
async def end_session(session_id: str, user=Depends(require_auth)):
    """
    Delete a session. Private sessions are hard-deleted (no DB trace).
    Regular sessions are archived (recoverable) rather than destroyed.
    """
    if not session_belongs_to(session_id, user.sub):
        raise HTTPException(status_code=404, detail="Session not found")

    audit = get_audit_logger()
    if store_is_private(session_id):
        delete_session(session_id)  # hard delete from memory
        audit.log(AuditEvent.PRIVATE_SESSION_ENDED, {"session_id": session_id}, user_id=user.sub)
        return {"status": "deleted", "session_id": session_id}

    store_update_session(session_id, is_archived=True)
    audit.log(AuditEvent.SESSION_ARCHIVED, {"session_id": session_id}, user_id=user.sub)
    return {"status": "archived", "session_id": session_id}


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
    EMBEDDING models are filtered out. Cloud models are flagged (is_cloud=True)
    and shown last so the UI can warn that data would leave the device.
    Sort: local before cloud, default first, then alphabetical.
    Returns ollama_available=False (empty list) if Ollama is not running.
    """
    import httpx
    from core.config import settings as cfg
    from core.storage.db import get_setting

    default_base = (get_setting("local_model") or cfg.local_model).split(":")[0]
    try:
        async with httpx.AsyncClient(base_url=cfg.ollama_url, timeout=5) as client:
            r = await client.get("/api/tags")
            r.raise_for_status()
            raw_models = r.json().get("models", [])
    except Exception:
        return {"models": [], "ollama_available": False}

    infos: list[ModelInfo] = []
    for m in raw_models:
        caps = m.get("capabilities", [])
        mode = classify_model(caps, m.get("name", ""))
        if mode == ModelMode.EMBEDDING:
            continue  # never expose embedding models in the chat picker
        infos.append(ModelInfo(
            name=m["name"],
            size_gb=round(m.get("size", 0) / 1e9, 2),
            mode=mode.value,
            supports_vision="vision" in caps,
            is_cloud=(mode == ModelMode.CLOUD),
            is_default=(m["name"].split(":")[0] == default_base),
        ))

    # Sort: local before cloud, default first, then alphabetically
    infos.sort(key=lambda x: (x.is_cloud, not x.is_default, x.name))
    return {"models": [i.model_dump() for i in infos], "ollama_available": True}


@router.post("/models/pull")
async def pull_model(request: SetModelRequest, user=Depends(require_auth)):
    """
    Download a model through Ollama, streaming progress as NDJSON so the UI
    can show a progress bar — non-technical users never touch a terminal.
    Cloud-tagged models are refused (local-first guarantee).
    """
    import json as _json
    import httpx
    from fastapi.responses import StreamingResponse
    from core.config import settings as cfg

    model = request.model.strip()
    if not model:
        raise HTTPException(status_code=400, detail="Model name is required.")
    if model.lower().endswith((":cloud", "-cloud")):
        raise HTTPException(
            status_code=400,
            detail="Cloud models transmit data off-device and cannot be used.",
        )

    get_audit_logger().log(
        AuditEvent.AGENT_QUERY, {"event": "model_pull_started", "model": model},
        user_id=user.sub,
    )

    async def _stream():
        try:
            async with httpx.AsyncClient(base_url=cfg.ollama_url, timeout=None) as client:
                async with client.stream(
                    "POST", "/api/pull", json={"model": model, "stream": True}
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line.strip():
                            yield line + "\n"
        except Exception as e:
            yield _json.dumps({"error": f"Download failed: {e}"}) + "\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


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
