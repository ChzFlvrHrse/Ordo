import os, json, logging
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Anthropic:
    def __init__(self):
        self.client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-6"

    async def run(
        self,
        messages: list[dict],
        system_prompt: str,
        tools: list[dict] = None,
        max_tokens: int = 4096,
    ) -> dict:
        try:
            kwargs = {
                "model": self.model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools

            response = await self.client.messages.create(**kwargs)

            return {
                "status": "success",
                "content": response.content,
                "stop_reason": response.stop_reason,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            }

        except Exception as e:
            logger.error(f"Anthropic error: {e}")
            return {"status": "error", "error": str(e)}
