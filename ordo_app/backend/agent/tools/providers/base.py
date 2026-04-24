"""
Base class and shared helpers for calendar providers.

Concrete providers (GoogleProvider, MicrosoftProvider, ...) subclass
CalendarProvider and implement the four abstract async methods:
  - get_events
  - book_event
  - cancel_event
  - reschedule_event

Each provider also declares its TOOL_DEFINITIONS (the JSON schemas Claude sees)
and its canonical `name` (e.g. "google", "microsoft") used to join DB rows.
"""

import logging
import pytz
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any

from classes import OrdoDB


logger = logging.getLogger(__name__)


class CalendarProvider(ABC):
    """Abstract interface every calendar provider must implement."""

    #: Canonical provider key as stored in the DB ("google", "microsoft", ...).
    name: str = ""

    #: Human-readable label used in error messages.
    display_name: str = ""

    #: Claude tool schemas contributed by this provider.
    TOOL_DEFINITIONS: list[dict] = []

    def __init__(self, db: OrdoDB | None = None):
        self.db = db or OrdoDB()
        self.logger = logging.getLogger(f"{__name__}.{self.name or 'provider'}")

    # ------------------------------------------------------------------
    # Tool name helpers
    # ------------------------------------------------------------------

    def tool_names(self) -> list[str]:
        return [t["name"] for t in self.TOOL_DEFINITIONS]

    def tool_map(self) -> dict[str, Any]:
        """Map of `tool_name -> bound method` for this provider."""
        return {
            f"{self.name}_get_events": self.get_events,
            f"{self.name}_book_event": self.book_event,
            f"{self.name}_cancel_event": self.cancel_event,
            f"{self.name}_reschedule_event": self.reschedule_event,
        }

    # ------------------------------------------------------------------
    # Shared helpers usable by every subclass
    # ------------------------------------------------------------------

    @staticmethod
    def parse_bound(value: str, tz) -> datetime:
        """Accept ISO 8601 datetime or 'YYYY-MM-DD'; return tz-aware datetime."""
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            dt = datetime.strptime(value, "%Y-%m-%d")
        return tz.localize(dt) if dt.tzinfo is None else dt.astimezone(tz)

    def load_integrations(
        self,
        app_id: str,
        user_id: str,
        email: str | None = None,
    ) -> list[dict]:
        """Fetch the integration rows for this provider. Optionally scoped to one email."""
        rows = (
            [self.db.get_integration(app_id, user_id, self.name, email=email)]
            if email
            else self.db.get_integrations_by_provider(app_id, user_id, self.name)
        )
        return [r for r in rows if r]

    def compute_window(
        self,
        integration: dict,
        start: str | None,
        end: str | None,
        lookahead_weeks: int | None,
    ) -> tuple[datetime, datetime] | dict:
        """Resolve the (window_start, window_end) datetime pair in the integration's timezone.

        Returns the pair on success, or an error-envelope dict if inputs are invalid.
        """
        tz_name = integration.get("timezone") or "America/New_York"
        tz = pytz.timezone(tz_name)

        if start and end:
            try:
                window_start = self.parse_bound(start, tz)
                window_end = self.parse_bound(end, tz)
            except ValueError:
                return {
                    "success": False,
                    "error": "start and end must be ISO 8601 datetimes or YYYY-MM-DD",
                }
            if window_end <= window_start:
                return {"success": False, "error": "end must be after start"}
            return window_start, window_end

        window_start = datetime.now(tz)
        weeks = lookahead_weeks or integration.get("lookahead_weeks") or 2
        window_end = window_start + timedelta(weeks=weeks)
        return window_start, window_end

    def fail(self, op: str, err: Exception, email: str | None = None) -> dict:
        suffix = f" ({email})" if email else ""
        self.logger.error(f"{self.name}.{op}{suffix} error: {err}")
        return {"success": False, "error": str(err)}

    # ------------------------------------------------------------------
    # Abstract API
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_events(
        self,
        app_id: str,
        user_id: str,
        email: str | None = None,
        lookahead_weeks: int | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> dict:
        ...

    @abstractmethod
    async def book_event(
        self,
        app_id: str,
        user_id: str,
        title: str,
        start_time: str,
        end_time: str,
        attendee_emails: list[str],
        email: str | None = None,
        description: str = "",
        **extra: Any,
    ) -> dict:
        ...

    @abstractmethod
    async def cancel_event(
        self,
        app_id: str,
        user_id: str,
        event_id: str,
        email: str | None = None,
    ) -> dict:
        ...

    @abstractmethod
    async def reschedule_event(
        self,
        app_id: str,
        user_id: str,
        event_id: str,
        start_time: str,
        end_time: str,
        email: str | None = None,
    ) -> dict:
        ...
