# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Google Calendar provider.

Uses OAuth2 authorization code flow with PKCE (no client secret needed
for installed/desktop apps).

Setup steps for users:
1. Go to console.cloud.google.com → New project
2. APIs & Services → Enable "Google Calendar API"
3. Credentials → Create OAuth 2.0 Client ID
4. Application type: Web application
5. Authorised redirect URIs: http://127.0.0.1:8747/calendar/oauth/callback
6. Copy the Client ID (and Client Secret) into BixDot Settings
"""

import base64
import hashlib
import secrets
from datetime import datetime, timezone, timedelta

import httpx

from core.skills.calendar.base import CalendarEvent, CalendarProvider


GOOGLE_AUTH_URL   = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL  = "https://oauth2.googleapis.com/token"
GOOGLE_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
REDIRECT_URI      = "http://127.0.0.1:8747/calendar/oauth/callback"

# BXD-012: was "https://www.googleapis.com/auth/calendar" — full read/write
# access to the calendar LIST itself (create/delete calendars, change ACLs
# and sharing settings), not just events. Nothing in BixDot touches calendar
# management; get_events() and create_event() below only ever read or write
# events on the primary calendar. `calendar.events` is Google's scope for
# exactly that: read/write on events, no calendar-management surface.
#
# Not narrowed to `calendar.events.readonly` — create_event() is a real,
# shipped, capability-gated (calendar:write) feature exercised by the
# "Assistant" persona (core/agent/personas.py) and by POST /calendar/events.
# A readonly scope would silently break it. "Least scope that still works"
# for a product that ships both a read and a write feature is calendar.events,
# not readonly — seeking a read-only grant to satisfy a docs sentence while
# breaking a shipped feature would be worse, not more secure.
SCOPES            = "https://www.googleapis.com/auth/calendar.events"


class GoogleCalendarProvider(CalendarProvider):
    provider_id = "google"

    def __init__(self, config: dict):
        self.client_id     = config.get("client_id", "")
        self.client_secret = config.get("client_secret", "")
        self.access_token  = config.get("access_token")
        self.refresh_token = config.get("refresh_token")
        self.token_expiry  = config.get("token_expiry")  # ISO string

    def is_connected(self) -> bool:
        return bool(self.access_token)

    # ── OAuth PKCE helpers ────────────────────────────────────────────────────

    @staticmethod
    def make_pkce() -> tuple[str, str]:
        """Return (code_verifier, code_challenge)."""
        verifier  = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()
        return verifier, challenge

    def build_auth_url(self, state: str, code_challenge: str) -> str:
        params = {
            "client_id":             self.client_id,
            "redirect_uri":          REDIRECT_URI,
            "response_type":         "code",
            "scope":                 SCOPES,
            "access_type":           "offline",
            "prompt":                "consent",
            "state":                 state,
            "code_challenge":        code_challenge,
            "code_challenge_method": "S256",
        }
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{GOOGLE_AUTH_URL}?{qs}"

    async def exchange_code(self, code: str, code_verifier: str) -> dict:
        """Exchange auth code for tokens. Returns token dict."""
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(GOOGLE_TOKEN_URL, data={
                "code":          code,
                "client_id":     self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri":  REDIRECT_URI,
                "grant_type":    "authorization_code",
                "code_verifier": code_verifier,
            })
            r.raise_for_status()
            return r.json()

    async def _refresh_if_needed(self) -> str:
        """Return a valid access token, refreshing if expired."""
        if self.token_expiry:
            expiry = datetime.fromisoformat(self.token_expiry)
            if datetime.now(timezone.utc) < expiry - timedelta(minutes=5):
                return self.access_token

        if not self.refresh_token:
            raise RuntimeError("No refresh token — please reconnect Google Calendar.")

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(GOOGLE_TOKEN_URL, data={
                "client_id":     self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type":    "refresh_token",
            })
            r.raise_for_status()
            data = r.json()

        self.access_token = data["access_token"]
        self.token_expiry = (
            datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))
        ).isoformat()
        return self.access_token

    # ── Calendar API calls ────────────────────────────────────────────────────

    async def get_events(self, days_ahead: int = 7) -> list[CalendarEvent]:
        from core.privacy import record_net
        record_net("calendar")
        token  = await self._refresh_if_needed()
        now    = datetime.now(timezone.utc)
        end    = now + timedelta(days=days_ahead)

        params = {
            "timeMin":      now.isoformat(),
            "timeMax":      end.isoformat(),
            "singleEvents": "true",
            "orderBy":      "startTime",
            "maxResults":   "20",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                GOOGLE_EVENTS_URL,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            r.raise_for_status()
            data = r.json()

        events = []
        for item in data.get("items", []):
            start_raw = item.get("start", {})
            end_raw   = item.get("end",   {})
            all_day   = "date" in start_raw and "dateTime" not in start_raw

            if all_day:
                start_dt = datetime.fromisoformat(start_raw["date"]).replace(tzinfo=timezone.utc)
                end_dt   = datetime.fromisoformat(end_raw["date"]).replace(tzinfo=timezone.utc)
            else:
                start_dt = datetime.fromisoformat(start_raw["dateTime"].replace("Z", "+00:00"))
                end_dt   = datetime.fromisoformat(end_raw["dateTime"].replace("Z", "+00:00"))

            events.append(CalendarEvent(
                id          = item.get("id", ""),
                title       = item.get("summary", "(No title)"),
                start       = start_dt,
                end         = end_dt,
                location    = item.get("location"),
                description = item.get("description"),
                all_day     = all_day,
            ))
        return events

    async def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        description: str = "",
        location: str = "",
    ) -> CalendarEvent:
        from core.privacy import record_net
        record_net("calendar")
        token = await self._refresh_if_needed()
        body = {
            "summary":     title,
            "description": description,
            "location":    location,
            "start":       {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end":         {"dateTime": end.isoformat(),   "timeZone": "UTC"},
        }

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                GOOGLE_EVENTS_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type":  "application/json",
                },
                json=body,
            )
            r.raise_for_status()
            item = r.json()

        return CalendarEvent(
            id          = item.get("id", ""),
            title       = item.get("summary", title),
            start       = start,
            end         = end,
            description = description,
            location    = location,
        )

    def to_config(self) -> dict:
        """Serialise back to config dict for storage."""
        return {
            "client_id":     self.client_id,
            "client_secret": self.client_secret,
            "access_token":  self.access_token,
            "refresh_token": self.refresh_token,
            "token_expiry":  self.token_expiry,
        }
