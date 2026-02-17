"""Create system_state table for global state tracking

Revision ID: 004
Revises: 003
Create Date: 2024-12-31

This table stores singleton configuration/state values.
Used for: credit reset date tracking (multi-instance safe)
"""
from typing import Sequence, Union

from alembic import op


revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create system_state table
    op.execute("""
        CREATE TABLE IF NOT EXISTS system_state (
            key VARCHAR(50) PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Initialize with past date so first reset will run
    op.execute("""
        INSERT INTO system_state (key, value, updated_at)
        VALUES ('last_credit_reset', '1970-01-01', NOW())
        ON CONFLICT (key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS system_state")
