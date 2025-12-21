"""Create scrape_tasks table

Revision ID: 002
Revises: 001
Create Date: 2024-12-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type if it doesn't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE task_state AS ENUM (
                'PERMISSION_GRANTED',
                'SCRAPED',
                'LLM_ANALYZED',
                'OUTPUT_GENERATION',
                'FINALIZED'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create table
    op.execute("""
        CREATE TABLE scrape_tasks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            state task_state NOT NULL DEFAULT 'PERMISSION_GRANTED',
            url VARCHAR(2048) NOT NULL,
            content TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ
        );
    """)

    # Indexes
    op.execute("CREATE INDEX ix_scrape_tasks_user_id ON scrape_tasks (user_id);")
    op.execute("CREATE INDEX ix_scrape_tasks_state ON scrape_tasks (state);")

    # PARTIAL UNIQUE INDEX: At most one non-FINALIZED task per user
    op.execute("""
        CREATE UNIQUE INDEX ix_one_active_task_per_user
        ON scrape_tasks (user_id)
        WHERE state != 'FINALIZED';
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS scrape_tasks;")
    op.execute("DROP TYPE IF EXISTS task_state;")

