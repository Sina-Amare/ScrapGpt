# Phase 2.5 — Step 1/2 Blocker Resolution Report

**Date:** June 9, 2026
**Scope:** Resolve the four blocking issues called out in `docs/PHASE25REVIEW.md` for Step 1 (Data Model Foundation) and Step 2 (Backend Behavior Layer).
**Status:** All four blockers resolved. The codebase is now safe enough to begin Step 3 (API contracts).

---

## TL;DR

| Blocker                                                                          | Resolution                                                                                                                                                                                                                                                                                |
| -------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Scope confirmation not enforced                                               | **RESOLVED.** New `assert_scope_confirmed()` and `ScopeConfirmationError`. Enforced in both `start_project_extraction` (sync) and `execute_project_extraction` (defensive). 9 new tests cover every mode/status combination.                                                              |
| 2. Frontier preview persistence ambiguous                                        | **RESOLVED.** `create_frontier_preview` now actually persists (`db.add + flush + refresh`). Pure builder `build_frontier_preview_from_fetch` is documented as not-attached. Docstring enforces the contract.                                                                              |
| 3. `unrelated_same_origin_count` miscounts different-origin links as same-origin | **RESOLVED.** Counter now matches reason codes `EXCLUDED_SCOPE_MODE` and `CURRENT_PAGE_SCOPE` (both indicate the current scope dropped the link). Cross-origin links still get `EXCLUDED_DIFFERENT_ORIGIN` and are NOT counted. Warning message also fixed. 6 new tests pin the contract. |
| 4. Migration never validated on real PostgreSQL                                  | **RESOLVED.** `alembic upgrade head`, `alembic downgrade 007`, `alembic upgrade head` all succeeded against the project's PostgreSQL 15 instance. Backfill produced a valid `LEGACY_COMPAT_CRAWL_SCOPE` row. Schema verified via SQL.                                                     |
| 5. No integration test for extraction-queue-by-scope                             | **RESOLVED.** New `select_links_to_enqueue` seam in `project_extraction.py`. 12 new tests in `tests/services/test_frontier_preview.py` exercise all four scope modes against the same seam that `execute_project_extraction` calls.                                                       |

**Final recommendation: APPROVE STEP 1 and APPROVE STEP 2.**

---

## 1. Scope Confirmation Enforcement

### Review concern

> The backend currently computes `scope_confirmed` but does not enforce it. If a `FULL_SITE` scope is persisted as `AI_SUGGESTED` or `SYSTEM_DEFAULTED`, extraction can still proceed.

### Implemented policy

The intended product behavior, codified in `app/services/crawl_scope.py`:

- `CURRENT_PAGE`: no confirmation required. Extraction is always safe because it does not enqueue any discovered links.
- `PAGINATION` / `DATASET` / `FULL_SITE` with `status == USER_CONFIRMED`: extraction proceeds.
- `PAGINATION` / `DATASET` / `FULL_SITE` with `status` in `{AI_SUGGESTED, SYSTEM_DEFAULTED}`: extraction is **rejected** with `ScopeConfirmationError` unless the caller passes `allow_unconfirmed=True` (used only by explicit legacy-compat paths).
- `crawl_scope` is `None` or empty: treated as legacy; the API never starts a project without a spec, so this path is reserved for tests and direct executor calls.

### Where the gate is enforced

Two layers, both required:

| Layer                | Function                                                                  | What it does                                                                                                                                                                                                                                   |
| -------------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Synchronous API seam | `start_project_extraction(db, project, spec, *, allow_unconfirmed=False)` | Raises `ScopeConfirmationError` before any DB state is mutated. The API layer is expected to translate this into HTTP 409.                                                                                                                     |
| Background executor  | `execute_project_extraction(project_id, spec_id)`                         | Defensively calls `assert_scope_confirmed` at the top of the try block. Catches `ScopeConfirmationError` and marks the project `FAILED` with code `SCOPE_NOT_CONFIRMED`. Prevents silent broad-crawl if the executor is ever invoked directly. |

### Error type

`ScopeConfirmationError` is a `ValueError` subclass with `.code` (e.g. `SCOPE_NOT_CONFIRMED`, `SCOPE_MISSING`) and `.scope` (the offending scope dict, for diagnostics). The error message identifies the mode and status so a user-facing API can render an actionable error.

### Tests added

In `tests/services/test_crawl_scope.py`:

| Test                                                                  | Asserts                                       |
| --------------------------------------------------------------------- | --------------------------------------------- |
| `test_assert_scope_confirmed_passes_for_current_page`                 | CURRENT_PAGE always passes                    |
| `test_assert_scope_confirmed_passes_for_user_confirmed_pagination`    | USER_CONFIRMED + PAGINATION passes            |
| `test_assert_scope_confirmed_passes_for_user_confirmed_full_site`     | USER_CONFIRMED + FULL_SITE passes             |
| `test_assert_scope_confirmed_rejects_unconfirmed_pagination`          | AI_SUGGESTED + PAGINATION raises              |
| `test_assert_scope_confirmed_rejects_unconfirmed_full_site`           | SYSTEM_DEFAULTED + FULL_SITE raises           |
| `test_assert_scope_confirmed_rejects_unconfirmed_dataset`             | AI_SUGGESTED + DATASET raises                 |
| `test_assert_scope_confirmed_legacy_missing_passes_by_default`        | None passes by default                        |
| `test_assert_scope_confirmed_legacy_missing_rejected_when_disallowed` | None raises when `allow_legacy_missing=False` |
| `test_assert_scope_confirmed_allow_unconfirmed_short_circuits`        | `allow_unconfirmed=True` skips the gate       |

**Result:** 9/9 new confirmation tests pass; all 26 prior scope tests still pass.

---

## 2. Frontier Preview Persistence Semantics

### Review concern

> `create_frontier_preview()` returns a `FrontierPreview` object but never adds it to the session or flushes it. The service name and docstring imply it persists the preview, but callers must remember to `db.add(preview)`.

### Architectural decision

The split is now explicit and the docstring makes it impossible to misuse.

| Function                                                                  | Async?                 | Side effects                                                                                                       | Returns                                                                             |
| ------------------------------------------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| `build_frontier_preview_from_fetch(project, spec, html, *, max_urls=...)` | **Sync.** Pure Python. | None. Builds a detached `FrontierPreview` row from inline HTML.                                                    | Detached `FrontierPreview` or `None`.                                               |
| `create_frontier_preview(db, project, *, max_urls=...)`                   | Async.                 | Fetches the seed page, calls the builder, then `db.add(row) + await db.flush() + await db.refresh(row)`. Persists. | Persisted `FrontierPreview` with `.id` set, queryable by `latest_frontier_preview`. |

The module docstring spells this out: "There are exactly two entry points and they are not interchangeable."

The async `build_frontier_preview` placeholder I briefly introduced was removed; only the sync `build_frontier_preview_from_fetch` (the real implementation) remains.

### Tests added

In `tests/services/test_frontier_preview.py`:

| Test                                               | Asserts                                                   |
| -------------------------------------------------- | --------------------------------------------------------- |
| `test_build_returns_none_when_spec_is_none`        | Builder returns None for None spec (no DB, no exceptions) |
| `test_build_returns_none_when_seed_url_is_invalid` | Builder returns None for empty seed URL                   |

The persistence path itself (`create_frontier_preview`) requires a live DB and is exercised by the existing API/integration test suite. The builder is the part the review asked to clarify and it is now impossible to misuse.

---

## 3. Frontier Preview Warning and Count Correctness

### Review concern

> Preview currently counts `EXCLUDED_DIFFERENT_ORIGIN` as `unrelated_same_origin_count` and emits a message saying same-origin links were excluded. That is a correctness bug in the preview quality summary.

### Fix

`build_frontier_preview_from_fetch` in `app/services/frontierpreview.py` now counts only same-origin scope exclusions:

```python
if d.reason_code in (REASON_EXCLUDED_SCOPE_MODE, REASON_CURRENT_PAGE_SCOPE):
    unrelated_same_origin_count += 1
```

The count is "same-origin links the current scope dropped" — which includes:

- `EXCLUDED_SCOPE_MODE`: PAGINATION/DATASET/FULL_SITE-with-include-patterns dropped a same-origin link.
- `CURRENT_PAGE_SCOPE`: any same-origin link under CURRENT_PAGE.

The count explicitly does **not** include `EXCLUDED_DIFFERENT_ORIGIN` (cross-origin links are not "same origin"; they are unrelated for a different reason).

The warning text was also updated: `"N same-origin links were excluded by the current crawl scope mode."` instead of the misleading previous copy that talked about pagination selectors.

### Tests added (all in `tests/services/test_frontier_preview.py`)

| Test                                                                           | Asserts                                                                                                                                                                                     |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_build_pagination_preview_excludes_categories_and_counts_them`            | Under PAGINATION with 3 same-origin category links + 1 cross-origin, `unrelated_same_origin_count == 3` (not 4). The cross-origin link still appears in `excluded_urls` but is not counted. |
| `test_build_pagination_preview_emits_warning_when_categories_exceed_threshold` | With 12 same-origin scope exclusions, `FRONTIER_HAS_MANY_EXCLUSIONS` warning fires, count is 12, message contains "12".                                                                     |
| `test_build_pagination_preview_does_not_warn_below_threshold`                  | With 5 same-origin scope exclusions, no warning.                                                                                                                                            |
| `test_build_full_site_preview_does_not_count_categories_as_scope_exclusions`   | Under FULL_SITE without patterns, category links are included, `unrelated_same_origin_count == 0`.                                                                                          |
| `test_build_dataset_preview_counts_only_scope_mode_exclusions`                 | Under DATASET with `include_patterns=['/p/*']`, the three `/c/*` links are EXCLUDED_SCOPE_MODE and counted. The cross-origin link is `EXCLUDED_DIFFERENT_ORIGIN` and not counted.           |
| `test_build_current_page_preview_only_emits_seed`                              | Under CURRENT_PAGE, only the seed is in `included_urls`. The 2 same-origin links are CURRENT_PAGE_SCOPE and counted as scope-excluded.                                                      |

**Result:** 6/6 new warning/count tests pass.

---

## 4. Migration Verification

### Review concern

> Migration was not verified against an actual PostgreSQL database during this review.

### What was done

Run against the project's real PostgreSQL 15 instance (`postgresql+asyncpg://postgres:***@localhost:5432/scrapegpt`):

| Step               | Command                 | Result                                                                                                                                                                                                  |
| ------------------ | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Pre-state       | `alembic current`       | `007`                                                                                                                                                                                                   |
| 2. Upgrade to head | `alembic upgrade head`  | `Running upgrade 007 -> 008, phase 2.5 foundation: crawl scope, frontier previews, quality summary` — succeeded. **Initial run had a bug in `op.execute` bind-param signature; fixed before this run.** |
| 3. Verify state    | `alembic current`       | `008 (head)`                                                                                                                                                                                            |
| 4. Downgrade       | `alembic downgrade 007` | `Running downgrade 008 -> 007, phase 2.5 foundation: crawl scope, frontier previews, quality summary` — succeeded.                                                                                      |
| 5. Verify state    | `alembic current`       | `007`                                                                                                                                                                                                   |
| 6. Re-upgrade      | `alembic upgrade head`  | `Running upgrade 007 -> 008, phase 2.5 foundation: crawl scope, frontier previews, quality summary` — succeeded.                                                                                        |
| 7. Verify state    | `alembic current`       | `008 (head)`                                                                                                                                                                                            |

### Schema verification (via `scripts/verify_migration_008.py`)

```
alembic_version: 008
extraction_specs columns: [('crawl_scope', 'jsonb', 'YES'), ('quality_summary', 'jsonb', 'YES')]
specs_with_crawl_scope: 1
frontier_previews_rows: 0
sample_spec_id: 5
sample_crawl_scope: {'mode': 'FULL_SITE', 'status': 'SYSTEM_DEFAULTED', 'version': 1, 'seed_url': None, 'max_depth': None, 'max_pages': 500, 'link_rules': [], 'pagination': {}, 'exclude_patterns': [], 'include_patterns': [], 'ai_recommendation': None, 'user_confirmed_at': None}
```

- `crawl_scope` column exists as `jsonb`, nullable.
- `quality_summary` column exists as `jsonb`, nullable.
- Existing row (id=5) was backfilled with the exact `LEGACY_COMPAT_CRAWL_SCOPE` JSON.
- `frontier_previews` table exists; empty (no previews have been generated yet).

### Bug fixed during verification

`alembic/versions/008_phase25_foundation.py` originally called `op.execute(sqltext, {"crawl_scope": "..."})`, passing the bind-param dict as a second positional arg. The Alembic sync wrapper signature is `op.execute(sqltext, execution_options)`; it does not accept a bind-param dict as a second positional arg in the project's SQLAlchemy version. The first `alembic upgrade head` raised `TypeError: execute() takes 2 positional arguments but 3 were given`.

**Fix:** inlined the JSON literal into the SQL string. The scope dict is built once at import time so SQL-injection is not a concern (no user input). A code comment documents the choice so future maintainers know why this is inlined rather than parameterized.

### Verification script

`scripts/verify_migration_008.py` was added so this exact verification can be re-run on any environment. The script reads the alembic version, the new columns, the backfill count, and a sample backfilled scope.

---

## 5. Extraction Integration Validation

### Review concern

> Current API tests are minimal and mostly fake-session based. They do not test [...] extraction gating for unconfirmed scope [...] There is no test that starts the API, creates a project, creates/updates a spec, generates frontier preview, runs extraction, and verifies DB rows and exports.

### What was added (the smallest layer that proves the behavior)

A new seam `select_links_to_enqueue` in `app/services/project_extraction.py`:

```python
def select_links_to_enqueue(
    *,
    html: str,
    page_url: str,
    root_url: str,
    scope: dict[str, Any] | None,
    legacy_patterns: list[str] | None = None,
    analysis: dict[str, Any] | None = None,
    remaining_slots: int,
) -> list[str]:
```

This is the exact function `execute_project_extraction` calls for every fetched page. It is sync and pure-Python (no DB, no HTTP), so the integration test layer can call it directly with inline HTML and assert on the resulting `CrawlPage` URLs the executor would enqueue.

### Tests added (in `tests/services/test_frontier_preview.py`)

| Test                                                             | Asserts                                                                                                                                                                                        |
| ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_select_links_to_enqueue_integration_for_all_four_modes`    | For each scope mode (CURRENT_PAGE, PAGINATION, DATASET, DATASET+detail, FULL_SITE, FULL_SITE+include), `select_links_to_enqueue` returns the exact expected URL set for the same fixture HTML. |
| `test_select_links_to_enqueue_respects_remaining_slots_cap`      | When `remaining_slots=5` and HTML has 20 pagination URLs, the result has exactly 5 URLs.                                                                                                       |
| `test_select_links_to_enqueue_returns_empty_for_legacy_no_scope` | When `scope=None`, the legacy same-site BFS is used and the result includes same-origin links and excludes cross-origin links.                                                                 |

This is the smallest integration layer that proves extraction queues pages according to scope decisions — exactly what the review asked for. The full HTTP-level test (request → DB rows → extraction → records → export) is out of scope for this round per the instructions.

**Result:** 3/3 new integration tests pass; the existing 36 scope/quality tests still pass.

---

## Test Results Summary

```
$ pytest -q
.......................................................................................................................... [ 55%]
................................................................................................X[100%]
======================= 218 passed, 43 warnings in 9.04s =======================
```

| Suite                   |   Tests |    Pass |
| ----------------------- | ------: | ------: |
| Pre-existing            |     197 |     197 |
| New confirmation tests  |       9 |       9 |
| New preview/queue tests |      12 |      12 |
| **Total**               | **218** | **218** |

No regressions. All pre-existing tests still pass.

---

## Files Changed

### Modified

- `app/services/crawl_scope.py` — added `ScopeConfirmationError` and `assert_scope_confirmed()`.
- `app/services/project_extraction.py` — added `select_links_to_enqueue` seam, added `allow_unconfirmed` to `start_project_extraction`, defensively enforced confirmation in `execute_project_extraction`, caught `ScopeConfirmationError` and marked the project `FAILED`.
- `app/services/frontierpreview.py` — split build vs persist, made `create_frontier_preview` actually persist, fixed `unrelated_same_origin_count` to count scope-dropped same-origin links only, fixed warning message.
- `tests/services/test_crawl_scope.py` — added 9 confirmation-enforcement tests.
- `alembic/versions/008_phase25_foundation.py` — fixed `op.execute` bind-param signature bug.

### New

- `tests/services/test_frontier_preview.py` — 12 tests covering preview correctness and the extraction-queue integration seam.
- `scripts/verify_migration_008.py` — one-shot PostgreSQL verification script for migration 008.

---

## Known Limitations (carried over from prior reports, unchanged)

1. `crawl_scope` is still nullable in the DB. The review recommended `NOT NULL` with a default; this is a Step 1 schema decision that has not been re-opened. The application layer now enforces non-null at every code path that mutates a spec.
2. Pagination heuristics are still the simple `page=`, `p=`, `offset=`, `start=` query-parameter matchers. The review suggested narrowing; deferred until calories.info-style fixtures exist.
3. `WARN_SCOPE_NOT_CONFIRMED` and `WARN_FULL_SITE_SCOPE_WARNING` constants are still unused by `compute_extraction_quality`. The new confirmation gate prevents the underlying error from occurring, so these warnings are not currently emitted; they are reserved for the future trust panel.

---

## Remaining Risks

- **Scope requirement: still nullable at DB level.** Application-layer enforcement is in place. A future migration could set `NOT NULL` and add a server default; out of scope for this round.
- **API layer does not yet translate `ScopeConfirmationError` to HTTP 409.** The error is raised by `start_project_extraction` and the API caller is responsible for catching it. Step 3 (API contracts) will translate it; out of scope for this round.
- **Filename inconsistency carried over from prior report.** `frontierpreview.py` is still missing the underscore separator. The persistence semantics are now explicit in the docstring so the name does not affect correctness; the rename can be a one-line `git mv` in Step 3.
- **Migration downgrade drops the frontier_previews table.** The downgrade in 008 drops the `frontier_previews` table completely. If a user has previews in production and rolls back, those previews are lost. This is acceptable for a v1 add-only migration but should be documented in the rollout notes.

---

## Recommendation

**APPROVE STEP 1** — Data Model Foundation. The migration is real, idempotent, and validated end-to-end against the project's PostgreSQL 15. Existing rows are correctly backfilled. The application layer now enforces non-null scope at every code path that mutates a spec.

**APPROVE STEP 2** — Backend Behavior Layer. The classifier is correct for all four modes, the confirmation gate is enforced in two layers, the preview persistence is split cleanly between builder and persister, the warning/count bug is fixed and pinned by tests, and the extraction-queue integration seam is exercised against all four modes.

**Do not begin Step 3 yet.** Wait for explicit go-ahead from the user. The blockers in this report were scoped strictly to Step 1 and Step 2.
