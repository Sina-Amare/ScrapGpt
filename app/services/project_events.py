"""Recorder and queries for the user-facing project activity log.

``record_project_event`` is the write path used by the pipeline. It opens its
own short-lived session and NEVER raises: activity logging must not be able to
break the analysis/extraction it is observing. Callers pass static message
templates; dynamic values go in ``metadata`` and are filtered to JSON scalars
so secrets or large objects cannot leak in.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_factory
from app.models.project_event import ProjectEvent

logger = logging.getLogger(__name__)

_ALLOWED_LEVELS = {"info", "warning", "error"}


def _sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Keep only JSON scalar values (and lists of scalars).

    Defense-in-depth so a caller cannot accidentally persist an object,
    credential, or unbounded blob into the user-visible timeline.
    """
    if not isinstance(metadata, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            safe[str(key)] = value
        elif isinstance(value, (list, tuple)):
            safe[str(key)] = [
                item for item in value if isinstance(item, (str, int, float, bool))
            ]
    return safe


async def record_project_event(
    project_id: int,
    user_id: int,
    event_type: str,
    *,
    level: str = "info",
    message: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append one project activity event. Never raises."""
    if level not in _ALLOWED_LEVELS:
        level = "info"
    try:
        async with async_session_factory() as session:
            session.add(
                ProjectEvent(
                    project_id=project_id,
                    user_id=user_id,
                    event_type=event_type,
                    level=level,
                    message=message,
                    event_metadata=_sanitize_metadata(metadata),
                )
            )
            await session.commit()
    except Exception:
        # Activity logging is best-effort; a failure here must not propagate
        # into the pipeline that triggered it.
        logger.error(
            "project_event.record_failed",
            extra={"project_id": project_id, "event_type": event_type},
        )


async def list_project_events(
    db: AsyncSession, project_id: int, user_id: int, limit: int = 100
) -> list[ProjectEvent]:
    """Events for one project, newest first. Owner-scoped by user_id."""
    result = await db.execute(
        select(ProjectEvent)
        .where(
            ProjectEvent.project_id == project_id,
            ProjectEvent.user_id == user_id,
        )
        .order_by(ProjectEvent.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_user_events(
    db: AsyncSession, user_id: int, limit: int = 100
) -> list[ProjectEvent]:
    """Recent events across all of a user's projects, newest first."""
    result = await db.execute(
        select(ProjectEvent)
        .where(ProjectEvent.user_id == user_id)
        .order_by(ProjectEvent.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
