# Phase 2.5 Implementation Plan

Date: June 9, 2026

Goal: before the next major feature phase, strengthen user intent capture, crawl scope correctness, extraction trust, validation coverage, and UX clarity.

This plan assumes the prior codebase, product, validation, and Advanced Settings reviews are approved. It is implementation-focused and optimized for correctness, trust, user intent, validation, and long-term architecture quality.

## Summary

Phase 2.5 should not add broad new scraping features. It should make the existing extraction workflow safer and more trustworthy.

The target product flow is:

`URL -> Understand Data -> Choose Fields -> Preview -> Extract -> Results`

Primary changes:

- Add first-class crawl scope to `ExtractionSpec`.
- Add a frontier preview before extraction can crawl beyond the seed page.
- Simplify Advanced Settings so user goals lead and system controls move to the right context.
- Add automated validation for crawl scope, extraction quality, preview correctness, and exports.
- Add first-layer trust signals: field success rates, missing rates, warnings, and quality summaries.
- Make result browsing work for 1,000 to 100,000+ records without loading everything into the browser.

## Implementation Principles

- User intent is part of the extraction contract. It must be stored, reviewed, and respected by the crawler.
- Page limit is a safety budget, not crawl scope.
- AI can recommend scope, but users confirm scope before broad extraction.
- Preview must validate both fields and frontier.
- Existing `/projects` workflow remains primary.
- Existing `/jobs` compatibility routes should not drive new UX decisions.
- Maintain backward compatibility where reasonable. Migrations should default old specs to conservative scope.

## New Core Concepts

### Crawl Scope

Add a typed crawl scope object stored on `ExtractionSpec`.

Recommended internal shape:

```json
{
  "version": 1,
  "mode": "CURRENT_PAGE",
  "status": "AI_SUGGESTED",
  "seed_url": "https://example.com/products",
  "max_pages": 500,
  "max_depth": 0,
  "include_patterns": [],
  "exclude_patterns": [],
  "pagination": {
    "selector": null,
    "url_pattern": null,
    "estimated_pages": null
  },
  "link_rules": [
    {
      "role": "pagination",
      "action": "include",
      "selector": "a.next",
      "pattern": null,
      "reason": "Detected next-page control",
      "confidence": 0.82
    }
  ],
  "ai_recommendation": {
    "recommended_mode": "PAGINATION",
    "confidence": 0.78,
    "warnings": [],
    "evidence": []
  },
  "user_confirmed_at": null
}
```

Allowed modes:

- `CURRENT_PAGE`: seed URL only.
- `PAGINATION`: seed URL plus pagination chain only.
- `DATASET`: pagination plus approved dataset/detail/related URLs.
- `FULL_SITE`: broad same-origin exploration with explicit depth and page limits.

Allowed status values:

- `AI_SUGGESTED`
- `USER_CONFIRMED`
- `SYSTEM_DEFAULTED`

### Frontier Preview

Add a preview of the crawl frontier before extraction. It should show included URLs, excluded URLs, reasons, and estimated page count.

Recommended URL decision shape:

```json
{
  "url": "https://example.com/products?page=2",
  "normalized_url": "https://example.com/products?page=2",
  "source_url": "https://example.com/products",
  "depth": 1,
  "decision": "included",
  "role": "pagination",
  "reason_code": "PAGINATION_SELECTOR_MATCH",
  "reason": "Matched detected pagination selector",
  "confidence": 0.84,
  "link_text": "Next"
}
```

## Workstream A - Crawl Scope

### Rationale

The crawler currently treats same-origin links as valid crawl candidates. That is technically safe but product-incorrect for many datasets. Users mean "this page", "this list", "this dataset", or "this site", not "any same-origin URL".

### Architecture Impact

- `ExtractionSpec` becomes the durable contract for both what to extract and where to extract it.
- Crawl discovery changes from same-origin BFS by default to scope-aware frontier generation.
- AI analysis gains optional scope recommendation output.
- User confirmation becomes part of extraction readiness for any mode beyond `CURRENT_PAGE`.
- Existing `url_patterns` remains as a compatibility/developer escape hatch but is no longer the main product model.

### Backend Changes

- Add a new service module, recommended name: `app/services/crawl_scope.py`.
- Add typed Pydantic schemas for crawl scope in `app/schemas/project.py`.
- Add helper functions:
  - `default_crawl_scope(project, analysis)`.
  - `normalize_crawl_scope(scope, seed_url, page_limit)`.
  - `scope_requires_confirmation(scope)`.
  - `classify_links_for_scope(html, page_url, root_url, scope, analysis)`.
  - `discover_links_for_scope(html, page_url, root_url, scope, limit)`.
- Update `default_spec_from_analysis()` so every new spec includes `crawl_scope`.
- Update `start_project_extraction()` and `execute_project_extraction()` to read `spec.crawl_scope`.
- Replace direct use of `discover_same_site_links()` in project extraction with scope-aware discovery.
- Keep `discover_same_site_links()` as a lower-level helper for `FULL_SITE` and compatibility tests.
- Extend analyzer structured output with optional `scope_recommendation`.
- Increment `ANALYZER_VERSION` when the prompt/schema changes.
- Add fallback behavior for old cached analysis without scope recommendations.

### Frontend Changes

- Add a crawl scope step inside the project workspace between analysis and extraction.
- User-facing labels:
  - "This page only"
  - "This list across pages"
  - "This dataset, including related/detail pages"
  - "The whole site"
- Show AI recommendation as suggestion, not as final decision.
- Require explicit confirmation for `PAGINATION`, `DATASET`, and `FULL_SITE`.
- Show stronger warning for `FULL_SITE`.
- Hide raw URL glob editing from default users.
- Advanced/developer view may show generated include/exclude patterns.

### Database Changes

- Add `crawl_scope JSONB NOT NULL` to `extraction_specs`.
- Default existing rows to:

```json
{
  "version": 1,
  "mode": "FULL_SITE",
  "status": "SYSTEM_DEFAULTED",
  "max_pages": 500,
  "max_depth": null,
  "include_patterns": [],
  "exclude_patterns": [],
  "pagination": {},
  "link_rules": [],
  "ai_recommendation": null,
  "user_confirmed_at": null
}
```

Reason for old rows: this preserves current behavior for existing projects. For new projects, default should be conservative: `CURRENT_PAGE` or AI-suggested `PAGINATION` with user confirmation.

### API Changes

- Extend `ExtractionSpecResponse` with `crawl_scope`.
- Extend `ExtractionSpecUpdate` with `crawl_scope`.
- Add validation that only known modes/status values are accepted.
- Do not expose raw enum names as frontend labels.
- Keep `url_patterns` in API for backward compatibility but treat it as advanced.

Recommended update payload:

```json
{
  "crawl_scope": {
    "mode": "PAGINATION",
    "status": "USER_CONFIRMED",
    "max_pages": 25,
    "pagination": {
      "selector": "a.next",
      "estimated_pages": 12
    }
  }
}
```

### Migration Requirements

- Add Alembic migration for `extraction_specs.crawl_scope`.
- Backfill existing specs with compatibility scope.
- Ensure downgrade removes column.
- No destructive data migration.
- Add schema validation at API/service layer, not only frontend.

### Scope Mode Behavior

| Mode | Crawl behavior | Confirmation | Default depth | Link discovery |
|---|---|---:|---:|---|
| `CURRENT_PAGE` | Seed URL only | Not required | 0 | No links inserted |
| `PAGINATION` | Seed plus pagination chain | Required if AI suggested | Pagination chain only | Include only pagination selector/rule matches |
| `DATASET` | Seed, pagination, approved dataset/detail URLs | Required | 1 initially | Include approved roles/patterns only |
| `FULL_SITE` | Broad same-origin crawl | Required | Configurable, default 2 for new specs | Same-origin with include/exclude and page limit |

### AI Recommendations

- Extend prompt so AI returns:
  - recommended scope mode
  - confidence
  - pagination selector candidate
  - detail link selector candidate
  - risky unrelated link examples
  - warnings
- Treat AI output as advisory.
- If AI confidence is low or unrelated same-origin links are detected, default to `CURRENT_PAGE` and ask user to choose.
- Do not allow AI to silently choose `FULL_SITE`.

### Crawl Frontier Generation

- Create a common `UrlDecision` data structure used by frontier preview and extraction.
- For extraction, only insert URLs with `decision="included"`.
- Preserve reason codes for audit/debugging.
- Enforce final URL safety with existing URL validator and robots checks.
- Continue deduplication by normalized URL.

Reason codes:

- `SEED_URL`
- `CURRENT_PAGE_SCOPE`
- `PAGINATION_SELECTOR_MATCH`
- `PAGINATION_PATTERN_MATCH`
- `DATASET_PATTERN_MATCH`
- `DETAIL_LINK_SELECTOR_MATCH`
- `FULL_SITE_SAME_ORIGIN`
- `EXCLUDED_DIFFERENT_ORIGIN`
- `EXCLUDED_SCOPE_MODE`
- `EXCLUDED_PATTERN`
- `EXCLUDED_NAVIGATION`
- `EXCLUDED_PAGE_LIMIT`
- `EXCLUDED_DEPTH_LIMIT`
- `EXCLUDED_INVALID_URL`

### Testing Requirements

- Unit tests for default scope creation.
- Unit tests for scope validation.
- Unit tests for each scope mode using local HTML fixtures.
- Regression test for current same-origin behavior moved behind `FULL_SITE`.
- API tests for updating scope.
- API tests that extraction rejects unconfirmed non-current-page scopes, unless `extract_anyway` is explicitly allowed for current compatibility.
- Migration test or model-level assertion that existing specs get a valid default.
- Analyzer tests for optional `scope_recommendation`.

### Acceptance Criteria

- Every new `ExtractionSpec` has a valid `crawl_scope`.
- `CURRENT_PAGE` extraction inserts no discovered links.
- `PAGINATION` extraction does not include unrelated same-origin category links.
- `DATASET` extraction includes only approved dataset/detail rules.
- `FULL_SITE` preserves current broad crawl behavior but requires explicit user confirmation in the project UI.
- API responses include crawl scope.
- Old specs continue to function after migration.
- Tests cover all four scope modes.

### Rollout Order

1. Add schemas and DB migration.
2. Add scope defaults and compatibility backfill.
3. Add scope-aware discovery service.
4. Update project extraction to use scope-aware discovery.
5. Extend analyzer output with optional recommendation.
6. Add API update/response support.
7. Add frontend scope confirmation UI.
8. Add tests and fixtures.

### Risks

- Too much schema complexity in the first version.
- AI scope recommendation may be unreliable.
- Existing projects could behave differently if backfill is not compatibility-safe.
- Users may misunderstand `DATASET` without frontier preview.

### Dependencies

- Existing `ExtractionSpec`.
- Existing URL validator, normalizer, robots service, fetcher, analyzer, and project extraction services.
- Workstream B for user-visible frontier review.
- Workstream D for fixture coverage.

## Workstream B - Frontier Preview

### Rationale

The user should see what ScrapGPT intends to crawl before extraction. This prevents wrong-dataset extraction, especially when same-domain links point to unrelated categories.

### Architecture Impact

- Add a pre-extraction planning step separate from selector preview.
- Reuse the same scope-aware frontier logic for preview and extraction.
- Store frontier preview evidence so users can refresh/navigate without losing context.
- Extraction should prefer a confirmed scope and recent preview but should not require the exact preview rows to be treated as a crawl queue.

### Backend Changes

- Add service module, recommended name: `app/services/frontier_preview.py`.
- Add table/model `FrontierPreview`.
- Add function:
  - `create_frontier_preview(db, project, spec, max_urls=100)`.
- Fetch seed page using existing fetcher and render mode.
- Use scope-aware link classification from Workstream A.
- Return included and excluded URL samples with reasons.
- Estimate page count from:
  - explicit pagination estimate from AI if available
  - observed pagination links
  - page limit
  - mode defaults
- Keep v1 bounded to seed-page link analysis and optional pagination first step. Do not crawl hundreds of pages just to preview.

### Frontend Changes

- Add a "Scope preview" or "Pages to visit" panel before Extract.
- Show:
  - selected scope mode
  - estimated pages
  - included URL samples
  - excluded URL samples
  - reason labels
  - warning if unrelated same-origin links were excluded
- Add "Confirm scope" action.
- Disable broad extraction until scope is confirmed or user explicitly chooses current page only.
- Keep selector preview as "Data preview"; do not mix with frontier preview.

### Database Changes

Add `frontier_previews` table:

- `id`
- `project_id`
- `spec_id`
- `scope_hash`
- `included_urls JSONB NOT NULL`
- `excluded_urls JSONB NOT NULL`
- `estimated_page_count INTEGER NULL`
- `warnings JSONB NOT NULL DEFAULT []`
- `quality_summary JSONB NOT NULL DEFAULT {}`
- `created_at`

Indexes:

- `(project_id, created_at DESC)`
- `(spec_id, created_at DESC)`

### API Changes

Add endpoints:

- `POST /projects/{id}/frontier-preview`
- `GET /projects/{id}/frontier-preview`

Response shape:

```json
{
  "id": 1,
  "project_id": 10,
  "spec_id": 22,
  "scope_hash": "abc123",
  "estimated_page_count": 12,
  "included_urls": [],
  "excluded_urls": [],
  "warnings": [],
  "quality_summary": {
    "included_count": 8,
    "excluded_count": 24,
    "unrelated_same_origin_count": 12,
    "source": "seed_page_frontier_preview"
  }
}
```

Extend `ProjectResponse` with latest `frontier_preview`.

### Migration Requirements

- Add Alembic migration for `frontier_previews`.
- No backfill required.
- Cascade delete with project/spec deletion.

### Performance Considerations

- Limit stored included/excluded samples to configurable counts, default 100 each.
- Do not recursively crawl in v1 preview.
- Store counts and warnings separately from samples.
- Use normalized URLs for dedupe.
- Avoid provider calls in frontier preview unless analysis is missing and user explicitly re-analyzes.

### Future Extensibility

- Multi-page frontier sampling.
- Sitemap-assisted estimates.
- Link clustering.
- Template fingerprinting.
- Per-link visual region labels.
- Provider-assisted link-role classification.

### Testing Requirements

- Service tests for included/excluded decisions.
- API tests for preview creation and retrieval.
- UI tests for rendering included/excluded samples.
- Tests that unrelated same-origin category links appear as excluded under `PAGINATION`.
- Tests that `FULL_SITE` includes same-origin links but warns.
- Tests that preview is invalidated or regenerated when scope changes.

### Acceptance Criteria

- User can preview URLs before extraction.
- Preview shows both included and excluded samples.
- Every URL sample has a human-readable reason.
- Estimated page count is shown when available.
- Extraction UI surfaces warnings when many links are excluded due to scope.
- Scope confirmation is visible before broad extraction.

### Rollout Order

1. Add `FrontierPreview` model and migration.
2. Add frontier preview service using Workstream A decisions.
3. Add API endpoints.
4. Add frontend panel.
5. Add confirmation gating.
6. Add tests.

### Risks

- Users may over-trust estimates.
- Preview may be slow on very large seed pages.
- Excluded URL list may overwhelm users if not summarized.

### Dependencies

- Workstream A scope-aware decisions.
- Existing fetcher/render mode.
- Existing project workspace.

## Workstream C - Advanced Settings Simplification

### Rationale

The current Advanced Settings mix user goals with implementation details. The next phase should simplify the product workflow and move controls to the point where users understand why they matter.

### Architecture Impact

- The primary `/projects` workflow becomes intent-first.
- Advanced controls remain available but are contextual.
- The route structure can stay mostly stable. The main change is information architecture inside pages.
- Backend compatibility remains unchanged except for new scope/frontier fields.

### Control Decisions

| Control | Decision | Future location | Reason |
|---|---|---|---|
| Data type | Keep, move, rename | Understand Data | It is a user goal, not an advanced setting |
| Page rendering | Infer automatically, hide by default | Troubleshooting/developer details | It is an implementation strategy |
| AI provider | Keep as secondary override | Provider settings plus compact project override | BYOK matters, but not as first-step data intent |
| `workflow_mode` | Hide from primary UX | Developer/automation only | "Fast" and "Guided" are workflow internals |
| Page limit | Keep, reframe | Extract | It is a safety budget, not scope |
| Export format | Move | Results | It is output selection, not extraction setup |
| Raw JSON advanced panel | Keep, rename | Developer details | Useful for debugging, not normal workflow |
| `url_patterns` | Hide from default users | Developer scope rules | Too technical for primary scope UX |

### Backend Changes

- Keep accepting existing advanced fields for backward compatibility.
- Add API support for new `crawl_scope` and frontier preview.
- Do not remove `workflow_mode` yet.
- Optionally add response hints for UI:
  - `recommended_extraction_goal`
  - `scope_confirmation_required`
  - `developer_details_available`

### Frontend Changes

Restructure project flow:

1. URL
   - URL input.
   - Optional goal picker using user language:
     - "Rows in a table"
     - "Knowledge/content pages"
   - No render mode shown by default.
   - No provider dropdown shown by default unless user opens "Use a different AI provider".

2. Understand Data
   - Show detected page type, suggested data goal, suggested scope, confidence, and warnings.
   - Let user change goal and scope.

3. Choose Fields
   - Existing field editor remains.
   - Keep selector internals hidden unless developer mode is enabled.

4. Preview
   - Split into:
     - Data preview
     - Frontier preview

5. Extract
   - Show confirmed scope, estimated pages, safety limit, and warnings.
   - Rename Page limit to "Safety limit" or "Maximum pages to visit".

6. Results
   - Show table.
   - Let user choose CSV/JSON/XLSX at export time.

### Route Changes

- Keep existing routes:
  - `/projects`
  - `/projects/new`
  - `/projects/:id`
- Do not add new top-level routes for Phase 2.5 unless frontend complexity requires it.
- Use sections/tabs/anchors inside Project Detail.
- De-emphasize `/jobs` in navigation if still visible.

### Database Changes

- No DB changes solely for Advanced Settings simplification.
- DB changes come from Workstream A and B.

### API Changes

- Keep `ProjectAdvancedOptions` backward compatible.
- Add user-goal oriented fields only if needed:
  - `extraction_goal` can map to `extraction_mode`, but do not add both if it creates duplication.
- Recommended v1: keep `extraction_mode` in API, change only frontend language.

### Migration Requirements

- No migration for UI simplification alone.
- If future `extraction_goal` is introduced as a DB field, add separate migration later. Not required for Phase 2.5.

### Testing Requirements

- Frontend tests for New Project default path.
- Frontend tests that render mode is not visible by default.
- Frontend tests that provider override is secondary.
- Frontend tests for scope confirmation UI.
- API compatibility tests proving old advanced payloads still work.
- Manual UX review for non-technical comprehension.

### Acceptance Criteria

- New Project first screen no longer leads with implementation controls.
- Data type is presented as user goal or inferred recommendation.
- Page rendering is not a default decision.
- Provider choice is available but secondary.
- Export format is chosen in Results, not required before Extract.
- Developer details remain available.
- `/projects` workflow matches `URL -> Understand Data -> Choose Fields -> Preview -> Extract -> Results`.

### Rollout Order

1. Add scope API/data model first.
2. Add frontier preview.
3. Rework New Project advanced drawer.
4. Rework Project Detail sections.
5. Move export selection emphasis to Results.
6. Rename raw advanced panel to Developer details.
7. Update tests.

### Risks

- Existing technical users may miss controls if hidden too deeply.
- Changing labels may confuse returning users.
- UI can become longer if scope preview and data preview are not visually organized.

### Dependencies

- Workstream A for scope model.
- Workstream B for frontier preview.
- Workstream E for trust signal display.

## Workstream D - Validation Infrastructure

### Rationale

Phase 2.5 changes must be validated with deterministic fixtures before real users or providers are involved. The project needs repeatable tests for scope correctness, extraction accuracy, selector quality, preview correctness, and export correctness.

### Architecture Impact

- Add fixture websites and golden expected outputs.
- Add benchmark-style tests that can run locally without real providers.
- Separate agent-executable validation, automated CI validation, human validation, and provider validation.

### Backend Changes

- Add fixture HTML pages under a test fixture directory.
- Add helper functions for loading fixture pages.
- Add optional local fixture server for integration tests.
- Add tests for:
  - crawl scope decisions
  - frontier preview decisions
  - selector extraction accuracy
  - exports
  - quality summaries

Recommended fixture site groups:

- `fixtures/sites/paginated_catalog`
- `fixtures/sites/category_mixed_links`
- `fixtures/sites/listing_with_details`
- `fixtures/sites/table_dataset`
- `fixtures/sites/content_docs`
- `fixtures/sites/js_hydration_like`

### Frontend Changes

- Add UI tests for:
  - scope mode selector
  - frontier preview panel
  - trust summary panel
  - paginated/virtualized results
  - export controls in Results

### Database Changes

- None for validation infrastructure itself.
- Tests should cover migrations from Workstreams A, B, E, and F.

### API Changes

- None solely for validation infrastructure.
- Tests should cover new APIs:
  - scope update
  - frontier preview
  - paginated records

### Migration Requirements

- Add migration tests or at least migration smoke checks in CI if current project test setup supports it.
- Confirm old specs receive valid `crawl_scope`.
- Confirm new tables can be inserted/read/deleted.

### Golden Datasets

Create golden expected outputs:

- Expected discovered URLs by scope mode.
- Expected included/excluded frontier previews.
- Expected extracted records.
- Expected missing field rates.
- Expected export rows for CSV/JSON/XLSX.
- Expected quality summaries.

Golden output files should be small, readable JSON files.

### Benchmark Methodology

For each fixture site:

1. Build default spec.
2. Apply known scope mode.
3. Generate frontier preview.
4. Run extraction.
5. Compare records to golden output.
6. Compare quality summary to expected thresholds.
7. Export and validate output shape.

Metrics:

- URL precision: included URLs that belong to intended dataset.
- URL recall: intended URLs included.
- Field success rate.
- Missing required field rate.
- Record count accuracy.
- Export row count and columns.
- Warning correctness.

### CI Integration

Add or document CI commands:

```powershell
venv\Scripts\python.exe -m pytest -q
cd frontend
npm.cmd test
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

In non-Windows CI, use native npm command equivalents.

### Agent-Executable Validation

The agent can execute these immediately after implementation:

- Run backend tests.
- Run frontend tests.
- Run typecheck/lint/build.
- Start local backend if configured.
- Make HTTP requests to local API.
- Inspect test database rows.
- Compare fixture outputs.

Agent validation should collect:

- command output
- pass/fail counts
- generated frontier preview JSON
- database row counts
- export file row counts
- screenshots only if frontend visual validation is needed

### Automated Validation

Must become part of the test suite:

- Scope decision unit tests.
- Frontier preview service tests.
- API contract tests.
- Extraction golden tests.
- Export correctness tests.
- Result pagination tests.
- Migration default tests.

### Human Validation

Requires human review:

- Do users understand scope choices?
- Do users understand "Safety limit"?
- Do users know why URLs were excluded?
- Does the new flow feel simpler than current Advanced Settings?
- Are warnings clear without CSS/crawler knowledge?

### Provider Validation

Requires real provider credentials:

- AI scope recommendation quality.
- AI field suggestion quality with new prompt.
- Provider variance across Gemini/OpenAI/Anthropic/OpenRouter/local models.
- Cost/latency of richer prompts.
- Robustness of structured output with `scope_recommendation`.

### Testing Requirements

- Keep full current suite passing.
- Add fixture tests in small increments.
- Ensure fixture tests do not require network.
- Ensure provider tests are marked optional and skipped unless credentials are present.

### Acceptance Criteria

- New scope behavior is covered by deterministic tests.
- Frontier preview has golden tests.
- Export correctness is covered for CSV, JSON, and XLSX.
- Large result browsing has API and frontend tests.
- Provider-backed tests are optional and documented.
- Human validation checklist exists for UX review.

### Rollout Order

1. Add fixture loader and first fixture site.
2. Add scope golden tests.
3. Add frontier preview tests.
4. Add extraction/export golden tests.
5. Add frontend UI tests.
6. Add optional provider benchmark scripts/tests.
7. Document agent validation commands.

### Risks

- Golden datasets can become brittle if selectors intentionally change.
- Large fixture sets can slow local tests.
- Provider tests can become flaky if not isolated from required CI.

### Dependencies

- Workstreams A, B, E, and F for behavior under test.

## Workstream E - Trust Signals

### Rationale

Users need to know whether extraction output is trustworthy. Phase 2.5 should add first-layer quality signals without implementing full selector repair.

### Architecture Impact

- Extraction and preview produce quality summaries.
- Trust signals are shown in the project workspace and results.
- Existing record warnings become part of aggregate quality.
- No automatic selector repair yet.

### Backend Changes

- Add shared quality calculation service, recommended name: `app/services/extraction_quality.py`.
- Compute for preview:
  - selected field count
  - fields with values
  - missing fields
  - required missing fields
  - warning count
  - sample record count
- Compute for extraction:
  - total pages attempted
  - pages extracted
  - pages blocked
  - pages failed
  - total records
  - field success rate per field
  - missing rate per field
  - required missing rate
  - record warning count
  - scope warning count
- Add quality warning reason codes:
  - `FIELD_MISSING_IN_PREVIEW`
  - `FIELD_LOW_SUCCESS_RATE`
  - `REQUIRED_FIELD_MISSING`
  - `NO_RECORDS_EXTRACTED`
  - `MANY_PAGES_FAILED`
  - `SCOPE_NOT_CONFIRMED`
  - `FULL_SITE_SCOPE_WARNING`
  - `FRONTIER_HAS_MANY_EXCLUSIONS`

### Frontend Changes

- Add a Quality/Trust panel in Project Detail.
- Show:
  - overall quality state: Good, Needs review, Risky
  - field success rates
  - missing field rates
  - scope warnings
  - page failure summary
  - preview warnings
- Avoid technical wording like "selector failed" in default view. Use:
  - "This field was missing on 42% of sampled records."
  - "These pages were skipped because robots.txt blocked them."
  - "This extraction includes broad site exploration."
- Developer details can show raw warnings.

### Database Changes

Recommended:

- Add `quality_summary JSONB NOT NULL DEFAULT '{}'` to `exports`.
- Continue using `preview_results.quality_summary`.
- Continue using `extracted_records.warnings`.
- Optionally add `quality_summary JSONB` to `frontier_previews` from Workstream B.

Do not add a separate quality table in Phase 2.5 unless aggregation becomes expensive.

### API Changes

- Extend `PreviewResponse.quality_summary` use.
- Extend export metadata response if exports are listed later.
- Extend `ProjectResponse` with optional `extraction_quality`:

```json
{
  "overall": "needs_review",
  "field_success_rates": {
    "Price": 0.93,
    "Seller": 0.41
  },
  "missing_field_rates": {
    "Seller": 0.59
  },
  "warnings": []
}
```

### Migration Requirements

- Add Alembic migration for `exports.quality_summary`.
- No backfill required. Existing exports can default to `{}`.

### Testing Requirements

- Unit tests for quality calculation.
- Preview tests for missing field summaries.
- Extraction tests for field success rates.
- API tests for `extraction_quality`.
- Frontend tests for trust panel rendering.
- Regression test that warnings do not block export.

### Acceptance Criteria

- Preview shows missing field count and warnings.
- Completed extraction shows field success/missing rates.
- Scope warnings appear when scope is broad or unconfirmed.
- Users can distinguish "good", "needs review", and "risky" outputs.
- No automatic selector repair is implemented.

### Rollout Order

1. Add quality service.
2. Expand preview quality summary.
3. Compute extraction quality on completion.
4. Persist export quality summary.
5. Add `ProjectResponse.extraction_quality`.
6. Add frontend Trust panel.
7. Add tests.

### Risks

- Quality score can create false confidence.
- Field rates can be misleading if record grouping is wrong.
- Too many warnings can overwhelm users.

### Dependencies

- Workstream A for scope warnings.
- Workstream B for frontier warning summaries.
- Existing preview/extraction services.

## Workstream F - Large Result Sets

### Rationale

The current result UI is acceptable for small datasets but will not scale to 1,000, 10,000, or 100,000+ records if the frontend loads and renders too much at once.

### Recommendation

Use server-side pagination plus frontend virtualization for browsing. Keep exports as the preferred way to handle 100,000+ records.

Do not use simple infinite scrolling as the primary design. Infinite scrolling makes row counts, navigation, and data verification harder. Use explicit pages with optional virtualized rendering inside each page.

### Scale Targets

| Size | Preferred behavior |
|---:|---|
| 1,000+ records | Server pagination, 50-100 rows per page |
| 10,000+ records | Server pagination, total count, stable sorting, virtualized table |
| 100,000+ records | Export-first workflow, paginated browsing for samples, avoid full browser load |

### Architecture Impact

- Records API should return pagination metadata.
- Frontend should not assume all records are loaded.
- Export should remain streaming/server generated.
- Results table should support stable columns and navigation.

### Backend Changes

- Keep existing `GET /projects/{id}/records` for compatibility if needed.
- Add new paginated response endpoint or evolve endpoint with a non-breaking query.

Recommended endpoint:

- `GET /projects/{id}/records-page?skip=0&limit=100`

Response:

```json
{
  "items": [],
  "total": 12345,
  "skip": 0,
  "limit": 100,
  "next_skip": 100,
  "has_more": true,
  "columns": ["source_url", "Name", "Price"]
}
```

- Add total count query.
- Preserve stable ordering by `ExtractedRecord.id`.
- Limit max page size, recommended 500.
- Keep export endpoint reading up to configured export limit or streaming all records.

### Frontend Changes

- Update Results table to request one page at a time.
- Add pagination controls:
  - Previous
  - Next
  - page size
  - total count
- Add virtualization for the visible page if table rendering remains heavy.
- Add loading and empty states per page.
- Do not build columns from all records. Use returned `columns` or infer from first page plus quality metadata.
- Keep export buttons prominent for large datasets.

### Database Changes

- No immediate schema change required.
- Confirm indexes:
  - `extracted_records.project_id`
  - `extracted_records.id`
- If queries become slow later, add compound index `(project_id, id)`.

### API Changes

- Add `RecordPageResponse` schema.
- Add `GET /projects/{id}/records-page`.
- Keep old `GET /projects/{id}/records` for compatibility and small consumers.
- Optionally add `limit` cap warning if old endpoint is used.

### Migration Requirements

- No migration unless adding compound index.
- If adding index, create Alembic migration:
  - `CREATE INDEX ix_extracted_records_project_id_id ON extracted_records(project_id, id)`

### Testing Requirements

- API tests for pagination metadata.
- API tests for max limit.
- API tests for stable ordering.
- Frontend tests for next/previous page behavior.
- Frontend tests that Results does not render all records.
- Export tests with large generated dataset.

### Acceptance Criteria

- Results page can browse 1,000+ records without loading all rows.
- Results page can browse 10,000+ records with stable page navigation.
- 100,000+ records are handled via export-first guidance and paginated samples.
- API returns total count and has-more metadata.
- Frontend keeps memory use bounded by page size.

### Rollout Order

1. Add paginated records API.
2. Add backend tests.
3. Update frontend API client.
4. Update Results table.
5. Add frontend tests.
6. Add optional index if needed after local benchmark.

### Risks

- Counting records can become expensive at very high scale.
- Dynamic columns can shift across pages if later pages contain new fields.
- Virtualization adds frontend complexity.

### Dependencies

- Existing `ExtractedRecord` model.
- Existing export endpoint.
- Workstream E quality metadata can help stabilize columns.

## Cross-Workstream Rollout Plan

### Step 1 - Data Model Foundation

Implement:

- `ExtractionSpec.crawl_scope`
- `FrontierPreview` table
- `Export.quality_summary`
- optional records compound index

Why first:

- Later services and APIs need durable storage.

Risk:

- Migration mistakes affect all projects.

Validation:

- Migration applies cleanly.
- Existing tests pass.
- Old specs receive compatibility defaults.

### Step 2 - Backend Scope and Preview Services

Implement:

- `crawl_scope.py`
- `frontier_preview.py`
- `extraction_quality.py`
- scope-aware project extraction

Why second:

- Enables API and frontend without placeholder logic.

Risk:

- Scope rules can unintentionally change current crawl behavior.

Validation:

- Fixture tests for all modes.
- Compatibility test for old broad crawl under `FULL_SITE`.

### Step 3 - API Contracts

Implement:

- `crawl_scope` in spec update/response.
- frontier preview endpoints.
- extraction quality in project response.
- records-page endpoint.

Why third:

- Frontend can be built against stable contracts.

Risk:

- Breaking current clients.

Validation:

- Existing API tests still pass.
- New API tests cover contracts.

### Step 4 - Frontend Workflow

Implement:

- Simplified New Project setup.
- Understand Data scope confirmation.
- Frontier preview panel.
- Trust panel.
- Results pagination.
- Export moved to Results emphasis.

Why fourth:

- UI depends on backend contracts.

Risk:

- Product flow may become too dense.

Validation:

- Frontend tests.
- Manual UX pass.

### Step 5 - Validation and Fixture Expansion

Implement:

- Golden fixture sites.
- Benchmark scripts/tests.
- Optional provider-backed validation harness.
- Human validation checklist.

Why fifth:

- Lock behavior after first implementation.

Risk:

- Tests become brittle.

Validation:

- CI/local suite remains reasonable in runtime.

## Prioritization

### P0 - Must Complete Before Future Feature Expansion

| Item | Effort | Impact | Risk reduction | Order |
|---|---:|---:|---:|---:|
| Add `crawl_scope` storage and compatibility migration | M | Very high | Very high | 1 |
| Implement scope-aware discovery for four modes | L | Very high | Very high | 2 |
| Add frontier preview API and UI | L | Very high | Very high | 3 |
| Require user confirmation for non-current-page scope | M | High | Very high | 4 |
| Simplify Advanced Settings in primary project flow | M | High | High | 5 |
| Add scope/frontier fixture tests | M | High | High | 6 |
| Add trust quality summary v1 | M | High | Medium-high | 7 |
| Add paginated records API and frontend browsing | M | Medium-high | Medium | 8 |

P0 completion definition:

- Users can choose and confirm crawl scope.
- Extraction respects scope.
- Users can preview included/excluded URLs.
- Advanced implementation controls no longer dominate first-run UX.
- Tests prove scope behavior and current suite passes.

### P1 - High-Value Next Work

| Item | Effort | Impact | Risk reduction | Order |
|---|---:|---:|---:|---:|
| Add richer DOM evidence fixture tests | M | High | Medium-high | 1 |
| Add provider-backed benchmark harness | M | High | Medium | 2 |
| Add multi-page selector quality sampling | L | High | High | 3 |
| Add frontend table virtualization | M | Medium | Medium | 4 |
| Add optional records compound index after benchmark | S | Medium | Medium | 5 |
| Add human UX validation scripts/checklists | S | Medium | Medium | 6 |

### P2 - Future Work

| Item | Effort | Impact | Risk reduction | Notes |
|---|---:|---:|---:|---|
| Template fingerprinting and template-specific selectors | L | Very high | High | Needed before complex multi-template sites |
| Selector repair | L | High | High | Explicitly not Phase 2.5 |
| Sitemap-assisted frontier estimates | M | Medium | Medium | Useful for full-site/content workflows |
| Scheduled extraction regression checks | M | Medium | Medium | Future reliability feature |
| Multi-worker durable crawl recovery | L | High | Medium | Important after scope correctness is solved |
| Advanced provider quality comparison dashboard | M | Medium | Low-medium | Useful for BYOK power users |

## Required Acceptance Gate For Phase 2.5

Phase 2.5 is complete only when:

- Full backend suite passes.
- Frontend tests, typecheck, lint, and build pass.
- New crawl scope tests cover all four modes.
- Frontier preview tests prove included/excluded reasons.
- Extraction cannot silently broad-crawl a new project without confirmed broad scope.
- Project UI follows `URL -> Understand Data -> Choose Fields -> Preview -> Extract -> Results`.
- Results browsing is paginated and does not load all records.
- Trust panel shows at least field success/missing rates and scope warnings.
- Existing projects remain usable after migration.

