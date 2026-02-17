"""
Watchdog service for stuck task cleanup.

Detects and fails tasks stuck in non-terminal states.
"""

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import async_session_factory
from app.models.scrape_task import ScrapeTask, TaskState


logger = logging.getLogger(__name__)


async def cleanup_stuck_tasks() -> int:
    """
    Find and fail tasks stuck in non-terminal states.

    Cleans up:
    - PERMISSION_GRANTED: Pipeline never started
    - SCRAPING: Scrape took too long
    - LLM_PROCESSING: LLM processing took too long

    Returns:
        Number of tasks cleaned up
    """
    now = datetime.now(timezone.utc)
    cleaned = 0

    async with async_session_factory() as db:
        # Find tasks stuck in PERMISSION_GRANTED (pipeline never started)
        pg_cutoff = now - timedelta(
            minutes=settings.WATCHDOG_PERMISSION_GRANTED_TIMEOUT_MINUTES
        )
        result = await db.execute(
            select(ScrapeTask).where(
                ScrapeTask.state == TaskState.PERMISSION_GRANTED,
                ScrapeTask.updated_at < pg_cutoff,
            )
        )
        stuck_pg = result.scalars().all()

        for task in stuck_pg:
            task.state = TaskState.FAILED
            mins = settings.WATCHDOG_PERMISSION_GRANTED_TIMEOUT_MINUTES
            task.error = f"Watchdog: Pipeline did not start within {mins}m"
            logger.warning(
                "watchdog.stuck_task",
                extra={"task_id": task.id, "state": "PERMISSION_GRANTED"},
            )
            cleaned += 1

        # Find tasks stuck in SCRAPING
        scraping_cutoff = now - timedelta(
            minutes=settings.WATCHDOG_SCRAPING_TIMEOUT_MINUTES
        )
        result = await db.execute(
            select(ScrapeTask).where(
                ScrapeTask.state == TaskState.SCRAPING,
                ScrapeTask.updated_at < scraping_cutoff,
            )
        )
        stuck_scraping = result.scalars().all()

        for task in stuck_scraping:
            task.state = TaskState.FAILED
            mins = settings.WATCHDOG_SCRAPING_TIMEOUT_MINUTES
            task.error = f"Watchdog: Stuck in SCRAPING for >{mins}m"
            logger.warning(
                "watchdog.stuck_task",
                extra={"task_id": task.id, "state": "SCRAPING"},
            )
            cleaned += 1

        # Find tasks stuck in LLM_PROCESSING
        llm_cutoff = now - timedelta(
            minutes=settings.WATCHDOG_LLM_TIMEOUT_MINUTES
        )
        result = await db.execute(
            select(ScrapeTask).where(
                ScrapeTask.state == TaskState.LLM_PROCESSING,
                ScrapeTask.updated_at < llm_cutoff,
            )
        )
        stuck_llm = result.scalars().all()

        for task in stuck_llm:
            task.state = TaskState.FAILED
            mins = settings.WATCHDOG_LLM_TIMEOUT_MINUTES
            task.error = f"Watchdog: Stuck in LLM_PROCESSING for >{mins}m"
            logger.warning(
                "watchdog.stuck_task",
                extra={"task_id": task.id, "state": "LLM_PROCESSING"},
            )
            cleaned += 1

        if cleaned > 0:
            await db.commit()
            logger.info("watchdog.cleanup_complete", extra={"cleaned": cleaned})

    return cleaned


async def run_watchdog_once() -> None:
    """Run watchdog cleanup once. Called by background scheduler."""
    try:
        cleaned = await cleanup_stuck_tasks()
        if cleaned > 0:
            logger.info("watchdog.run_complete", extra={"cleaned": cleaned})
    except Exception as e:
        logger.exception("watchdog.error", extra={"error": str(e)})
