"""
Background scheduler for periodic tasks.

Handles:
- Watchdog cleanup of stuck tasks

"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.services.watchdog import run_watchdog_once


logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler(timezone="UTC")


def configure_scheduler() -> None:
    """Configure all scheduled jobs."""

    # Watchdog: every 60 seconds
    scheduler.add_job(
        run_watchdog_once,
        trigger=IntervalTrigger(seconds=60),
        id="watchdog_cleanup",
        name="Clean up stuck tasks",
        replace_existing=True,
    )

    logger.info("scheduler.configured", extra={"jobs": 1})


def start_scheduler() -> None:
    """
    Start the background scheduler.

    """
    configure_scheduler()
    scheduler.start()
    logger.info("scheduler.started")


def stop_scheduler() -> None:
    """Stop the background scheduler gracefully."""
    scheduler.shutdown(wait=False)
    logger.info("scheduler.stopped")
