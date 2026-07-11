# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Ask My Files routes (v0.6), mounted under /agent/knowledge.

GET    /agent/knowledge/status        — folders, index counts, embedding model
POST   /agent/knowledge/folders       — add a folder (inside home only)
DELETE /agent/knowledge/folders/{id}  — remove a folder and its index
POST   /agent/knowledge/reindex       — index a batch right now

All routes require JWT auth.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth.middleware import require_auth
from core.skills.knowledge import store
from core.audit.logger import get_audit_logger, AuditEvent

router = APIRouter(prefix="/agent/knowledge", tags=["knowledge"])


class AddFolderRequest(BaseModel):
    path: str


@router.get("/status")
async def knowledge_status(user=Depends(require_auth)):
    status = store.get_status(user.sub)
    status["embedding_model"] = await store.find_embedding_model()
    return status


@router.post("/folders")
async def add_folder(request: AddFolderRequest, user=Depends(require_auth)):
    try:
        folder = store.add_folder(user.sub, request.path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    get_audit_logger().log(
        AuditEvent.KNOWLEDGE_FOLDER_ADDED,
        {"folder_id": folder["folder_id"], "path": folder["path"]},
        user_id=user.sub,
    )
    return folder


@router.delete("/folders/{folder_id}")
async def remove_folder(folder_id: str, user=Depends(require_auth)):
    if not store.remove_folder(folder_id, user.sub):
        raise HTTPException(status_code=404, detail="Folder not found")
    get_audit_logger().log(
        AuditEvent.KNOWLEDGE_FOLDER_REMOVED, {"folder_id": folder_id},
        user_id=user.sub,
    )
    return {"removed": True, "folder_id": folder_id}


@router.post("/reindex")
async def reindex(user=Depends(require_auth)):
    """Index a batch immediately (the scheduler continues in the background)."""
    if not await store.find_embedding_model():
        raise HTTPException(
            status_code=400,
            detail="No embedding model installed. Download one first "
                   "(e.g. nomic-embed-text) from this settings section.",
        )
    indexed = await store.index_pending(user.sub, budget=20)
    return {"indexed": indexed, **store.get_status(user.sub)}
