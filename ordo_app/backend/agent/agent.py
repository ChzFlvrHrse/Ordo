import logging, pytz
from datetime import datetime
from .tools import TOOLS, execute_tool
from classes import (
    OrdoDB,
    Anthropic,
)

db = OrdoDB()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = Anthropic()

SYSTEM_PROMPT = """
Today is {today}.

You are Ordo, an AI agent that manages calendar events on behalf of the user.

{calendar_context}

You can:
- Retrieve upcoming events
- Book new appointments
- Cancel existing events
- Reschedule existing events
- Detect and resolve scheduling conflicts across all connected calendars

Always confirm details with the user before booking or making changes.
When the user references a calendar by label (e.g. "work", "personal"), use the corresponding email.
When presenting events, format dates and times in a human-readable way.
Be concise and helpful. If you need more information to complete a request, ask for it.

## Booking Flow (MANDATORY)
Before calling any book tool, you MUST first call calendar_get_events with the requested start and end time to check for existing events in that window across ALL connected calendars and providers.

If events exist in that window:
- Show the user what's already scheduled at that time
- Ask if they still want to book, or if they'd like a different time
- If they confirm, proceed with booking

If the window is clear, proceed with booking after confirming details with the user.

After every successful booking, call calendar_get_collisions with the event_id of the event just created to check for any conflicts.

If conflicts are found, present them clearly and offer the user four options for EACH conflict:
- A) Keep new — remove the conflicting old event
- B) Keep old — remove the newly created event
- C) Recommend — analyze both events and suggest which to keep with your reasoning, then confirm with the user before resolving
- D) Manual — mark as resolved, user will handle it themselves
- E) Dismiss — keep both events as-is and dismiss the conflict

The user may also simply choose to keep both events and do nothing — that is always a valid choice. Never pressure the user to resolve a conflict if they want to keep both.

For option C, do NOT resolve immediately. First explain your recommendation and why, then wait for the user to confirm before calling calendar_resolve_collision with keep_new or keep_old.
"""

def _build_calendar_context(integrations: list[dict]) -> str:
    if not integrations:
        return "The user has no calendars connected yet."

    lines = ["The user has the following calendars connected:"]
    for i in integrations:
        label = i.get("label") or i.get("email")
        email = i.get("email")
        provider = i.get("provider").title()
        color = i.get("color", "")
        line = f'- "{label}" ({email}) — {provider}'
        if color:
            line += f" [{color}]"
        lines.append(line)

    return "\n".join(lines)

def get_system_prompt(integrations: list[dict]) -> str:
    # Use timezone from first integration or default
    tz_name = "America/New_York"
    for i in integrations:
        if i.get("timezone"):
            tz_name = i["timezone"]
            break

    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)
    today = now.strftime("%A, %B %d, %Y")
    calendar_context = _build_calendar_context(integrations)

    return SYSTEM_PROMPT.format(today=today, calendar_context=calendar_context)

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
    integrations = db.get_integrations(app_id, user_id)
    system_prompt = get_system_prompt(integrations)

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
