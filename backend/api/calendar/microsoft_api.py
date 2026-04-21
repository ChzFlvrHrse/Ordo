import os
import pytz
import uuid
import logging
from classes import OrdoDB
from functools import wraps
from httpx import AsyncClient
from datetime import datetime, timedelta
from msal import ConfidentialClientApplication
from quart import Blueprint, request, jsonify, redirect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = OrdoDB()

microsoft_calendar_bp = Blueprint(
    'microsoft_calendar', __name__, url_prefix='/microsoft_calendar')

SCOPES = [
    "Calendars.ReadWrite",
    "Calendars.ReadWrite.Shared",
    "User.Read",
    "email",
]


def _build_msal_app():
    return ConfidentialClientApplication(
        os.environ["MICROSOFT_CLIENT_ID"],
        authority=f"https://login.microsoftonline.com/{os.environ.get('MICROSOFT_TENANT_ID', 'common')}",
        client_credential=os.environ["MICROSOFT_CLIENT_SECRET"],
    )


async def get_refreshed_token_microsoft(app_id: str, user_id: str, email: str = None) -> tuple[str, dict]:
    integration = db.get_integration(app_id, user_id, "microsoft", email=email)
    if not integration:
        raise ValueError(
            f"No Microsoft Calendar integration found for user {user_id}")

    expiry = datetime.fromisoformat(
        integration["token_expiry"]) if integration.get("token_expiry") else None
    skew = timedelta(minutes=5)
    needs_refresh = (
        not integration.get("access_token")
        or expiry is None
        or datetime.utcnow() + skew >= expiry
    )

    if needs_refresh:
        msal_app = _build_msal_app()
        result = msal_app.acquire_token_by_refresh_token(
            integration["refresh_token"],
            scopes=SCOPES,
        )
        if "error" in result:
            raise Exception(
                f"Token refresh failed: {result['error']} - {result.get('error_description')}")

        new_expiry = (datetime.utcnow() +
                      timedelta(seconds=result["expires_in"])).isoformat()
        db.upsert_integration(
            app_id=app_id,
            user_id=user_id,
            provider="microsoft",
            email=integration["email"],
            access_token=result["access_token"],
            refresh_token=result.get(
                "refresh_token", integration["refresh_token"]),
            token_expiry=new_expiry,
        )
        integration["access_token"] = result["access_token"]
        logger.info(
            f"=== ORDO: Refreshed Microsoft token app={app_id} user={user_id} email={integration['email']} ===")

    return integration["access_token"], integration


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

@microsoft_calendar_bp.route('/connect', methods=['POST'])
@require_api_key
async def microsoft_calendar_connect():
    try:
        data = await request.get_json()
        user_id = data.get("user_id")

        ordo_redirect_uri = f"{os.environ.get('ORDO_BASE_URL')}/microsoft_calendar/exchange"
        post_exchange_uri = request.ordo_app.get("redirect_uri")

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        if not post_exchange_uri:
            return jsonify({"error": "redirect_uri is required"}), 400

        msal_app = _build_msal_app()
        auth_url = msal_app.get_authorization_request_url(
            scopes=SCOPES,
            redirect_uri=ordo_redirect_uri,
            state=f"{request.ordo_app['id']}:{user_id}:{post_exchange_uri}",
        )
        return jsonify({"auth_url": auth_url, "state": None, "success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@microsoft_calendar_bp.route('/exchange', methods=['GET'])
async def microsoft_calendar_exchange():
    try:
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")

        if error:
            return jsonify({"error": error, "description": request.args.get("error_description")}), 400

        if not code or not state:
            return jsonify({"error": "Missing code or state"}), 400

        parts = state.split(":", 2)
        if len(parts) != 3:
            return jsonify({"error": "Invalid state"}), 400

        app_id, user_id, post_exchange_uri = parts

        app = db.get_app_by_id(app_id)
        if not app:
            return jsonify({"error": "Unknown app"}), 403

        ordo_redirect_uri = f"{os.environ.get('ORDO_BASE_URL')}/microsoft_calendar/exchange"
        msal_app = _build_msal_app()
        result = msal_app.acquire_token_by_authorization_code(
            code,
            scopes=SCOPES,
            redirect_uri=ordo_redirect_uri,
        )

        if "error" in result:
            return jsonify({"error": result["error"], "description": result.get("error_description")}), 400

        claims = result.get("id_token_claims", {})
        email = claims.get("preferred_username") or claims.get("email")
        token_expiry = (datetime.utcnow(
        ) + timedelta(seconds=result.get("expires_in", 3600))).isoformat()

        # Fetch primary calendar ID from Graph
        async with AsyncClient() as client:
            cal_resp = await client.get(
                "https://graph.microsoft.com/v1.0/me/calendar",
                headers={"Authorization": f"Bearer {result['access_token']}"},
            )
            calendar_id = cal_resp.json().get("id")

        db.upsert_integration(
            app_id=app_id,
            user_id=user_id,
            provider="microsoft",
            email=email,
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token"),
            token_expiry=token_expiry,
            scopes=SCOPES,
            calendar_id=calendar_id,
            redirect_uri=post_exchange_uri,
        )

        try:
            await register_microsoft_watch(app_id, user_id, email=email)
            logger.info(
                f"=== ORDO: Registered Microsoft watch app={app_id} user={user_id} ===")
        except Exception as e:
            logger.warning(f"=== ORDO: Failed to register Microsoft watch: {e} ===")

        logger.info(
            f"=== ORDO: Connected Microsoft Calendar app={app_id} user={user_id} email={email} ===")
        return redirect(post_exchange_uri)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------
# Status / Disconnect
# -------------------------

@microsoft_calendar_bp.route('/status', methods=['GET'])
@require_api_key
async def microsoft_calendar_status():
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        integrations = db.get_integrations_by_provider(
            request.ordo_app["id"], user_id, "microsoft")
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


@microsoft_calendar_bp.route('/disconnect', methods=['POST'])
@require_api_key
async def microsoft_calendar_disconnect():
    try:
        data = await request.get_json()
        user_id = data.get("user_id")
        email = data.get("email")

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        if not email:
            return jsonify({"error": "email is required"}), 400

        deleted = db.delete_integration(
            request.ordo_app["id"], user_id, "microsoft", email)
        if not deleted:
            return jsonify({"error": "Integration not found"}), 404

        return jsonify({"message": f"Microsoft Calendar {email} disconnected", "success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------
# Events
# -------------------------

@microsoft_calendar_bp.route('/events', methods=['GET'])
@require_api_key
async def microsoft_calendar_events():
    try:
        user_id = request.args.get("user_id")
        email = request.args.get("email")
        start_param = request.args.get("start")
        end_param = request.args.get("end")

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        logger.info(
            f"=== MICROSOFT CALENDAR EVENTS: app={request.ordo_app['name']} "
            f"user_id={user_id} email={email} start={start_param} end={end_param} ==="
        )

        if email:
            integrations = [db.get_integration(
                request.ordo_app["id"], user_id, "microsoft", email=email)]
            integrations = [i for i in integrations if i]
        else:
            integrations = db.get_integrations_by_provider(
                request.ordo_app["id"], user_id, "microsoft")

        if not integrations:
            return jsonify({"error": "No Microsoft Calendar integration found"}), 404

        all_events = []

        for integration in integrations:
            try:
                token, integration = await get_refreshed_token_microsoft(
                    request.ordo_app["id"], user_id, email=integration["email"]
                )

                tz_name = integration.get("timezone") or "America/New_York"
                tz = pytz.timezone(tz_name)

                if start_param and end_param:
                    try:
                        parsed_start = datetime.fromisoformat(
                            start_param.replace("Z", "+00:00"))
                        parsed_end = datetime.fromisoformat(
                            end_param.replace("Z", "+00:00"))
                    except ValueError:
                        try:
                            parsed_start = datetime.strptime(
                                start_param, "%Y-%m-%d")
                            parsed_end = datetime.strptime(
                                end_param, "%Y-%m-%d")
                        except ValueError:
                            return jsonify({"error": "start and end must be valid ISO datetimes or YYYY-MM-DD"}), 400

                    start = tz.localize(
                        parsed_start) if parsed_start.tzinfo is None else parsed_start.astimezone(tz)
                    end = tz.localize(
                        parsed_end) if parsed_end.tzinfo is None else parsed_end.astimezone(tz)

                    if end <= start:
                        return jsonify({"error": "end must be after start"}), 400

                elif start_param or end_param:
                    return jsonify({"error": "Pass both start and end together"}), 400

                else:
                    start = datetime.now(tz)
                    end = start + \
                        timedelta(weeks=integration.get(
                            "lookahead_weeks") or 4)

                params = {
                    "startDateTime": start.isoformat(),
                    "endDateTime": end.isoformat(),
                    "$orderby": "start/dateTime",
                    "$top": 100,
                }

                items = []
                url = "https://graph.microsoft.com/v1.0/me/calendarView"
                headers = {"Authorization": f"Bearer {token}"}

                async with AsyncClient() as client:
                    while url:
                        resp = await client.get(url, headers=headers, params=params if "calendarView" in url else None)
                        data = resp.json()
                        batch = data.get("value", [])
                        for item in batch:
                            item["_ordo_account"] = integration["email"]
                        items.extend(batch)
                        url = data.get("@odata.nextLink")

                available_days = integration.get("available_days")
                available_start = integration.get("available_start")
                available_end = integration.get("available_end")

                if available_days or available_start:
                    from datetime import time as time_type
                    filtered = []
                    for event in items:
                        dt_str = (event.get("start") or {}).get("dateTime")
                        if not dt_str:
                            continue
                        dt = datetime.fromisoformat(
                            dt_str.replace("Z", "+00:00")).astimezone(tz)

                        if available_days and dt.isoweekday() not in available_days:
                            continue
                        if available_start and available_end:
                            t = dt.time().replace(tzinfo=None)
                            if not (time_type.fromisoformat(available_start) <= t <= time_type.fromisoformat(available_end)):
                                continue
                        filtered.append(event)
                    items = filtered

                all_events.extend(items)

            except Exception as e:
                logger.error(
                    f"=== ORDO: Error fetching Microsoft events for {integration.get('email')}: {e} ===")
                continue

        all_events.sort(key=lambda e: (
            e.get("start") or {}).get("dateTime") or "")

        return jsonify({
            "events": all_events,
            "success": True,
            "count": len(all_events),
            "range": {"start": start_param, "end": end_param},
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------
# Book / Cancel / Reschedule
# -------------------------

@microsoft_calendar_bp.route('/book', methods=['POST'])
@require_api_key
async def microsoft_calendar_book():
    try:
        data = await request.get_json()
        args = data.get("args") or data

        user_id = args.get("user_id")
        email = args.get("email")
        title = args.get("title")
        start_time = args.get("start_time")
        end_time = args.get("end_time")
        attendee_emails = args.get("attendee_emails")
        description = args.get("description")
        add_teams = args.get("add_teams", False)

        logger.info(
            f"=== MICROSOFT CALENDAR BOOK: app={request.ordo_app['name']} user_id={user_id} email={email} title={title} ===")

        missing = [k for k, v in {"user_id": user_id, "title": title, "start_time": start_time,
                                  "end_time": end_time, "attendee_emails": attendee_emails}.items() if not v]
        if missing:
            return jsonify({"error": f"Missing required fields: {', '.join(missing)}", "success": False}), 400

        token, integration = await get_refreshed_token_microsoft(request.ordo_app["id"], user_id, email=email)
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
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json"},
                json=event_body,
            )
            event = resp.json()

        return jsonify({"event": event, "success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@microsoft_calendar_bp.route('/cancel', methods=['POST'])
@require_api_key
async def microsoft_calendar_cancel():
    try:
        data = await request.get_json()
        args = data.get("args") or data
        user_id = args.get("user_id")
        email = args.get("email")
        event_id = args.get("event_id")

        if not user_id or not event_id:
            return jsonify({"error": "user_id and event_id are required"}), 400

        token, _ = await get_refreshed_token_microsoft(request.ordo_app["id"], user_id, email=email)

        async with AsyncClient() as client:
            resp = await client.delete(
                f"https://graph.microsoft.com/v1.0/me/events/{event_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        if resp.status_code not in (200, 204):
            return jsonify({"error": f"Graph API error: {resp.text}"}), resp.status_code

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@microsoft_calendar_bp.route('/reschedule', methods=['POST'])
@require_api_key
async def microsoft_calendar_reschedule():
    try:
        data = await request.get_json()
        args = data.get("args") or data
        user_id = args.get("user_id")
        email = args.get("email")
        event_id = args.get("event_id")
        start_time = args.get("start_time")
        end_time = args.get("end_time")

        if not all([user_id, event_id, start_time, end_time]):
            return jsonify({"error": "user_id, event_id, start_time, end_time are required"}), 400

        token, integration = await get_refreshed_token_microsoft(request.ordo_app["id"], user_id, email=email)
        tz_name = integration.get("timezone") or "America/New_York"

        async with AsyncClient() as client:
            resp = await client.patch(
                f"https://graph.microsoft.com/v1.0/me/events/{event_id}",
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json"},
                json={
                    "start": {"dateTime": start_time, "timeZone": tz_name},
                    "end": {"dateTime": end_time, "timeZone": tz_name},
                },
            )
            event = resp.json()

        return jsonify({"event": event, "success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------
# Webhook (Microsoft Graph change notifications)
# -------------------------

@microsoft_calendar_bp.route('/webhook', methods=['GET', 'POST'])
async def microsoft_calendar_webhook():
    # Validation handshake
    validation_token = request.args.get("validationToken")
    if validation_token:
        return validation_token, 200, {"Content-Type": "text/plain"}

    try:
        payload = await request.get_json()
        notifications = (payload or {}).get("value", [])

        for notification in notifications:
            subscription_id = notification.get("subscriptionId")
            if not subscription_id:
                continue

            row = db.get_watch_channel_by_channel_id(subscription_id)
            if not row:
                continue

            await process_microsoft_changes(row["app_id"], row["user_id"], email=row["email"])

        return "", 202

    except Exception as e:
        logger.error(f"=== ORDO: Microsoft webhook error: {e} ===")
        return "", 202


async def process_microsoft_changes(app_id: str, user_id: str, email: str):
    try:
        token, integration = await get_refreshed_token_microsoft(app_id, user_id, email=email)
    except ValueError:
        logger.warning(
            f"=== ORDO: No Microsoft integration for app={app_id} user={user_id} email={email} ===")
        return

    channel_row = db.get_watch_channel(
        app_id, user_id, "microsoft", email=email)
    delta_link = channel_row.get("sync_token") if channel_row else None

    try:
        headers = {"Authorization": f"Bearer {token}"}
        url = delta_link or "https://graph.microsoft.com/v1.0/me/calendarView/delta?startDateTime={}&endDateTime={}".format(
            datetime.utcnow().isoformat() + "Z",
            (datetime.utcnow() + timedelta(weeks=8)).isoformat() + "Z",
        )

        async with AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            data = resp.json()

        new_delta_link = data.get("@odata.deltaLink")
        if new_delta_link:
            db.update_watch_channel_sync_token(
                app_id, user_id, "microsoft", email, new_delta_link)

        from agent.tools.calendar_tools import check_collision
        for event in data.get("value", []):
            if event.get("@removed"):
                continue
            await check_collision(app_id, user_id, email, event, None, provider="microsoft")

    except Exception as e:
        logger.error(f"=== ORDO: process_microsoft_changes error: {e} ===")


# -------------------------
# Subscription registration
# -------------------------

async def register_microsoft_watch(app_id: str, user_id: str, email: str = None):
    integration = db.get_integration(app_id, user_id, "microsoft", email=email)
    if not integration:
        raise Exception(
            f"No Microsoft integration for user {user_id} email={email}")

    actual_email = integration["email"]
    token, _ = await get_refreshed_token_microsoft(app_id, user_id, email=actual_email)
    expiration = (datetime.utcnow() + timedelta(minutes=4230)
                  ).strftime("%Y-%m-%dT%H:%M:%S.0000000Z")

    body = {
        "changeType": "created,updated,deleted",
        "notificationUrl": f"{os.environ['ORDO_BASE_URL']}/microsoft_calendar/webhook",
        "resource": "me/events",
        "expirationDateTime": expiration,
        "clientState": f"{app_id}:{user_id}",
    }

    async with AsyncClient() as client:
        resp = await client.post(
            "https://graph.microsoft.com/v1.0/subscriptions",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json=body,
        )
        result = resp.json()

    subscription_id = result.get("id")
    if not subscription_id:
        raise Exception(f"Microsoft subscription failed: {result}")

    db.upsert_watch_channel(
        app_id=app_id,
        user_id=user_id,
        provider="microsoft",
        email=actual_email,
        channel_id=subscription_id,
        resource_id=subscription_id,
        expiration=expiration,
        sync_token=None,
    )
