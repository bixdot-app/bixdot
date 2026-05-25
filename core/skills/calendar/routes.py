# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
BixDot — Calendar Skill Routes

GET  /calendar/status                   — which provider is connected
POST /calendar/connect/google           — start Google OAuth flow
GET  /calendar/oauth/callback           — Google OAuth callback (browser redirect)
POST /calendar/connect/ical             — connect a local .ics file
DELETE /calendar/disconnect/{provider}  — disconnect a provider
GET  /calendar/events?days=7            — upcoming events
POST /calendar/events                   — create event
"""

import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from core.auth.middleware import require_auth
from core.skills.calendar.store import (
    init_calendar_db, save_provider, load_active_provider, delete_provider, list_providers,
)
from core.skills.calendar.google_cal import GoogleCalendarProvider
from core.skills.calendar.ical_cal import ICalProvider

router = APIRouter(prefix="/calendar", tags=["calendar"])

# Initialise DB table on import
init_calendar_db()

# In-memory OAuth state store (short-lived, cleared after use)
# state → {"code_verifier": str, "client_id": str, "client_secret": str, "user_id": str}
_oauth_states: dict[str, dict] = {}


# ─── Request / Response Models ────────────────────────────────────────────────

class GoogleConnectRequest(BaseModel):
    client_id: str
    client_secret: str


class ICalConnectRequest(BaseModel):
    file_path: str


class CreateEventRequest(BaseModel):
    title: str
    date: str            # YYYY-MM-DD
    time: str            # HH:MM (24h)
    duration_minutes: int = 60
    description: str = ""
    location: str = ""


class EventResponse(BaseModel):
    id: str
    title: str
    start: str
    end: str
    location: Optional[str]
    description: Optional[str]
    all_day: bool
    friendly: str


class StatusResponse(BaseModel):
    connected: bool
    providers: list[str]
    active_provider: Optional[str]


# ─── Helper ───────────────────────────────────────────────────────────────────

def _provider_for_user(user_id: str):
    """Load the active provider instance for a user."""
    result = load_active_provider(user_id)
    if not result:
        return None
    name, config = result
    if name == "google":
        return GoogleCalendarProvider(config)
    if name == "ical":
        return ICalProvider(config)
    return None


def _event_to_response(e) -> EventResponse:
    return EventResponse(
        id          = e.id,
        title       = e.title,
        start       = e.start.isoformat(),
        end         = e.end.isoformat(),
        location    = e.location,
        description = e.description,
        all_day     = e.all_day,
        friendly    = e.friendly(),
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/status", response_model=StatusResponse)
async def calendar_status(user=Depends(require_auth)):
    providers = list_providers(user.sub)
    active = load_active_provider(user.sub)
    return StatusResponse(
        connected       = len(providers) > 0,
        providers       = providers,
        active_provider = active[0] if active else None,
    )


@router.post("/connect/google")
async def connect_google(req: GoogleConnectRequest, user=Depends(require_auth)):
    """
    Step 1 of Google OAuth flow.
    Returns the URL the user should open in their browser.
    """
    provider = GoogleCalendarProvider({
        "client_id":     req.client_id,
        "client_secret": req.client_secret,
    })
    state            = secrets.token_urlsafe(16)
    verifier, challenge = provider.make_pkce()

    _oauth_states[state] = {
        "code_verifier": verifier,
        "client_id":     req.client_id,
        "client_secret": req.client_secret,
        "user_id":       user.sub,
    }

    auth_url = provider.build_auth_url(state, challenge)
    return {"auth_url": auth_url, "state": state}


@router.get("/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(
    code: str  = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None),
):
    """
    Google redirects here after the user grants permission.
    Exchanges the code for tokens, saves them, shows a success page.
    This endpoint is unauthenticated (browser redirect from Google).
    """
    if error:
        return HTMLResponse(_result_page(False, f"Google denied access: {error}"))

    pending = _oauth_states.pop(state, None)
    if not pending:
        return HTMLResponse(_result_page(False, "Invalid or expired auth state. Please try again."))

    try:
        provider = GoogleCalendarProvider({
            "client_id":     pending["client_id"],
            "client_secret": pending["client_secret"],
        })
        tokens = await provider.exchange_code(code, pending["code_verifier"])

        expiry = (
            datetime.now(timezone.utc) + timedelta(seconds=tokens.get("expires_in", 3600))
        ).isoformat()

        config = {
            "client_id":     pending["client_id"],
            "client_secret": pending["client_secret"],
            "access_token":  tokens["access_token"],
            "refresh_token": tokens.get("refresh_token", ""),
            "token_expiry":  expiry,
        }
        save_provider(pending["user_id"], "google", config)
        return HTMLResponse(_result_page(True, "Google Calendar connected successfully!"))

    except Exception as e:
        return HTMLResponse(_result_page(False, f"Connection failed: {e}"))


@router.post("/connect/ical")
async def connect_ical(req: ICalConnectRequest, user=Depends(require_auth)):
    """Connect a local .ics calendar file."""
    from pathlib import Path
    p = Path(req.file_path).expanduser()
    if not p.exists():
        raise HTTPException(status_code=400, detail=f"File not found: {p}")
    if not p.suffix.lower() == ".ics":
        raise HTTPException(status_code=400, detail="File must be a .ics calendar file")

    save_provider(user.sub, "ical", {"file_path": str(p)})
    return {"connected": True, "provider": "ical", "path": str(p)}


@router.delete("/disconnect/{provider}")
async def disconnect(provider: str, user=Depends(require_auth)):
    """Disconnect a calendar provider."""
    delete_provider(user.sub, provider)
    return {"disconnected": True, "provider": provider}


@router.get("/events", response_model=list[EventResponse])
async def get_events(
    days: int = Query(7, ge=1, le=30),
    user=Depends(require_auth),
):
    """Get upcoming events from the connected calendar."""
    provider = _provider_for_user(user.sub)
    if not provider:
        raise HTTPException(status_code=404, detail="No calendar connected. Set one up in Settings.")

    try:
        events = await provider.get_events(days_ahead=days)
        return [_event_to_response(e) for e in events]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/events", response_model=EventResponse)
async def create_event(req: CreateEventRequest, user=Depends(require_auth)):
    """Create a new calendar event."""
    provider = _provider_for_user(user.sub)
    if not provider:
        raise HTTPException(status_code=404, detail="No calendar connected.")

    try:
        start_str = f"{req.date}T{req.time}:00+00:00"
        start = datetime.fromisoformat(start_str)
        end   = start + timedelta(minutes=req.duration_minutes)

        event = await provider.create_event(
            title       = req.title,
            start       = start,
            end         = end,
            description = req.description,
            location    = req.location,
        )
        # Persist updated tokens if refreshed
        if hasattr(provider, "to_config"):
            save_provider(user.sub, provider.provider_id, provider.to_config())

        return _event_to_response(event)

    except NotImplementedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── HTML result pages ────────────────────────────────────────────────────────

def _result_page(success: bool, message: str) -> str:
    color  = "#00d4aa" if success else "#ff4757"
    icon   = "✓" if success else "✗"
    title  = "Connected!" if success else "Connection failed"
    return f"""<!DOCTYPE html>
<html><head><title>BixDot Calendar</title>
<style>
  body{{margin:0;background:#080c10;color:#e2eaf5;font-family:-apple-system,sans-serif;
        display:flex;align-items:center;justify-content:center;height:100vh;}}
  .box{{background:#0f1520;border:1px solid #1e2d40;border-radius:16px;padding:40px;
         text-align:center;max-width:340px;}}
  .icon{{font-size:48px;color:{color};margin-bottom:16px;}}
  h2{{color:{color};margin:0 0 10px;}}
  p{{color:#4a6080;font-size:14px;}}
  button{{margin-top:20px;background:{color};color:#080c10;border:none;
           border-radius:8px;padding:10px 24px;font-size:14px;font-weight:600;cursor:pointer;}}
</style></head>
<body><div class="box">
  <div class="icon">{icon}</div>
  <h2>{title}</h2>
  <p>{message}</p>
  <button onclick="window.close()">Close this tab</button>
</div></body></html>"""
