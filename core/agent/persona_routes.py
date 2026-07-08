# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Persona routes (v0.5), mounted under /agent/personas.

GET    /agent/personas          — list all personas (built-in + custom)
POST   /agent/personas          — create a custom persona
PUT    /agent/personas/{id}     — edit a persona (built-ins editable, not deletable)
DELETE /agent/personas/{id}     — delete a custom persona

All routes require JWT auth. Personas shape what tools the model is offered;
the permission system still gates every execution.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth.middleware import require_auth
from core.agent import personas as store
from core.audit.logger import get_audit_logger, AuditEvent

router = APIRouter(prefix="/agent/personas", tags=["personas"])


class PersonaBody(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    allowed_tools: Optional[list[str]] = None


@router.get("")
async def list_personas(user=Depends(require_auth)):
    return store.list_personas()


@router.post("")
async def create_persona(body: PersonaBody, user=Depends(require_auth)):
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Persona name is required.")
    persona = store.create_persona(
        name=body.name.strip(),
        icon=body.icon or "🤖",
        description=body.description or "",
        system_prompt=body.system_prompt or "",
        model=body.model or "",
        allowed_tools=body.allowed_tools or [],
    )
    get_audit_logger().log(
        AuditEvent.PERSONA_CREATED,
        {"persona_id": persona["persona_id"], "name": persona["name"]},
        user_id=user.sub,
    )
    return persona


@router.put("/{persona_id}")
async def update_persona(persona_id: str, body: PersonaBody, user=Depends(require_auth)):
    if not store.get_persona(persona_id):
        raise HTTPException(status_code=404, detail="Persona not found")
    persona = store.update_persona(persona_id, **body.model_dump(exclude_unset=True))
    get_audit_logger().log(
        AuditEvent.PERSONA_UPDATED,
        {"persona_id": persona_id},
        user_id=user.sub,
    )
    return persona


@router.delete("/{persona_id}")
async def delete_persona(persona_id: str, user=Depends(require_auth)):
    try:
        found = store.delete_persona(persona_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not found:
        raise HTTPException(status_code=404, detail="Persona not found")
    get_audit_logger().log(
        AuditEvent.PERSONA_DELETED,
        {"persona_id": persona_id},
        user_id=user.sub,
    )
    return {"deleted": True, "persona_id": persona_id}
