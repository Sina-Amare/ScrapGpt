"""
Admission service for scrape task creation.

Validates:
1. User has credits (>= 1)
2. User has no active task

Credits reset daily at 00:00 UTC.
"""

import logging
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scrape_task import ScrapeTask, TaskState, TERMINAL_STATES
from app.models.user import User


logger = logging.getLogger(__name__)


class AdmissionErrorType(str, Enum):
    """Types of admission failures."""
    ALREADY_HAS_ACTIVE_TASK = "ALREADY_HAS_ACTIVE_TASK"
    INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"


@dataclass
class AdmissionError:
    """Error result from admission attempt."""
    error_type: AdmissionErrorType
    message: str
    active_task_id: int | None = None


@dataclass
class AdmissionSuccess:
    """Success result from admission attempt."""
    task: ScrapeTask


AdmissionResult = AdmissionSuccess | AdmissionError


async def admit_scrape_task(
    user: User,
    url: str,
    db: AsyncSession,
) -> AdmissionResult:
    """
    Create a scrape task in PERMISSION_GRANTED state.

    Checks:
    1. User has >= 1 credit (credits reset daily at 00:00 UTC)
    2. User has no active task (enforced by partial unique index)

    Credits are NOT deducted here - deduction happens at LLM processing.

    Args:
        user: Authenticated user
        url: URL to scrape
        db: Database session

    Returns:
        AdmissionSuccess: Task created
        AdmissionError: Insufficient credits or already has active task
    """
    # Credit check (credits reset at 00:00 UTC daily by scheduler)
    if user.credits_remaining <= 0:
        logger.info(
            "admission.blocked.no_credits",
            extra={"user_id": user.id, "credits": user.credits_remaining},
        )
        return AdmissionError(
            error_type=AdmissionErrorType.INSUFFICIENT_CREDITS,
            message="Insufficient credits. Credits reset daily at 00:00 UTC.",
        )

    task = ScrapeTask(
        user_id=user.id,
        url=url,
        state=TaskState.PERMISSION_GRANTED,
    )

    try:
        async with db.begin():
            db.add(task)
            await db.flush()

        await db.refresh(task)

        logger.info(
            "admission.success",
            extra={"user_id": user.id, "task_id": task.id, "url": url},
        )

        return AdmissionSuccess(task=task)

    except IntegrityError as e:
        if "ix_one_active_task_per_user" in str(e.orig):
            from sqlalchemy import select

            result = await db.execute(
                select(ScrapeTask.id).where(
                    ScrapeTask.user_id == user.id,
                    ScrapeTask.state.notin_(TERMINAL_STATES),
                )
            )
            active_task_id = result.scalar_one_or_none()

            logger.info(
                "admission.blocked.active_task",
                extra={"user_id": user.id, "active_task_id": active_task_id},
            )

            return AdmissionError(
                error_type=AdmissionErrorType.ALREADY_HAS_ACTIVE_TASK,
                message="You already have an active scraping task",
                active_task_id=active_task_id,
            )
        raise


