# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from core.auth.middleware import require_auth
from core.skills.memory.store import (
    load_all_memories, save_memory, delete_memory, search_memories
)

router = APIRouter(prefix="/memory", tags=["memory"])


class MemorySaveRequest(BaseModel):
    content: str
    category: Optional[str] = "general"
    source: Optional[str] = "user"


class MemorySearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 10


@router.get("/")
async def list_memories(user=Depends(require_auth)):
    return load_all_memories(user["sub"])


@router.post("/")
async def create_memory(req: MemorySaveRequest, user=Depends(require_auth)):
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="content cannot be empty")
    mem_id = save_memory(user["sub"], req.content.strip(), req.category or "general", req.source or "user")
    return {"id": mem_id, "saved": True}


@router.delete("/{mem_id}")
async def remove_memory(mem_id: str, user=Depends(require_auth)):
    ok = delete_memory(mem_id, user["sub"])
    if not ok:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"deleted": True}


@router.post("/search")
async def search(req: MemorySearchRequest, user=Depends(require_auth)):
    results = search_memories(user["sub"], req.query, limit=min(req.limit or 10, 50))
    return results
