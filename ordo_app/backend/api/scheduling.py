import logging
import pytz
from quart import Blueprint, request, jsonify
from functools import wraps
from classes import OrdoDB
from agent.tools.calendar_tools import get_busy_blocks, generate_available_slots
from agent.tools import get_provider
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = OrdoDB()
scheduling_bp = Blueprint('scheduling', __name__, url_prefix='/scheduling')


def render_message(
    message_type: str,
    recipient: str,
    display_start: str,
    booking: dict,
    user: dict,
    event_type: dict,
) -> str:
    name = user.get("name", "your host")
    attendee_name = booking["attendee_name"]
    event_name = event_type["name"]

    templates = {
        ("confirmation", "user"): f"New booking: {attendee_name} has booked {event_name} on {display_start}.",
        ("confirmation", "attendee"): f"You're confirmed for {event_name} with {name} on {display_start}. Reply anytime to cancel or reschedule.",
        ("reminder_24h", "user"): f"Reminder: {attendee_name} has {event_name} with you tomorrow at {display_start}.",
        ("reminder_24h", "attendee"): f"Just a reminder — you have {event_name} with {name} tomorrow at {display_start}. Reply to cancel or reschedule.",
        ("reminder_1h", "user"): f"Heads up: {attendee_name} has {event_name} with you in 1 hour.",
        ("reminder_1h", "attendee"): f"Your {event_name} with {name} is in 1 hour. Reply if you need to make any changes.",
        ("no_show", "user"): f"Looks like {attendee_name} may have missed your {event_name}. Want to follow up?",
        ("no_show", "attendee"): f"We missed you at your {event_name} with {name}. Want to reschedule?",
    }

    return templates.get((message_type, recipient), "")


async def schedule_sms_jobs(booking: dict, user: dict, event_type: dict):
    start_dt = datetime.fromisoformat(
        booking["start_time"]).astimezone(pytz.utc)
    end_dt = datetime.fromisoformat(booking["end_time"]).astimezone(pytz.utc)
    now = datetime.now(pytz.utc)

    jobs = []

    jobs.append(("confirmation", now))

    reminder_24h = start_dt - timedelta(hours=24)
    if reminder_24h > now:
        jobs.append(("reminder_24h", reminder_24h))

    reminder_1h = start_dt - timedelta(hours=1)
    if reminder_1h > now:
        jobs.append(("reminder_1h", reminder_1h))

    jobs.append(("no_show", end_dt + timedelta(minutes=10)))

    attendee_tz = pytz.timezone(booking["timezone"])
    display_start = start_dt.astimezone(
        attendee_tz).strftime("%A, %B %-d at %-I:%M %p")

    for message_type, send_at in jobs:
        if user.get("sms_phone"):
            db.create_scheduled_message(
                booking_id=booking["id"],
                user_id=user["id"],
                recipient="user",
                phone=user["sms_phone"],
                email=user["email"],
                message_type=message_type,
                body=render_message(message_type, "user",
                                    display_start, booking, user, event_type),
                send_at=send_at.isoformat(),
            )

        if booking.get("attendee_phone") and booking.get("sms_consent"):
            db.create_scheduled_message(
                booking_id=booking["id"],
                user_id=user["id"],
                recipient="attendee",
                phone=booking["attendee_phone"],
                email=booking["attendee_email"],
                message_type=message_type,
                body=render_message(message_type, "attendee",
                                    display_start, booking, user, event_type),
                send_at=send_at.isoformat(),
            )


@scheduling_bp.route("/availability/<username>/<slug>", methods=["GET"])
async def get_availability(username: str, slug: str):
    try:
        user = db.get_user_by_username(username)
        if not user:
            return jsonify({"error": "User not found"}), 404

        event_type = db.get_event_type(user["id"], slug)
        if not event_type or not event_type["active"]:
            return jsonify({"error": "Event type not found"}), 404

        attendee_tz = request.args.get("timezone", "America/New_York")
        try:
            pytz.timezone(attendee_tz)
        except pytz.exceptions.UnknownTimeZoneError:
            return jsonify({"error": f"Unknown timezone: {attendee_tz}"}), 400

        user_tz = user["timezone"]
        now = datetime.now(pytz.timezone(user_tz))
        start_date = now
        end_date = now + timedelta(days=event_type["booking_window_days"])

        busy_result = await get_busy_blocks(
            app_id=user["app_id"],
            user_id=user["id"],
            start=start_date.astimezone(pytz.utc).isoformat(),
            end=end_date.astimezone(pytz.utc).isoformat(),
        )
        if not busy_result["success"]:
            return jsonify({"error": "Failed to fetch calendar data"}), 500

        busy_blocks = [
            (
                datetime.fromisoformat(s).astimezone(pytz.utc),
                datetime.fromisoformat(e).astimezone(pytz.utc),
            )
            for s, e in busy_result["busy_blocks"]
        ]

        working_hours = db.get_working_hours(user["id"])
        if not working_hours:
            return jsonify({"error": "User has not configured working hours"}), 400

        slots = generate_available_slots(
            working_hours=working_hours,
            busy_blocks=busy_blocks,
            event_type=event_type,
            user_tz=user_tz,
            attendee_tz=attendee_tz,
            start_date=start_date,
            end_date=end_date,
        )

        return jsonify({
            "success": True,
            "event_type": {
                "name": event_type["name"],
                "duration_minutes": event_type["duration_minutes"],
                "description": event_type["description"],
                "location": event_type["location"],
            },
            "timezone": attendee_tz,
            "slots": slots,
            "count": len(slots),
        })

    except Exception as e:
        logger.error(f"get_availability error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@scheduling_bp.route("/book/<username>/<slug>", methods=["POST"])
async def create_booking(username: str, slug: str):
    try:
        user = db.get_user_by_username(username)
        if not user:
            return jsonify({"error": "User not found"}), 404

        event_type = db.get_event_type(user["id"], slug)
        if not event_type or not event_type["active"]:
            return jsonify({"error": "Event type not found"}), 404

        body = await request.get_json()
        attendee_name = body.get("attendee_name", "").strip()
        attendee_email = body.get("attendee_email", "").strip()
        attendee_phone = body.get("attendee_phone", "").strip() or None
        sms_consent = body.get("sms_consent", False)
        notes = body.get("notes", "").strip() or None
        slot_start = body.get("start")
        attendee_tz = body.get("timezone", "America/New_York")

        if not all([attendee_name, attendee_email, slot_start]):
            return jsonify({"error": "attendee_name, attendee_email, and start are required"}), 400

        try:
            start_dt = datetime.fromisoformat(slot_start).astimezone(pytz.utc)
        except ValueError:
            return jsonify({"error": "Invalid start time format"}), 400

        end_dt = start_dt + timedelta(minutes=event_type["duration_minutes"])

        # re-validate slot is still available
        busy_result = await get_busy_blocks(
            app_id=user["app_id"],
            user_id=user["id"],
            start=start_dt.isoformat(),
            end=end_dt.isoformat(),
        )
        if not busy_result["success"]:
            return jsonify({"error": "Failed to validate slot availability"}), 500

        buffer_before = timedelta(minutes=event_type["buffer_before"])
        buffer_after = timedelta(minutes=event_type["buffer_after"])
        padded_start = start_dt - buffer_before
        padded_end = end_dt + buffer_after

        conflict = any(
            padded_start < datetime.fromisoformat(be).astimezone(pytz.utc)
            and padded_end > datetime.fromisoformat(bs).astimezone(pytz.utc)
            for bs, be in busy_result["busy_blocks"]
        )
        if conflict:
            return jsonify({"error": "This slot is no longer available"}), 409

        # resolve which provider + account to book on
        integrations = db.get_integrations(user["app_id"], user["id"])
        if not integrations:
            return jsonify({"error": "User has no connected calendars"}), 400

        # prefer google, fall back to microsoft
        integration = next(
            (i for i in integrations if i["provider"] == "google"), None
        ) or integrations[0]
        provider = integration["provider"]
        calendar_email = integration["email"]

        try:
            result = await get_provider(provider).book_event(
                app_id=user["app_id"],
                user_id=user["id"],
                title=f"{event_type['name']} with {attendee_name}",
                start_time=start_dt.isoformat(),
                end_time=end_dt.isoformat(),
                attendee_emails=[attendee_email],
                email=calendar_email,
                description=notes or "",
            )
        except ValueError:
            return jsonify({"error": f"Unsupported provider: {provider}"}), 400

        if not result.get("success"):
            return jsonify({"error": "Failed to create calendar event"}), 500

        calendar_event_id = result["event"]["id"]

        # create booking record
        booking = db.create_booking(
            event_type_id=event_type["id"],
            user_id=user["id"],
            calendar_event_id=calendar_event_id,
            attendee_name=attendee_name,
            attendee_email=attendee_email,
            attendee_phone=attendee_phone,
            sms_consent=sms_consent,
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            timezone=attendee_tz,
            notes=notes,
        )

        # schedule SMS jobs
        await schedule_sms_jobs(booking, user, event_type)

        return jsonify({
            "success": True,
            "booking_id": booking["id"],
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "timezone": attendee_tz,
        }), 201

    except Exception as e:
        logger.error(f"create_booking error: {e}")
        return jsonify({"error": "Internal server error"}), 500
