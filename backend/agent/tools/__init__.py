import json, logging
from dotenv import load_dotenv
from . import (
    google
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Aggregate tool definitions from all providers
TOOLS = [
    *google.TOOL_DEFINITIONS,
    # *outlook.TOOL_DEFINITIONS,
]

TOOL_MAP = {
    "google_get_events": (google.get_events, ["lookahead_weeks"]),
    "google_book_event": (google.book_event, ["title", "start_time", "end_time", "attendee_emails", "description", "add_meet"]),
    "google_cancel_event": (google.cancel_event, ["event_id"]),
    "google_reschedule_event": (google.reschedule_event, ["event_id", "start_time", "end_time"]),
    # outlook tools go here
}


async def execute_tool(tool_name: str, tool_input: dict, app_id: str, user_id: str) -> str:
    if tool_name not in TOOL_MAP:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    tool_call, param_keys = TOOL_MAP[tool_name]
    kwargs = {k: tool_input[k] for k in param_keys if k in tool_input}

    logger.info(
        f"=== ORDO TOOLS: tool={tool_name} user={user_id} kwargs={kwargs} ===")

    result = await tool_call(app_id, user_id, **kwargs)
    return json.dumps(result)
