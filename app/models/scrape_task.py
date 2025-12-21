"""
ScrapeTask model for tracking scraping job states.

Each user can have at most one non-FINALIZED task at a time,
enforced by a partial unique index at the database level.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TaskState(str, enum.Enum):
    """
    State machine for scrape tasks.

    Flow: PERMISSION_GRANTED -> SCRAPED -> LLM_ANALYZED
          -> OUTPUT_GENERATION -> FINALIZED
    """
    PERMISSION_GRANTED = "PERMISSION_GRANTED"
    SCRAPED = "SCRAPED"
    LLM_ANALYZED = "LLM_ANALYZED"
    OUTPUT_GENERATION = "OUTPUT_GENERATION"
    FINALIZED = "FINALIZED"


class ScrapeTask(Base):
    """
    Scrape task tracking model.

    Invariant: At most one non-FINALIZED task per user.
    Enforced by partial unique index in database.
    """

    __tablename__ = "scrape_tasks"

    # Primary Key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Foreign Key to User
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Task State (NOT NULL)
    state: Mapped[TaskState] = mapped_column(
        Enum(TaskState, name="task_state", native_enum=True),
        nullable=False,
        default=TaskState.PERMISSION_GRANTED,
        index=True,
    )

    # Target URL
    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )

    # Scraped content (populated after SCRAPED state)
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    # Relationship
    user = relationship("User", back_populates="scrape_tasks")

    def __repr__(self) -> str:
        return f"<ScrapeTask {self.id} state={self.state.value}>"
