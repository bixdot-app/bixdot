# Copyright (c) 2026 DigiTech Business Pte. Ltd. All rights reserved.
# Licensed under the Business Source License 1.1 (BUSL-1.1).

"""Calendar skill — base types."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CalendarEvent:
    id: str
    title: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    description: Optional[str] = None
    all_day: bool = False

    def friendly(self) -> str:
        """Human-readable single-line summary."""
        day = self.start.strftime("%a %d %b")
        if self.all_day:
            return f"{day} — {self.title} (all day)"
        t = self.start.strftime("%H:%M")
        return f"{day} {t} — {self.title}"


class CalendarProvider:
    """Abstract base for all calendar backends."""
    provider_id: str = "base"

    async def get_events(self, days_ahead: int = 7) -> list[CalendarEvent]:
        raise NotImplementedError

    async def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        description: str = "",
        location: str = "",
    ) -> CalendarEvent:
        raise NotImplementedError

    def is_connected(self) -> bool:
        raise NotImplementedError
