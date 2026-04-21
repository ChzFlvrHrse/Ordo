import json, logging
from dotenv import load_dotenv
from . import (
    calendar_tools,
    google_tools,
    microsoft_tools
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOOLS = [
    *calendar_tools.TOOL_DEFINITIONS,
    *google_tools.TOOL_DEFINITIONS,
    *microsoft_tools.TOOL_DEFINITIONS,
]

TOOL_MAP = {
    # Calendar tools
    "calendar_get_events": calendar_tools.get_events,
    "calendar_get_collisions": calendar_tools.get_collisions,
    "calendar_resolve_collision": calendar_tools.resolve_collision,
    "calendar_resolve_all_collisions": calendar_tools.resolve_all_collisions,

    # Google tools
    "google_get_events": google_tools.get_events,
    "google_book_event": google_tools.book_event,
    "google_cancel_event": google_tools.cancel_event,
    "google_reschedule_event": google_tools.reschedule_event,

    # Microsoft tools
    "microsoft_get_events": microsoft_tools.get_events,
    "microsoft_book_event": microsoft_tools.book_event,
    "microsoft_cancel_event": microsoft_tools.cancel_event,
    "microsoft_reschedule_event": microsoft_tools.reschedule_event,
}


async def execute_tool(tool_name: str, tool_input: dict, app_id: str, user_id: str) -> str:
    if tool_name not in TOOL_MAP:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    fn = TOOL_MAP[tool_name]
    logger.info(f"=== ORDO TOOLS: tool={tool_name} user={user_id} input={tool_input} ===")

    result = await fn(app_id=app_id, user_id=user_id, **tool_input)
    return json.dumps(result)
