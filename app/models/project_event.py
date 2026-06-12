"""User-facing project activity event.

An append-only, human-readable timeline of milestones for a project (analysis,
preview, extraction, export, and user actions). Deliberately NOT operator logs:
rows are sanitized and bounded to milestones — never per-crawl-page spam, never
secrets or extracted record content. Rows cascade-delete with the project and
the user, so completed-project history is cleaned up automatically.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProjectEvent(Base):
    __tablename__ = "project_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(
        String(16), nullable=False, default="info", server_default="info"
    )
    message: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # Python attribute is event_metadata to avoid clashing with Base.metadata;
    # the DB column and API field are named "metadata".
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="'{}'::jsonb"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
