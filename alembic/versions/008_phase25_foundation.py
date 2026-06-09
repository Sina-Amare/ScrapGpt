"""phase 2.5 foundation: crawl scope, frontier previews, quality summary

Revision ID: 008
Revises: 007
Create Date: 2026-06-09

Adds the durable storage primitives required for Phase 2.5:

* ``extraction_specs.crawl_scope`` JSONB: user-confirmed or AI-suggested crawl
  scope (mode, status, max_pages/max_depth, include/exclude patterns,
  pagination hint, link rules, AI recommendation, user confirmation stamp).

* ``extraction_specs.quality_summary`` JSONB: per-spec extraction-quality
  metrics (overall state, field success rates, missing rates, warnings).

* ``frontier_previews`` table: pre-extraction planning artifact with
  included/excluded URL samples, estimated page count, warnings, and
  quality summary. CASCADE-deletes with the owning project and spec.

Existing rows are backfilled with the legacy-compatibility crawl scope
(matching current behavior) so old projects continue to function.

This migration is intentionally additive and non-destructive. No enum
types are added because crawl-scope mode and status are persisted in
JSONB and validated at the service/API layer.
"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CRAWL_SCOPE_VERSION = 1
LEGACY_COMPAT_CRAWL_SCOPE: dict = {
    "version": CRAWL_SCOPE_VERSION,
    "mode": "FULL_SITE",
    "status": "SYSTEM_DEFAULTED",
    "seed_url": None,
    "max_pages": 500,
    "max_depth": None,
    "include_patterns": [],
    "exclude_patterns": [],
    "pagination": {},
    "link_rules": [],
    "ai_recommendation": None,
    "user_confirmed_at": None,
}


def upgrade() -> None:
    # Add new JSONB columns to extraction_specs.
    op.add_column(
        "extraction_specs",
        sa.Column("crawl_scope", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "extraction_specs",
        sa.Column("quality_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # Backfill existing rows with the legacy-compatibility scope.
    op.execute(
        sa.text(
            "UPDATE extraction_specs SET crawl_scope = CAST(:crawl_scope AS jsonb) "
            "WHERE crawl_scope IS NULL"
        ),
        {"crawl_scope": json.dumps(LEGACY_COMPAT_CRAWL_SCOPE)},
    )

    # FrontierPreview table.
    op.create_table(
        "frontier_previews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("spec_id", sa.Integer(), nullable=False),
        sa.Column("scope_hash", sa.String(length=64), nullable=False),
        sa.Column("included_urls", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("excluded_urls", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("estimated_page_count", sa.Integer(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("quality_summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spec_id"], ["extraction_specs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_frontier_previews_project_created",
        "frontier_previews",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_frontier_previews_spec_created",
        "frontier_previews",
        ["spec_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_frontier_previews_spec_created", table_name="frontier_previews")
    op.drop_index("ix_frontier_previews_project_created", table_name="frontier_previews")
    op.drop_table("frontier_previews")
    op.drop_column("extraction_specs", "quality_summary")
    op.drop_column("extraction_specs", "crawl_scope")
