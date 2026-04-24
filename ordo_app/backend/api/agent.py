import logging
from functools import wraps
from classes import OrdoDB
from agent import run_agent
from quart import Blueprint, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = OrdoDB()
agent_bp = Blueprint('agent', __name__, url_prefix='/agent')


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


@agent_bp.route('/chat', methods=['POST'])
@require_api_key
async def chat():
    try:
        data = await request.get_json()
        user_id = data.get("user_id")
        messages = data.get("messages")

        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        if not messages or not isinstance(messages, list):
            return jsonify({"error": "messages must be a non-empty array"}), 400

        result = await run_agent(request.ordo_app["id"], user_id, messages)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
