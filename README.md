# ScrapGPT

An async FastAPI and React application for authenticated, BYOK web extraction analysis.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![Status](https://img.shields.io/badge/status-Phase%201%20implemented-teal.svg)](docs/STATUS.md)

> **Status:** Phase 0, Phase 0.5, frontend v0, and Phase 1 analysis jobs are implemented and runnable. The app currently supports auth, BYOK provider management, legacy scrape tasks, and the new AI site-analysis job pipeline. The next product phase is extraction setup/review and crawl execution.

## What it does

1. User registers / logs in (JWT).
2. User adds their own AI provider credentials in the Providers screen.
3. User submits a URL through **New Analysis** or `POST /api/v1/jobs`.
4. Server validates the URL, checks `robots.txt`, fetches HTML using static or optional browser rendering, summarizes the DOM, and asks the user's provider for structured analysis.
5. User views the analysis job result: suggested fields/content structure, confidence, warnings, fetch metadata, and terminal state.

Users configure their own AI provider keys. Keys are encrypted at rest; normal provider responses never include key material. A user can explicitly reveal their own stored key only after password confirmation.

The older `/scrape` pipeline still exists for compatibility and is labeled as legacy in the frontend. It is not the primary Phase 1 workflow.

## Tech stack

| Concern         | Library                                             |
| --------------- | --------------------------------------------------- |
| Web framework   | FastAPI 0.115 (async)                               |
| ASGI server     | Uvicorn (Gunicorn for prod)                         |
| ORM             | SQLAlchemy 2.0 async + asyncpg                      |
| Migrations      | Alembic                                             |
| Validation      | Pydantic 2 + pydantic-settings                      |
| Auth            | python-jose (JWT) + passlib/bcrypt                  |
| Scraping        | httpx + BeautifulSoup4 + lxml; optional Playwright browser rendering |
| Background jobs | APScheduler (in-process)                            |
| Rate limiting   | SlowAPI                                             |
| Tests           | pytest + pytest-asyncio (152 backend) / tsx (31 frontend) |

PostgreSQL 14+ is required (uses JSONB and partial unique indexes).

## Quick start

```bash
# 1. Clone and create venv
git clone <your-fork-url> scrapegpt
cd scrapegpt
python -m venv venv
.\venv\Scripts\activate         # Windows
# source venv/bin/activate      # Linux/Mac

# 2. Install
pip install -r requirements.txt

# 2b. Optional: browser rendering for JavaScript-heavy sites
#     Required only if you use render_mode=BROWSER; static mode works without it.
pip install playwright
python -m playwright install chromium

# 3. Configure
cp .env.example .env
# Edit .env: at minimum set DATABASE_URL and a real SECRET_KEY
#   openssl rand -hex 32

# 4. Migrate
createdb scrapegpt
alembic upgrade head

# 5. Run backend on Windows
venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 6. Run frontend on Windows, in another terminal
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) for the app and [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for Swagger UI.

## API surface

All routes are under `/api/v1`.

### Health

| Method | Path             | Auth | Description                                    |
| ------ | ---------------- | ---- | ---------------------------------------------- |
| GET    | `/health`        | no   | Basic status (env, version)                    |
| GET    | `/health/ready`  | no   | Readiness probe with DB + schema sanity check  |
| GET    | `/health/live`   | no   | Minimal liveness probe                         |

### Auth

| Method | Path             | Auth | Description                                |
| ------ | ---------------- | ---- | ------------------------------------------ |
| POST   | `/auth/register` | no   | Create account; returns user + token pair  |
| POST   | `/auth/login`    | no   | OAuth2 form login; returns token pair      |
| POST   | `/auth/refresh`  | no   | Exchange refresh token for new access token |

### Providers

| Method | Path                                | Auth | Description                                      |
| ------ | ----------------------------------- | ---- | ------------------------------------------------ |
| GET    | `/providers`                        | yes  | List provider configs without key material       |
| POST   | `/providers`                        | yes  | Create provider config; key is encrypted         |
| PATCH  | `/providers/{provider_id}`          | yes  | Update metadata or replace key                   |
| DELETE | `/providers/{provider_id}`          | yes  | Delete provider config                           |
| POST   | `/providers/{provider_id}/test`     | yes  | Test provider connectivity and JSON capability   |
| POST   | `/providers/{provider_id}/reveal-key` | yes | Reveal own key after password confirmation       |

### Scraping

| Method | Path                       | Auth | Description                                          |
| ------ | -------------------------- | ---- | ---------------------------------------------------- |
| POST   | `/scrape/start`            | yes  | Admit + queue a scrape task (returns 202)              |
| GET    | `/scrape/tasks`            | yes  | List user's tasks, newest first (skip/limit supported) |
| GET    | `/scrape/tasks/{task_id}`  | yes  | Get full task detail incl. content_length (owner-only) |
| GET    | `/scrape/tasks/current`    | yes  | Get the user's current non-terminal task (404 if none) |
| DELETE | `/scrape/tasks/{task_id}`  | yes  | Delete a terminal task (400 if active, 404 if not owned) |

### Analysis jobs

| Method | Path                  | Auth | Description                                                        |
| ------ | --------------------- | ---- | ------------------------------------------------------------------ |
| POST   | `/jobs`               | yes  | Create a Phase 1 analysis job; rate limited; returns `202`          |
| GET    | `/jobs`               | yes  | List user's analysis jobs, newest first                            |
| GET    | `/jobs/{job_id}`      | yes  | Get full analysis job detail                                       |
| POST   | `/jobs/{job_id}/cancel` | yes | Cancel a `QUEUED` or `ANALYZING` job                               |
| DELETE | `/jobs/{job_id}`      | yes  | Delete a terminal job (`AWAITING_SETUP`, `ANALYSIS_READY`, `FAILED`, `CANCELED`) |

## Project structure

```text
scrapegpt/
├── app/
│   ├── main.py                    # FastAPI factory + lifespan (starts scheduler)
│   ├── api/
│   │   ├── deps.py                # get_db, get_current_user
│   │   └── v1/
│   │       ├── router.py          # Mounts health/auth/providers/scrape/jobs routers
│   │       └── endpoints/
│   │           ├── health.py      # /, /ready, /live
│   │           ├── auth.py        # register, login, refresh
│   │           ├── providers.py   # BYOK provider CRUD/test/reveal
│   │           ├── scrape.py      # legacy scrape start, tasks/{id}, tasks/current
│   │           └── jobs.py        # Phase 1 analysis jobs
│   ├── core/
│   │   ├── config.py              # Pydantic Settings (env-driven)
│   │   ├── security.py            # bcrypt hash + JWT issue/verify
│   │   ├── rate_limit.py          # SlowAPI limiter + key fn
│   │   └── scheduler.py           # APScheduler watchdog
│   ├── db/
│   │   └── database.py            # async engine, sessionmaker, close_db
│   ├── models/
│   │   ├── base.py                # Declarative Base
│   │   ├── user.py                # users (auth + default provider)
│   │   ├── provider_config.py     # encrypted BYOK provider configs
│   │   ├── job.py                 # analysis jobs + analysis cache
│   │   └── scrape_task.py         # legacy scrape_tasks + TaskState enum
│   ├── schemas/
│   │   ├── auth.py                # register/login/token DTOs
│   │   ├── provider.py            # provider DTOs
│   │   ├── job.py                 # analysis job DTOs
│   │   └── scrape.py              # legacy scrape DTOs
│   └── services/
│       ├── admission.py           # per-user active task limit
│       ├── provider_service.py    # provider config, encryption, LiteLLM wrapper
│       ├── job_admission.py       # analysis job admission + provider preflight
│       ├── job_executor.py        # Phase 1 pipeline orchestrator
│       ├── job_state.py           # analysis job state transitions
│       ├── url_validator.py       # SSRF-safe URL validation
│       ├── robots_service.py      # robots.txt fetch/parse/cache
│       ├── fetcher.py             # static/browser HTML fetcher
│       ├── dom_summary.py         # token-efficient DOM summarizer
│       ├── analyzer.py            # cached structured/content analysis
│       ├── task_state.py          # explicit transition fns
│       ├── task_executor.py       # legacy scrape pipeline orchestrator
│       ├── scraper.py             # httpx + BeautifulSoup fetch/extract
│       ├── llm_processor.py       # BYOK LLM analysis
│       ├── readiness.py           # bounded DB readiness probe
│       └── watchdog.py            # fails tasks stuck past timeout
├── alembic/versions/
│   ├── 001_create_users.py
│   ├── 002_create_scrape_tasks.py
│   ├── 003_update_task_states.py          # enum values + (now-dropped) partial unique idx
│   ├── 004_system_state.py                # legacy credit-reset table (dropped in 005)
│   ├── fe292fc905ad_remove_old_enum_values.py  # enum rename fix
│   ├── 005_provider_foundation.py         # credit removal + BYOK provider_configs table
│   └── 006_analysis_jobs.py               # jobs + analysis_cache
├── docs/
│   ├── product/strategic_redesign.md  # Authoritative roadmap + architecture decisions
│   ├── ops/health.md                  # Health/readiness operations notes
│   ├── archive/project_master.md      # Pre-redesign reference
│   ├── STATUS.md                      # Current implementation status
│   └── learning/                      # Decision logs 01–07
├── frontend/                      # React control surface
├── tests/                         # backend pytest suite
├── requirements.txt
└── .env.example
```

## Configuration

All settings come from `.env` and are validated at startup by `app/core/config.py`. Highlights:

| Variable                                       | Default                                  | Purpose                                                  |
| ---------------------------------------------- | ---------------------------------------- | -------------------------------------------------------- |
| `ENVIRONMENT`                                  | `development`                            | One of `development` / `staging` / `production`          |
| `DEBUG`                                        | `false`                                  | Enables `/docs`, `/redoc`, `/openapi.json` and reload    |
| `DATABASE_URL`                                 | `postgresql+asyncpg://…/scrapegpt`       | Async PostgreSQL DSN                                     |
| `SECRET_KEY`                                   | placeholder (warns)                      | JWT signing key — **must change for production**         |
| `ACCESS_TOKEN_EXPIRE_MINUTES`                  | `15`                                     | Access token TTL                                         |
| `REFRESH_TOKEN_EXPIRE_DAYS`                    | `7`                                      | Refresh token TTL                                        |
| `PROVIDER_KEY_ENCRYPTION_SECRET`               | required                                 | Fernet key for provider API-key encryption               |
| `MAX_CONCURRENT_JOBS_PER_USER`                 | `3`                                      | Active scrape jobs allowed per user                      |
| `MAX_PAGES_PER_JOB` / `CRAWL_CONCURRENCY`      | `500` / `3`                              | Future crawler resource controls                         |
| `SCRAPE_TIMEOUT` / `LLM_TIMEOUT`               | `30` / `120`                             | Per-stage HTTP / LLM timeouts (seconds)                  |
| `WATCHDOG_*_TIMEOUT_MINUTES`                   | `3` / `5` / `10`                         | Stuck-task thresholds for PERMISSION_GRANTED / SCRAPING / LLM_PROCESSING |
| `WATCHDOG_JOB_*_TIMEOUT_MINUTES`               | `3` / `5`                                | Stuck-job thresholds for QUEUED / ANALYZING              |
| `ALLOW_PRIVATE_NETWORK_URLS`                   | `false`                                  | Allows private URLs only when explicitly enabled for dev/tests |
| `ROBOTS_FAILURE_POLICY`                        | `deny`                                   | `deny` or `allow` when robots.txt cannot be fetched      |
| `MAX_FETCH_BYTES` / `MAX_REDIRECTS`             | `2097152` / `5`                          | Fetch truncation and redirect limit                      |
| `ANALYSIS_CONFIDENCE_FAST_THRESHOLD`           | `0.75`                                   | FAST workflow confidence threshold                       |
| `RATE_LIMIT_PER_MINUTE` / `_SCRAPE_` / `_AUTH_`| `60` / `10` / `5`                        | SlowAPI limits                                           |
| `READINESS_TIMEOUT_SECONDS`                    | `2.0`                                    | Bound on `/health/ready` DB probe                        |

See [.env.example](.env.example) for the full list.

## Development

```bash
# Run dev server (auto-reload)
venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Run frontend dev server
cd frontend
npm install
npm run dev

# Run backend tests
venv\Scripts\python.exe -m pytest -q

# Run frontend checks
cd frontend
npm run typecheck
npm run lint
npm test
npm run build

# Create a new migration after model edits
alembic revision --autogenerate -m "your message"
alembic upgrade head
```

## Security notes and limitations

- **SSRF**: Private IP ranges (RFC 1918, loopback, link-local) and non-HTTP schemes are blocked at validation time and, for browser mode, at the network layer via Playwright route interception.
- **DNS rebinding (TOCTOU)**: URL validation resolves DNS in Python; the HTTP client re-resolves at TCP connect time. An attacker-controlled hostname can return a public IP during the check and switch to a private IP at connection time. This race is not fixable at the application layer. Full mitigation requires an egress firewall.
- **API keys**: Provider API keys are Fernet-encrypted at rest. They are never returned in list/get API responses. Revealing a key requires a separate `POST /providers/{id}/reveal-key` with your account password.
- **Browser mode**: Playwright is an optional dependency. Static fetch mode is used by default and is safe to run without Playwright installed.
- **Windows browser mode**: Uvicorn can run with a selector event loop that cannot spawn Playwright subprocesses directly. The fetcher detects that case and runs Playwright through a worker-thread sync path with a Proactor policy. Verified with Browser mode on Windows.

## Production notes

1. Set `ENVIRONMENT=production` and `DEBUG=false` (this disables `/docs`).
2. Generate a real `SECRET_KEY`: `openssl rand -hex 32`.
3. Set `CORS_ORIGINS` to your real frontend origin(s). For local Vite development, include `http://localhost:5173`.
4. Run with multiple workers only after deciding how to operate **APScheduler**, which runs in-process. For multi-host deployments, run the scheduler in a dedicated process.

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Where to go next

Read [docs/STATUS.md](docs/STATUS.md) for the current implementation snapshot, then [docs/product/strategic_redesign.md](docs/product/strategic_redesign.md) for the remaining roadmap.

## License

MIT.
