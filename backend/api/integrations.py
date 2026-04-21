import logging
from quart import Blueprint, request, jsonify
from functools import wraps
from classes import OrdoDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = OrdoDB()
integrations_bp = Blueprint('integrations', __name__, url_prefix='/integrations')

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

@integrations_bp.route('/calendars', methods=['GET'])
@require_api_key
async def calendars():
    try:
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        calendars = db.get_integrations(request.ordo_app["id"], user_id)
        if not calendars:
            return jsonify({"calendars": []}), 200

        for calendar in calendars:
            calendar.pop("access_token")
            calendar.pop("refresh_token")

        return jsonify({"calendars": calendars}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@integrations_bp.route('/labels', methods=['PUT'])
@require_api_key
async def labels():
    try:
        data = await request.get_json()

        user_id = data.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        labels = data.get("labels")
        if not labels:
            return jsonify({"error": "labels are required"}), 400

        updated_labels = []
        for label in labels:
            if not label.get("id") or not label.get("provider") or not label.get("email") or not label.get("label") or not label.get("color"):
                return jsonify({"error": "id, provider, email, label, and color are required"}), 400

            integration = db.update_integration_config(
                app_id=request.ordo_app["id"],
                user_id=user_id,
                provider=label.get("provider"),
                email=label.get("email"),
                label=label.get("label"),
                color=label.get("color"),
            )

            updated_labels.append(integration)

        return jsonify({"labels": updated_labels, "success": True}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
