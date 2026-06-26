# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Skill Plugin API routes (mounted under /agent/skills).

GET    /agent/skills                  — list installed skills + capability grants
POST   /agent/skills/install          — install from an uploaded .zip (multipart)
DELETE /agent/skills/{skill_id}       — uninstall
PUT    /agent/skills/{skill_id}/toggle — enable/disable
GET    /agent/skills/{skill_id}/verify — re-verify integrity on demand

All routes require JWT auth. Install/uninstall require owner role — only the
machine owner may add third-party code. Installing a skill is the user's
explicit approval of every capability it declares.
"""
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from core.auth.middleware import require_auth, require_owner
from core.skills import registry, plugin_manager

router = APIRouter(prefix="/agent/skills", tags=["skills"])


class SkillResponse(BaseModel):
    skill_id: str
    name: str
    version: str
    description: str
    author: str
    license: str
    capabilities: list[str]
    granted_capabilities: list[str]
    trigger: str
    is_enabled: bool
    installed_at: str


class ToggleRequest(BaseModel):
    enabled: Optional[bool] = None


def _to_response(skill: dict) -> SkillResponse:
    return SkillResponse(
        skill_id=skill["skill_id"],
        name=skill["name"],
        version=skill["version"],
        description=skill["description"],
        author=skill["author"],
        license=skill["license"],
        capabilities=skill["capabilities"],
        granted_capabilities=registry.get_skill_grants(skill["skill_id"]),
        trigger=skill["trigger"],
        is_enabled=skill["is_enabled"],
        installed_at=skill["installed_at"],
    )


@router.get("", response_model=list[SkillResponse])
async def list_skills(user=Depends(require_auth)):
    """List all installed third-party skills with their granted capabilities."""
    return [_to_response(s) for s in registry.list_skills()]


@router.post("/inspect")
async def inspect_skill(file: UploadFile = File(...), user=Depends(require_owner)):
    """
    Validate an uploaded .zip and return its manifest (id, capabilities, license,
    …) WITHOUT installing — powers the capability-approval screen.
    """
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload must be a .zip archive.")
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "skill.zip"
        zip_path.write_bytes(await file.read())
        try:
            manifest = plugin_manager.inspect_skill(zip_path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return manifest


@router.post("/install", response_model=SkillResponse)
async def install_skill(file: UploadFile = File(...), user=Depends(require_owner)):
    """
    Install a skill from an uploaded .zip. The manifest is validated, the entry
    file SHA-256 verified, the license checked, and every declared capability
    granted to the approving user. Owner role required.
    """
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload must be a .zip archive.")

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "skill.zip"
        zip_path.write_bytes(await file.read())
        try:
            manifest = plugin_manager.install_skill(zip_path, approved_by=user.sub)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    skill = registry.get_skill(manifest["id"])
    if not skill:
        raise HTTPException(status_code=500, detail="Skill install did not persist.")
    return _to_response(skill)


@router.delete("/{skill_id}")
async def uninstall_skill(skill_id: str, user=Depends(require_owner)):
    """Uninstall a skill (owner only)."""
    try:
        plugin_manager.uninstall_skill(skill_id, user.sub)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"uninstalled": True, "skill_id": skill_id}


@router.put("/{skill_id}/toggle", response_model=SkillResponse)
async def toggle_skill(skill_id: str, request: ToggleRequest, user=Depends(require_auth)):
    """Enable or disable a skill. Omit `enabled` to flip the current state."""
    skill = registry.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    new_state = request.enabled if request.enabled is not None else (not skill["is_enabled"])
    plugin_manager.set_enabled(skill_id, new_state, user.sub)
    return _to_response(registry.get_skill(skill_id))


@router.get("/{skill_id}/verify")
async def verify_skill(skill_id: str, user=Depends(require_auth)):
    """Re-verify a skill's entry-file integrity on demand."""
    if not registry.get_skill(skill_id):
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    ok = plugin_manager.verify_skill_integrity(skill_id)
    return {"skill_id": skill_id, "verified": ok}
