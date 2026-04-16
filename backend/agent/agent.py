import logging, pytz
from datetime import datetime
from classes import Anthropic
from .tools import TOOLS, execute_tool
from classes import OrdoDB

db = OrdoDB()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = Anthropic()

SYSTEM_PROMPT = """
Today is {today}.

You are Ordo, an AI agent that manages calendar events on behalf of the user.

You have access to the user's connected calendars. You can:
- Retrieve upcoming events
- Book new appointments
- Cancel existing events
- Reschedule existing events

Always confirm details with the user before booking or making changes.
When presenting events, format dates and times in a human-readable way.
Be concise and helpful. If you need more information to complete a request, ask for it.
"""

def get_system_prompt(timezone: str = "America/New_York") -> str:
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    today = now.strftime("%A, %B %d, %Y")
    return SYSTEM_PROMPT.format(today=today)

def _serialize_content(content: list) -> list:
    result = []
    for block in content:
        if block.type == "text":
            result.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            result.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
    return result

async def run_agent(app_id: str, user_id: str, messages: list[dict]) -> dict:
    """
    Main agent loop.
    messages: full conversation history as list of {"role": "user"|"assistant", "content": str|list}
    Returns the agent's text response and updated message history.
    """
    integration = db.get_integration(app_id, user_id)
    tz_name = (integration.get("timezone") or "America/New_York") if integration else "America/New_York"
    system_prompt = get_system_prompt(tz_name)

    try:
        while True:
            response = await client.run(
                messages=messages,
                system_prompt=system_prompt,
                tools=TOOLS,
            )

            if response["status"] == "error":
                return {"success": False, "error": response["error"]}

            content = response["content"]
            stop_reason = response["stop_reason"]

            serialized = _serialize_content(content)
            messages.append({"role": "assistant", "content": serialized})

            if stop_reason != "tool_use":
                text = next((b["text"] for b in serialized if b["type"] == "text"), "")
                return {
                    "success": True,
                    "message": text,
                    "messages": messages,
                    "usage": response["usage"],
                }

            tool_results = []
            for block in serialized:
                if block["type"] != "tool_use":
                    continue
                result = await execute_tool(block["name"], block["input"], app_id, user_id)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": result,
                })

            messages.append({"role": "user", "content": tool_results})

    except Exception as e:
        logger.error(f"Agent error: {e}")
        return {"success": False, "error": str(e)}
