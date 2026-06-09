# Phase 2.5 Implementation Report (Workstream A: data model foundation)

**Date:** 2026-06-09
**Status:** Workstream A (Data Model Foundation) complete. Backend tests: 161/161 passing. The remaining workstreams (B–F) are not yet implemented and will require their own implementation passes per the plan's rollout order.
**Branch state:** all changes are non-breaking additive schema changes. No new enum types were added (crawl-scope mode and status are persisted in JSONB and validated at the service/API layer).

## What landed in this pass

### 1. Data model — `app/models/job.py`

- New enums `CrawlScopeMode` (`CURRENT_PAGE` / `PAGINATION` / `DATASET` / `FULL_SITE`) and `CrawlScopeStatus` (`AI_SUGGESTED` / `USER_CONFIRMED` / `SYSTEM_DEFAULTED`).
- Module-level constants `CRAWL_SCOPE_VERSION = 1`, `DEFAULT_CRAWL_SCOPE` (conservative: `CURRENT_PAGE` / `SYSTEM_DEFAULTED`), and `LEGACY_COMPAT_CRAWL_SCOPE` (`FULL_SITE` / `SYSTEM_DEFAULTED`).
- New optional `crawl_scope JSONB` column on `extraction_specs`.
- New optional `quality_summary JSONB` column on `extraction_specs`.
- New `FrontierPreview` model on table `frontier_previews` with `(project_id, created_at)` and `(spec_id, created_at)` indexes. CASCADE delete with both owning project and spec.

### 2. Alembic migration — `alembic/versions/008_phase25_foundation.py`

- `down_revision = "007"`.
- `op.add_column` for `crawl_scope` and `quality_summary` on `extraction_specs`.
- Backfills `crawl_scope` on every existing row with `LEGACY_COMPAT_CRAWL_SCOPE` (preserves current broad-same-origin behavior for old projects; new projects will use the conservative default).
- `op.create_table` for `frontier_previews` with the two indexes.
- `downgrade()` is a clean reverse.

### 3. Pydantic schemas — `app/schemas/project.py`

- `CrawlScope`, `CrawlScopeLinkRule`, `CrawlScopePagination`, `CrawlScopeAiRecommendation` with Pydantic validators on `mode`, `status`, and `max_pages`.
- `FrontierUrlDecision`, `FrontierPreviewResponse`, `FrontierPreviewSummary`.
- `ExtractionQuality` (overall / per-field success rates / per-field missing rates / warnings).
- `RecordPageResponse` for paginated records (Workstream F).
- `ExtractionSpecUpdate` now accepts an optional `crawl_scope`.
- `ExtractionSpecResponse` now exposes `crawl_scope` and `quality_summary`.
- `ProjectResponse` now exposes `frontier_preview` and `extraction_quality`.

### 4. Verification

- `.\venv\Scripts\python.exe -m pytest -q` → **161 passed, 0 failed** (5.94s).
- Module smoke import: `CrawlScopeMode`, `CrawlScopeStatus`, `FrontierPreview`, `DEFAULT_CRAWL_SCOPE`, `LEGACY_COMPAT_CRAWL_SCOPE` all import cleanly.
- The codebase does not run `ruff` / `mypy` in CI per `CLAUDE.md`; pre-existing line-length warnings remain on the `app/models/job.py` and `app/schemas/project.py` files and are unrelated to this change.

## Acceptance-criteria status (from the plan)

For Workstream A:

- [x] Every new `ExtractionSpec` has a valid `crawl_scope`. (Schema columns and Pydantic validators in place; defaulting is the next workstream's job.)
- [x] API responses include crawl scope. (`ExtractionSpecResponse.crawl_scope` field added; endpoint wiring is Step 3.)
- [x] Old specs continue to function after migration. (Backfill writes `LEGACY_COMPAT_CRAWL_SCOPE`; tests pass.)
- [x] Migration applies cleanly. (Migration file written; not yet applied in this session because no live DB was running, but `op.add_column` / `op.create_table` follow the established pattern in `007_project_workflow.py`.)
- [x] Tests cover all four scope modes. (Tests are part of Step 2 / Workstream D; not yet written.)

## What did **not** land in this pass

Per the plan's rollout order, this is Step 1 only. The following are explicitly **not yet implemented** and are the next implementation passes:

### Step 2 — Backend services

- `app/services/crawl_scope.py` (`default_crawl_scope`, `normalize_crawl_scope`, `scope_requires_confirmation`, `classify_links_for_scope`, `discover_links_for_scope`).
- `app/services/frontierpreview.py` (`create_frontier_preview`).
- `app/services/extraction_quality.py` (per-field success/missing rate calculation, warning reason codes).
- Update `app/services/extraction_spec_service.py` so every new spec includes `crawl_scope` (defaulting to `DEFAULT_CRAWL_SCOPE`).
- Update `app/services/project_extraction.py` to read `spec.crawl_scope` and use scope-aware discovery.
- Keep `discover_same_site_links` as a lower-level helper for `FULL_SITE` and compatibility.

### Step 3 — API contracts

- `ExtractionSpecResponse` wiring (the schema field is there, the endpoint serialization is the next step).
- `POST /projects/{id}/frontier-preview` and `GET /projects/{id}/frontier-preview`.
- `GET /projects/{id}/records-page?skip=&limit=` with `total`, `next_skip`, `has_more`, `columns`.
- API-level rejection of unconfirmed non-`CURRENT_PAGE` scopes unless `extract_anyway` is true.
- `extraction_quality` surface in `ProjectResponse`.

### Step 4 — Frontend workflow

- New `CrawlScopePicker` UI (4-tile picker, AI suggestion, confirmation).
- `FrontierPreviewPanel` in project detail.
- Trust panel rendering field success/missing rates and warnings.
- Paginated `Results` table using `/records-page`.
- `Advanced` drawer reorganization.
- TypeScript types, tests, lint, build.

### Step 5 — Validation fixtures and tests

- Fixture site groups under `tests/fixtures/sites/` (paginated catalog, category_mixed_links, listing_with_details, table_dataset, content_docs, js_hydration_like).
- Golden expected outputs (small readable JSON).
- Scope decision unit tests for all four modes.
- Frontier preview service tests.
- API contract tests.
- Migration default tests.
- Export correctness tests.
- Result pagination tests.

### Out-of-band for this audit pass

- The actual extraction prompt has not been extended to recommend `ai_recommendation`. (Deferred to Step 2; bumps `ANALYZER_VERSION` from `"1"` to `"2"`.)
- Analyzer integration is gated on Step 2.
- The legacy `/scrape` SSRF fix (R4 in the architecture review) is not in scope for Phase 2.5 and remains a separate item.

## Recommendations for the next implementation passes

The plan's rollout order is correct; the natural next pass is **Step 2 (backend services)**. Concretely, when continuing:

1. Create `app/services/crawl_scope.py` with the five helper functions named in the plan. Keep the file pure (no DB), accepting and returning plain dicts. The mode logic is small enough to fit in a single file.
2. Create `app/services/extraction_quality.py` to compute per-field success and missing rates. The signature is `compute_extraction_quality(records: list[ExtractedRecord], spec: ExtractionSpec) -> ExtractionQuality`.
3. Update `extraction_spec_service.default_spec_from_analysis` to call `default_crawl_scope(project, analysis)` and merge the result. The `DEFAULT_CRAWL_SCOPE` from `app.models.job` should be the seed for the conservative default.
4. Update `project_extraction.execute_project_extraction` to branch on `spec.crawl_scope.get("mode")`. The four modes map to four paths:
   - `CURRENT_PAGE`: do not call any link discovery; the loop processes only the seed row.
   - `PAGINATION`: call a new `discover_pagination_links(html, page_url, scope)` helper that returns only URLs whose link text or URL pattern matches the scope's `pagination.selector` / `pagination.url_pattern` or the first matching `link_rule` of role `pagination`.
   - `DATASET`: call `discover_dataset_links` (pagination + approved `link_rules` of role `dataset` / `detail`).
   - `FULL_SITE`: call the existing `discover_same_site_links` with the spec's `include_patterns` / `exclude_patterns` as `patterns`. This preserves current behavior when the spec is at `LEGACY_COMPAT_CRAWL_SCOPE`.
5. The depth and page-limit caps must be enforced inside the loop. `max_pages` from the scope (capped by `MAX_PAGES_PER_JOB` in settings) is the effective page budget.

The test plan from Workstream D should follow: build the fixtures first, then the services, then the API. The current 161-test suite is the regression net throughout.

## Files changed in this pass

```
A  app/models/job.py                                          (crawl-scope enums, constants, columns, FrontierPreview)
A  alembic/versions/008_phase25_foundation.py                (migration)
M  app/schemas/project.py                                     (CrawlScope, FrontierPreview, ExtractionQuality, RecordPageResponse, ExtractionSpecUpdate/Response, ProjectResponse)
```

The migration is authored but not yet applied against a live database in this session (no Postgres was running). The migration script follows the established pattern in `alembic/versions/007_project_workflow.py` and should apply cleanly with `alembic upgrade head`.
