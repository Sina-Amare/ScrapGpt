# ScrapGPT Status

Last verified: June 8, 2026.

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
  - Fluid grid layout with correct boundary constraints for form fields and scrolling dialogs.
- Phase 1 analysis jobs:
  - Project-based workflow foundation with `projects` replacing the old `jobs` table.
  - `/jobs` remains as a temporary compatibility API over the same project rows.
  - `analysis_cache` remains unchanged.
  - SSRF-safe URL validation.
  - `robots.txt` checks with TTL cache and configurable failure policy.
  - Static fetcher with per-redirect validation.
  - Optional Playwright browser rendering, including Windows Uvicorn selector-loop handling.
  - DOM summary builder.
  - Cached LLM analysis for structured datasets and content/RAG-style extraction.
  - Job admission with provider preflight, active-job limit, and per-user advisory lock.
  - Job executor with always-finalize failure handling.
  - Compatibility Jobs API: create, list, detail, cancel, delete.
  - Project API:
    - `POST /projects/analyze`
    - `GET /projects`
    - `GET /projects/{id}`
    - `PATCH /projects/{id}/spec`
    - `POST /projects/{id}/preview`
    - `POST /projects/{id}/extract`
    - `GET /projects/{id}/records`
    - `GET /projects/{id}/export`
    - `POST /projects/{id}/cancel`
    - `DELETE /projects/{id}`
  - Project workflow tables:
    - `extraction_specs`
    - `preview_results`
    - `crawl_pages`
    - `extracted_records`
    - `exports`
  - Frontend project workflow:
    - Projects list.
    - New Extraction URL-first form.
    - Advanced drawer for mode/render/provider overrides.
    - Project workspace with Overview, Fields, Preview, Extraction, Results, and Advanced sections.
    - `/jobs` frontend routes redirect to `/projects`.
- Phase 2 real extraction engine:
  - DOM summary now includes richer repeated-container samples, table samples, data attributes, up to 15 repeated classes, and a 10,000-character cap.
  - Preview executes saved CSS selectors against the seed page instead of showing AI sample values.
  - Extraction runs as a background project task after `POST /projects/{id}/extract`.
  - Same-site links are discovered from fetched HTML and normalized with tracking parameters stripped.
  - Crawl execution is bounded by the saved spec `page_limit` and `MAX_PAGES_PER_JOB`.
  - Every crawled URL is persisted in `crawl_pages` with page-level states: pending, fetching, extracted, blocked, or failed.
  - Extracted records are produced by deterministic selector execution and stored in `extracted_records`.
  - Structured extraction groups records by the AI-provided `repeated_item_selector` when available, with index-based extraction as fallback.
  - Content extraction stores the selected primary content text plus selected metadata fields.
  - Results can be exported as CSV, JSON, or XLSX.
  - The project workspace shows page-limit/export controls and page-state progress counts.

## Current Primary Workflow

1. Start backend and frontend.
2. Register or log in.
3. Add a provider in Providers.
4. Submit a URL from New Extraction.
5. Watch the project move through analysis.
6. Open the project workspace when it is ready.
7. Select fields and edit user-facing field labels.
8. Run Preview to inspect real selector output from the seed page.
9. Run Extract to crawl same-site pages, execute saved selectors, and persist real records.
10. Inspect Results and download CSV, JSON, or XLSX through the export endpoint.

The older Legacy Scrape page still exists for the `/scrape` pipeline, but it is no longer the primary product flow.

## Not Implemented Yet

- Visual field selection.
- Concurrent crawler workers and lease-based resume after process crash.
- Template routing, DOM fingerprinting, and selector repair.
- File-backed export storage beyond streamed CSV/JSON/XLSX responses.
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

- Backend: 161 passed.
- Frontend tests: 31 passed.
- Frontend typecheck, lint, and production build: passed.
