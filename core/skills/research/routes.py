# Copyright (c) 2026 DigiTect Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from core.auth.middleware import require_auth
from core.skills.research.researcher import deep_research

router = APIRouter(prefix="/research", tags=["research"])

# In-memory job store (move to SQLite in v0.4)
_jobs: dict[str, dict] = {}


class ResearchRequest(BaseModel):
    question: str


async def _run_research(job_id: str, question: str, llm_backend: str, user_id: str):
    _jobs[job_id]["status"] = "running"
    try:
        from core.agent.llm import LLMAdapter
        llm = LLMAdapter(backend=llm_backend, user_id=user_id)
        result = await deep_research(question, llm, user_id)
        _jobs[job_id].update({"status": "done", "result": result})
    except Exception as e:
        _jobs[job_id].update({"status": "error", "result": str(e)})


@router.post("/")
async def start_research(
    req: ResearchRequest,
    background_tasks: BackgroundTasks,
    user=Depends(require_auth),
):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "queued", "question": req.question, "result": None}
    background_tasks.add_task(_run_research, job_id, req.question, "ollama", user["sub"])
    return {"job_id": job_id, "status": "queued"}


@router.get("/{job_id}")
async def get_research(job_id: str, user=Depends(require_auth)):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
