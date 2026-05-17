# ScrapGPT — Complete Project Context

> This document gives any LLM (or human) full context to understand, discuss, and contribute to this project. It covers what exists, how it works, what's planned, and what the key decisions are.

Last updated: 2026-05-17

---

## What Is This Project?

ScrapGPT is an AI-powered web scraping platform. The user pastes a URL, the system fetches and analyzes the page using AI (Google Gemini), presents the user with selectable data patterns, and then extracts structured data — including across multiple pages with different URL patterns.

**Current state:** Backend MVP is functional (auth, task pipeline, scraping). No frontend, no real AI integration (LLM is a stub), no multi-page crawling, no checkpointing.

**Target state:** Full-stack platform with React GUI, Gemini-powered page analysis, deterministic CSS-selector extraction, multi-page crawling, and crash-safe checkpointing.

---

## Tech Stack

| Layer                       | Technology                                          |
| --------------------------- | --------------------------------------------------- |
| Backend framework           | FastAPI 0.115 (async)                               |
| ASGI server                 | Uvicorn                                             |
| Database                    | PostgreSQL 14+ (uses JSONB, partial unique indexes) |
| ORM                         | SQLAlchemy 2.0 async + asyncpg driver               |
| Migrations                  | Alembic                                             |
| Validation                  | Pydantic 2 + pydantic-settings                      |
| Auth                        | python-jose (JWT) + passlib/bcrypt                  |
| Scraping                    | httpx (async HTTP) + BeautifulSoup4 + lxml          |
| Background jobs             | APScheduler (in-process)                            |
| Rate limiting               | SlowAPI                                             |
| AI (planned)                | Google Gemini via google-genai (free tier)          |
| Frontend (planned)          | React + Vite + TypeScript + Tailwind + shadcn/ui    |
| Browser rendering (planned) | Playwright Chromium                                 |

---

## Project Structure

```
scrapegpt/
├── app/
│   ├── main.py                 # FastAPI app factory + lifespan (starts scheduler)
│   ├── api/
│   │   ├── deps.py             # Dependency injection: get_db, get_current_user
│   │   └── v1/
│   │       ├── router.py       # Mounts health/auth/scrape routers
│   │       └── endpoints/
│   │           ├── health.py   # /health, /health/ready, /health/live
│   │           ├── auth.py     # register, login, refresh
│   │           └── scrape.py   # start, tasks/{id}, tasks/current
│   ├── core/
│   │   ├── config.py           # Pydantic Settings (all config from .env)
│   │   ├── security.py         # bcrypt + JWT create/verify
│   │   ├── rate_limit.py       # SlowAPI limiter + key function
│   │   └── scheduler.py        # APScheduler: credit reset + watchdog
│   ├── db/
│   │   └── database.py         # async engine, session factory, get_db
│   ├── models/
│   │   ├── base.py             # Declarative Base + mixins
│   │   ├── user.py             # User model (auth + credits)
│   │   └── scrape_task.py      # ScrapeTask + TaskState enum + transitions
│   ├── schemas/
│   │   ├── auth.py             # Auth request/response DTOs
│   │   └── scrape.py           # Scrape DTOs
│   └── services/
│       ├── admission.py        # One-active-task + credit gating
│       ├── task_state.py       # Atomic state transitions + credit deduction
│       ├── task_executor.py    # Pipeline orchestrator (always-finalize)
│       ├── scraper.py          # httpx + BeautifulSoup fetch/extract
│       ├── llm_processor.py    # ⚠️ STUB — returns mock dict
│       ├── readiness.py        # Bounded DB readiness probe
│       └── watchdog.py         # Fails tasks stuck past timeout
├── alembic/versions/           # DB migrations (001-004)
├── tests/                      # Skeleton (health + readiness only)
├── docs/
│   ├── plan/
│   │   ├── AI_SCRAPING_PLATFORM_PLAN.md  # ← THE PLAN (chosen)
│   │   └── MASTER_PLAN.md               # Earlier draft (superseded)
│   ├── architecture.md
│   ├── STATUS.md
│   └── learning/              # Decision logs (01-04)
├── requirements.txt
└── .env                       # Local config (not in git)
```

---

## How the Current Backend Works

### Authentication Flow

1. **Register:** `POST /api/v1/auth/register` — email + password → creates User, returns JWT pair (access + refresh)
2. **Login:** `POST /api/v1/auth/login` — OAuth2 form login → returns JWT pair
3. **Refresh:** `POST /api/v1/auth/refresh` — refresh token → new access token
4. **Protected routes:** Use `Authorization: Bearer <access_token>` header

JWT tokens:

- Access token: 15 min TTL, contains `sub` (user ID as string), `type: "access"`
- Refresh token: 7 day TTL, contains `sub` (user ID), `type: "refresh"`
- Signed with HS256 using `SECRET_KEY` from config

### User Model

```python
class User(Base):
    id: int                    # Primary key
    email: str                 # Unique, indexed
    hashed_password: str       # bcrypt
    is_active: bool            # Account enabled
    is_verified: bool          # Email verified (not enforced yet)
    credits_remaining: int     # Current balance (default 5)
    daily_credit_limit: int    # Reset ceiling (default 5)
    credits_reset_at: datetime # Last reset timestamp
```

### Scrape Task Pipeline

The core workflow today (single-URL, no AI):

```
User: POST /api/v1/scrape/start {url}
  → Admission check (credits > 0, no active task)
  → Create ScrapeTask(state=PERMISSION_GRANTED)
  → Return 202 + task_id
  → Background pipeline starts:
      PERMISSION_GRANTED → SCRAPING (fetch URL with httpx)
      SCRAPING → SCRAPED (store extracted text)
      SCRAPED → LLM_PROCESSING (deduct 1 credit atomically)
      LLM_PROCESSING → COMPLETED (store result JSON)
      Any failure → FAILED (with error message)
User: GET /api/v1/scrape/tasks/{task_id} (poll for status)
```

### State Machine

```
PERMISSION_GRANTED → SCRAPING → SCRAPED → LLM_PROCESSING → COMPLETED
                         ↓          ↓            ↓
                       FAILED     FAILED       FAILED
```

Terminal states: `COMPLETED`, `FAILED`

Enforced by `VALID_TRANSITIONS` dict and `can_transition_to()` method.

### Key Invariants

1. **One active task per user** — Partial unique index on `scrape_tasks(user_id) WHERE state NOT IN ('COMPLETED', 'FAILED')`. Database-enforced, race-condition proof.

2. **Credits deducted at LLM phase only** — Not at admission. If scraping fails, user isn't charged. Deduction is atomic with the state transition (same DB transaction).

3. **Always-finalize** — Every task reaches COMPLETED or FAILED. The executor has a catch-all try/except. The watchdog catches anything that slips through.

4. **Multi-instance-safe credit reset** — Daily at 00:00 UTC via compare-and-swap on `system_state` table. Only one instance performs the reset.

### Credit System

- Each user gets 5 credits/day (configurable per user via `daily_credit_limit`)
- Credits reset at 00:00 UTC by a scheduled job (APScheduler)
- Credits are checked at admission (gate) and deducted at LLM phase (charge)
- The `system_state` table with key `last_credit_reset` prevents duplicate resets across instances

### Scheduled Jobs

1. **Credit reset** — CronTrigger at 00:00 UTC. Uses check-and-set on `system_state`.
2. **Watchdog** — IntervalTrigger every 60s. Fails tasks stuck in non-terminal states past configurable timeouts (3/5/10 min for PERMISSION_GRANTED/SCRAPING/LLM_PROCESSING).

### Database Schema

**Tables:**

- `users` — Auth + credits
- `scrape_tasks` — Task tracking with state machine
- `system_state` — Key/value for coordination (credit reset cursor)
- `alembic_version` — Migration tracking

**Key indexes:**

- `ix_one_active_task_per_user` — Partial unique on `scrape_tasks(user_id) WHERE state NOT IN ('COMPLETED', 'FAILED')`
- Standard indexes on `users.email`, `scrape_tasks.user_id`, `scrape_tasks.state`

---

## Known Bugs (Must Fix Before New Features)

1. **SlowAPI parameter collision** — `POST /scrape/start` has `request: StartScrapeRequest` but SlowAPI needs `request: starlette.Request`. Fix: rename body to `payload`.

2. **Route shadowing** — `/tasks/{task_id}` declared before `/tasks/current`. FastAPI matches "current" as a task_id → 422. Fix: reorder routes.

3. **Watchdog NULL-skip** — `updated_at` is nullable with no insert default. `NULL < cutoff` is always false. Fix: use `COALESCE(updated_at, created_at)`.

4. **Migration enum drift** — Old enum values (FINALIZED, LLM_ANALYZED) in migration 002 don't match current model. Fix: squash migrations.

5. **JWT int() cast** — `int(payload.sub)` can raise ValueError for malformed tokens → 500. Fix: try/except → 401.

---

## The Plan Forward (AI_SCRAPING_PLATFORM_PLAN.md)

### Core Architecture Decision

**Gemini suggests selectors; deterministic code does extraction.**

- Gemini is NOT called per-page for extraction (would burn free tier in minutes)
- Gemini analyzes the FIRST page to understand structure and suggest CSS selectors
- Those selectors are validated against real DOM before being accepted
- Extraction on all subsequent pages uses those CSS selectors (fast, free, reliable)
- Gemini is called sparingly: page analysis, crawl strategy, sample classification

### New Workflow

```
1. POST /api/v1/scrape/preview {url, render_mode}
   → Validate URL (HEAD, DNS, robots.txt)
   → Fetch/render seed page
   → Extract deterministic DOM candidates (tables, lists, repeated elements)
   → Send compact candidates to Gemini for analysis
   → Return task in AWAITING_SELECTION state with suggested fields

2. POST /api/v1/scrape/tasks/{id}/run {fields, page_limit, export_format}
   → User confirms/edits extraction spec
   → Start crawling same-site links
   → Extract records using CSS selectors
   → Checkpoint after each page
   → Export when done

3. GET /api/v1/scrape/tasks/{id} — progress
4. GET /api/v1/scrape/tasks/{id}/records — paginated results
5. GET /api/v1/scrape/tasks/{id}/export — CSV/JSON/JSONL/XLSX
6. POST /api/v1/scrape/tasks/{id}/cancel — graceful cancel
```

### New State Machine

```
AWAITING_SELECTION → DISCOVERING → EXTRACTING → EXPORTING → COMPLETED
                         ↓              ↓            ↓
                       FAILED         FAILED       FAILED
                       CANCELED       CANCELED     CANCELED
```

### Rendering Strategy

- `static` — httpx + BeautifulSoup (fast, for simple HTML)
- `browser` — Playwright Chromium (for JS-heavy sites)
- `auto` — Try static first, fall back to browser if page appears JS-dependent

### Multi-Page Crawling

- Same-site only (same host)
- BFS with priority: index/list pages first, then detail pages
- URL normalization and deduplication (canonical URL + content hash)
- Page classification: index, detail, pagination, irrelevant
- Gemini used on samples only, not every page
- Stop at `page_limit` or when no matching pages remain

### Checkpointing

- Page-level persistence: each page has its own status (queued/fetching/fetched/extracting/extracted/failed)
- Commit after every page extraction
- Unique constraints prevent duplicates: `(task_id, normalized_url)`
- Retry with exponential backoff (3 attempts per page)
- Watchdog requeues expired in-progress pages
- Partial export always available from committed records

### Gemini Integration Details

- Use official `google-genai` SDK
- Models: `gemini-3.1-flash-lite` (fast/cheap) with escalation to `gemini-2.5-flash` (reasoning)
- Structured outputs with Pydantic validation on every response
- Send only compact DOM summaries, never full HTML
- Cache analysis by content hash to reduce API calls
- Configurable RPM/RPD caps with backoff on 429s
- Free tier: variable limits per project, app must handle gracefully

### Frontend

- React + Vite + TypeScript + Tailwind + TanStack Query
- First screen is the tool itself (URL input), not a landing page
- Preview screen: screenshot, detected groups, suggested fields, sample rows
- Progress screen: SSE live updates with polling fallback
- Results screen: table preview, failed pages, partial/final export

---

## Configuration (app/core/config.py)

All settings from `.env`, validated at startup by Pydantic:

| Variable                       | Default                    | Purpose                            |
| ------------------------------ | -------------------------- | ---------------------------------- |
| `ENVIRONMENT`                  | `development`              | dev/staging/production             |
| `DEBUG`                        | `false`                    | Enables /docs, /redoc              |
| `DATABASE_URL`                 | `postgresql+asyncpg://...` | Async PG connection                |
| `SECRET_KEY`                   | placeholder                | JWT signing (must change for prod) |
| `ACCESS_TOKEN_EXPIRE_MINUTES`  | `15`                       | Access token TTL                   |
| `REFRESH_TOKEN_EXPIRE_DAYS`    | `7`                        | Refresh token TTL                  |
| `DEFAULT_DAILY_CREDITS`        | `5`                        | Credits for new users              |
| `SCRAPE_TIMEOUT`               | `30`                       | HTTP fetch timeout (seconds)       |
| `LLM_TIMEOUT`                  | `120`                      | LLM call timeout (seconds)         |
| `WATCHDOG_*_TIMEOUT_MINUTES`   | `3/5/10`                   | Stuck-task thresholds              |
| `RATE_LIMIT_PER_MINUTE`        | `60`                       | Default rate limit                 |
| `RATE_LIMIT_SCRAPE_PER_MINUTE` | `10`                       | Scrape endpoint limit              |

---

## How to Run

```bash
# Setup
python -m venv venv
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env: set DATABASE_URL and SECRET_KEY

# Database
createdb scrapegpt
alembic upgrade head

# Run
uvicorn app.main:app --reload

# Test
cmd.exe /c "set DEBUG=true&& venv\Scripts\python.exe -m pytest -q"
# Result: 13 passed
```

---

## Code Patterns & Conventions

### Layering Rule

Endpoints parse requests and delegate. Services own business logic and transactions. Models define schema. Never put business logic in endpoints.

### Transaction Pattern

```python
async with db.begin():
    # All DB operations here
    # Context manager commits on success, rolls back on exception
# After the block: await db.refresh(obj) if needed
```

### Error Pattern (Services)

Services return result objects, not exceptions:

```python
result = await admit_scrape_task(user, url, db)
if isinstance(result, AdmissionError):
    # Handle error
task = result.task  # Success
```

### Dependency Injection

```python
@router.get("/protected")
async def endpoint(
    user: User = Depends(get_current_user),  # Auth
    db: AsyncSession = Depends(get_db),       # DB session
):
```

### Structured Logging

```python
logger.info("event.name", extra={"key": "value", "task_id": 42})
```

---

## Constraints & Assumptions

- **No paid APIs.** Gemini free tier only (Google AI Studio key).
- **Local-first MVP.** Not a public SaaS yet.
- **Same-site crawling only.** Won't follow links to other domains.
- **No anti-bot bypass.** Won't handle captchas, logins, or paywalls.
- **PostgreSQL required.** Uses JSONB, partial unique indexes, native enums.
- **Single-host deployment.** Scheduler runs in-process. For multi-host, run scheduler in dedicated worker.

---

## What's NOT Done Yet (Ordered by Priority)

1. Fix the 5 known bugs (see above)
2. Gemini AI integration (page analysis, selector suggestion)
3. React frontend (URL input → preview → configure → run → results)
4. Browser rendering (Playwright for JS-heavy pages)
5. Multi-page crawling engine
6. Checkpointing and recovery
7. Export layer (CSV, JSON, JSONL, XLSX)
8. Real-time progress (SSE)
9. URL validation and safety (SSRF prevention, robots.txt)
10. Comprehensive test suite

---

## File-by-File Quick Reference

| File                             | What it does                                         | Lines |
| -------------------------------- | ---------------------------------------------------- | ----- |
| `app/main.py`                    | App factory, lifespan, CORS, rate limit middleware   | 170   |
| `app/api/deps.py`                | get_db, get_current_user, deprecated helpers         | 206   |
| `app/api/v1/router.py`           | Mounts health/auth/scrape routers                    | 29    |
| `app/api/v1/endpoints/health.py` | /health, /health/ready, /health/live                 | 133   |
| `app/api/v1/endpoints/auth.py`   | register, login, refresh                             | 229   |
| `app/api/v1/endpoints/scrape.py` | start, tasks/{id}, tasks/current (has bugs)          | 185   |
| `app/core/config.py`             | Pydantic Settings, all env vars                      | 184   |
| `app/core/security.py`           | hash_password, verify_password, JWT create/verify    | 235   |
| `app/core/rate_limit.py`         | SlowAPI limiter, key function, rate constants        | 42    |
| `app/core/scheduler.py`          | APScheduler config, credit reset, watchdog trigger   | 130   |
| `app/db/database.py`             | Async engine, session factory, get_db generator      | 136   |
| `app/models/base.py`             | Declarative Base, TimestampMixin, SoftDeleteMixin    | ~50   |
| `app/models/user.py`             | User model with credit methods                       | 214   |
| `app/models/scrape_task.py`      | ScrapeTask, TaskState enum, VALID_TRANSITIONS        | 130   |
| `app/schemas/auth.py`            | Auth request/response Pydantic models                | 68    |
| `app/services/admission.py`      | admit_scrape_task (credit gate + one-active check)   | 126   |
| `app/services/task_state.py`     | All transition*to*\* functions, atomic credit deduct | 263   |
| `app/services/task_executor.py`  | execute_scrape_pipeline (always-finalize)            | 112   |
| `app/services/scraper.py`        | scrape_url (httpx + BS4 + timeout)                   | 98    |
| `app/services/llm_processor.py`  | STUB: sleeps 1s, returns mock dict                   | 63    |
| `app/services/readiness.py`      | Bounded DB probe for /health/ready                   | 127   |
| `app/services/watchdog.py`       | cleanup_stuck_tasks (has NULL bug)                   | 117   |

---

## Questions This Document Should Answer

- "What does this project do?" → AI-powered web scraping platform
- "What's built vs what's planned?" → Backend MVP built, AI/frontend/crawling planned
- "What tech stack?" → FastAPI + PostgreSQL + Gemini + React (planned)
- "How does auth work?" → JWT (access + refresh), bcrypt passwords
- "How does the task pipeline work?" → State machine with always-finalize guarantee
- "Why are credits deducted at LLM phase?" → Fairness: don't charge for failed scrapes
- "What's the AI strategy?" → Gemini suggests selectors, deterministic code extracts
- "What are the known bugs?" → 5 bugs listed, all in STATUS.md
- "What's the plan?" → AI_SCRAPING_PLATFORM_PLAN.md is the source of truth
- "How do I run it?" → See "How to Run" section above
