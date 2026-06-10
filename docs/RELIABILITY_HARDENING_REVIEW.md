# Reliability Hardening Review

Date: 2026-06-10

Scope: independent technical review of the reliability hardening implementation on `feature/reliability-hardening`. I treated the implementation report, commit messages, and claimed test results as untrusted. Code is the source of truth.

## Verdict

**APPROVE WITH CHANGES**

Most hardening goals are implemented and covered by focused tests, but two issues remain important enough to require follow-up before calling the reliability pass fully complete:

1. The stuck-project watchdog can mark a project `FAILED` while an in-flight extractor later forces that same project through `EXPORTING` to `COMPLETED`.
2. The legacy `/scrape` SSRF fix validates the initial URL but still does not validate redirect targets inside `scraper.py`, which uses `follow_redirects=True`.

## Validation Run

Commands run:

```powershell
venv\Scripts\python.exe -m pytest tests\services\test_reliability_hardening.py -q
venv\Scripts\python.exe -m pytest tests\api\v1\test_scrape_tasks.py tests\services\test_url_validator.py tests\services\test_project_workflow.py tests\core\test_scheduler.py -q
venv\Scripts\python.exe -m pytest tests\ -q
cd frontend; npm.cmd test
cd frontend; npm.cmd run typecheck
cd frontend; npm.cmd run lint
cd frontend; npm.cmd run build
```

Observed results:

- Reliability tests: `14 passed`.
- Adjacent scrape/project/scheduler tests: `35 passed`.
- Full backend pytest output: `362 passed, 45 warnings`, but the shell tool reported exit code `1` despite no pytest failures or errors in output.
- Frontend tests: `70 passed`.
- Frontend typecheck, lint, and production build passed.

Note: a combined targeted pytest command also printed `49 passed` while returning exit code `1`. I did not find a failing test in the output.

## VERIFIED Findings

### Legacy `/scrape` Initial URL Validation

`POST /scrape/start` now calls `validate_url()` before task admission and returns HTTP 400 with `error_code` on blocked URLs. Evidence: `app/api/v1/endpoints/scrape.py:36`, `app/api/v1/endpoints/scrape.py:98`.

The executor also validates the stored task URL before transitioning to `SCRAPING`, so old/pre-existing rows are protected at start time. Evidence: `app/services/task_executor.py:60`.

### Legacy `/scrape` Robots Check

The executor calls `check_robots()` before scraping and fails the task if robots blocks or is unavailable under deny policy. Evidence: `app/services/task_executor.py:78`.

### CrawlPage Lease Reaper Exists

`cleanup_expired_crawl_page_leases()` resets expired `FETCHING` pages to `PENDING`, clears `lease_expires_at`, and only considers projects in `DISCOVERING` or `EXTRACTING`. Evidence: `app/services/watchdog.py:258`, `app/services/watchdog.py:293`, `app/services/watchdog.py:300`, `app/services/watchdog.py:306`.

The scheduled watchdog path now calls the lease reaper. Evidence: `app/services/watchdog.py:489`; scheduler continues to run the single `watchdog_cleanup` job via `run_watchdog_once()` in `app/core/scheduler.py:28`.

### Stuck Project Watchdog Exists

`cleanup_stuck_projects()` updates stale `DISCOVERING`, `EXTRACTING`, and `EXPORTING` projects to `FAILED` with `EXTRACTION_FAILED`. Evidence: `app/services/watchdog.py:330`, `app/services/watchdog.py:370`, `app/services/watchdog.py:411`, `app/services/watchdog.py:451`.

The updates include state predicates in the SQL `WHERE` clauses, so a project that has already moved out of that state will not be overwritten by that specific update.

### Extraction All-Failed Semantics

`execute_project_extraction()` now counts `EXTRACTED` crawl pages after the crawl loop. If `pages_extracted == 0` and `total_records == 0`, it marks the project failed with `ALL_PAGES_FAILED`. Evidence: `app/services/project_extraction.py:412`, `app/services/project_extraction.py:420`, `app/services/project_extraction.py:429`.

This covers fetch failures, URL validation failures, and robots-blocked pages because those paths never set a page to `EXTRACTED`.

### Config and Docs Updates

Default CORS origins include `http://127.0.0.1:5173`. Evidence: `app/core/config.py:86`.

`CRAWL_CONCURRENCY` is described as reserved for future use. Evidence: `app/core/config.py:110`.

`docs/STATUS.md` and `docs/learning/12_reliability_hardening.md` describe the new reliability behavior. The broad direction is accurate.

## PARTIALLY VERIFIED Findings

### Legacy `/scrape` SSRF Safety Is Improved, Not Complete

Initial URL validation and executor defense-in-depth are real. However, `scraper.py` still performs the actual network fetch with `httpx.AsyncClient(follow_redirects=True)` and does not validate each redirect hop. Evidence: `app/services/scraper.py:42`, `app/services/scraper.py:44`.

That means a public URL that redirects to a private or metadata address can still be followed by the legacy scraper after the initial URL passes validation. The project pipeline avoids this by using `follow_redirects=False` and validating redirect targets manually in `fetcher.py`. Evidence: `app/services/fetcher.py:100`, `app/services/fetcher.py:123`.

This is not merely a deferred improvement; it leaves a known SSRF class open in the legacy route.

### Lease Recovery Is Page-Level Only

The page-level reaper works as written, but it does not restart a dead extraction task. The new stuck-project watchdog marks long-stuck projects failed. That is a valid recovery strategy, but it means the reset pages are mainly useful for a future manual re-extraction path, not automatic resume.

This is acceptable if documented as "fail and allow restart", but it is not durable crash resume.

### Tests Cover the Shape, Not the Full Behavior

The new reliability tests cover endpoint rejection, executor defense-in-depth, lease reaper mutation, watchdog rowcount handling, config defaults, and simplified all-pages-failed logic.

However, the all-pages-failed tests do not execute `execute_project_extraction()`; they assert a local reproduction of the condition. Evidence: `tests/services/test_reliability_hardening.py:481`.

The watchdog tests use fake `execute()` rowcounts, so they do not verify the generated SQL predicates against real model state or the interaction between watchdog and extractor sessions. Evidence: `tests/services/test_reliability_hardening.py:375`, `tests/services/test_reliability_hardening.py:429`.

## INCORRECT Findings

### The Report's "Correct and Complete Legacy SSRF Fix" Claim Is Too Strong

The implementation report says modifying `scraper.py` for per-redirect validation was deferred and implies endpoint plus executor validation is enough. It is not enough to close redirect-based SSRF because the actual fetch still follows redirects automatically.

Impact: an attacker-controlled public URL can pass `validate_url()` and then redirect the legacy scraper to a blocked internal target.

### The Report's "Concurrency Safety" Claim Is Incomplete

The watchdog uses state guards when it marks stale projects failed, but the extractor finalization path can overwrite a concurrently failed project.

Problem path:

- Watchdog updates an old `EXTRACTING` project to `FAILED`.
- A still-running `execute_project_extraction()` later reloads the project.
- It only returns early for missing or `CANCELED` projects.
- If state is `FAILED`, it falls into the fallback branch and forcibly sets `project.state = ProjectState.EXPORTING`.
- It then calls `project.transition_to(ProjectState.COMPLETED)`.

Evidence: `app/services/project_extraction.py:441`, `app/services/project_extraction.py:444`, `app/services/project_extraction.py:445`, `app/services/project_extraction.py:448`, `app/services/project_extraction.py:506`.

This violates state machine integrity because `FAILED` has no valid transition to `EXPORTING` or `COMPLETED`. Evidence: `app/models/job.py:154`. The fallback assignment bypasses `transition_to()`.

### Documentation Overstates Current Verification

`docs/STATUS.md` says E2E validation is `8/8 scenarios PASSED` as current status. Evidence: `docs/STATUS.md:127`. I did not run the validation harness in this review. The historical report exists, but the reliability pass changed extraction and legacy scrape behavior. Treat that statement as historical unless the harness is rerun on this branch.

## Newly Discovered Risks

### Watchdog Can Create False Failure and Then Be Overwritten

The timeout-based stuck-project watchdog has no heartbeat/progress timestamp beyond `updated_at`. During a very slow but valid extraction, `updated_at` may not change while the project remains `EXTRACTING`, because per-page commits update `CrawlPage`, not necessarily `Project`. A long crawl can be marked failed after the timeout even while work continues.

That risk is amplified by the overwrite bug above: the final state may end up `COMPLETED` even after the watchdog recorded failure, or fail then complete with mixed error/export rows.

### Reaped Pages Can Be Duplicated by a Live Worker

If a page's 5-minute lease expires while the original worker is still fetching, the reaper can reset it to `PENDING`. In a future concurrent worker setup, another worker could pick it up while the first worker is still alive. Current extraction is sequential, so this is less likely today, but the recovery design should not assume expired lease equals dead worker without a heartbeat.

### Robots Check Added to Legacy `/scrape` May Be a Behavior Change

The legacy pipeline now fails tasks when robots is unavailable under the default deny policy. That aligns with the project pipeline, but it may cause legacy scrape tasks that previously succeeded to fail if a site blocks or redirects `/robots.txt`. This is probably intended, but it should be treated as a user-visible behavior change.

### Test Result Reporting Needs Care

The backend test output shows all tests passing but the shell tool returned exit code `1` twice. This may be a local/tooling artifact, but it means automated status should not be summarized simply as "clean green" without investigating the exit-code mismatch in CI.

## Approval Recommendation

**APPROVE WITH CHANGES**

Required changes before full approval:

1. Prevent extractor finalization from overwriting `FAILED` or other terminal states. The extractor should not bypass `transition_to()` from `FAILED` to `EXPORTING`.
2. Close the legacy `/scrape` redirect SSRF gap or explicitly disable redirects in the legacy scraper.
3. Add behavioral tests that execute the real extraction finalization path for all-pages-failed and for "project became FAILED while extractor was running".

Recommended follow-up:

- Clarify docs that current recovery is fail-and-retry, not automatic durable resume.
- Rerun the live Phase 2.5 validation harness on this branch after the `.env` issue is fixed.
- Add a focused test for legacy scrape public-to-private redirect handling.
