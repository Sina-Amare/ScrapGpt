"""password_reset: add password_reset_codes table and users.password_changed_at

Revision ID: 010_password_reset
Revises: dcbda4fc8a19
Create Date: 2026-06-12

Adds support for the forgot-password flow:

* ``password_reset_codes`` — one row per issued 6-digit code. Only a hash of
  the code is stored. A code expires (``expires_at``), is single-use
  (``consumed_at``), and is attempt-capped (``attempt_count``). Rows cascade
  with the owning user.
* ``users.password_changed_at`` — set when the password changes; tokens issued
  before this instant are rejected, so a reset invalidates existing sessions.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "010_password_reset"
down_revision: Union[str, None] = "dcbda4fc8a19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "password_changed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "When the password was last changed (e.g. via reset). Access/"
                "refresh tokens issued before this instant are rejected."
            ),
        ),
    )

    op.create_table(
        "password_reset_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_password_reset_codes_user_id",
        "password_reset_codes",
        ["user_id"],
    )
    op.create_index(
        "ix_password_reset_codes_expires_at",
        "password_reset_codes",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_password_reset_codes_expires_at", "password_reset_codes")
    op.drop_index("ix_password_reset_codes_user_id", "password_reset_codes")
    op.drop_table("password_reset_codes")
    op.drop_column("users", "password_changed_at")
