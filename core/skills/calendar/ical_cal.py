# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""
Local .ics calendar provider.

Reads any standard iCalendar (.ics) file.
Works offline, no auth needed. Read-only.

How to get your .ics file:
- Google Calendar: Settings → Export → Downloads a .ics file
- Outlook: File → Save Calendar → .ics
- Apple Calendar: File → Export → Export…
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path

from core.skills.calendar.base import CalendarEvent, CalendarProvider


class ICalProvider(CalendarProvider):
    provider_id = "ical"

    def __init__(self, config: dict):
        self.file_path = config.get("file_path", "")

    def is_connected(self) -> bool:
        return bool(self.file_path) and Path(self.file_path).expanduser().exists()

    async def get_events(self, days_ahead: int = 7) -> list[CalendarEvent]:
        try:
            from icalendar import Calendar  # pip install icalendar
        except ImportError:
            raise RuntimeError(
                "icalendar package not installed. Run: pip install icalendar"
            )

        p = Path(self.file_path).expanduser()
        if not p.exists():
            raise FileNotFoundError(f"Calendar file not found: {p}")

        cal  = Calendar.from_ical(p.read_bytes())
        now  = datetime.now(timezone.utc)
        end  = now + timedelta(days=days_ahead)
        events = []

        for component in cal.walk():
            if component.name != "VEVENT":
                continue

            try:
                dtstart = component.get("DTSTART").dt
                dtend   = component.get("DTEND").dt

                # Normalise to datetime with timezone
                if not hasattr(dtstart, "hour"):  # date object, not datetime
                    all_day  = True
                    dtstart  = datetime(dtstart.year, dtstart.month, dtstart.day, tzinfo=timezone.utc)
                    dtend    = datetime(dtend.year,   dtend.month,   dtend.day,   tzinfo=timezone.utc)
                else:
                    all_day = False
                    if dtstart.tzinfo is None:
                        dtstart = dtstart.replace(tzinfo=timezone.utc)
                    if dtend.tzinfo is None:
                        dtend = dtend.replace(tzinfo=timezone.utc)

                if not (now <= dtstart <= end):
                    continue

                events.append(CalendarEvent(
                    id          = str(component.get("UID", "")),
                    title       = str(component.get("SUMMARY", "(No title)")),
                    start       = dtstart,
                    end         = dtend,
                    location    = str(component.get("LOCATION", "")) or None,
                    description = str(component.get("DESCRIPTION", "")) or None,
                    all_day     = all_day,
                ))
            except Exception:
                continue

        return sorted(events, key=lambda e: e.start)[:20]

    async def create_event(self, title, start, end, description="", location=""):
        raise NotImplementedError(
            "Local .ics files are read-only. Connect Google Calendar or Outlook to create events."
        )
