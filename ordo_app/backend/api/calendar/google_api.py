import os
import pytz
import uuid
import logging
from classes import OrdoDB
from functools import wraps
import google.oauth2.credentials
import google.auth.transport.requests
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from quart import Blueprint, request, jsonify, redirect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = OrdoDB()

google_calendar_bp = Blueprint(
    'google_calendar', __name__, url_prefix='/google_calendar')

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


def _parse_expiry(value) -> datetime | None:
    """google-auth stores Credentials.expiry as a naive UTC datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(pytz.UTC).replace(tzinfo=None)
    return dt


def _credentials(integration: dict) -> google.oauth2.credentials.Credentials:
    return google.oauth2.credentials.Credentials(
        token=integration.get("access_token"),
        refresh_token=integration.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        scopes=integration.get("scopes"),
        expiry=_parse_expiry(integration.get("token_expiry")),
    )


async def get_refreshed_credentials_google(app_id: str, user_id: str,
                                    provider: str = "google", email: str = None):
    integration = db.get_integration(app_id, user_id, provider, email=email)
    if not integration:
        raise ValueError(
            f"No {provider} calendar integration found for user {user_id}")

    credentials = _credentials(integration)

    skew = timedelta(minutes=5)
    expiry = credentials.expiry  # naive UTC
    needs_refresh = (
        not credentials.token
        or expiry is None
        or datetime.utcnow() + skew >= expiry
    )

    if needs_refresh:
        credentials.refresh(google.auth.transport.requests.Request())
        db.upsert_integration(
            app_id=app_id,
            user_id=user_id,
            provider=provider,
            email=integration["email"],
            access_token=credentials.token,
            token_expiry=credentials.expiry.isoformat() if credentials.expiry else None,
        )
        logger.info(
            f"=== ORDO: Refreshed token app={app_id} user={user_id} email={integration['email']} ===")

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


# -------------------------
# OAuth
# -------------------------

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
            state=f"{request.ordo_app['id']}:{user_id}:{post_exchange_uri}"
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

        user_info = build(
            "oauth2", "v2", credentials=creds).userinfo().get().execute()
        email = user_info.get("email")

        calendar_id = (
            build("calendar", "v3", credentials=creds, cache_discovery=False)
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

        # Register webhook watch
        try:
            register_google_watch(app_id, user_id, email=email)
            logger.info(
                f"=== ORDO: Registered Google watch app={app_id} user={user_id} ===")
        except Exception as e:
            logger.warning(
                f"=== ORDO: Failed to register Google watch: {e} ===")
            # Non-fatal — don't block the OAuth flow

        logger.info(
            f"=== ORDO: Connected google calendar app={app_id} user={user_id} email={email} ===")
        return redirect(post_exchange_uri)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------
# Status / Disconnect
# -------------------------

@google_calendar_bp.route('/status', methods=['GET'])
@require_api_key
async def google_calendar_status():
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        integrations = db.get_integrations_by_provider(
            request.ordo_app["id"], user_id, "google")
        sanitized = [
            {k: i[k] for k in ("id", "email", "created_at", "provider",
                               "lookahead_weeks", "timezone", "available_days",
                               "available_start", "available_end", "label", "color") if k in i}
            for i in integrations
        ]

        return jsonify({
            "integrations": sanitized,
            "success": True,
            "is_connected": len(sanitized) > 0,
            "count": len(sanitized),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@google_calendar_bp.route('/disconnect', methods=['POST'])
@require_api_key
async def google_calendar_disconnect():
    try:
        data = await request.get_json()
        user_id = data.get("user_id")
        email = data.get("email")

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        if not email:
            return jsonify({"error": "email is required"}), 400

        deleted = db.delete_integration(
            request.ordo_app["id"], user_id, "google", email)
        if not deleted:
            return jsonify({"error": "Integration not found"}), 404

        return jsonify({"message": f"Google Calendar {email} disconnected", "success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------
# Webhook
# -------------------------

@google_calendar_bp.route('/webhook', methods=['POST'])
async def google_calendar_webhook():
    channel_id = request.headers.get("X-Goog-Channel-ID")
    resource_state = request.headers.get("X-Goog-Resource-State")

    # add this
    logger.info(
        f"=== ORDO WEBHOOK: channel_id={channel_id} state={resource_state} ===")

    if resource_state == "sync":
        return "", 200

    if not channel_id:
        return "", 400

    row = db.get_watch_channel_by_channel_id(channel_id)
    if not row:
        return "", 404

    await process_calendar_changes(row["app_id"], row["user_id"], email=row["email"])
    return "", 200


async def process_calendar_changes(app_id: str, user_id: str, email: str):
    try:
        credentials, integration = await get_refreshed_credentials_google(app_id, user_id, "google", email=email)
    except ValueError:
        logger.warning(
            f"=== ORDO: No integration found for app={app_id} user={user_id} email={email} ===")
        return

    service = build("calendar", "v3", credentials=credentials,
                    cache_discovery=False)
    channel_row = db.get_watch_channel(app_id, user_id, "google", email=email)
    sync_token = channel_row.get("sync_token") if channel_row else None

    try:
        if sync_token:
            events_result = service.events().list(
                calendarId="primary",
                syncToken=sync_token,
            ).execute()
        else:
            events_result = service.events().list(
                calendarId="primary",
                timeMin=datetime.utcnow().isoformat() + "Z",
                maxResults=250,
                singleEvents=True,
            ).execute()

        new_sync_token = events_result.get("nextSyncToken")
        if new_sync_token:
            db.update_watch_channel_sync_token(
                app_id, user_id, "google", email, new_sync_token)

        from agent.tools.calendar_tools import check_collision
        for event in events_result.get("items", []):
            if event.get("status") == "cancelled":
                continue
            await check_collision(app_id, user_id, email, event, service)

    except Exception as e:
        if "410" in str(e):
            logger.warning(
                f"=== ORDO: Sync token expired for app={app_id} user={user_id} email={email}, resetting ===")
            db.update_watch_channel_sync_token(
                app_id, user_id, "google", email, None)
        else:
            logger.error(f"=== ORDO: process_calendar_changes error: {e} ===")


# -------------------------
# Watch registration helpers
# -------------------------


def get_google_credentials(app_id: str, user_id: str, email: str = None) -> google.oauth2.credentials.Credentials:
    row = db.get_integration(app_id, user_id, provider="google", email=email)
    if not row:
        raise Exception(
            f"No Google integration for user {user_id} email={email}")

    creds = google.oauth2.credentials.Credentials(
        token=row["access_token"],
        refresh_token=row["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
    )

    if creds.expired:
        creds.refresh(google.auth.transport.requests.Request())
        db.upsert_integration(
            app_id, user_id, "google", row["email"],
            access_token=creds.token,
            token_expiry=creds.expiry.isoformat(),
        )

    return creds


def register_google_watch(app_id: str, user_id: str, email: str = None):
    integration = db.get_integration(app_id, user_id, "google", email=email)
    if not integration:
        raise Exception(
            f"No Google integration for user {user_id} email={email}")

    actual_email = integration["email"]  # use this everywhere below
    creds = get_google_credentials(app_id, user_id, email=actual_email)
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    channel_id = str(uuid.uuid4())
    expiration = datetime.utcnow() + timedelta(days=6)
    expiration_ms = int(expiration.timestamp() * 1000)

    result = service.events().watch(
        calendarId="primary",
        body={
            "id": channel_id,
            "type": "web_hook",
            "address": f"{os.environ['ORDO_BASE_URL']}/google_calendar/webhook",
            "expiration": expiration_ms,
        }
    ).execute()

    db.upsert_watch_channel(
        app_id=app_id,
        user_id=user_id,
        provider="google",
        email=actual_email,
        channel_id=channel_id,
        resource_id=result["resourceId"],
        expiration=expiration.isoformat(),
        sync_token=None,
    )
