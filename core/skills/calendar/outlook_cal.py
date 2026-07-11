# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# BixDot is a trademark of DigiTech Business Pte. Ltd (Singapore).
# Licensed under the Business Source License 1.1 (BUSL-1.1).
# Commercial use requires a license: legal@bixdot.app
# Security disclosures: security@bixdot.app
# See LICENSE in the project root for full terms.

"""
Outlook / Microsoft 365 calendar provider.

Uses Microsoft Identity Platform OAuth 2.0 authorization code flow
with PKCE. Reads and creates events via Microsoft Graph API.

Setup steps for users:
1. Go to https://portal.azure.com → Azure Active Directory → App registrations
2. Click "New registration"
   - Name: BixDot Calendar (or anything)
   - Supported account types: "Accounts in any organizational directory and
     personal Microsoft accounts" (multi-tenant + personal)
   - Redirect URI: Web → http://127.0.0.1:8747/calendar/oauth/microsoft/callback
3. Copy the "Application (client) ID"  — this is your Client ID
4. Under "Certificates & secrets" → "New client secret" — copy the value
5. Under "API permissions" → Add: Microsoft Graph → Delegated →
   Calendars.Read, Calendars.ReadWrite, offline_access, User.Read
6. Click "Grant admin consent" if on an org account
7. Paste the Client ID and Secret into BixDot Settings → Calendar → Outlook

Note: for personal use (no org admin), the admin-consent step is skipped —
the user approves scopes on sign-in.
"""

import base64
import hashlib
import secrets
from datetime import datetime, timezone, timedelta

import httpx

from core.skills.calendar.base import CalendarEvent, CalendarProvider

# ─── Microsoft Identity endpoints ─────────────────────────────────────────────
# "common" tenant supports both personal (MSA) and work/school (AAD) accounts
MS_AUTH_URL    = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MS_TOKEN_URL   = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_BASE     = "https://graph.microsoft.com/v1.0"
REDIRECT_URI   = "http://127.0.0.1:8747/calendar/oauth/microsoft/callback"
SCOPES         = "Calendars.Read Calendars.ReadWrite offline_access User.Read"


class OutlookCalendarProvider(CalendarProvider):
    provider_id = "outlook"

    def __init__(self, config: dict):
        self.client_id     = config.get("client_id", "")
        self.client_secret = config.get("client_secret", "")
        self.access_token  = config.get("access_token")
        self.refresh_token = config.get("refresh_token")
        self.token_expiry  = config.get("token_expiry")   # ISO string

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
            "response_type":         "code",
            "redirect_uri":          REDIRECT_URI,
            "scope":                 SCOPES,
            "response_mode":         "query",
            "state":                 state,
            "code_challenge":        code_challenge,
            "code_challenge_method": "S256",
            "prompt":                "select_account",
        }
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{MS_AUTH_URL}?{qs}"

    async def exchange_code(self, code: str, code_verifier: str) -> dict:
        """Exchange auth code for tokens."""
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(MS_TOKEN_URL, data={
                "client_id":     self.client_id,
                "client_secret": self.client_secret,
                "code":          code,
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
                return self.access_token  # type: ignore[return-value]

        if not self.refresh_token:
            raise RuntimeError(
                "No refresh token — please reconnect your Microsoft account."
            )

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(MS_TOKEN_URL, data={
                "client_id":     self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type":    "refresh_token",
                "scope":         SCOPES,
            })
            r.raise_for_status()
            data = r.json()

        self.access_token = data["access_token"]
        if "refresh_token" in data:
            self.refresh_token = data["refresh_token"]
        self.token_expiry = (
            datetime.now(timezone.utc)
            + timedelta(seconds=data.get("expires_in", 3600))
        ).isoformat()
        return self.access_token  # type: ignore[return-value]

    # ── Graph API calls ───────────────────────────────────────────────────────

    async def get_events(self, days_ahead: int = 7) -> list[CalendarEvent]:
        from core.privacy import record_net
        record_net("calendar")
        token = await self._refresh_if_needed()
        now   = datetime.now(timezone.utc)
        end   = now + timedelta(days=days_ahead)

        params = {
            "startDateTime": now.isoformat(),
            "endDateTime":   end.isoformat(),
            "$orderby":      "start/dateTime",
            "$top":          "20",
            "$select":       "id,subject,start,end,location,body,isAllDay",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{GRAPH_BASE}/me/calendarView",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            r.raise_for_status()
            data = r.json()

        events = []
        for item in data.get("value", []):
            start_raw = item.get("start", {})
            end_raw   = item.get("end",   {})
            all_day   = item.get("isAllDay", False)

            def _parse_dt(raw: dict) -> datetime:
                dt_str = raw.get("dateTime", "")
                # Graph returns local time with timezone name — normalise to UTC
                try:
                    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except Exception:
                    return datetime.now(timezone.utc)

            location_obj = item.get("location", {})
            location     = location_obj.get("displayName") if location_obj else None
            description  = item.get("body", {}).get("content", "") if item.get("body") else ""

            events.append(CalendarEvent(
                id          = item.get("id", ""),
                title       = item.get("subject", "(No subject)"),
                start       = _parse_dt(start_raw),
                end         = _parse_dt(end_raw),
                location    = location or None,
                description = description or None,
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
            "subject": title,
            "body": {"contentType": "text", "content": description},
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end":   {"dateTime": end.isoformat(),   "timeZone": "UTC"},
        }
        if location:
            body["location"] = {"displayName": location}

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{GRAPH_BASE}/me/events",
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
            title       = item.get("subject", title),
            start       = start,
            end         = end,
            description = description,
            location    = location or None,
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
