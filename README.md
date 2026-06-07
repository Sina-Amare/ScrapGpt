# ScrapGPT

An async FastAPI and React application for authenticated, BYOK URL scraping with an LLM post-processing stage.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![Status](https://img.shields.io/badge/status-MVP%20%2F%20WIP-orange.svg)](docs/STATUS.md)

> **Status:** Phase 0 and Phase 0.5 complete. Backend + React frontend are end-to-end runnable with BYOK provider management, real LLM integration, and a full task pipeline. Phase 1 (intelligent site analysis) is next — see `docs/product/strategic_redesign.md` for the roadmap.

## What it does

1. User registers / logs in (JWT).
2. User submits a URL via `POST /api/v1/scrape/start`.
3. Server admits the task using configurable per-user concurrency limits and returns `202 Accepted` with a `task_id`.
4. A background pipeline drives the task through a state machine: `PERMISSION_GRANTED → SCRAPING → SCRAPED → LLM_PROCESSING → COMPLETED` (or `FAILED` from any non-terminal state).
5. User polls `GET /api/v1/scrape/tasks/{task_id}` for status and final result.

Users configure their own AI provider keys. Keys are encrypted at rest; normal provider responses never include key material. A user can explicitly reveal their own stored key only after password confirmation.

## Tech stack

| Concern         | Library                                             |
| --------------- | --------------------------------------------------- |
| Web framework   | FastAPI 0.115 (async)                               |
| ASGI server     | Uvicorn (Gunicorn for prod)                         |
| ORM             | SQLAlchemy 2.0 async + asyncpg                      |
| Migrations      | Alembic                                             |
| Validation      | Pydantic 2 + pydantic-settings                      |
| Auth            | python-jose (JWT) + passlib/bcrypt                  |
| Scraping        | httpx + BeautifulSoup4 + lxml                       |
| Background jobs | APScheduler (in-process)                            |
| Rate limiting   | SlowAPI                                             |
| Tests           | pytest + pytest-asyncio (95 backend) / tsx (16 frontend) |

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

## Project structure

```text
scrapegpt/
├── app/
│   ├── main.py                    # FastAPI factory + lifespan (starts scheduler)
│   ├── api/
│   │   ├── deps.py                # get_db, get_current_user
│   │   └── v1/
│   │       ├── router.py          # Mounts health/auth/scrape routers
│   │       └── endpoints/
│   │           ├── health.py      # /, /ready, /live
│   │           ├── auth.py        # register, login, refresh
│   │           └── scrape.py      # start, tasks/{id}, tasks/current
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
│   │   └── scrape_task.py         # scrape_tasks + TaskState enum + transitions
│   ├── schemas/
│   │   ├── auth.py                # register/login/token DTOs
│   │   └── scrape.py              # scrape DTOs
│   └── services/
│       ├── admission.py           # per-user active task limit
│       ├── provider_service.py    # provider config, encryption, LiteLLM wrapper
│       ├── task_state.py          # explicit transition fns
│       ├── task_executor.py       # pipeline orchestrator (always-finalize)
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
│   └── 005_provider_foundation.py         # credit removal + BYOK provider_configs table
├── docs/
│   ├── product/strategic_redesign.md  # Authoritative roadmap + architecture decisions
│   ├── ops/health.md                  # Health/readiness operations notes
│   ├── archive/project_master.md      # Pre-redesign reference
│   └── learning/                      # Decision logs 01–05 (one per feature)
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

## Production notes

1. Set `ENVIRONMENT=production` and `DEBUG=false` (this disables `/docs`).
2. Generate a real `SECRET_KEY`: `openssl rand -hex 32`.
3. Set `CORS_ORIGINS` to your real frontend origin(s). For local Vite development, include `http://localhost:5173`.
4. Run with multiple workers only after deciding how to operate **APScheduler**, which runs in-process. For multi-host deployments, run the scheduler in a dedicated process.

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Where to go next

Read [docs/product/strategic_redesign.md](docs/product/strategic_redesign.md) — the authoritative roadmap covering the current architecture, completed phases, and what Phase 1 builds next (intelligent site analysis, URL validation, robots.txt, fetcher, AI-driven field discovery).

## License

MIT.
