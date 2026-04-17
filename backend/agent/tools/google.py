import json, logging, pytz
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


async def _get_service(app_id: str, user_id: str, email: str = None):
    credentials, integration = await get_refreshed_credentials(app_id, user_id, "google", email=email)
    service = build("calendar", "v3", credentials=credentials)
    return service, integration


async def get_events(app_id: str, user_id: str, email: str = None,
                     lookahead_weeks: int = None) -> dict:
    try:
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
                service = build("calendar", "v3", credentials=credentials)

                tz_name = integration.get("timezone") or "America/New_York"
                tz = pytz.timezone(tz_name)
                now = datetime.now(tz)
                weeks = lookahead_weeks or integration.get("lookahead_weeks") or 2
                end = now + timedelta(weeks=weeks)

                items = service.events().list(
                    calendarId=integration.get("calendar_id"),
                    timeMin=now.isoformat(),
                    timeMax=end.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                ).execute().get("items", [])

                for item in items:
                    item["_ordo_account"] = integration["email"]

                all_events.extend(items)

            except Exception as e:
                logger.error(f"google.get_events error for {integration.get('email')}: {e}")
                continue

        all_events.sort(key=lambda e: (
            (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date") or ""
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
