# 12 — Reliability Hardening (Phase 2.5 Closeout)

**Date:** June 10, 2026
**Branch:** `feature/reliability-hardening` (from `feature/logging-observability` checkpoint `91ee6ee`)
**Plan:** `plans/reliability_hardening_plan.md`

---

## Purpose

Close the remaining reliability and extraction-hardening gaps identified during the engineering review process. Focus on current-system correctness and crash recovery. No Phase 3 features.

---

## What Was Implemented

### Item 1: Fix Legacy `/scrape` SSRF Vulnerability

**Problem:** `app/services/scraper.py` fetched user-supplied URLs without calling `validate_url()`. The `/scrape/start` endpoint only validated with Pydantic `HttpUrl`, which does not block private-network IPs.

**Solution:** Defense-in-depth approach:

- **Endpoint level** (`app/api/v1/endpoints/scrape.py`): Added `validate_url()` before task creation. Returns HTTP 400 with `error_code` immediately, giving the user feedback without creating a task.
- **Executor level** (`app/services/task_executor.py`): Added Phase 0 (SSRF validation) and Phase 0.5 (robots.txt check) before Phase 1 (transition to SCRAPING). Uses `validated_url` for the scrape call instead of the raw URL. This catches any URLs stored before the endpoint check was added.
- **Redirect level** (`app/services/scraper.py`): The legacy scraper now disables automatic redirects and validates each `Location` target before following it.

**Design decision:** Keep the legacy scraper changes narrow. It still performs simple HTML fetch/extract behavior, but redirect following now uses the same redirect-target validator as the project fetcher.

**Files changed:**

- `app/api/v1/endpoints/scrape.py` — added `validate_url()` import and call before task creation
- `app/services/task_executor.py` — added Phase 0 (SSRF) and Phase 0.5 (robots) before scraping

---

### Item 2: CrawlPage Lease Reaper

**Problem:** `CrawlPage.lease_expires_at` was written when a worker claimed a page (FETCHING state) but never swept. A process crash mid-extraction left pages in FETCHING indefinitely, blocking the project forever.

**Solution:** Added `cleanup_expired_crawl_page_leases()` to `app/services/watchdog.py`. Finds pages where `state == FETCHING AND lease_expires_at < now()` and resets them to `PENDING` with `lease_expires_at = None` and `error = None`. Only operates on pages within projects in active extraction states (DISCOVERING, EXTRACTING).

**Ownership boundary:** The lease reaper is page-level recovery. It resets individual pages so they can be retried. The stuck-project watchdog (item 3) handles project-level recovery.

**Files changed:**

- `app/services/watchdog.py` — added `cleanup_expired_crawl_page_leases()`

---

### Item 3: Stuck-Project Watchdog

**Problem:** Projects stuck in DISCOVERING, EXTRACTING, or EXPORTING had no recovery mechanism. A crashed extraction background task left the project in a non-terminal active state forever.

**Solution:** Added `cleanup_stuck_projects()` to `app/services/watchdog.py` with configurable timeouts per state. Uses atomic SQLAlchemy `update()` statements with WHERE-clause state guards (same concurrency-safety pattern as `expected_states` guards in task/job transition functions, but applied at the SQL level for projects which have no dedicated transition function).

**Critical bug found and fixed:** The initial implementation incorrectly called `transition_job_to_failed()` (a Job-state function) with `project.id` and `ProjectState` values. This would have queried the `jobs` table by project ID and checked `JobState` enums against `ProjectState` enums — a type mismatch that would fail at runtime. Fixed by using atomic `update()` statements instead.

**Config settings added:**

- `WATCHDOG_PROJECT_DISCOVERING_TIMEOUT_MINUTES` (default: 10)
- `WATCHDOG_PROJECT_EXTRACTING_TIMEOUT_MINUTES` (default: 60)
- `WATCHDOG_PROJECT_EXPORTING_TIMEOUT_MINUTES` (default: 10)

**Files changed:**

- `app/services/watchdog.py` — added `cleanup_stuck_projects()`, removed unused `ACTIVE_PROJECT_STATES` import
- `app/core/config.py` — added three watchdog timeout settings

---

### Item 4: Extraction Completion Semantics (All-Pages-Failed)

**Problem:** If all crawled pages failed or were blocked, `execute_project_extraction()` still transitioned the project through EXPORTING to COMPLETED with zero records. This was misleading — the user saw "Completed" but got nothing.

**Solution:** After the crawl loop, count pages in EXTRACTED state. If `pages_extracted == 0 AND total_records == 0`, transition to FAILED with `error_code = "ALL_PAGES_FAILED"` instead of COMPLETED.

**Edge case analysis:**

- `pages_extracted == 0, total_records == 0` → FAILED (`ALL_PAGES_FAILED`) — clear failure
- `pages_extracted > 0, total_records == 0` → COMPLETED with poor quality — the spec doesn't match the content, but this is a quality issue, not a hard failure. The existing quality computation already surfaces this.
- `pages_extracted > 0, total_records > 0` → normal COMPLETED with quality assessment

**Files changed:**

- `app/services/project_extraction.py` — added all-pages-failed check after crawl loop

---

### Item 5: CORS Vite Dev Origin

**Problem:** Default `CORS_ORIGINS` was `http://localhost:3000,http://localhost:8000`. Vite dev server runs on `http://127.0.0.1:5173`. Every new developer had to manually add this.

**Solution:** Added `http://127.0.0.1:5173` to the default `CORS_ORIGINS` string in `app/core/config.py`. `.env.example` already had this origin.

**Files changed:**

- `app/core/config.py` — updated `CORS_ORIGINS` default

---

### Item 6: CRAWL_CONCURRENCY Clarification

**Problem:** `CRAWL_CONCURRENCY` existed in settings but the executor was sequential. This could mislead operators.

**Solution:** Updated the description field to clarify it's reserved for future concurrent worker implementation.

**Files changed:**

- `app/core/config.py` — updated `CRAWL_CONCURRENCY` description

---

## Invariants

- User-scoped resources are always owner-checked before read or mutation (unchanged).
- Provider API keys are encrypted at rest and never returned in normal responses (unchanged).
- No credit system exists (unchanged).
- Project extraction must not silently broad-crawl new projects (unchanged).
- **New:** Projects where all pages fail must transition to FAILED, not COMPLETED with zero records.
- **New:** CrawlPage leases must be swept by the watchdog to prevent indefinite FETCHING states.
- **New:** Projects stuck in extraction states beyond their timeout must be failed by the watchdog.

---

## Design Decisions

1. **Defense-in-depth for SSRF:** Endpoint validates for immediate user feedback; executor validates for crash recovery and robots check. Both use the same `validate_url()` function.

2. **Atomic UPDATE for stuck-project watchdog:** Projects have no dedicated transition function (unlike tasks and jobs). Using `update()` with WHERE-clause state guards provides the same concurrency safety as `expected_states` guards without requiring a new transition function.

3. **Lease reaper scope:** Only resets pages in active projects (DISCOVERING/EXTRACTING). Pages in completed/failed/canceled projects are not touched — they're already terminal.

4. **All-pages-failed vs partial success:** The FAILED transition only applies when zero pages were successfully processed. Partial success (some EXTRACTED, some FAILED/BLOCKED) still completes normally with quality assessment. This preserves the per-page failure isolation invariant while fixing the misleading zero-record COMPLETED case.

5. **CRAWL_CONCURRENCY description:** Marked as "Reserved for future use" rather than removing it, because the setting will be needed when concurrent workers are implemented (Phase 3+).

---

## Failure Paths

- **SSRF validation fails at endpoint:** HTTP 400 with `error_code` and human-readable message. No task created.
- **SSRF validation fails at executor:** Task transitions to FAILED with the validation error message. No scrape attempted.
- **Robots.txt blocks at executor:** Task transitions to FAILED with robots reason. No scrape attempted.
- **Lease expires mid-extraction:** Watchdog resets page to PENDING on next sweep (within 60 seconds). If the project's background task is still running, the page will be retried on the next loop iteration. If the task has crashed, the stuck-project watchdog will fail the project.
- **Background task crashes during extraction:** Stuck-project watchdog fails the project after the configured timeout (10/60/10 minutes for DISCOVERING/EXTRACTING/EXPORTING).
- **All pages fail during extraction:** Project transitions to FAILED with `ALL_PAGES_FAILED` error code. Per-page failure details are preserved on each CrawlPage row for debugging.

---

## Safe-Evolution Notes

- Legacy scraper redirect targets are now validated before being followed.
- `CRAWL_CONCURRENCY` will be used when concurrent workers are implemented. The description should be updated at that time.
- The watchdog timeout defaults (10/60/10 minutes) are tuned for single-instance self-hosted deployment. Multi-worker deployment may need different timeouts.
- The lease reaper runs at 60-second intervals. For multi-worker deployment with higher concurrency, a 30-second interval may be appropriate (as suggested in the strategic redesign).
- The all-pages-failed check could be extended with a "low yield" quality warning (e.g., fewer records than expected relative to pages crawled), but this is a quality reporting enhancement, not a reliability fix.

---

## Test Results

- **New tests:** 14 tests in `tests/services/test_reliability_hardening.py`
  - 2 SSRF endpoint rejection tests (private IP, loopback)
  - 1 SSRF endpoint acceptance test (valid public URL)
  - 1 executor SSRF defense-in-depth test
  - 2 scraper redirect validation tests
  - 2 lease reaper tests (expired reset, inactive project skip)
  - 2 stuck-project watchdog tests (DISCOVERING, EXTRACTING)
  - 2 extraction completion semantics tests (all-failed, partial success)
  - 4 config tests (CORS origin, CRAWL_CONCURRENCY description, watchdog timeout defaults, watchdog timeout field info)

- **Backend full suite:** 362 passed, 0 failed, 3 warnings
- **Frontend full suite:** 70 passed, 0 failed

---

## What Changed From the Original Plan

1. **Stuck-project watchdog implementation:** The plan suggested using `transition_job_to_failed()` with `expected_states` guards. During implementation, I discovered this was a type mismatch — `transition_job_to_failed()` operates on the `jobs` table with `JobState` enums, not the `projects` table with `ProjectState` enums. Fixed by using atomic `update()` statements with WHERE-clause state guards instead.

2. **SSRF fix scope:** The first implementation added endpoint and executor validation. Final approval fixes also added per-redirect validation in `scraper.py` to close public-to-private redirect SSRF.

3. **Ownership boundaries:** The plan mentioned documenting ownership boundaries between lease recovery and watchdog recovery. This is now documented in the watchdog.py module docstring and in this learning doc.

4. **Extraction completion edge cases:** Per the user's implementation note, I evaluated additional edge cases. The all-pages-failed check only triggers when `pages_extracted == 0 AND total_records == 0`. Partial success (some pages extracted, zero records from selectors) still completes normally — this is a quality issue, not a hard failure. The existing quality computation already surfaces this through `quality_summary`.
