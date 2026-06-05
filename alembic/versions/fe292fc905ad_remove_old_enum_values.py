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
    # Rename old enum type
    op.execute("ALTER TYPE task_state RENAME TO task_state_old")
    # Create new enum type
    op.execute("CREATE TYPE task_state AS ENUM('PERMISSION_GRANTED', 'SCRAPING', 'SCRAPED', 'LLM_PROCESSING', 'COMPLETED', 'FAILED')")
    # Alter column to use new enum type
    op.execute("ALTER TABLE scrape_tasks ALTER COLUMN state TYPE task_state USING state::text::task_state")
    # Drop old enum type
    op.execute("DROP TYPE task_state_old")

def downgrade() -> None:
    # Revert to old enum type
    op.execute("ALTER TYPE task_state RENAME TO task_state_new")
    op.execute("CREATE TYPE task_state AS ENUM('PERMISSION_GRANTED', 'SCRAPING', 'SCRAPED', 'LLM_PROCESSING', 'COMPLETED', 'FAILED', 'FINALIZED', 'LLM_ANALYZED', 'OUTPUT_GENERATION')")
    op.execute("ALTER TABLE scrape_tasks ALTER COLUMN state TYPE task_state USING state::text::task_state")
    op.execute("DROP TYPE task_state_new")
