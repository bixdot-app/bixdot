# Copyright (c) 2026 DigiTect Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth.middleware import require_auth
from core.skills.github.client import GitHubClient
from core.skills.github.store import save_github_token, load_github_token, delete_github_token

router = APIRouter(prefix="/github", tags=["github"])


class ConnectRequest(BaseModel):
    token: str


@router.post("/connect")
async def connect(req: ConnectRequest, user=Depends(require_auth)):
    if not req.token.strip():
        raise HTTPException(status_code=400, detail="token is required")
    client = GitHubClient(req.token.strip())
    try:
        gh_user = await client.get_user()
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"GitHub token invalid: {e}")
    save_github_token(user["sub"], req.token.strip())
    return {"connected": True, "github_user": gh_user.get("login")}


@router.delete("/disconnect")
async def disconnect(user=Depends(require_auth)):
    delete_github_token(user["sub"])
    return {"disconnected": True}


@router.get("/status")
async def status(user=Depends(require_auth)):
    token = load_github_token(user["sub"])
    if not token:
        return {"connected": False}
    try:
        gh_user = await GitHubClient(token).get_user()
        return {"connected": True, "github_user": gh_user.get("login")}
    except Exception:
        return {"connected": False}


@router.get("/repos")
async def list_repos(user=Depends(require_auth)):
    token = load_github_token(user["sub"])
    if not token:
        raise HTTPException(status_code=401, detail="GitHub not connected")
    return await GitHubClient(token).list_repos()


@router.get("/{owner}/{repo}/issues")
async def list_issues(owner: str, repo: str, state: str = "open", user=Depends(require_auth)):
    token = load_github_token(user["sub"])
    if not token:
        raise HTTPException(status_code=401, detail="GitHub not connected")
    return await GitHubClient(token).list_issues(f"{owner}/{repo}", state=state)
