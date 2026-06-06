"""provider foundation and credit removal

Revision ID: 005
Revises: fe292fc905ad
Create Date: 2026-06-06

This migration intentionally removes the old credit system. Downgrade recreates
the dropped columns structurally, but historical credit balances are not
recoverable.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "005"
down_revision: Union[str, None] = "fe292fc905ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_one_active_task_per_user")

    op.create_table(
        "provider_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "capability_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_configs_user_id", "provider_configs", ["user_id"], unique=False)
    op.create_index("ix_provider_configs_provider", "provider_configs", ["provider"], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX ix_provider_configs_one_default_per_user
        ON provider_configs (user_id)
        WHERE is_default = true
        """
    )

    op.add_column("users", sa.Column("default_provider_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_default_provider_id_provider_configs",
        "users",
        "provider_configs",
        ["default_provider_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_column("users", "credits_reset_at")
    op.drop_column("users", "daily_credit_limit")
    op.drop_column("users", "credits_remaining")
    op.execute("DROP TABLE IF EXISTS system_state")


def downgrade() -> None:
    op.create_table(
        "system_state",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.execute(
        """
        INSERT INTO system_state (key, value, updated_at)
        VALUES ('last_credit_reset', '1970-01-01', NOW())
        ON CONFLICT (key) DO NOTHING
        """
    )

    op.add_column(
        "users",
        sa.Column("credits_remaining", sa.Integer(), server_default="5", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("daily_credit_limit", sa.Integer(), server_default="5", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "credits_reset_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.drop_constraint("fk_users_default_provider_id_provider_configs", "users", type_="foreignkey")
    op.drop_column("users", "default_provider_id")
    op.execute("DROP INDEX IF EXISTS ix_provider_configs_one_default_per_user")
    op.drop_index("ix_provider_configs_provider", table_name="provider_configs")
    op.drop_index("ix_provider_configs_user_id", table_name="provider_configs")
    op.drop_table("provider_configs")

    op.execute(
        """
        CREATE UNIQUE INDEX ix_one_active_task_per_user
        ON scrape_tasks (user_id)
        WHERE state NOT IN ('COMPLETED', 'FAILED')
        """
    )
