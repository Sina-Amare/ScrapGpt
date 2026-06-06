"""remove_old_enum_values

Revision ID: fe292fc905ad
Revises: 004
Create Date: 2026-06-05 15:22:26.555249

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe292fc905ad'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The partial index references the enum type — drop it before renaming so
    # PostgreSQL doesn't choke on the type operator mismatch.
    # Migration 005 is the permanent owner of this index's removal; here we
    # just drop it early enough that the rename can proceed cleanly.
    op.execute("DROP INDEX IF EXISTS ix_one_active_task_per_user")

    op.execute("ALTER TYPE task_state RENAME TO task_state_old")
    op.execute("CREATE TYPE task_state AS ENUM('PERMISSION_GRANTED', 'SCRAPING', 'SCRAPED', 'LLM_PROCESSING', 'COMPLETED', 'FAILED')")
    # Drop DEFAULT before ALTER TYPE — PostgreSQL can't cast a default that still
    # binds to task_state_old.
    op.execute("ALTER TABLE scrape_tasks ALTER COLUMN state DROP DEFAULT")
    op.execute("ALTER TABLE scrape_tasks ALTER COLUMN state TYPE task_state USING state::text::task_state")
    op.execute("ALTER TABLE scrape_tasks ALTER COLUMN state SET DEFAULT 'PERMISSION_GRANTED'")
    op.execute("DROP TYPE task_state_old")

def downgrade() -> None:
    op.execute("ALTER TYPE task_state RENAME TO task_state_new")
    op.execute("CREATE TYPE task_state AS ENUM('PERMISSION_GRANTED', 'SCRAPING', 'SCRAPED', 'LLM_PROCESSING', 'COMPLETED', 'FAILED', 'FINALIZED', 'LLM_ANALYZED', 'OUTPUT_GENERATION')")
    op.execute("ALTER TABLE scrape_tasks ALTER COLUMN state DROP DEFAULT")
    op.execute("ALTER TABLE scrape_tasks ALTER COLUMN state TYPE task_state USING state::text::task_state")
    op.execute("ALTER TABLE scrape_tasks ALTER COLUMN state SET DEFAULT 'PERMISSION_GRANTED'")
    op.execute("DROP TYPE task_state_new")
    # Restore the partial unique index (migration 005 downgrade will also recreate
    # it, but this keeps the schema consistent if you stop at this revision).
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ix_one_active_task_per_user
        ON scrape_tasks (user_id)
        WHERE state NOT IN ('COMPLETED', 'FAILED')
    """)
