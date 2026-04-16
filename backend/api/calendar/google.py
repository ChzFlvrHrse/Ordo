import os, pytz, logging, google.oauth2.credentials, google.auth.transport.requests
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from functools import wraps
from quart import Blueprint, request, jsonify, redirect
from classes import OrdoDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = OrdoDB()

google_calendar_bp = Blueprint('google_calendar', __name__, url_prefix='/google_calendar')

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

def _flow(redirect_uri: str) -> Flow:
    return Flow.from_client_config(
        {
            "web": {
                "client_id": os.environ["GOOGLE_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )

def _credentials(integration: dict) -> google.oauth2.credentials.Credentials:
    return google.oauth2.credentials.Credentials(
        token=integration.get("access_token"),
        refresh_token=integration.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        scopes=integration.get("scopes"),
    )

async def get_refreshed_credentials(app_id: str, user_id: str, provider: str = "google"):
    integration = db.get_integration(app_id, user_id, provider)
    if not integration:
        raise ValueError(f"No {provider} calendar integration found for user {user_id}")

    credentials = _credentials(integration)

    if credentials.expired or not credentials.token:
        credentials.refresh(google.auth.transport.requests.Request())
        db.upsert_integration(
            app_id=app_id,
            user_id=user_id,
            provider=provider,
            access_token=credentials.token,
            token_expiry=credentials.expiry.isoformat() if credentials.expiry else None,
        )
        logger.info(f"=== ORDO: Refreshed token for app={app_id} user={user_id} provider={provider} ===")

    return credentials, integration

def require_api_key(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({"error": "Missing API key"}), 403
        app = db.get_app_by_key(api_key)
        if not app:
            return jsonify({"error": "Invalid API key"}), 403
        request.ordo_app = app
        return await f(*args, **kwargs)
    return decorated


@google_calendar_bp.route('/connect', methods=['POST'])
@require_api_key
async def google_calendar_connect():
    try:
        data = await request.get_json()
        user_id = data.get("user_id")

        ordo_redirect_uri = f"{os.environ.get('ORDO_BASE_URL')}/google_calendar/exchange"
        post_exchange_uri = request.ordo_app.get("redirect_uri")

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        if not post_exchange_uri:
            return jsonify({"error": "redirect_uri is required"}), 400

        auth_url, state = _flow(ordo_redirect_uri).authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=f"{request.ordo_app['id']}:{user_id}:{post_exchange_uri}",
        )
        return jsonify({"auth_url": auth_url, "state": state, "success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@google_calendar_bp.route('/exchange', methods=['GET'])
async def google_calendar_exchange():
    try:
        code = request.args.get("code")
        state = request.args.get("state")

        if not code or not state:
            return jsonify({"error": "Missing code or state"}), 400

        parts = state.split(":", 2)
        if len(parts) != 3:
            return jsonify({"error": "Invalid state"}), 400

        app_id, user_id, post_exchange_uri = parts

        app = db.get_app_by_id(app_id)
        if not app:
            return jsonify({"error": "Unknown app"}), 403

        ordo_redirect_uri = f"{os.environ.get('ORDO_BASE_URL')}/google_calendar/exchange"
        flow = _flow(ordo_redirect_uri)
        flow.fetch_token(code=code)
        creds = flow.credentials

        user_info = build("oauth2", "v2", credentials=creds).userinfo().get().execute()
        email = user_info.get("email")

        calendar_id = (
            build("calendar", "v3", credentials=creds)
            .calendars().get(calendarId="primary").execute()
            .get("id")
        )

        db.upsert_integration(
            app_id=app_id,
            user_id=user_id,
            provider="google",
            email=email,
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            token_expiry=creds.expiry.isoformat(),
            scopes=list(creds.scopes),
            calendar_id=calendar_id,
            redirect_uri=post_exchange_uri,
        )

        return redirect(post_exchange_uri)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@google_calendar_bp.route('/status', methods=['GET'])
@require_api_key
async def google_calendar_status():
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        integration = db.get_integration(request.ordo_app["id"], user_id, "google")
        if integration:
            integration = {k: integration[k] for k in (
                "id", "email", "created_at", "provider",
                "lookahead_weeks", "timezone", "available_days",
                "available_start", "available_end"
            ) if k in integration}

        return jsonify({
            "integration": integration,
            "success": True,
            "is_connected": integration is not None
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@google_calendar_bp.route('/disconnect', methods=['POST'])
@require_api_key
async def google_calendar_disconnect():
    try:
        data = await request.get_json()
        user_id = data.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        db.delete_integration(request.ordo_app["id"], user_id, "google")
        return jsonify({"message": "Google Calendar disconnected", "success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@google_calendar_bp.route('/config', methods=['PUT'])
@require_api_key
async def google_calendar_config():
    try:
        data = await request.get_json()
        user_id = data.get("user_id")
        lookahead_weeks = data.get("lookahead_weeks")
        timezone = data.get("timezone")

        if not user_id or not lookahead_weeks or not timezone:
            return jsonify({"error": "user_id, lookahead_weeks, and timezone are required"}), 400

        integration = db.update_integration_config(
            app_id=request.ordo_app["id"],
            user_id=user_id,
            provider="google",
            lookahead_weeks=lookahead_weeks,
            timezone=timezone,
            available_days=data.get("available_days"),
            available_start=data.get("available_start"),
            available_end=data.get("available_end"),
        )
        return jsonify({"integration": integration, "success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@google_calendar_bp.route('/events', methods=['GET'])
@require_api_key
async def google_calendar_events():
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        logger.info(f"=== GOOGLE CALENDAR EVENTS: app={request.ordo_app['name']} user_id={user_id} ===")

        credentials, integration = await get_refreshed_credentials(request.ordo_app["id"], user_id)

        calendar_id = integration.get("calendar_id")
        if not calendar_id:
            return jsonify({"error": "calendar_id missing from integration"}), 400

        tz_name = integration.get("timezone") or "America/New_York"
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        end = now + timedelta(weeks=integration.get("lookahead_weeks") or 2)

        service = build("calendar", "v3", credentials=credentials)
        items = service.events().list(
            calendarId=calendar_id,
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute().get("items", [])

        available_days = integration.get("available_days")
        available_start = integration.get("available_start")
        available_end = integration.get("available_end")

        if available_days or available_start:
            from datetime import time as time_type
            filtered = []
            for event in items:
                dt_str = (event.get("start") or {}).get("dateTime") or (event.get("start") or {}).get("date")
                if not dt_str:
                    continue
                dt = datetime.fromisoformat(dt_str).astimezone(tz)
                if available_days and dt.isoweekday() not in available_days:
                    continue
                if available_start and available_end:
                    t = dt.time().replace(tzinfo=None)
                    if not (time_type.fromisoformat(available_start) <= t <= time_type.fromisoformat(available_end)):
                        continue
                filtered.append(event)
            items = filtered

        return jsonify({"events": items, "success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@google_calendar_bp.route('/book', methods=['POST'])
@require_api_key
async def google_calendar_book():
    try:
        data = await request.get_json()
        args = data.get("args") or data

        user_id = args.get("user_id")
        title = args.get("title")
        start_time = args.get("start_time")
        end_time = args.get("end_time")
        attendee_emails = args.get("attendee_emails")
        description = args.get("description")
        add_meet = args.get("add_meet", False)

        logger.info(f"=== GOOGLE CALENDAR BOOK: app={request.ordo_app['name']} user_id={user_id} title={title} ===")

        missing = [k for k, v in {"user_id": user_id, "title": title, "start_time": start_time, "end_time": end_time, "attendee_emails": attendee_emails}.items() if not v]
        if missing:
            return jsonify({"error": f"Missing required fields: {', '.join(missing)}", "success": False}), 400

        credentials, integration = await get_refreshed_credentials(request.ordo_app["id"], user_id)

        tz_name = integration.get("timezone") or "America/New_York"
        event_body = {
            "summary": title,
            "description": description or "",
            "start": {"dateTime": start_time, "timeZone": tz_name},
            "end": {"dateTime": end_time, "timeZone": tz_name},
            "attendees": [{"email": e} for e in attendee_emails],
        }

        if add_meet:
            event_body["conferenceData"] = {
                "createRequest": {
                    "requestId": f"{user_id}-{start_time}-{end_time}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }

        service = build("calendar", "v3", credentials=credentials)
        insert_kwargs = {
            "calendarId": integration.get("calendar_id"),
            "body": event_body,
            "sendUpdates": "all",
        }
        if add_meet:
            insert_kwargs["conferenceDataVersion"] = 1

        event = service.events().insert(**insert_kwargs).execute()
        return jsonify({"event": event, "success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@google_calendar_bp.route('/cancel', methods=['POST'])
@require_api_key
async def google_calendar_cancel():
    try:
        data = await request.get_json()
        args = data.get("args") or data
        user_id = args.get("user_id")
        event_id = args.get("event_id")

        if not user_id or not event_id:
            return jsonify({"error": "user_id and event_id are required"}), 400

        credentials, integration = await get_refreshed_credentials(request.ordo_app["id"], user_id)

        service = build("calendar", "v3", credentials=credentials)
        service.events().delete(
            calendarId=integration.get("calendar_id"),
            eventId=event_id,
            sendUpdates="all",
        ).execute()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@google_calendar_bp.route('/reschedule', methods=['POST'])
@require_api_key
async def google_calendar_reschedule():
    try:
        data = await request.get_json()
        args = data.get("args") or data
        user_id = args.get("user_id")
        event_id = args.get("event_id")
        start_time = args.get("start_time")
        end_time = args.get("end_time")

        if not all([user_id, event_id, start_time, end_time]):
            return jsonify({"error": "user_id, event_id, start_time, end_time are required"}), 400

        credentials, integration = await get_refreshed_credentials(request.ordo_app["id"], user_id)

        tz_name = integration.get("timezone") or "America/New_York"
        service = build("calendar", "v3", credentials=credentials)

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

        return jsonify({"event": event, "success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
