"""Project lifecycle operations that span project-owned tables."""

from __future__ import annotations

import logging

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import (
    CrawlPage,
    Export,
    ExtractedRecord,
    ExtractionSpec,
    FrontierPreview,
    PreviewResult,
    Project,
)

logger = logging.getLogger(__name__)


async def delete_project_tree(db: AsyncSession, project: Project) -> None:
    """Delete a project and all project-owned artifacts.

    This intentionally uses bulk deletes in dependency order instead of
    relying solely on ORM relationship cascades. Projects can accumulate
    specs, previews, frontier previews, crawl pages, exports, and records
    across failed preview/extraction attempts; deleting each table
    explicitly keeps the endpoint deterministic for those partial states.
    """
    project_id = project.id

    for model in (
        ExtractedRecord,
        Export,
        FrontierPreview,
        PreviewResult,
        CrawlPage,
        ExtractionSpec,
    ):
        result = await db.execute(delete(model).where(model.project_id == project_id))
        logger.debug(
            "project.delete_artifacts",
            extra={
                "project_id": project_id,
                "table": model.__tablename__,
                "rowcount": result.rowcount,
            },
        )

    result = await db.execute(delete(Project).where(Project.id == project_id))
    logger.info(
        "project.deleted",
        extra={
            "project_id": project_id,
            "rowcount": result.rowcount,
        },
    )
    await db.commit()
