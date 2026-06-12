"""project_events: user-facing activity timeline

Revision ID: 011_project_events
Revises: 010_password_reset
Create Date: 2026-06-12

Adds the ``project_events`` table — an append-only, sanitized activity log
surfaced to users in the dashboard. Rows cascade-delete with both the owning
project and the owning user.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "011_project_events"
down_revision: Union[str, None] = "010_password_reset"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_project_events_user_id", "project_events", ["user_id"])
    op.create_index("ix_project_events_project_id", "project_events", ["project_id"])
    op.create_index("ix_project_events_created_at", "project_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_project_events_created_at", "project_events")
    op.drop_index("ix_project_events_project_id", "project_events")
    op.drop_index("ix_project_events_user_id", "project_events")
    op.drop_table("project_events")
