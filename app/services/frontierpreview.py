"""Frontier preview service (Workstream B, behavior layer).

Generates a pre-extraction preview of the crawl frontier. The preview
reuses the same scope-aware classifier as ``crawl_scope`` so preview
and extraction agree on what is included and excluded.

v1 is bounded: it samples the seed page only and uses the same
heuristic link discovery the executor uses. Multi-page sampling and
LLM-assisted link classification are deferred.

The preview row counts are stored as small samples (default 100 each)
so the row never grows unbounded. The estimated page count is the
``spec.crawl_scope.max_pages`` clamped to ``MAX_PAGES_PER_JOB``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import FrontierPreview, Project
from app.services.crawl_scope import (
    REASON_EXCLUDED_SCOPE_MODE,
    classify_links_for_scope,
    discover_links_for_scope,
    scope_max_pages,
)
from app.services.extraction_spec_service import latest_spec
from app.services.fetcher import fetch_url
from app.services.url_normalizer import normalize_url
from app.services.url_validator import URLValidationError, validate_url

DEFAULT_SAMPLE_LIMIT = 100


async def create_frontier_preview(
    db: AsyncSession,
    project: Project,
    *,
    max_urls: int = DEFAULT_SAMPLE_LIMIT,
) -> FrontierPreview | None:
    """Generate a frontier preview for the project's current spec.

    Returns the persisted ``FrontierPreview`` row, or None if the project
    has no spec yet or the seed URL cannot be fetched safely.
    """
    spec = await latest_spec(db, project.id)
    if spec is None:
        return None

    scope = spec.crawl_scope or {}
    seed = project.normalized_url or project.url
    if not seed:
        return None
    try:
        seed_validated = validate_url(seed)
    except URLValidationError:
        return None

    # Fetch the seed page using the project's render mode. We do not
    # call the provider for link classification in v1; heuristics only.
    try:
        fetch = await fetch_url(seed_validated, project.render_mode.value)
    except Exception:
        fetch = None

    html = fetch.html if fetch is not None else ""
    if not html:
        return FrontierPreview(
            project_id=project.id,
            spec_id=spec.id,
            scope_hash=_scope_hash(scope),
            included_urls=[],
            excluded_urls=[],
            estimated_page_count=scope_max_pages(scope),
            warnings=[
                {
                    "code": "SEED_FETCH_FAILED",
                    "message": "Could not fetch the seed URL; preview is empty.",
                }
            ],
            quality_summary={
                "included_count": 0,
                "excluded_count": 0,
                "unrelated_same_origin_count": 0,
                "source": "seed_page_frontier_preview",
            },
        )

    decisions = classify_links_for_scope(
        html,
        page_url=seed_validated,
        root_url=seed_validated,
        scope=scope,
        analysis=project.analysis if isinstance(project.analysis, dict) else None,
    )

    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    unrelated_count = 0
    for d in decisions:
        if d.decision == "included":
            if len(included) < max_urls:
                included.append(d.to_dict())
        else:
            if d.reason_code == "EXCLUDED_DIFFERENT_ORIGIN":
                unrelated_count += 1
            if len(excluded) < max_urls:
                excluded.append(d.to_dict())

    warnings: list[dict[str, Any]] = []
    if unrelated_count >= 10:
        warnings.append(
            {
                "code": "FRONTIER_HAS_MANY_EXCLUSIONS",
                "count": unrelated_count,
                "message": (
                    f"{unrelated_count} same-origin links were excluded by the current scope."
                ),
            }
        )

    # Always also persist the seed decision so downstream UIs can render it.
    seed_decision = {
        "url": seed,
        "normalized_url": normalize_url(seed),
        "source_url": None,
        "depth": 0,
        "decision": "included",
        "role": "seed",
        "reason_code": "SEED_URL",
        "reason": "Seed URL.",
        "confidence": None,
        "link_text": None,
    }
    if not included:
        included.append(seed_decision)
    elif included[0].get("normalized_url") != seed_decision["normalized_url"]:
        included.insert(0, seed_decision)

    return FrontierPreview(
        project_id=project.id,
        spec_id=spec.id,
        scope_hash=_scope_hash(scope),
        included_urls=included,
        excluded_urls=excluded,
        estimated_page_count=scope_max_pages(scope),
        warnings=warnings,
        quality_summary={
            "included_count": len(included),
            "excluded_count": len(excluded),
            "unrelated_same_origin_count": unrelated_count,
            "source": "seed_page_frontier_preview",
        },
    )


async def latest_frontier_preview(db: AsyncSession, project_id: int) -> FrontierPreview | None:
    result = await db.execute(
        select(FrontierPreview)
        .where(FrontierPreview.project_id == project_id)
        .order_by(FrontierPreview.created_at.desc(), FrontierPreview.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _scope_hash(scope: dict[str, Any]) -> str:
    payload = json.dumps(scope, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "DEFAULT_SAMPLE_LIMIT",
    "create_frontier_preview",
    "latest_frontier_preview",
]
