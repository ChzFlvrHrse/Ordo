import pytz
import logging
from classes import OrdoDB
from httpx import AsyncClient
from zoneinfo import ZoneInfo
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from agent.tools.providers import get_provider
from api.calendar import (
    get_refreshed_credentials_google,
    get_refreshed_token_microsoft
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = OrdoDB()

TOOL_DEFINITIONS = [
    {
        "name": "calendar_get_events",
        "description": "Retrieve upcoming events across ALL connected calendars and providers. Use this before booking to check for conflicts at a given time, or when the user wants to see their full schedule.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {
                    "type": "string",
                    "description": "Start of the time window. Accepts ISO 8601 datetime or 'YYYY-MM-DD'. Must be passed together with end.",
                },
                "end": {
                    "type": "string",
                    "description": "End of the time window. Accepts ISO 8601 datetime or 'YYYY-MM-DD'. Must be passed together with start.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "calendar_get_collisions",
        "description": "Check for any pending collision notifications across all connected calendars. Optionally pass event_id to only check collisions for a specific event just booked.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "Optional. The event ID just booked to scope the collision check to that event only.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "calendar_resolve_collision",
        "description": (
            "Resolve a calendar collision. Always present the user with all four options before calling this:\n"
            "A) Keep new — delete the conflicting old event\n"
            "B) Keep old — delete the newly created event\n"
            "C) Recommend — analyze both events and recommend which to keep with reasoning, then confirm with user before resolving\n"
            "D) Manual — acknowledge and let the user handle it themselves\n\n"
            "For option C, do NOT call this tool first. Analyze the events, give your recommendation, "
            "then wait for confirmation before calling this tool with keep_new or keep_old."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "notification_id": {
                    "type": "string",
                    "description": "The collision notification ID to resolve.",
                },
                "resolution": {
                    "type": "string",
                    "enum": ["keep_new", "keep_old", "manual", "dismiss"],
                    "description": "keep_new: delete the conflicting old event. keep_old: delete the newly created event. manual: user will handle it themselves. dismiss: keep both events and mark the conflict as resolved.",
                },
            },
            "required": ["notification_id", "resolution"],
        },
    },
    {
        "name": "calendar_resolve_all_collisions",
        "description": "Resolve multiple calendar collision notifications at once with the same resolution. Use when the user wants to apply the same action to all or multiple conflicts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "notification_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of collision notification IDs to resolve. Pass all pending IDs to resolve everything at once.",
                },
                "resolution": {
                    "type": "string",
                    "enum": ["keep_new", "keep_old", "manual", "dismiss"],
                    "description": "Resolution to apply to all notifications. keep_new: delete conflicting old events. keep_old: delete newly created events. manual: mark as resolved, user handles. dismiss: keep both, dismiss conflicts.",
                },
            },
            "required": ["notification_ids", "resolution"],
        },
    },
    {
        "name": "calendar_get_busy_blocks",
        "description": (
            "Get all busy time blocks across the user's connected calendars (Google, Outlook) "
            "for a given time window. Returns merged, non-overlapping intervals when calendars overlap. "
            "Use this before generating available slots or checking if a proposed time is free."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {
                    "type": "string",
                    "description": "Start of the time window in UTC ISO8601 format. e.g. '2026-04-23T00:00:00+00:00'",
                },
                "end": {
                    "type": "string",
                    "description": "End of the time window in UTC ISO8601 format. e.g. '2026-04-30T23:59:59+00:00'",
                },
            },
            "required": ["start", "end"],
        },
    }
]


def _parse_bound(value: str, tz) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.strptime(value, "%Y-%m-%d")
    return tz.localize(dt) if dt.tzinfo is None else dt.astimezone(tz)


async def _fetch_google_events(app_id: str, user_id: str, email: str,
                               window_start: datetime, window_end: datetime) -> list:
    try:
        credentials, integration = await get_refreshed_credentials_google(
            app_id, user_id, "google", email=email
        )
        service = build("calendar", "v3",
                        credentials=credentials, cache_discovery=False)

        items = service.events().list(
            calendarId=integration.get("calendar_id") or "primary",
            timeMin=window_start.isoformat(),
            timeMax=window_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute().get("items", [])

        for item in items:
            item["_ordo_account"] = email
            item["_ordo_provider"] = "google"

        return items
    except Exception as e:
        logger.error(f"calendar._fetch_google_events error for {email}: {e}")
        return []


async def _fetch_microsoft_events(app_id: str, user_id: str, email: str,
                                  window_start: datetime, window_end: datetime) -> list:
    try:
        token, integration = await get_refreshed_token_microsoft(app_id, user_id, email=email)
        async with AsyncClient() as client:
            resp = await client.get(
                "https://graph.microsoft.com/v1.0/me/calendarView",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "startDateTime": window_start.isoformat(),
                    "endDateTime": window_end.isoformat(),
                    "$orderby": "start/dateTime",
                    "$top": 100,
                },
            )
        items = resp.json().get("value", [])
        for item in items:
            item["_ordo_account"] = email
            item["_ordo_provider"] = "microsoft"
        return items
    except Exception as e:
        logger.error(
            f"calendar._fetch_microsoft_events error for {email}: {e}")
        return []


async def fetch_events_in_window(app_id: str, user_id: str,
                                 integration: dict, start: str, end: str) -> list[dict]:
    provider = integration["provider"]

    if provider == "google":
        creds, integ = await get_refreshed_credentials_google(
            app_id, user_id, "google", email=integration["email"]
        )
        svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
        items = svc.events().list(
            calendarId=integ.get("calendar_id") or "primary",
            timeMin=start,
            timeMax=end,
            singleEvents=True,
        ).execute().get("items", [])

        return [
            {
                "id": e["id"],
                "summary": e.get("summary", "Untitled"),
                "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
                "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
                "email": integration["email"],
                "provider": "google",
            }
            for e in items
            if e.get("status") != "cancelled"
            and (e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"))
        ]

    elif provider == "microsoft":
        token, _ = await get_refreshed_token_microsoft(
            app_id, user_id, email=integration["email"]
        )
        async with AsyncClient() as client:
            resp = await client.get(
                "https://graph.microsoft.com/v1.0/me/calendarView",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "startDateTime": start,
                    "endDateTime": end,
                    "$top": 100,
                },
            )
        items = resp.json().get("value", [])

        return [
            {
                "id": e["id"],
                "summary": e.get("subject", "Untitled"),
                "start": (e.get("start") or {}).get("dateTime"),
                "end": (e.get("end") or {}).get("dateTime"),
                "email": integration["email"],
                "provider": "microsoft",
            }
            for e in items
            if not e.get("isCancelled")
            and (e.get("start") or {}).get("dateTime")
        ]

    return []


async def check_collision(app_id: str, user_id: str, email: str, new_event: dict,
                          service=None, provider: str = "google"):
    start = (new_event.get("start") or {}).get("dateTime")
    end = (new_event.get("end") or {}).get("dateTime")
    event_id = new_event.get("id")
    summary = new_event.get(
        "subject", "Untitled") if provider == "microsoft" else new_event.get("summary", "Untitled")

    if not start or not end:
        return

    integrations = db.get_integrations(app_id, user_id)
    all_collisions = []

    for integration in integrations:
        try:
            events = await fetch_events_in_window(app_id, user_id, integration, start, end)
            for e in events:
                if e["id"] == event_id:
                    continue
                all_collisions.append(e)
        except Exception as ex:
            logger.error(
                f"=== ORDO: check_collision error for {integration.get('email')}: {ex} ===")
            continue

    if not all_collisions:
        return

    logger.info(
        f"=== ORDO: Collision detected for user={user_id} event={summary} ===")

    db.create_collision_notification(
        app_id=app_id,
        user_id=user_id,
        email=email,
        new_event_id=event_id,
        new_event_summary=summary,
        new_event_start=start,
        new_event_end=end,
        colliding_events=all_collisions,
    )


async def get_events(app_id: str, user_id: str,
                     start: str = None, end: str = None) -> dict:
    try:
        if bool(start) ^ bool(end):
            return {"success": False, "error": "Pass both start and end together"}

        integrations = db.get_integrations(app_id, user_id)
        if not integrations:
            return {"success": False, "error": "No calendar integrations found"}

        all_events = []

        for integration in integrations:
            tz_name = integration.get("timezone") or "America/New_York"
            tz = pytz.timezone(tz_name)

            if start and end:
                try:
                    window_start = _parse_bound(start, tz)
                    window_end = _parse_bound(end, tz)
                except ValueError:
                    return {"success": False, "error": "start and end must be ISO 8601 or YYYY-MM-DD"}
                if window_end <= window_start:
                    return {"success": False, "error": "end must be after start"}
            else:
                window_start = datetime.now(tz)
                window_end = window_start + \
                    timedelta(weeks=integration.get("lookahead_weeks") or 2)

            provider = integration.get("provider")
            email = integration["email"]

            if provider == "google":
                items = await _fetch_google_events(app_id, user_id, email, window_start, window_end)
            elif provider == "microsoft":
                items = await _fetch_microsoft_events(app_id, user_id, email, window_start, window_end)
            else:
                continue

            all_events.extend(items)

        all_events.sort(key=lambda e: (
            (e.get("start") or {}).get("dateTime") or
            (e.get("start") or {}).get("date") or ""
        ))

        return {"success": True, "events": all_events, "count": len(all_events)}

    except Exception as e:
        logger.error(f"calendar.get_events error: {e}")
        return {"success": False, "error": str(e)}


async def get_collisions(app_id: str, user_id: str, event_id: str = None) -> dict:
    try:
        db.resolve_expired_collisions(user_id)
        collisions = db.get_pending_collisions(app_id, user_id)
        if event_id:
            collisions = [
                c for c in collisions if c["new_event_id"] == event_id]
        return {"success": True, "collisions": collisions, "count": len(collisions)}
    except Exception as e:
        logger.error(f"calendar.get_collisions error: {e}")
        return {"success": False, "error": str(e)}


async def resolve_collision(app_id: str, user_id: str,
                            notification_id: str, resolution: str) -> dict:
    try:
        if resolution == "recommend":
            return {"success": False, "error": "recommend is not a valid resolution — analyze the events and ask the user to confirm keep_new or keep_old"}

        updated = db.resolve_collision(notification_id, resolution)
        if not updated:
            return {"success": False, "error": "Notification not found"}

        if resolution == "keep_new":
            for colliding in updated.get("colliding_events", []):
                provider = colliding.get("provider")
                email = colliding.get("email")
                event_id = colliding["id"]
                try:
                    await get_provider(provider).cancel_event(
                        app_id, user_id, event_id, email=email
                    )
                except ValueError:
                    logger.warning(f"Unknown provider {provider!r} — skipping cancel")

        elif resolution == "keep_old":
            email = updated.get("email")
            event_id = updated["new_event_id"]
            all_integrations = db.get_integrations(app_id, user_id)
            integration = next(
                (i for i in all_integrations if i["email"] == email), None)
            provider = integration["provider"] if integration else "google"
            try:
                await get_provider(provider).cancel_event(
                    app_id, user_id, event_id, email=email
                )
            except ValueError:
                logger.warning(f"Unknown provider {provider!r} — skipping cancel")

        return {"success": True, "collision": updated}
    except Exception as e:
        logger.error(f"calendar.resolve_collision error: {e}")
        return {"success": False, "error": str(e)}


async def resolve_all_collisions(app_id: str, user_id: str,
                                 notification_ids: list, resolution: str) -> dict:
    try:
        results = []
        errors = []
        for notification_id in notification_ids:
            result = await resolve_collision(app_id, user_id, notification_id, resolution)
            if result.get("success"):
                results.append(notification_id)
            else:
                errors.append(
                    {"id": notification_id, "error": result.get("error")})

        return {
            "success": True,
            "resolved": len(results),
            "errors": errors,
        }
    except Exception as e:
        logger.error(f"calendar.resolve_all_collisions error: {e}")
        return {"success": False, "error": str(e)}


def _collapse_blocks(blocks: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Merge overlapping or adjacent busy intervals."""
    if not blocks:
        return []
    sorted_blocks = sorted(blocks, key=lambda x: x[0])
    merged = [sorted_blocks[0]]
    for start, end in sorted_blocks[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged

# -----------------------------------------------------------------------------
# Available slots
# -----------------------------------------------------------------------------

async def get_busy_blocks(
    app_id: str,
    user_id: str,
    start: str,
    end: str,
) -> dict:
    try:
        integrations = db.get_integrations(app_id, user_id)
        raw_blocks = []

        for integration in integrations:
            provider = integration["provider"]
            if provider in ("google", "microsoft"):
                events = await fetch_events_in_window(app_id, user_id, integration, start, end)
                for e in events:
                    try:
                        block_start = _parse_bound(e["start"], pytz.utc)
                        block_end = _parse_bound(e["end"], pytz.utc)
                        raw_blocks.append((block_start, block_end))
                    except (ValueError, TypeError):
                        continue

        collapsed = _collapse_blocks(raw_blocks)

        return {
            "success": True,
            "busy_blocks": [(s.isoformat(), e.isoformat()) for s, e in collapsed],
            "count": len(collapsed),
        }
    except Exception as ex:
        logger.error(f"calendar.get_busy_blocks error: {ex}")
        return {"success": False, "error": str(ex)}


def generate_available_slots(
    working_hours: list[dict],
    busy_blocks: list[tuple[datetime, datetime]],
    event_type: dict,
    user_tz: str,
    attendee_tz: str,
    start_date: datetime,
    end_date: datetime,
    slot_interval_minutes: int = 15,
    minimum_notice_minutes: int = 30,
) -> list[dict]:

    user_zone = pytz.timezone(user_tz)
    attendee_zone = pytz.timezone(attendee_tz)
    duration = timedelta(minutes=event_type["duration_minutes"])
    buffer_before = timedelta(minutes=event_type["buffer_before"])
    buffer_after = timedelta(minutes=event_type["buffer_after"])
    interval = timedelta(minutes=slot_interval_minutes)
    now = datetime.now(pytz.utc) + timedelta(minutes=minimum_notice_minutes)

    wh_by_day = {
        wh["day_of_week"]: wh
        for wh in working_hours
        if wh["enabled"]
    }

    slots = []
    current_date = start_date

    while current_date.date() <= end_date.date():
        dow = current_date.weekday()

        if dow not in wh_by_day:
            current_date += timedelta(days=1)
            continue

        wh = wh_by_day[dow]

        wh_start_naive = datetime.strptime(
            f"{current_date.date().isoformat()} {wh['start_time']}", "%Y-%m-%d %H:%M"
        )
        wh_end_naive = datetime.strptime(
            f"{current_date.date().isoformat()} {wh['end_time']}", "%Y-%m-%d %H:%M"
        )

        wh_start = user_zone.localize(wh_start_naive)
        wh_end = user_zone.localize(wh_end_naive)

        cursor = wh_start
        while cursor + duration <= wh_end:

            slot_start = cursor
            slot_end = cursor + duration
            padded_start = slot_start - buffer_before
            padded_end = slot_end + buffer_after

            if slot_start < now:
                cursor += interval
                continue

            conflict = any(
                padded_start < block_end and padded_end > block_start
                for block_start, block_end in busy_blocks
            )

            if not conflict:
                slots.append({
                    "start": slot_start.astimezone(pytz.utc).isoformat(),
                    "end": slot_end.astimezone(pytz.utc).isoformat(),
                    "display_start": slot_start.astimezone(attendee_zone).strftime("%Y-%m-%dT%H:%M:%S"),
                    "display_end": slot_end.astimezone(attendee_zone).strftime("%Y-%m-%dT%H:%M:%S"),
                    "display_tz": attendee_tz,
                })

            cursor += interval

        current_date += timedelta(days=1)

    return slots

async def get_available_slots(
    app_id: str,
    user_id: str,
    slug: str,
    attendee_tz: str = None,
) -> dict:
    try:
        event_type = db.get_event_type(user_id, slug)
        if not event_type or not event_type["active"]:
            return {"success": False, "error": f"Event type '{slug}' not found"}

        working_hours = db.get_working_hours(user_id)
        if not working_hours:
            return {"success": False, "error": "No working hours configured"}

        user = db.get_user(user_id)
        user_tz = user["timezone"] if user else "America/New_York"
        attendee_tz = attendee_tz or user_tz

        try:
            pytz.timezone(attendee_tz)
        except pytz.exceptions.UnknownTimeZoneError:
            return {"success": False, "error": f"Unknown timezone: {attendee_tz}"}

        now = datetime.now(pytz.utc)
        end = now + timedelta(days=event_type["booking_window_days"])

        busy_result = await get_busy_blocks(
            app_id=app_id,
            user_id=user_id,
            start=now.isoformat(),
            end=end.isoformat(),
        )
        if not busy_result["success"]:
            return {"success": False, "error": "Failed to fetch busy blocks"}

        busy_blocks = [
            (
                datetime.fromisoformat(s).astimezone(pytz.utc),
                datetime.fromisoformat(e).astimezone(pytz.utc),
            )
            for s, e in busy_result["busy_blocks"]
        ]

        slots = generate_available_slots(
            working_hours=working_hours,
            busy_blocks=busy_blocks,
            event_type=event_type,
            user_tz=user_tz,
            attendee_tz=attendee_tz,
            start_date=now,
            end_date=end,
        )

        return {
            "success": True,
            "event_type": event_type["name"],
            "slots": slots,
            "count": len(slots),
        }

    except Exception as e:
        logger.error(f"calendar.get_available_slots error: {e}")
        return {"success": False, "error": str(e)}

# -----------------------------------------------------------------------------
