"""Google Calendar integration — free/busy and event creation."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class GoogleCalendarClient:
    def __init__(self, calendar_id: str, service_account_json: str, tz_name: str = "Europe/Moscow"):
        self.calendar_id = calendar_id
        self.tz_name = tz_name
        self._creds = None
        self._service = None
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            info = json.loads(service_account_json)
            scopes = ["https://www.googleapis.com/auth/calendar"]
            self._creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
            self._service = build("calendar", "v3", credentials=self._creds, cache_discovery=False)
        except Exception as e:
            logger.warning("Google Calendar init failed: %s", e)

    @property
    def available(self) -> bool:
        return self._service is not None

    def get_busy_slots(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        if not self._service:
            return []
        tz = ZoneInfo(self.tz_name)
        body = {
            "timeMin": start.astimezone(tz).isoformat(),
            "timeMax": end.astimezone(tz).isoformat(),
            "items": [{"id": self.calendar_id}],
        }
        try:
            result = self._service.freebusy().query(body=body).execute()
            busy = result.get("calendars", {}).get(self.calendar_id, {}).get("busy", [])
            out = []
            for b in busy:
                out.append(
                    (
                        datetime.fromisoformat(b["start"].replace("Z", "+00:00")),
                        datetime.fromisoformat(b["end"].replace("Z", "+00:00")),
                    )
                )
            return out
        except Exception as e:
            logger.exception("freebusy error: %s", e)
            return []

    def create_event(
        self,
        summary: str,
        start: datetime,
        duration_minutes: int = 60,
        description: str = "",
        attendee_email: str | None = None,
    ) -> str | None:
        if not self._service:
            return None
        tz = ZoneInfo(self.tz_name)
        end = start + timedelta(minutes=duration_minutes)
        event: dict[str, Any] = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.astimezone(tz).isoformat(), "timeZone": self.tz_name},
            "end": {"dateTime": end.astimezone(tz).isoformat(), "timeZone": self.tz_name},
        }
        if attendee_email:
            event["attendees"] = [{"email": attendee_email}]
        try:
            created = self._service.events().insert(calendarId=self.calendar_id, body=event).execute()
            return created.get("id")
        except Exception as e:
            logger.exception("create event error: %s", e)
            return None

    def filter_available_slots(
        self,
        slots: list[Any],
        busy: list[tuple[datetime, datetime]],
    ) -> list[Any]:
        if not busy:
            return slots
        available = []
        for slot in slots:
            start = slot.starts_at
            end = start + timedelta(hours=1)
            conflict = any(not (end <= b_start or start >= b_end) for b_start, b_end in busy)
            if not conflict:
                available.append(slot)
        return available if available else slots
