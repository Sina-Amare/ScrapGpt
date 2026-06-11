"""analysis_cache_ttl: add expires_at column

Revision ID: 009
Revises: 008
Create Date: 2026-06-11

Adds an ``expires_at`` column to the ``analysis_cache`` table.
When ANALYSIS_CACHE_TTL_DAYS > 0, cache entries are written with an
expiry timestamp. The watchdog purges expired entries on each sweep.
Setting ANALYSIS_CACHE_TTL_DAYS=0 preserves the old behavior (no expiry).

Existing rows get NULL expires_at, which means "no expiry" — they
continue to work indefinitely until the watchdog is configured with
a positive TTL.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'analysis_cache',
        sa.Column(
            'expires_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                'When this cache entry expires. Null = no expiry. '
                'Purged by the watchdog when past now().'
            ),
        ),
    )
    op.create_index(
        'ix_analysis_cache_expires_at',
        'analysis_cache',
        ['expires_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_analysis_cache_expires_at')
    op.drop_column('analysis_cache', 'expires_at')