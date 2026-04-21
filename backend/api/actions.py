import logging
from functools import wraps
from classes import OrdoDB
from agent.tools import TOOL_MAP
from quart import Blueprint, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = OrdoDB()
action_bp = Blueprint('action', __name__)


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


@action_bp.route('/action', methods=['POST'])
@require_api_key
async def action():
    """
    Single dispatch endpoint for all calendar tool functions.

    POST /action
    {
        "user_id": "...",
        "tool": "google_book_event",
        "params": { "title": "...", "start_time": "...", ... }
    }
    """
    try:
        body = await request.get_json()
    except Exception:
        return jsonify({"success": False, "error": "Invalid JSON body"}), 400

    user_id = body.get("user_id")
    tool_name = body.get("tool")
    params = body.get("params", {})

    if not user_id:
        return jsonify({"success": False, "error": "user_id is required"}), 400
    if not tool_name:
        return jsonify({"success": False, "error": "tool is required"}), 400

    handler = TOOL_MAP.get(tool_name)
    if not handler:
        return jsonify({
            "success": False,
            "error": f"Unknown tool: {tool_name}",
            "available_tools": sorted(TOOL_MAP.keys()),
        }), 400

    logger.info(f"=== ORDO ACTION: tool={tool_name} app={request.ordo_app['name']} user={user_id} ===")

    try:
        result = await handler(app_id=request.ordo_app["id"], user_id=user_id, **params)

        if isinstance(result, dict) and not result.get("success", True):
            return jsonify(result), 400

        return jsonify(result)

    except TypeError as e:
        return jsonify({"success": False, "error": f"Invalid parameters: {e}"}), 400
    except Exception as e:
        logger.exception(f"Tool '{tool_name}' failed")
        return jsonify({"success": False, "error": str(e)}), 500
