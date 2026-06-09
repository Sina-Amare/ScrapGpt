# ScrapGPT Status

Last verified: June 9, 2026.

## Implemented

- **Phase 0 — Security fixes:**
  - Rate-limit keying verifies JWT signatures.
  - Refresh-token endpoint is rate limited.
  - Watchdog transitions guard expected states.
  - Ownership mismatches do not mutate another user's task.

- **Phase 0.5 — BYOK provider foundation:**
  - Old credit columns and `system_state` were removed.
  - BYOK provider configs are stored per user with Fernet-encrypted API keys.
  - Normal provider responses never return keys; reveal requires password confirmation.

- **Frontend v0:**
  - React/Vite app with auth, protected routes, provider management, health, legacy scrape, dashboard, jobs, and project screens.
  - Access tokens are in memory; refresh tokens are stored locally.
  - Provider key reveal is password-confirmed and not cached client-side.

- **Phase 1 — Analysis jobs:**
  - Project-based workflow with `projects` as the primary entity. `/jobs` is a thin compat API.
  - SSRF-safe URL validation with per-redirect checking.
  - `robots.txt` checks with TTL cache and configurable failure policy.
  - Static fetcher (httpx) + optional Playwright browser rendering, including Windows Uvicorn selector-loop handling.
  - DOM summary builder (10,000-character cap with repeated container samples, table samples, `data-*` attributes).
  - Cached LLM analysis for structured datasets and content/RAG extraction.
  - Job admission with provider preflight, active-job limit, and per-user advisory lock.
  - Project API: analyze, list, detail, spec patch, preview, extract, records, export, cancel, delete.
  - Project workflow tables: `extraction_specs`, `preview_results`, `crawl_pages`, `extracted_records`, `exports`.

- **Phase 2 — Real extraction engine:**
  - Preview executes saved CSS selectors against the seed page (real HTTP, not AI sample values).
  - Same-site BFS crawl with per-page state persistence and bounded retries.
  - Deterministic CSS extraction groups records by `repeated_item_selector` with index-based fallback.
  - Content extraction stores selected primary content text plus selected metadata fields.
  - Results exported as CSV, JSON, or XLSX.
  - Page-state progress counts visible in project workspace.

- **Phase 2.5 — Crawl scope, frontier preview, and extraction trust:**
  - **Crawl scope** (`CrawlScope` JSONB on `ExtractionSpec`) — four modes: `CURRENT_PAGE`, `PAGINATION`, `DATASET`, `FULL_SITE`.
  - **Scope confirmation gate** — non-`CURRENT_PAGE` scopes require `status = USER_CONFIRMED` before extraction; HTTP 409 `SCOPE_NOT_CONFIRMED` otherwise.
  - **Frontier preview** — `POST /projects/{id}/frontier-preview` classifies seed-page links by scope mode; shows included/excluded URLs with reason codes; preview and extraction share the same classifier.
  - **Extraction quality** — per-field success/missing rates, warning codes, and overall quality label (`good`/`needs_review`/`risky`) persisted as `quality_summary` on the spec.
  - **Server-side paginated results** — `GET /projects/{id}/records-page` with `total`, `has_more`, `next_skip`, `columns`; max 500 records/page.
  - **Frontend UX layer**: `ScopeSelector`, `FrontierPreviewPanel`, `TrustSummaryPanel`, `PaginatedResultsTable`; scope confirmation flow; 409 error handling; safety limit rename; export format moved to Results.
  - All 8 E2E validation scenarios passing (see `docs/reviews/03_phase25_validation.md`).

## Current Primary Workflow

1. Start backend and frontend.
2. Register or log in.
3. Add a provider in Providers.
4. Submit a URL from New Extraction. Choose "Rows in a table" or "Content for knowledge base".
5. Watch the project move through analysis.
6. Open the project workspace when it is ready.
7. Choose crawl scope ("This page only", "This list across pages", "This dataset", "The whole site").
8. Generate a frontier preview to see which URLs will be crawled.
9. Confirm scope for any non-current-page mode.
10. Select fields and run Preview to inspect real selector output from the seed page.
11. Run Extract to crawl approved pages, execute saved selectors, and persist records.
12. Inspect Results and download CSV, JSON, or XLSX.

The older Legacy Scrape page still exists for the `/scrape` pipeline, but it is no longer the primary product flow.

## Not Implemented Yet

- Visual field selection (click-to-extract, iframe seed page, CSS path generator).
- SSE live progress stream (`/projects/{id}/stream`).
- Concurrent crawler workers and durable lease-based crash recovery.
- Template routing, DOM fingerprinting, and selector repair.
- File-backed export storage beyond streamed CSV/JSON/XLSX responses.
- Authenticated-content browser sessions.
- Per-page retry endpoint (`POST /projects/{id}/pages/{page_id}/retry`).
- Rich DOM summary (microdata, full JSON-LD, multi-sample containers) — `ANALYZER_VERSION` still `"1"`.
- Watchdog sweep for projects stuck in `DISCOVERING/EXTRACTING/EXPORTING` states.
- Docker/docker-compose one-command setup.
- CAPTCHA solving, stealth browser patches, proxy evasion, or challenge bypass (permanent non-goals).

## Known Issues

- **Legacy `/scrape` pipeline is SSRF-vulnerable.** `app/services/scraper.py` fetches user-supplied URLs without SSRF validation. Mitigation: add `validate_url()` call in `app/api/v1/endpoints/scrape.py`, or remove the legacy pipeline before public deployment.
- **`CrawlPage.lease_expires_at` is written but never swept.** A process crash mid-extraction leaves pages in `FETCHING` indefinitely. The watchdog reaper for crawl page leases is not yet implemented.
- **CORS default missing Vite dev origin.** Add `http://localhost:5173` to `CORS_ORIGINS` in `.env` for local frontend development.

## Verification Snapshot

Commands last run successfully:

```bash
# Backend
venv\Scripts\python.exe -m pytest -q

# Frontend
cd frontend
npm.cmd test
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
```

Results:

- Backend: **237 passed**, 43 warnings.
- Frontend tests: **70 passed**.
- Frontend typecheck, lint, and production build: passed.

E2E validation:

```bash
venv\Scripts\python.exe tests/validation/run_validation.py
```

Result: **8/8 scenarios PASSED** (see `docs/reviews/03_phase25_validation.md`).
