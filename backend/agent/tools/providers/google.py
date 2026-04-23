from googleapiclient.discovery import build
from api.calendar import get_refreshed_credentials_google
from .base import CalendarProvider


GOOGLE_TOOL_DEFINITIONS = [
    {
        "name": "google_get_events",
        "description": "Retrieve upcoming Google Calendar events for the user. Fetches from all connected Google accounts by default. If the user has multiple Google accounts and wants events from a specific one, pass the email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Optional. The Google account email to fetch from. If omitted, fetches from all connected accounts.",
                },
                "lookahead_weeks": {
                    "type": "integer",
                    "description": "Number of weeks to look ahead. Defaults to integration setting.",
                },
                "start": {
                    "type": "string",
                    "description": "Optional. Start of the time window. Accepts ISO 8601 datetime (e.g. '2026-04-18T00:00:00Z') or 'YYYY-MM-DD'. Must be passed together with `end`.",
                },
                "end": {
                    "type": "string",
                    "description": "Optional. End of the time window (exclusive). Accepts ISO 8601 datetime or 'YYYY-MM-DD'. Must be passed together with `start`.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "google_book_event",
        "description": "Book a new event on the user's Google Calendar. If the user has multiple Google accounts, ask which one to book on.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title of the event."},
                "start_time": {"type": "string", "description": "Start time in ISO 8601 format."},
                "end_time": {"type": "string", "description": "End time in ISO 8601 format."},
                "description": {"type": "string", "description": "Optional description or notes."},
                "attendee_emails": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of attendee email addresses.",
                },
                "email": {
                    "type": "string",
                    "description": "Optional. The Google account email to book on. Defaults to first connected account.",
                },
                "add_meet": {"type": "boolean", "description": "Add a Google Meet link. Defaults to false."},
            },
            "required": ["title", "start_time", "end_time", "attendee_emails"],
        },
    },
    {
        "name": "google_cancel_event",
        "description": "Cancel an existing Google Calendar event by its event ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "The Google Calendar event ID to cancel."},
                "email": {
                    "type": "string",
                    "description": "Optional. The Google account email the event belongs to.",
                },
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "google_reschedule_event",
        "description": "Reschedule an existing Google Calendar event to a new time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "The Google Calendar event ID to reschedule."},
                "start_time": {"type": "string", "description": "New start time in ISO 8601 format."},
                "end_time": {"type": "string", "description": "New end time in ISO 8601 format."},
                "email": {
                    "type": "string",
                    "description": "Optional. The Google account email the event belongs to.",
                },
            },
            "required": ["event_id", "start_time", "end_time"],
        },
    },
]


class GoogleProvider(CalendarProvider):
    name = "google"
    display_name = "Google"
    TOOL_DEFINITIONS = GOOGLE_TOOL_DEFINITIONS

    async def _service(self, app_id: str, user_id: str, email: str | None = None):
        credentials, integration = await get_refreshed_credentials_google(
            app_id, user_id, "google", email=email
        )
        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        return service, integration

    async def get_events(
        self,
        app_id: str,
        user_id: str,
        email: str | None = None,
        lookahead_weeks: int | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> dict:
        try:
            if bool(start) ^ bool(end):
                return {"success": False, "error": "Pass both start and end together"}

            integrations = self.load_integrations(app_id, user_id, email=email)
            if not integrations:
                return {"success": False, "error": "No Google Calendar integration found"}

            all_events: list[dict] = []

            for integration in integrations:
                try:
                    credentials, integration = await get_refreshed_credentials_google(
                        app_id, user_id, "google", email=integration["email"]
                    )
                    service = build(
                        "calendar", "v3", credentials=credentials, cache_discovery=False
                    )

                    window = self.compute_window(integration, start, end, lookahead_weeks)
                    if isinstance(window, dict):
                        return window
                    window_start, window_end = window

                    items = (
                        service.events()
                        .list(
                            calendarId=integration.get("calendar_id"),
                            timeMin=window_start.isoformat(),
                            timeMax=window_end.isoformat(),
                            singleEvents=True,
                            orderBy="startTime",
                        )
                        .execute()
                        .get("items", [])
                    )

                    for item in items:
                        item["_ordo_account"] = integration["email"]

                    all_events.extend(items)

                except Exception as e:
                    self.logger.error(
                        f"google.get_events error for {integration.get('email')}: {e}"
                    )
                    continue

            all_events.sort(
                key=lambda e: (
                    (e.get("start") or {}).get("dateTime")
                    or (e.get("start") or {}).get("date")
                    or ""
                )
            )

            return {"success": True, "events": all_events, "count": len(all_events)}

        except Exception as e:
            return self.fail("get_events", e)

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
        add_meet: bool = False,
        **_: dict,
    ) -> dict:
        try:
            service, integration = await self._service(app_id, user_id, email=email)
            tz_name = integration.get("timezone") or "America/New_York"

            event_body: dict = {
                "summary": title,
                "description": description,
                "start": {"dateTime": start_time, "timeZone": tz_name},
                "end": {"dateTime": end_time, "timeZone": tz_name},
                "attendees": [{"email": e} for e in attendee_emails],
            }

            if add_meet:
                event_body["conferenceData"] = {
                    "createRequest": {
                        "requestId": f"{user_id}-{start_time}",
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                }

            insert_kwargs: dict = {
                "calendarId": integration.get("calendar_id"),
                "body": event_body,
                "sendUpdates": "all",
            }
            if add_meet:
                insert_kwargs["conferenceDataVersion"] = 1

            event = service.events().insert(**insert_kwargs).execute()
            return {"success": True, "event": event, "account": integration["email"]}

        except Exception as e:
            return self.fail("book_event", e)

    async def cancel_event(
        self,
        app_id: str,
        user_id: str,
        event_id: str,
        email: str | None = None,
    ) -> dict:
        try:
            service, integration = await self._service(app_id, user_id, email=email)
            service.events().delete(
                calendarId=integration.get("calendar_id"),
                eventId=event_id,
                sendUpdates="all",
            ).execute()
            return {"success": True}
        except Exception as e:
            return self.fail("cancel_event", e)

    async def reschedule_event(
        self,
        app_id: str,
        user_id: str,
        event_id: str,
        start_time: str,
        end_time: str,
        email: str | None = None,
    ) -> dict:
        try:
            service, integration = await self._service(app_id, user_id, email=email)
            tz_name = integration.get("timezone") or "America/New_York"

            existing = (
                service.events()
                .get(
                    calendarId=integration.get("calendar_id"),
                    eventId=event_id,
                )
                .execute()
            )

            existing["start"] = {"dateTime": start_time, "timeZone": tz_name}
            existing["end"] = {"dateTime": end_time, "timeZone": tz_name}

            event = (
                service.events()
                .update(
                    calendarId=integration.get("calendar_id"),
                    eventId=event_id,
                    body=existing,
                    sendUpdates="all",
                )
                .execute()
            )

            return {"success": True, "event": event}

        except Exception as e:
            return self.fail("reschedule_event", e)
