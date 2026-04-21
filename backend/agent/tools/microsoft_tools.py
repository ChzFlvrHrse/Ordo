import pytz
import logging
from classes import OrdoDB
from httpx import AsyncClient
from datetime import datetime, timedelta
from api.calendar import get_refreshed_token_microsoft

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = OrdoDB()

TOOL_DEFINITIONS = [
    {
        "name": "microsoft_get_events",
        "description": "Retrieve upcoming Microsoft Calendar events for the user. Fetches from all connected Microsoft accounts by default. If the user has multiple Microsoft accounts and wants events from a specific one, pass the email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Optional. The Microsoft account email to fetch from. If omitted, fetches from all connected accounts.",
                },
                "lookahead_weeks": {
                    "type": "integer",
                    "description": "Number of weeks to look ahead. Defaults to integration setting.",
                },
                "start": {
                    "type": "string",
                    "description": "Optional. Start of the time window. Accepts ISO 8601 datetime or 'YYYY-MM-DD'. Must be passed together with end.",
                },
                "end": {
                    "type": "string",
                    "description": "Optional. End of the time window. Accepts ISO 8601 datetime or 'YYYY-MM-DD'. Must be passed together with start.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "microsoft_book_event",
        "description": "Book a new event on the user's Microsoft Calendar. If the user has multiple Microsoft accounts, ask which one to book on.",
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
                    "description": "Optional. The Microsoft account email to book on. Defaults to first connected account.",
                },
                "add_teams": {"type": "boolean", "description": "Add a Teams meeting link. Defaults to false."},
            },
            "required": ["title", "start_time", "end_time", "attendee_emails"],
        },
    },
    {
        "name": "microsoft_cancel_event",
        "description": "Cancel an existing Microsoft Calendar event by its event ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "The Microsoft Calendar event ID to cancel."},
                "email": {
                    "type": "string",
                    "description": "Optional. The Microsoft account email the event belongs to.",
                },
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "microsoft_reschedule_event",
        "description": "Reschedule an existing Microsoft Calendar event to a new time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "The Microsoft Calendar event ID to reschedule."},
                "start_time": {"type": "string", "description": "New start time in ISO 8601 format."},
                "end_time": {"type": "string", "description": "New end time in ISO 8601 format."},
                "email": {
                    "type": "string",
                    "description": "Optional. The Microsoft account email the event belongs to.",
                },
            },
            "required": ["event_id", "start_time", "end_time"],
        },
    },
]


def _parse_bound(value: str, tz) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.strptime(value, "%Y-%m-%d")
    return tz.localize(dt) if dt.tzinfo is None else dt.astimezone(tz)


async def _get_token(app_id: str, user_id: str, email: str = None):
    token, integration = await get_refreshed_token_microsoft(app_id, user_id, email=email)
    return token, integration


async def get_events(app_id: str, user_id: str, email: str = None,
                     lookahead_weeks: int = None,
                     start: str = None, end: str = None) -> dict:
    try:
        if bool(start) ^ bool(end):
            return {"success": False, "error": "Pass both start and end together"}

        integrations = (
            [db.get_integration(app_id, user_id, "microsoft", email=email)]
            if email
            else db.get_integrations_by_provider(app_id, user_id, "microsoft")
        )
        integrations = [i for i in integrations if i]

        if not integrations:
            return {"success": False, "error": "No Microsoft Calendar integration found"}

        all_events = []

        for integration in integrations:
            try:
                token, integration = await get_refreshed_token_microsoft(
                    app_id, user_id, email=integration["email"]
                )

                tz_name = integration.get("timezone") or "America/New_York"
                tz = pytz.timezone(tz_name)

                if start and end:
                    try:
                        window_start = _parse_bound(start, tz)
                        window_end = _parse_bound(end, tz)
                    except ValueError:
                        return {"success": False, "error": "start and end must be ISO 8601 datetimes or YYYY-MM-DD"}
                    if window_end <= window_start:
                        return {"success": False, "error": "end must be after start"}
                else:
                    window_start = datetime.now(tz)
                    weeks = lookahead_weeks or integration.get("lookahead_weeks") or 2
                    window_end = window_start + timedelta(weeks=weeks)

                items = []
                url = "https://graph.microsoft.com/v1.0/me/calendarView"
                headers = {"Authorization": f"Bearer {token}"}
                params = {
                    "startDateTime": window_start.isoformat(),
                    "endDateTime": window_end.isoformat(),
                    "$orderby": "start/dateTime",
                    "$top": 100,
                }

                async with AsyncClient() as client:
                    while url:
                        resp = await client.get(url, headers=headers, params=params if "calendarView" in url else None)
                        data = resp.json()
                        batch = data.get("value", [])
                        for item in batch:
                            item["_ordo_account"] = integration["email"]
                        items.extend(batch)
                        url = data.get("@odata.nextLink")

                all_events.extend(items)

            except Exception as e:
                logger.error(f"microsoft.get_events error for {integration.get('email')}: {e}")
                continue

        all_events.sort(key=lambda e: (e.get("start") or {}).get("dateTime") or "")

        return {"success": True, "events": all_events, "count": len(all_events)}

    except Exception as e:
        logger.error(f"microsoft.get_events error: {e}")
        return {"success": False, "error": str(e)}


async def book_event(app_id: str, user_id: str, title: str, start_time: str,
                     end_time: str, attendee_emails: list,
                     email: str = None, description: str = "",
                     add_teams: bool = False) -> dict:
    try:
        token, integration = await _get_token(app_id, user_id, email=email)
        tz_name = integration.get("timezone") or "America/New_York"

        event_body = {
            "subject": title,
            "body": {"contentType": "text", "content": description or ""},
            "start": {"dateTime": start_time, "timeZone": tz_name},
            "end": {"dateTime": end_time, "timeZone": tz_name},
            "attendees": [
                {"emailAddress": {"address": e}, "type": "required"}
                for e in attendee_emails
            ],
        }

        if add_teams:
            event_body["isOnlineMeeting"] = True
            event_body["onlineMeetingProvider"] = "teamsForBusiness"

        async with AsyncClient() as client:
            resp = await client.post(
                "https://graph.microsoft.com/v1.0/me/events",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=event_body,
            )
            event = resp.json()

        return {"success": True, "event": event, "account": integration["email"]}

    except Exception as e:
        logger.error(f"microsoft.book_event error: {e}")
        return {"success": False, "error": str(e)}


async def cancel_event(app_id: str, user_id: str, event_id: str,
                       email: str = None) -> dict:
    try:
        token, _ = await _get_token(app_id, user_id, email=email)

        async with AsyncClient() as client:
            resp = await client.delete(
                f"https://graph.microsoft.com/v1.0/me/events/{event_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        if resp.status_code not in (200, 204):
            return {"success": False, "error": f"Graph API error: {resp.text}"}

        return {"success": True}

    except Exception as e:
        logger.error(f"microsoft.cancel_event error: {e}")
        return {"success": False, "error": str(e)}


async def reschedule_event(app_id: str, user_id: str, event_id: str,
                           start_time: str, end_time: str,
                           email: str = None) -> dict:
    try:
        token, integration = await _get_token(app_id, user_id, email=email)
        tz_name = integration.get("timezone") or "America/New_York"

        async with AsyncClient() as client:
            resp = await client.patch(
                f"https://graph.microsoft.com/v1.0/me/events/{event_id}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={
                    "start": {"dateTime": start_time, "timeZone": tz_name},
                    "end": {"dateTime": end_time, "timeZone": tz_name},
                },
            )
            event = resp.json()

        return {"success": True, "event": event}

    except Exception as e:
        logger.error(f"microsoft.reschedule_event error: {e}")
        return {"success": False, "error": str(e)}
