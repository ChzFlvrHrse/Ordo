import os
import asyncio
import logging
import resend
from twilio.rest import Client as TwilioClient
from datetime import datetime, timezone
from classes import OrdoDB

logger = logging.getLogger(__name__)
db = OrdoDB()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
ORDO_DEFAULT_NUMBER = os.getenv("ORDO_TWILIO_NUMBER")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
CHANNEL = os.getenv("CHANNEL", "email")  # "sms" | "email"
MAX_RETRIES = 3

# twilio = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
resend.api_key = RESEND_API_KEY


async def send_message(message: dict) -> bool:
    try:
        if CHANNEL == "sms":
            # from_number = message.get("ordo_number") or ORDO_DEFAULT_NUMBER
            # result = await asyncio.to_thread(
            #     twilio.messages.create,
            #     to=message["phone"],
            #     from_=from_number,
            #     body=message["body"],
            # )
            # db.update_message_status(
            #     message_id=message["id"],
            #     status="sent",
            #     sent_at=datetime.now(timezone.utc).isoformat(),
            #     twilio_sid=result.sid,
            # )
            pass

        else:  # email
            await asyncio.to_thread(
                resend.Emails.send,
                {
                    "from": "Ordo <onboarding@resend.dev>",
                    "to": [message["email"]],
                    "subject": "Ordo Notification",
                    "html": f"<p>{message['body']}</p>",
                },
            )
            db.update_message_status(
                message_id=message["id"],
                status="sent",
                sent_at=datetime.now(timezone.utc).isoformat(),
                twilio_sid=None,
            )

        return True

    except Exception as e:
        logger.error(f"sms_worker.send_message failed id={message['id']}: {e}")
        retry_count = message.get("retry_count", 0) + 1
        if retry_count >= MAX_RETRIES:
            db.update_message_status(
                message_id=message["id"],
                status="failed",
                retry_count=retry_count,
            )
        else:
            db.update_message_status(
                message_id=message["id"],
                status="pending",
                retry_count=retry_count,
            )
        return False


async def run_worker(interval_seconds: int = 60):
    logger.info("SMS worker started")
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat()
            messages = db.get_pending_messages(before=now)

            if messages:
                logger.info(f"SMS worker: processing {len(messages)} messages")
                for message in messages:
                    await send_message(message)

        except Exception as e:
            logger.error(f"SMS worker error: {e}")

        await asyncio.sleep(interval_seconds)
