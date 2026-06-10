# CLAUDE.md

Guidance for Claude Code and other coding agents working in this repository.

## Project

ScrapGPT is a self-hosted, BYOK AI-assisted web data extraction platform. The primary product workflow is:

`URL -> Understand Data -> Choose Fields -> Preview -> Extract -> Results`

The current implementation includes Phase 2.5 (crawl-scope, frontier-preview, trust-signal, paginated-results) and structured logging with correlation IDs. Read `docs/STATUS.md` for the current runnable surface and `docs/product/strategic_redesign.md` for the forward roadmap.

## Commands

PowerShell on Windows; a venv normally lives in `venv/`.

```powershell
# Activate venv
.\venv\Scripts\activate

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..

# Run backend dev server
venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Run frontend dev server
cd frontend
npm.cmd run dev

# Backend tests
venv\Scripts\python.exe -m pytest -q

# Frontend checks
cd frontend
npm.cmd test
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build

# Phase 2.5 validation harness
venv\Scripts\python.exe tests\validation\run_validation.py

# Migrations
alembic upgrade head
alembic downgrade -1
alembic revision --autogenerate -m "message"
```

Notes:

- PostgreSQL is required for normal runtime and Alembic migrations.
- Copy `.env.example` to `.env` and set at minimum `DATABASE_URL`, `SECRET_KEY`, and `PROVIDER_KEY_ENCRYPTION_SECRET`.
- Use `npm.cmd` on Windows when PowerShell blocks `npm.ps1`.
- Frontend Vite runs on `127.0.0.1:5173`; the default `CORS_ORIGINS` now includes this origin.

## Documentation Rules

Always keep docs synchronized with behavior changes.

- `docs/STATUS.md` is the current implementation snapshot.
- `docs/README.md` is the documentation map.
- `docs/product/strategic_redesign.md` is the active strategic roadmap.
- `docs/learning/` contains chronological implementation decision logs.
- `docs/reviews/` contains audit, product review, and validation reports.
- `docs/archive/` contains superseded historical material.

For non-trivial implementation work, add or update a learning/review document that explains purpose, invariants, design decisions, trade-offs, runtime lifecycle, failure paths, and safe-evolution notes.

## Architecture

Dependency direction is:

`api -> services -> models/db`

- `app/api/v1/endpoints/`: HTTP boundary only. Parse, validate, authorize, delegate.
- `app/services/`: business logic and transaction ownership.
- `app/models/` and `app/db/`: SQLAlchemy async ORM and database session setup.
- `app/core/logging_config.py`: logging configuration — `configure_logging()`, formatters, `ContextInjectingFilter`, `SecretRedactingFilter`. Called first in `main.py` lifespan.
- `app/core/log_context.py`: context variable bindings (`request_id`, `user_id`, `project_id`, `page_id`) for log correlation across async boundaries.
- `alembic/versions/`: all schema changes.
- `frontend/src/`: React app and API client.

Avoid putting business logic in endpoints or UI-specific assumptions in services.

## Current Product Flow

1. User logs in.
2. User configures a BYOK provider.
3. User starts a project from a URL.
4. Backend validates URL, checks robots, fetches HTML, summarizes DOM, and runs AI analysis.
5. User chooses crawl scope:
   - `CURRENT_PAGE`
   - `PAGINATION`
   - `DATASET`
   - `FULL_SITE`
6. User generates a frontier preview and confirms broad scope.
7. User chooses fields and runs sample preview.
8. User starts extraction.
9. Backend crawls approved pages, extracts records, computes quality summary, and exposes paginated records/export.

## Invariants

- User-scoped resources must always be owner-checked before read or mutation.
- Provider API keys are encrypted at rest and never returned in normal responses.
- No credit system exists. Do not reintroduce credits, billing counters, or old `system_state` credit logic.
- Project extraction must not silently broad-crawl new projects. Non-`CURRENT_PAGE` crawl scopes require `USER_CONFIRMED`.
- Frontier preview and extraction must continue sharing the same scope classifier.
- `extract_anyway=True` may bypass preview-required checks, but must not bypass scope confirmation.
- `records-page` is the preferred results browsing endpoint; legacy records endpoint remains for compatibility.
- Schema changes go through Alembic and require migration verification.

## Known Risks

- Legacy `/scrape` is not the primary product path. SSRF validation is now applied at both the endpoint and executor levels, but the legacy scraper (`app/services/scraper.py`) still uses `follow_redirects=True` without per-hop validation. Per-redirect validation in the legacy scraper is deferred.
- `CrawlPage.lease_expires_at` is swept by the watchdog lease reaper every 60 seconds. Expired FETCHING pages are reset to PENDING within active projects.
- `CRAWL_CONCURRENCY` is reserved for future use; the extraction executor is sequential.
- APScheduler runs in-process; multi-worker/multi-host deployment needs an explicit scheduler strategy.
- Real provider analysis still requires valid user-supplied credentials.

## Git and Verification

- Work on a feature branch, not directly on `main`.
- Do not commit generated logs, local `.env`, build output, virtualenvs, or frontend `dist`.
- Before committing product code, run backend tests and frontend checks unless the change is docs-only.
- For Phase 2.5 workflow changes, also run `tests\validation\run_validation.py`.
