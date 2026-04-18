import json
import logging
import pytz
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from api.calendar import get_refreshed_credentials
from classes import OrdoDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = OrdoDB()

TOOL_DEFINITIONS = [
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
    {
        "name": "google_get_collisions",
        "description": "Check for any pending calendar collision notifications for the user. Call this after booking an event to see if any conflicts were detected.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "google_resolve_collision",
        "description": "Resolve a calendar collision. Present the user with all three options before calling this.",
        "input_schema": {
            "type": "object",
            "properties": {
                "notification_id": {
                    "type": "string",
                    "description": "The collision notification ID to resolve.",
                },
                "resolution": {
                    "type": "string",
                    "enum": ["keep_new", "keep_old", "manual"],
                    "description": "keep_new: delete the conflicting old event. keep_old: delete the newly created event. manual: acknowledge and handle manually.",
                },
            },
            "required": ["notification_id", "resolution"],
        },
    },
]


async def _get_service(app_id: str, user_id: str, email: str = None):
    credentials, integration = await get_refreshed_credentials(app_id, user_id, "google", email=email)
    service = build("calendar", "v3", credentials=credentials,
                    cache_discovery=False)
    return service, integration


def _parse_bound(value: str, tz) -> datetime:
    """Accept ISO 8601 datetime or YYYY-MM-DD; return tz-aware datetime in `tz`."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.strptime(value, "%Y-%m-%d")
    return tz.localize(dt) if dt.tzinfo is None else dt.astimezone(tz)


async def get_events(app_id: str, user_id: str, email: str = None,
                     lookahead_weeks: int = None,
                     start: str = None, end: str = None) -> dict:
    try:
        if bool(start) ^ bool(end):
            return {"success": False, "error": "Pass both start and end together"}

        integrations = (
            [db.get_integration(app_id, user_id, "google", email=email)]
            if email
            else db.get_integrations_by_provider(app_id, user_id, "google")
        )
        integrations = [i for i in integrations if i]

        if not integrations:
            return {"success": False, "error": "No Google Calendar integration found"}

        all_events = []

        for integration in integrations:
            try:
                credentials, integration = await get_refreshed_credentials(
                    app_id, user_id, "google", email=integration["email"]
                )
                service = build("calendar", "v3",
                                credentials=credentials, cache_discovery=False)

                tz_name = integration.get("timezone") or "America/New_York"
                tz = pytz.timezone(tz_name)

                if start and end:
                    try:
                        window_start = _parse_bound(start, tz)
                        window_end = _parse_bound(end, tz)
                    except ValueError:
                        return {
                            "success": False,
                            "error": "start and end must be ISO 8601 datetimes or YYYY-MM-DD",
                        }
                    if window_end <= window_start:
                        return {"success": False, "error": "end must be after start"}
                else:
                    window_start = datetime.now(tz)
                    weeks = lookahead_weeks or integration.get(
                        "lookahead_weeks") or 2
                    window_end = window_start + timedelta(weeks=weeks)

                items = service.events().list(
                    calendarId=integration.get("calendar_id"),
                    timeMin=window_start.isoformat(),
                    timeMax=window_end.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                ).execute().get("items", [])

                for item in items:
                    item["_ordo_account"] = integration["email"]

                all_events.extend(items)

            except Exception as e:
                logger.error(
                    f"google.get_events error for {integration.get('email')}: {e}")
                continue

        all_events.sort(key=lambda e: (
            (e.get("start") or {}).get("dateTime") or (
                e.get("start") or {}).get("date") or ""
        ))

        return {"success": True, "events": all_events, "count": len(all_events)}

    except Exception as e:
        logger.error(f"google.get_events error: {e}")
        return {"success": False, "error": str(e)}


async def book_event(app_id: str, user_id: str, title: str, start_time: str,
                     end_time: str, attendee_emails: list,
                     email: str = None, description: str = "",
                     add_meet: bool = False) -> dict:
    try:
        service, integration = await _get_service(app_id, user_id, email=email)
        tz_name = integration.get("timezone") or "America/New_York"

        event_body = {
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

        insert_kwargs = {
            "calendarId": integration.get("calendar_id"),
            "body": event_body,
            "sendUpdates": "all",
        }
        if add_meet:
            insert_kwargs["conferenceDataVersion"] = 1

        event = service.events().insert(**insert_kwargs).execute()
        return {"success": True, "event": event, "account": integration["email"]}

    except Exception as e:
        logger.error(f"google.book_event error: {e}")
        return {"success": False, "error": str(e)}


async def cancel_event(app_id: str, user_id: str, event_id: str,
                       email: str = None) -> dict:
    try:
        service, integration = await _get_service(app_id, user_id, email=email)
        service.events().delete(
            calendarId=integration.get("calendar_id"),
            eventId=event_id,
            sendUpdates="all",
        ).execute()
        return {"success": True}

    except Exception as e:
        logger.error(f"google.cancel_event error: {e}")
        return {"success": False, "error": str(e)}


async def reschedule_event(app_id: str, user_id: str, event_id: str,
                           start_time: str, end_time: str,
                           email: str = None) -> dict:
    try:
        service, integration = await _get_service(app_id, user_id, email=email)
        tz_name = integration.get("timezone") or "America/New_York"

        existing = service.events().get(
            calendarId=integration.get("calendar_id"),
            eventId=event_id,
        ).execute()

        existing["start"] = {"dateTime": start_time, "timeZone": tz_name}
        existing["end"] = {"dateTime": end_time, "timeZone": tz_name}

        event = service.events().update(
            calendarId=integration.get("calendar_id"),
            eventId=event_id,
            body=existing,
            sendUpdates="all",
        ).execute()

        return {"success": True, "event": event}

    except Exception as e:
        logger.error(f"google.reschedule_event error: {e}")
        return {"success": False, "error": str(e)}


async def get_collisions(app_id: str, user_id: str) -> dict:
    try:
        collisions = db.get_pending_collisions(app_id, user_id)
        return {"success": True, "collisions": collisions, "count": len(collisions)}
    except Exception as e:
        logger.error(f"google.get_collisions error: {e}")
        return {"success": False, "error": str(e)}


async def resolve_collision(app_id: str, user_id: str,
                            notification_id: str, resolution: str) -> dict:
    try:
        updated = db.resolve_collision(notification_id, resolution)
        if not updated:
            return {"success": False, "error": "Notification not found"}

        # If keep_new, cancel the old conflicting events
        if resolution == "keep_new":
            for colliding in updated.get("colliding_events", []):
                await cancel_event(app_id, user_id, colliding["id"])

        # If keep_old, cancel the new event
        elif resolution == "keep_old":
            await cancel_event(app_id, user_id, updated["new_event_id"])

        return {"success": True, "collision": updated}
    except Exception as e:
        logger.error(f"google.resolve_collision error: {e}")
        return {"success": False, "error": str(e)}
