"""
Background scheduler for periodic tasks.

Handles:
- Daily credit reset at 00:00 UTC (multi-instance safe)
- Watchdog cleanup of stuck tasks

Uses database locking to prevent duplicate execution across instances.
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import text

from app.db.database import async_session_factory
from app.services.watchdog import run_watchdog_once


logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler(timezone="UTC")


async def try_reset_all_credits() -> None:
    """
    Reset all user credits to daily limit.

    Multi-instance safe: Uses database locking to ensure only one
    instance performs the reset per day.

    Behavior:
    - Runs at 00:00 UTC daily (or first instance wake-up after midnight)
    - Checks system_state.last_credit_reset to prevent duplicates
    - Atomically updates all users in single transaction
    """
    today = datetime.now(timezone.utc).date().isoformat()

    async with async_session_factory() as db:
        try:
            async with db.begin():
                # Atomic check-and-set: only one instance wins
                result = await db.execute(
                    text("""
                        UPDATE system_state
                        SET value = :today, updated_at = NOW()
                        WHERE key = 'last_credit_reset' AND value != :today
                    """),
                    {"today": today},
                )

                if result.rowcount == 0:
                    # Already reset today by another instance
                    logger.debug("credits.reset_skipped", extra={"date": today})
                    return

                # This instance wins - perform the reset
                reset_result = await db.execute(
                    text("""
                        UPDATE users
                        SET credits_remaining = daily_credit_limit,
                            credits_reset_at = NOW(),
                            updated_at = NOW()
                    """)
                )

                logger.info(
                    "credits.global_reset",
                    extra={
                        "date": today,
                        "users_reset": reset_result.rowcount,
                    },
                )

        except Exception as e:
            logger.exception("credits.reset_error", extra={"error": str(e)})
            raise


def configure_scheduler() -> None:
    """Configure all scheduled jobs."""

    # Credit reset: 00:00 UTC daily
    # misfire_grace_time=3600: If app starts within 1 hour of midnight, still run
    scheduler.add_job(
        try_reset_all_credits,
        trigger=CronTrigger(hour=0, minute=0, timezone="UTC"),
        id="daily_credit_reset",
        name="Reset all user credits at midnight UTC",
        replace_existing=True,
        misfire_grace_time=3600,  # 1 hour grace period
    )

    # Watchdog: every 60 seconds
    scheduler.add_job(
        run_watchdog_once,
        trigger=IntervalTrigger(seconds=60),
        id="watchdog_cleanup",
        name="Clean up stuck tasks",
        replace_existing=True,
    )

    logger.info("scheduler.configured", extra={"jobs": 2})


def start_scheduler() -> None:
    """
    Start the background scheduler.

    Also runs credit reset check on startup to handle case where
    app was down during midnight.
    """
    configure_scheduler()
    scheduler.start()
    logger.info("scheduler.started")

    # Run credit reset check on startup (handles app downtime over midnight)
    import asyncio
    asyncio.create_task(try_reset_all_credits())
    logger.info("scheduler.startup_reset_scheduled")


def stop_scheduler() -> None:
    """Stop the background scheduler gracefully."""
    scheduler.shutdown(wait=False)
    logger.info("scheduler.stopped")
