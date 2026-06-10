# Reliability Hardening Final Report

Date: 2026-06-10

Scope: smallest safe fixes for the remaining blockers from `docs/RELIABILITY_HARDENING_REVIEW.md`.

## Final Recommendation

**APPROVE**

The review blockers have been resolved:

- Extraction finalization no longer overwrites `FAILED`, `CANCELED`, `COMPLETED`, or other terminal project states.
- Legacy `/scrape` no longer follows redirects automatically; each redirect target is validated before being followed.
- Behavioral tests now exercise the real extraction executor finalization path and legacy scrape redirect handling.

## What Changed

### Extractor Finalization Guard

Updated `app/services/project_extraction.py`:

- The all-pages-failed branch now only writes `ALL_PAGES_FAILED` if the project is not already terminal.
- The normal finalization path now returns early when the project is terminal.
- Removed the unsafe fallback that forced `project.state = ProjectState.EXPORTING` when no legal transition existed.
- Added a warning log for non-terminal states that cannot legally proceed to `EXPORTING`.

Why this fixes the blocker:

- If the watchdog marks a project `FAILED` while extraction is still running, the extractor now sees `project.is_terminal` and exits.
- The model state machine is no longer bypassed from `FAILED` to `EXPORTING` or `COMPLETED`.

### Legacy Scrape Redirect SSRF Closure

Updated `app/services/scraper.py`:

- Changed `httpx.AsyncClient(..., follow_redirects=True)` to `follow_redirects=False`.
- Added a manual redirect loop bounded by `settings.MAX_REDIRECTS`.
- Each redirect `Location` is passed through `validate_redirect_target()` before the next request.
- Redirects to loopback/private/metadata targets now raise `ScrapeError` before any request is made to the blocked target.

Why this fixes the blocker:

- Initial endpoint/executor validation no longer needs to carry all SSRF protection alone.
- A public URL that redirects to `http://127.0.0.1/...` or another blocked address is stopped before the second fetch.

### Behavioral Tests

Updated `tests/services/test_reliability_hardening.py`:

- Added a real-path executor test for all-pages-failed finalization through `execute_project_extraction()`.
- Added a real-path executor race test where the project becomes `FAILED` before finalization; it verifies the project remains `FAILED` and no export is created.

Updated `tests/services/test_scraper.py`:

- Added a public redirect success test.
- Added a private-address redirect block test.

### Documentation

Updated only current-state documentation that became inaccurate after closing redirect SSRF:

- `docs/STATUS.md`
- `docs/learning/12_reliability_hardening.md`
- `CLAUDE.md`

These now state that legacy `/scrape` has endpoint, executor, and redirect-hop URL validation.

## Test Results

Targeted scraper tests:

```powershell
venv\Scripts\python.exe -m pytest tests\services\test_scraper.py -q
```

Result: `14 passed, 7 warnings`.

Reliability hardening tests:

```powershell
venv\Scripts\python.exe -m pytest tests\services\test_reliability_hardening.py -q
```

Result: `16 passed, 3 warnings`.

Broader reliability slice:

```powershell
venv\Scripts\python.exe -m pytest tests\services\test_reliability_hardening.py tests\services\test_scraper.py tests\api\v1\test_scrape_tasks.py tests\services\test_url_validator.py tests\services\test_project_workflow.py tests\core\test_scheduler.py -q
```

Output result: `65 passed, 12 warnings`.

Full backend suite:

```powershell
venv\Scripts\python.exe -m pytest tests\ -q
```

Output result: `366 passed, 46 warnings`.

Important note: for the broader reliability slice and full backend suite, the command output showed all tests passing, but the shell tool reported exit code `1`. The same exit-code mismatch existed before these final fixes. No pytest failure or error was present in the output.

## Remaining Risks

- DNS rebinding remains a known limitation of DNS-time URL validation. Full mitigation requires network egress controls or IP-pinned transport.
- Legacy `/scrape` is still a compatibility path and remains simpler than the project pipeline; it now validates redirect hops, but it does not have the full fetcher feature set.
- Lease recovery is still fail-and-retry recovery, not automatic durable job resume.
- The live Phase 2.5 E2E validation harness was not run in this pass because of the reported local `.env` issue. Backend unit/integration coverage was run instead.
- The pytest exit-code mismatch should be investigated in CI or the local test wrapper, even though pytest output reports passing tests.
