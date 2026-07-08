# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Telegram bridge routes (v0.5), mounted under /agent/telegram.

GET    /agent/telegram/status              — enabled flag, bot username, pairings
POST   /agent/telegram/connect             — validate + store bot token (owner)
POST   /agent/telegram/disconnect          — stop, forget token, clear pairings (owner)
POST   /agent/telegram/pair                — mint a 6-digit pairing code
DELETE /agent/telegram/pairings/{chat_id}  — unpair a chat

All routes require JWT auth; connect/disconnect require the owner role.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth.middleware import require_auth, require_owner
from core.channels import telegram

router = APIRouter(prefix="/agent/telegram", tags=["telegram"])


class ConnectRequest(BaseModel):
    token: str


class PairRequest(BaseModel):
    persona_id: str = ""


@router.get("/status")
async def telegram_status(user=Depends(require_auth)):
    return telegram.status()


@router.post("/connect")
async def telegram_connect(request: ConnectRequest, user=Depends(require_owner)):
    try:
        return await telegram.connect(request.token, user.sub)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/disconnect")
async def telegram_disconnect(user=Depends(require_owner)):
    telegram.disconnect(user.sub)
    return {"enabled": False}


@router.post("/pair")
async def telegram_pair(request: PairRequest, user=Depends(require_auth)):
    if not telegram.is_enabled():
        raise HTTPException(status_code=400,
                            detail="Connect a Telegram bot first (Settings → Telegram).")
    return telegram.start_pairing(user.sub, request.persona_id)


@router.delete("/pairings/{chat_id}")
async def telegram_unpair(chat_id: str, user=Depends(require_auth)):
    if not telegram.unpair(chat_id, user.sub):
        raise HTTPException(status_code=404, detail="Pairing not found")
    return {"unpaired": True, "chat_id": chat_id}
