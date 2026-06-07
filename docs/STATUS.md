# ScrapGPT Status

Last verified: June 7, 2026.

## Implemented

- Phase 0 security fixes:
  - Rate-limit keying verifies JWT signatures.
  - Refresh-token endpoint is rate limited.
  - Watchdog transitions guard expected states.
  - Ownership mismatches do not mutate another user's task.
- Phase 0.5 provider foundation:
  - Old credit columns and `system_state` were removed.
  - BYOK provider configs are stored per user.
  - Provider API keys are Fernet-encrypted at rest.
  - Normal provider responses never return keys.
  - Explicit key reveal requires password confirmation.
- Frontend v0:
  - React/Vite app with auth, protected routes, provider management, health, legacy scrape, dashboard, jobs, and new analysis screens.
  - Access tokens are in memory; refresh tokens are stored locally.
  - Provider key reveal is password-confirmed and not cached client-side.
- Phase 1 analysis jobs:
  - `jobs` and `analysis_cache` tables.
  - SSRF-safe URL validation.
  - `robots.txt` checks with TTL cache and configurable failure policy.
  - Static fetcher with per-redirect validation.
  - Optional Playwright browser rendering, including Windows Uvicorn selector-loop handling.
  - DOM summary builder.
  - Cached LLM analysis for structured datasets and content/RAG-style extraction.
  - Job admission with provider preflight, active-job limit, and per-user advisory lock.
  - Job executor with always-finalize failure handling.
  - Jobs API: create, list, detail, cancel, delete.
  - Jobs frontend: create analysis job, poll status, list jobs, inspect analysis, hide advanced selector/raw details by default.

## Current Primary Workflow

1. Start backend and frontend.
2. Register or log in.
3. Add a provider in Providers.
4. Submit a URL from New Analysis.
5. Watch the job move from `QUEUED` to `ANALYZING`.
6. Inspect the terminal analysis result:
   - `ANALYSIS_READY` for high-confidence FAST results with no warnings.
   - `AWAITING_SETUP` for complete analysis that will need the future setup/review phase.
   - `FAILED` or `CANCELED` for terminal failure/cancel cases.

The older Legacy Scrape page still exists for the `/scrape` pipeline, but it is no longer the primary product flow.

## Not Implemented Yet

- Visual field selection.
- Review/approve/edit extraction setup.
- `POST /jobs/{id}/start`.
- Multi-page crawl execution.
- Record extraction table.
- Export pipeline.
- Authenticated-content browser sessions.
- CAPTCHA solving, stealth browser patches, proxy evasion, or challenge bypass.

## Verification Snapshot

Commands last run successfully:

```bash
venv\Scripts\python.exe -m pytest -q
cd frontend
npm test
npm run typecheck
npm run lint
npm run build
```

Results:

- Backend: 152 passed.
- Frontend tests: 31 passed.
- Frontend typecheck, lint, and production build: passed.
- Browser render smoke with Windows selector event loop: passed for `https://example.com`.

