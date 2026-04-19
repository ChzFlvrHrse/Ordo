import json, logging
from dotenv import load_dotenv
from . import (
    calendar_tools,
    google_tool
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOOLS = [
    *calendar_tools.TOOL_DEFINITIONS,
    *google_tool.TOOL_DEFINITIONS,
    # *outlook.TOOL_DEFINITIONS,
]

TOOL_MAP = {
    "google_get_events": google_tool.get_events,
    "google_book_event": google_tool.book_event,
    "google_cancel_event": google_tool.cancel_event,
    "google_reschedule_event": google_tool.reschedule_event,
    "calendar_get_events": calendar_tools.get_events,
    "calendar_get_collisions": calendar_tools.get_collisions,
    "calendar_resolve_collision": calendar_tools.resolve_collision,
    "calendar_resolve_all_collisions": calendar_tools.resolve_all_collisions,
}


async def execute_tool(tool_name: str, tool_input: dict, app_id: str, user_id: str) -> str:
    if tool_name not in TOOL_MAP:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    fn = TOOL_MAP[tool_name]
    logger.info(f"=== ORDO TOOLS: tool={tool_name} user={user_id} input={tool_input} ===")

    result = await fn(app_id=app_id, user_id=user_id, **tool_input)
    return json.dumps(result)
