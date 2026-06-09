# Phase 2.5 Step 1-2 Review

Date: June 9, 2026

Scope: code-first architecture and correctness review of Phase 2.5 Step 1, Data Model Foundation, and Step 2, Backend Behavior Layer.

This is the final review checkpoint before Step 3. It reviews implementation code first. Documentation and implementation reports are treated only as supporting material.

## Review Result

| Area | Verdict |
|---|---|
| Step 1 - Data Model Foundation | APPROVE WITH CHANGES |
| Step 2 - Backend Behavior Layer | APPROVE WITH CHANGES |
| Begin Step 3 now? | No. Fix the Step 1/2 blockers first. |

Reason: the core direction is sound and the focused tests pass, but the foundation is not yet safe enough to become the API contract layer. The largest issues are nullable/weakly enforced persisted scope, incomplete API wiring, no extraction-time confirmation enforcement, a preview service that is not yet actually persisted by itself, and insufficient integration/migration validation.

## Evidence Summary

### Verified By Code Inspection

- `CrawlScopeMode` and `CrawlScopeStatus` exist in `app/models/job.py`.
- `DEFAULT_CRAWL_SCOPE` defaults new scope to `CURRENT_PAGE`; `LEGACY_COMPAT_CRAWL_SCOPE` defaults old/missing scope to `FULL_SITE`.
- `ExtractionSpec` now has nullable `crawl_scope` and nullable `quality_summary`.
- `FrontierPreview` model and `frontier_previews` table exist.
- Alembic revision `008` adds `crawl_scope`, `quality_summary`, and `frontier_previews`, and backfills existing `crawl_scope` to legacy `FULL_SITE`.
- `default_spec_from_analysis()` now creates a `crawl_scope`.
- `project_extraction.execute_project_extraction()` uses `discover_links_for_scope()` when `spec.crawl_scope` has a mode.
- `frontierpreview.create_frontier_preview()` uses `classify_links_for_scope()`, the same classifier extraction uses indirectly through `discover_links_for_scope()`.
- `compute_extraction_quality()` exists and is persisted to `spec.quality_summary` at extraction completion.
- `app/schemas/project.py` includes crawl-scope, frontier-preview, extraction-quality, and record-page response DTOs.
- Project API currently does not return `crawl_scope`, `quality_summary`, `frontier_preview`, or `extraction_quality` from `_project_response()` / `_spec_response()`.
- Project API currently does not apply `payload.crawl_scope` in `update_project_spec()`.
- No frontier-preview endpoint is wired in `app/api/v1/endpoints/projects.py`.

### Verified By Test Execution

Commands run:

```powershell
venv\Scripts\python.exe -m pytest tests\services\test_crawl_scope.py tests\services\test_extraction_quality.py tests\services\test_project_workflow.py tests\api\v1\test_projects.py -q
```

Result:

- `45 passed, 16 warnings`

```powershell
venv\Scripts\python.exe -m pytest -q
```

Result:

- `197 passed, 28 warnings`

### Not Verified

- Alembic upgrade/downgrade against a real PostgreSQL database.
- Backfill correctness on existing production-like rows.
- End-to-end project extraction through HTTP using `crawl_scope`.
- Frontier preview persistence through an API route.
- Extraction-time rejection of unconfirmed non-current-page scopes.
- Real-world pagination, dataset, and category classification.
- Export correctness after quality-summary changes.
- Performance on large pages or large frontier samples.

## 1. Data Model Review

### Crawl Scope Model

Verified by code inspection.

The model has the right high-level concepts:

- `mode`
- `status`
- `seed_url`
- `max_pages`
- `max_depth`
- include/exclude patterns
- pagination hints
- link rules
- AI recommendation
- user confirmation timestamp

This is a good long-term shape because it separates user intent from low-level `url_patterns`.

Concern: `crawl_scope` is nullable in both SQLAlchemy and the Alembic migration.

- `ExtractionSpec.crawl_scope` is declared `nullable=True`.
- Migration `008` adds `crawl_scope` as nullable, backfills existing rows, but does not set `nullable=False`.

Risk:

- Future code must always defend against `None`.
- API clients can receive specs with no durable scope.
- The system can silently fall back to legacy broad behavior in some paths.

Recommended fix:

- Before Step 3, make `crawl_scope` effectively required at the application boundary.
- Prefer DB `NOT NULL` with server default if feasible.
- If DB `NOT NULL` is deferred, add service/API enforcement so `ensure_default_spec()` and `update_project_spec()` cannot persist missing/invalid scope.

Concern: the persisted JSON has no database-level shape validation.

Risk:

- Bad modes, statuses, malformed rules, or extreme values can be persisted by direct DB access or incomplete API code.
- JSONB flexibility helps migration but shifts correctness to service/API layers.

Recommended fix:

- Keep JSONB for flexibility, but centralize validation through the Pydantic `CrawlScope` schema and call it before persistence.
- Add tests that invalid modes/statuses cannot be saved through the API.

### Quality Summary

Verified by code inspection.

`quality_summary` was added to `ExtractionSpec`, not `Export`.

This is acceptable for Step 2 because extraction quality is tied to the spec used for the run. It also lets Project Detail show trust information without listing exports.

Concern:

- `quality_summary` is nullable and not returned by current project/spec API responses.
- If a spec is reused for multiple extractions, the summary is overwritten.

Risk:

- Users may see stale or missing quality information.
- Future export-level quality history will require a second storage location or a snapshot on `Export`.

Recommended fix:

- Before Step 3, return `quality_summary` in `ExtractionSpecResponse` and `ProjectResponse.extraction_quality`.
- For later phases, snapshot quality on `Export` or create extraction-run records if repeated extraction history matters.

### Frontier Previews

Verified by code inspection.

The `FrontierPreview` model includes:

- project/spec foreign keys
- scope hash
- included/excluded URL samples
- estimated page count
- warnings
- quality summary

This is a reasonable storage model for Step 1.

Concern: `create_frontier_preview()` returns a `FrontierPreview` object but never adds it to the session or flushes it.

Risk:

- The service name and docstring imply it persists the preview, but callers must remember to `db.add(preview)`.
- This is easy to misuse in Step 3 API wiring.

Recommended fix:

- Make `create_frontier_preview()` actually persist: `db.add(row)`, `await db.flush()`, `await db.refresh(row)`.
- Or rename it to `build_frontier_preview()` and create a separate persistence function. The safer Step 3 foundation is to persist inside the service.

Concern: the file is named `frontierpreview.py`, while the plan and naming pattern expected `frontier_preview.py`.

Risk:

- Low functional risk, but naming inconsistency will cause import mistakes.

Recommended fix:

- Rename to `frontier_preview.py` before Step 3 if no external imports depend on it yet.

### Migration Strategy

Verified by code inspection.

Alembic has a single head at `008`, and revision history is linear from `001` to `008`.

Migration `008` is additive:

- adds `crawl_scope`
- adds `quality_summary`
- backfills `crawl_scope`
- creates `frontier_previews`

Hidden risks:

- Migration was not verified against an actual PostgreSQL database during this review.
- `crawl_scope` remains nullable after backfill.
- There is no default/server default for new rows created outside the application.
- The migration hardcodes legacy scope JSON separately from model constants, which can drift.

Recommended fix:

- Run `alembic upgrade head` and `alembic downgrade 007` against a test Postgres database before Step 3.
- Add a migration verification test or documented validation command.
- Decide whether `crawl_scope` should be `NOT NULL`; this review recommends yes.

### Backfill Behavior

Verified by code inspection.

Existing specs are backfilled to `FULL_SITE` / `SYSTEM_DEFAULTED`, preserving current broad same-origin behavior.

This is compatibility-safe but product-risky.

Risk:

- Existing projects keep broad crawl behavior, which is intentional.
- If UI later treats `SYSTEM_DEFAULTED` as safe/confirmed, old projects may broad-crawl without explicit review.

Recommended fix:

- In Step 3, surface legacy/system-defaulted `FULL_SITE` as needing review unless the user explicitly confirms.
- Do not treat `SYSTEM_DEFAULTED` as equivalent to `USER_CONFIRMED`.

### Compatibility Behavior

Verified by code inspection.

The extraction executor falls back to `discover_same_site_links()` if `spec.crawl_scope` is absent or lacks a mode.

This preserves legacy behavior but weakens safety.

Recommended fix:

- Keep fallback only for legacy rows during transition.
- Add logging when fallback legacy same-site crawl is used.
- Add a future migration or repair path to normalize all specs.

## 2. Crawl Scope Correctness

### CURRENT_PAGE

Verified by code inspection and test execution.

Behavior:

- `classify_links_for_scope()` excludes all links for `CURRENT_PAGE`.
- `execute_project_extraction()` also zeroes `links` if `scope_mode == CURRENT_PAGE`.

Verdict:

- Correct and intentionally conservative.

Edge cases:

- Same-page anchors, mailto, tel, and javascript links are excluded.
- Redirected final URLs are still extracted as the seed page, which is acceptable.

### PAGINATION

Verified by code inspection and test execution.

Behavior:

- Includes URLs with common pagination query tokens: `page=`, `p=`, `offset=`, `start=`.
- Includes URLs matching `scope.pagination.url_pattern`.
- Does not actually evaluate `pagination.selector` against anchor elements. The code comment says selector is informational in v1.

Risk:

- The name "pagination selector" can create false expectations. A user/AI may store `a.next`, but the classifier does not check whether a link matched that selector.
- Query token heuristic is broad. `p=` can mean product, post, parameter, or page.
- Pagination can break on path-based URLs like `/food/potato-products/2` unless `url_pattern` is present.
- "Next" links without query/path pattern will not be included.

Calories.info example:

- If the potato-products page has category links to Pizza, Meat, Beer, Fruit and no `page=` style links, `PAGINATION` will exclude them.
- That is good for preventing wrong-dataset crawl.
- If unrelated links include a query parameter like `?p=beer`, they may be incorrectly included as pagination.

Recommended fix:

- Before Step 3, rename or document selector semantics clearly.
- Prefer evaluating actual anchor selectors where possible.
- Narrow the `p=` heuristic or require stronger evidence, especially for `PAGINATION`.

### DATASET

Verified by code inspection and test execution.

Behavior:

- Includes pagination matches.
- Includes `include_patterns`.
- Includes `link_rules` with role `dataset` or `detail` and matching `pattern`.
- Does not evaluate `link_rules.selector`.

Risk:

- Dataset correctness depends heavily on pattern quality.
- `include_patterns: ["/p/*"]` can include potato and meat alike if both live under `/p/`.
- Detail selector rules are not selector rules in v1; only pattern matching is used.
- There is no template fingerprint or record-quality feedback in the inclusion decision.

Calories.info example:

- A naive dataset include pattern like `/food/*` would include Potato Products, Pizza, Meat, Beer, Fruit, and other unrelated categories.
- A safer pattern may need `/food/potato-products*` or pagination-only, depending on site shape.

Recommended fix:

- Require frontier preview for `DATASET`.
- Show included/excluded examples before extraction.
- Treat broad include patterns as warnings.
- Do not let AI-generated dataset patterns become `USER_CONFIRMED` without user review.

### FULL_SITE

Verified by code inspection and test execution.

Behavior:

- Includes all same-origin URLs unless excluded.
- Supports include/exclude path patterns.
- Preserves legacy broad crawl behavior.

Risk:

- This intentionally can crawl the wrong dataset if selected accidentally.
- The backend currently computes `scope_confirmed` but does not enforce it.
- If a `FULL_SITE` scope is persisted as `AI_SUGGESTED` or `SYSTEM_DEFAULTED`, extraction can still proceed.

Recommended fix:

- Before Step 3, enforce confirmation for non-`CURRENT_PAGE` scopes either in `extract_project()` or `start_project_extraction()`.
- `FULL_SITE` should require explicit user confirmation except for legacy compatibility paths that are clearly marked.

### Do The Modes Behave Differently Enough?

Verified by code inspection and test execution.

Yes, mechanically:

- `CURRENT_PAGE` inserts no links.
- `PAGINATION` only includes pagination-like URLs.
- `DATASET` includes pagination plus approved patterns/rules.
- `FULL_SITE` includes broad same-origin URLs.

But the differences depend on weak heuristics and user/AI-supplied patterns. They are safe enough as behavior-layer primitives, not yet safe enough as user-facing API contracts.

## 3. Frontier Preview Integrity

Verified by code inspection.

Preview and extraction share the core classifier:

- Preview calls `classify_links_for_scope()`.
- Extraction calls `discover_links_for_scope()`, which calls `classify_links_for_scope()`.

This is the right architecture.

Drift risks:

- Preview samples only the seed page; extraction classifies links on every fetched page. A later page can introduce different links and patterns.
- Preview's estimate is `scope_max_pages(scope)`, not an actual crawl estimate.
- Preview includes seed manually even when classifier returns no included links.
- Preview currently counts `EXCLUDED_DIFFERENT_ORIGIN` as `unrelated_same_origin_count` and emits a message saying same-origin links were excluded. That is a correctness bug in the preview quality summary.
- Preview service does not persist its returned object by itself.
- API endpoints are not yet wired, so no end-to-end preview/extraction consistency exists.

Recommended fix before Step 3:

- Fix `unrelated_count` to count excluded same-origin scope exclusions, not different-origin links.
- Persist previews inside `create_frontier_preview()` or rename it to a builder.
- Add tests that preview included URLs equal `discover_links_for_scope()` for the same seed page and scope.
- Add a test proving `PAGINATION` preview excludes calories.info-style category links.

## 4. Extraction Quality Review

Verified by code inspection and test execution.

Metrics implemented:

- per-field success rates
- per-field missing rates
- low-success warnings
- required-field-missing warnings
- no-records warning
- many-pages-failed warning
- coarse overall state: `good`, `needs_review`, `risky`, `unknown`

These metrics are useful as first-layer trust signals.

Trust gaps:

- Field success rates are computed from resulting records only. If records are dropped entirely because required fields are missing, missing rates can look better than the real page-level failure.
- Field naming can drift. `_selected_field_names()` prefers `name`, but extraction output keys use `user_label` / `label` / `name`. If user labels differ from names, required-field warnings can miss or misattribute fields.
- The rate calculation accumulates field names as it iterates. Fields that first appear later are counted as missing in earlier records only after they appear; this can undercount missingness for sparse late fields.
- `source_url` is included as a field in quality rates, which can inflate perceived quality.
- `scope_confirmed` and `WARN_SCOPE_NOT_CONFIRMED` are imported/computed in project extraction but not used.
- `FULL_SITE_SCOPE_WARNING` is defined but not emitted by `compute_extraction_quality()`.
- Quality calculation is best-effort and swallowed on exception, so failures can silently produce `{}`.

Can metrics create false confidence?

Yes.

Examples:

- If selector grouping extracts only records with a price and drops all price-missing records, price success can appear high.
- If `source_url` is always present, the quality summary always has at least one perfect field unless filtered.
- If a `DATASET` pattern includes unrelated pages but those pages produce some matching fields, quality may look "good" while the dataset is semantically wrong.

Recommended fix:

- Exclude system fields like `source_url` from field success rates.
- Compute selected-field rates using selected field output keys, not discovered record keys.
- Add page-level and container-level denominators later.
- Emit scope warnings outside selector-quality metrics.
- Do not show a single "good" badge unless scope was confirmed and field/page warnings are clean.

## 5. Test Review

### Unit Tests

Verified by code inspection and test execution.

`tests/services/test_crawl_scope.py` covers:

- default scope
- scope normalization
- confirmation requirements
- max pages/depth
- all four scope modes
- navigation/different-origin/dedupe
- discovery limit

`tests/services/test_extraction_quality.py` covers:

- all fields present
- low success
- required missing
- no records
- page failure thresholds
- full-site low-success risk
- preview missing-field warnings

These are useful and fast.

### Service Tests

Verified by code inspection and test execution.

`tests/services/test_project_workflow.py` still covers default spec creation, selector extraction, and URL normalizer behavior, but it only lightly touches new scope behavior through default spec creation indirectly.

Missing service tests:

- `frontierpreview.create_frontier_preview()`.
- `project_extraction.execute_project_extraction()` with each scope mode.
- quality summary persistence after real extraction executor run.

### Integration Tests

Verified by code inspection.

Current API tests are minimal and mostly fake-session based. They test auth requirement, analyze defaults, and project ownership 404.

They do not test:

- patching `crawl_scope`
- returning `crawl_scope`
- returning `quality_summary`
- frontier preview endpoint
- extraction gating for unconfirmed scope
- persisted frontier preview rows

### End-to-End Tests

Not verified because they do not appear to exist for Step 1/2.

There is no test that starts the API, creates a project, creates/updates a spec, generates frontier preview, runs extraction, and verifies DB rows and exports.

### Are The New Tests Mostly example.com-Style Isolated Tests?

Verified by code inspection.

Yes. The new crawl-scope tests use small inline HTML strings and `example.com` URLs. This is appropriate for unit tests but does not validate real-world crawl behavior.

### Real-World Behavior Remaining Unvalidated

Not verified:

- calories.info-style page with many category links and possible table/list data.
- path-based pagination.
- next-button-only pagination.
- detail links with selectors but no stable URL pattern.
- JavaScript-rendered links.
- redirects changing origin/path.
- robots behavior in scoped extraction.
- multi-page recursive crawl correctness.
- export correctness after scoped extraction.

## 6. Validation Gaps

Missing integration tests:

- Scope update through API and persisted DB row.
- Extraction rejects or warns on unconfirmed non-current-page scope.
- Frontier preview persistence through API.
- Project response includes new fields once Step 3 is wired.

Missing E2E tests:

- Full project flow with local fixture site.
- Current page only extraction creates one crawl page.
- Pagination-only extraction follows only pagination fixture links.
- Dataset extraction includes detail pages but excludes unrelated categories.
- Full-site extraction preserves broad behavior only when confirmed.

Missing fixture datasets:

- paginated catalog
- mixed category navigation site
- calories.info-style food category page
- listing with detail pages
- dense table dataset
- content/docs site

Missing regression tests:

- Broad same-origin crawl only under `FULL_SITE`.
- Preview and extraction produce same seed-page include decisions.
- `crawl_scope=None` legacy fallback behavior is logged/controlled.
- Bad `crawl_scope.mode` is rejected by API before persistence.

Missing migration verification:

- `alembic upgrade head` on real Postgres.
- `alembic downgrade 007`.
- Backfill existing specs to legacy scope.
- New rows cannot be scope-less if `NOT NULL` is adopted.

Missing export validation:

- CSV/JSON/XLSX row and column correctness after scoped extraction.
- Quality summary snapshot consistency with exported data.

Missing extraction accuracy benchmarks:

- URL precision/recall by scope mode.
- record count accuracy.
- field success vs golden data.
- warnings correctness.

## 7. Future Compatibility

### Frontier Preview

Verified by code inspection.

The core classifier reuse is compatible with future preview work. The storage table is reasonable.

Needs before Step 3:

- Persistence semantics fixed.
- API wiring.
- Preview/extraction equality tests.

### Trust Layer

Verified by code inspection.

`compute_extraction_quality()` is a useful start, but should be treated as low-confidence trust v1.

Compatible with future work:

- field-level rates
- warning codes
- overall labels

Needs improvement:

- filter system fields
- selected-field denominators
- scope warnings
- page/template denominators

### Template Intelligence

Verified by code inspection.

Current scope model can carry link roles and patterns, but no template identity exists.

Future compatibility:

- `link_rules` can be extended with `template`, `template_id`, or `route_to_spec_id`.
- JSONB makes this easy, but lack of normalization can become messy.

Recommendation:

- Add `version`-based migration helpers for crawl scope as shape evolves.

### Visual Selection

Verified by code inspection.

No conflict. Visual selection can update field selectors independently of crawl scope.

Future risk:

- Visual selector output must be validated across scope/template samples, not only seed page.

### Selector Repair

Verified by code inspection.

Current quality summary can trigger future repair, but it does not preserve enough evidence for repair.

Future needs:

- failed selector examples
- source HTML snippets
- template/page context
- before/after selector proposals

No major rewrite required, but more evidence capture will be needed.

## 8. Final Verdict

### Step 1 - Data Model Foundation

Verdict: APPROVE WITH CHANGES

Why:

- The core model direction is correct.
- Alembic has one head and the migration is additive.
- Existing-row backfill preserves compatibility.

Blocking changes before Step 3:

1. Tighten `crawl_scope` persistence.
   - Risk: nullable scope undermines the entire intent model.
   - Fix: make DB column non-null with default, or enforce non-null scope at all service/API creation/update points before exposing Step 3 APIs.

2. Decide and enforce response/persistence shape.
   - Risk: schemas include fields that endpoint helpers do not return or update.
   - Fix: wire `crawl_scope`, `quality_summary`, `frontier_preview`, and `extraction_quality` consistently in Step 3, but do not begin Step 3 until the intended shape is settled.

3. Verify migration on Postgres.
   - Risk: migration/backfill issues are invisible in unit tests.
   - Fix: run upgrade/downgrade validation and document output.

Recommended non-blocking changes:

- Rename `frontierpreview.py` to `frontier_preview.py`.
- Consider explicit relationships with `back_populates` instead of `backref`.
- Add JSON schema/version helper for future crawl-scope shape changes.

### Step 2 - Backend Behavior Layer

Verdict: APPROVE WITH CHANGES

Why:

- The classifier model is clean and testable.
- All four scope modes have different behavior.
- Focused and full test suites pass.
- Preview and extraction share a common classifier path.

Blocking changes before Step 3:

1. Enforce confirmation before broad extraction.
   - Risk: non-`CURRENT_PAGE` scopes can run even when `scope_requires_confirmation()` is true; `scope_confirmed` is computed but unused.
   - Fix: reject extraction or force current-page behavior unless scope is `USER_CONFIRMED`, except for explicit legacy compatibility policy.

2. Fix frontier preview persistence semantics.
   - Risk: Step 3 endpoint can easily return an unpersisted object and `latest_frontier_preview()` will not find it.
   - Fix: persist in `create_frontier_preview()` or rename/split builder and persister.

3. Fix frontier preview exclusion counts/warnings.
   - Risk: current `unrelated_same_origin_count` counts `EXCLUDED_DIFFERENT_ORIGIN`, but message says same-origin links were excluded.
   - Fix: count same-origin links excluded by scope, likely `EXCLUDED_SCOPE_MODE` and/or include-pattern misses.

4. Add integration tests around executor behavior.
   - Risk: unit tests prove classifier output, not that extraction queues the right pages.
   - Fix: test `execute_project_extraction()` or a smaller extraction-service seam with local fixture HTML for all scope modes.

Recommended non-blocking changes:

- Narrow pagination heuristics, especially `p=`.
- Evaluate actual selectors for pagination/detail rules or rename fields to avoid implying selector enforcement.
- Exclude `source_url` from quality field rates.
- Use selected field output keys for quality denominators.

## 9. Pre-Step-3 Checklist

### Must Fix Before Step 3

- Enforce non-current-page scope confirmation before extraction.
- Fix/pin persistence semantics of `create_frontier_preview()`.
- Fix frontier preview `unrelated_same_origin_count` / warning logic.
- Decide whether `crawl_scope` is DB `NOT NULL`; if not, enforce non-null at service/API boundaries.
- Run Alembic upgrade/downgrade against real Postgres or equivalent project test DB.
- Add at least one integration test proving extraction queues pages according to scope, not just classifier output.

### Recommended Before Step 3

- Rename `frontierpreview.py` to `frontier_preview.py`.
- Add API tests for `crawl_scope` update/response behavior before exposing it.
- Add tests that preview included URLs match `discover_links_for_scope()` for same page/scope.
- Add calories.info-style fixture HTML with potato-products plus Pizza/Meat/Beer/Fruit links.
- Add a quality-summary test excluding `source_url` as a trust field.
- Add logging when legacy `crawl_scope=None` fallback is used.

### Can Wait Until Later

- Template fingerprinting.
- Multi-page frontier sampling.
- Selector repair.
- Visual selection integration.
- Provider-backed AI scope evaluation.
- Sitemap-assisted estimates.
- Large-result virtualization.

## Bottom Line

Step 1 and Step 2 are directionally correct and test-backed at the unit/service level, but they are not yet a safe foundation for Step 3 API contracts. Step 3 should wait until the confirmation gate, frontier preview persistence, preview warning logic, and migration/integration validation are tightened.

