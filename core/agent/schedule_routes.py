# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
BixDot — Scheduled agent + notification routes (v0.5).

GET    /agent/schedules            — list the user's schedules
POST   /agent/schedules            — create (capabilities approved here, up front)
PUT    /agent/schedules/{id}       — enable/disable
DELETE /agent/schedules/{id}       — delete
POST   /agent/schedules/{id}/run-now — run immediately (test / on-demand)
GET    /agent/notifications/pending  — undelivered notifications (marks delivered)

All routes require JWT auth.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth.middleware import require_auth
from core.agent import scheduler
from core.audit.logger import get_audit_logger, AuditEvent

router = APIRouter(prefix="/agent", tags=["schedules"])


class CreateScheduleRequest(BaseModel):
    name: str
    prompt: str
    persona_id: str = ""
    frequency: str = "daily"          # hourly | daily | weekdays | weekly
    at_time: str = "07:00"            # HH:MM local
    weekday: Optional[int] = None     # 0=Mon..6=Sun (weekly only)
    notify_desktop: bool = True
    notify_telegram: bool = False
    capabilities: list[str] = []      # pre-approved for headless runs


class UpdateScheduleRequest(BaseModel):
    is_enabled: Optional[bool] = None


@router.get("/schedules")
async def list_schedules(user=Depends(require_auth)):
    return scheduler.list_schedules(user.sub)


@router.post("/schedules")
async def create_schedule(request: CreateScheduleRequest, user=Depends(require_auth)):
    if not request.name.strip() or not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Name and prompt are required.")
    try:
        schedule = scheduler.create_schedule(
            user.sub,
            name=request.name.strip(),
            prompt=request.prompt.strip(),
            persona_id=request.persona_id,
            frequency=request.frequency,
            at_time=request.at_time,
            weekday=request.weekday,
            notify_desktop=request.notify_desktop,
            notify_telegram=request.notify_telegram,
            capabilities=request.capabilities,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    get_audit_logger().log(
        AuditEvent.SCHEDULE_CREATED,
        {"schedule_id": schedule["schedule_id"], "name": schedule["name"],
         "frequency": schedule["frequency"], "at_time": schedule["at_time"],
         "capabilities": schedule["capabilities"]},
        user_id=user.sub,
    )
    return schedule


@router.put("/schedules/{schedule_id}")
async def update_schedule(schedule_id: str, request: UpdateScheduleRequest,
                          user=Depends(require_auth)):
    if not scheduler.schedule_belongs_to(schedule_id, user.sub):
        raise HTTPException(status_code=404, detail="Schedule not found")
    if request.is_enabled is not None:
        scheduler.set_schedule_enabled(schedule_id, request.is_enabled)
        get_audit_logger().log(
            AuditEvent.SCHEDULE_UPDATED,
            {"schedule_id": schedule_id, "is_enabled": request.is_enabled},
            user_id=user.sub,
        )
    return scheduler.get_schedule(schedule_id)


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str, user=Depends(require_auth)):
    if not scheduler.schedule_belongs_to(schedule_id, user.sub):
        raise HTTPException(status_code=404, detail="Schedule not found")
    scheduler.delete_schedule(schedule_id)
    get_audit_logger().log(
        AuditEvent.SCHEDULE_DELETED, {"schedule_id": schedule_id}, user_id=user.sub,
    )
    return {"deleted": True, "schedule_id": schedule_id}


@router.post("/schedules/{schedule_id}/run-now")
async def run_schedule_now(schedule_id: str, user=Depends(require_auth)):
    """Run a schedule immediately — lets the user test it after creating it."""
    if not scheduler.schedule_belongs_to(schedule_id, user.sub):
        raise HTTPException(status_code=404, detail="Schedule not found")
    schedule = scheduler.get_schedule(schedule_id)
    result = await scheduler.run_schedule(schedule)
    return result


@router.get("/notifications/pending")
async def pending_notifications(user=Depends(require_auth)):
    """Undelivered notifications for the frontend poller (marks them delivered)."""
    return {"notifications": scheduler.fetch_pending_notifications(user.sub)}
