import logging
from classes import OrdoDB
from datetime import datetime, timedelta
from api.calendar.google_api import register_google_watch
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("interval", hours=12)
async def renew_expiring_watch_channels():

    db = OrdoDB()
    cutoff = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    rows = db.get_expiring_watch_channels(before=cutoff)

    if not rows:
        logger.info("=== ORDO: No watch channels expiring soon ===")
        return

    logger.info(f"=== ORDO: Renewing {len(rows)} expiring watch channel(s) ===")

    for row in rows:
        try:
            register_google_watch(row["app_id"], row["user_id"], email=row["email"])
            logger.info(f"=== ORDO: Renewed watch app={row['app_id']} user={row['user_id']} ===")
        except Exception as e:
            logger.error(f"=== ORDO: Failed to renew watch app={row['app_id']} user={row['user_id']}: {e} ===")

# Production will run very frequently, every 30 seconds for efficient cleanup
@scheduler.scheduled_job("interval", hours=30)
async def cleanup_expired_collisions():
    db = OrdoDB()
    count = db.resolve_expired_collisions()
    if count:
        logger.info(f"=== ORDO: Resolved {count} expired collision notification(s) ===")
