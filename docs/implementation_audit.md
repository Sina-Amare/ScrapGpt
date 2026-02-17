# ScrapGPT Implementation Audit

Date: 2026-02-16  
Scope: Full repository analysis (`app/`, `alembic/`, `docs/`, `tests/`, `README.md`)

## 1. What This Project Is About

ScrapGPT is a FastAPI backend for authenticated URL scraping jobs with:
- JWT auth (register/login/refresh)
- User credit gating
- Async background task pipeline for scrape + LLM processing
- Task state tracking in PostgreSQL
- Scheduled maintenance jobs (daily credit reset + stuck-task watchdog)

Core flow:
1. User authenticates.
2. User starts a scrape task (`/api/v1/scrape/start`).
3. Task progresses through state machine in background.
4. User polls task status endpoints.

## 2. High-Level Implementation Status

| Area | Status | Correctness Verdict |
|---|---|---|
| FastAPI app bootstrap, routing, CORS, lifespan | Implemented | Mostly correct |
| Health endpoints (`/health`, `/health/ready`, `/health/live`) | Implemented | Correct for MVP |
| Auth endpoints (`register`, `login`, `refresh`) | Implemented | Mostly correct with edge-case gaps |
| DB models (`User`, `ScrapeTask`) | Implemented | Core design good, some mismatches/risks |
| Alembic migrations (`001`-`004`) | Implemented | Functional but has migration-evolution risk |
| Admission logic (credits + one active task) | Implemented | Correct pattern |
| Async scrape pipeline + state transitions | Implemented | Good architecture, but endpoint integration has blockers |
| Watchdog cleanup | Implemented | Partially incorrect (PERMISSION_GRANTED cleanup bug) |
| LLM integration | Half implemented | Stub only |
| Rate limiting | Partially implemented | Miswired in current endpoint usage |
| Tests | Not implemented | No test suite yet |

## 3. Implemented and Correct (or Mostly Correct)

### 3.1 Application/Foundation
- `app/main.py`: app factory, lifespan startup/shutdown, router inclusion.
- `app/api/v1/router.py`: health/auth/scrape router composition.
- `app/core/config.py`: centralized typed settings via `pydantic-settings`.

Verdict: structure is clean and production-oriented for a monolith MVP.

### 3.2 Authentication
- `app/api/v1/endpoints/auth.py`: registration, OAuth2 form login, refresh flow.
- `app/core/security.py`: bcrypt hashing + JWT issue/verify.
- `app/models/user.py`: auth and account fields.

Verdict: core flow works; password hashing and token flow are correctly wired for MVP.

### 3.3 Task Domain and Pipeline
- `app/models/scrape_task.py`: state model + transition constraints in code.
- `app/services/admission.py`: one-active-task admission with DB-enforced invariant handling.
- `app/services/task_executor.py`: orchestrates scrape -> llm -> completion with fail-safe fallback.
- `app/services/task_state.py`: explicit transition functions and atomic credit deduction at LLM phase.
- `app/services/scraper.py`: async HTTP fetch + extraction + timeout/error handling.

Verdict: architecture and separation of concerns are strong; most internals are coherent.

### 3.4 Scheduler and Credit Reset
- `app/core/scheduler.py`: APScheduler jobs for daily reset and watchdog.
- `alembic/versions/004_system_state.py`: global state table for once-per-day reset coordination.

Verdict: daily reset logic is a good multi-instance-safe check-and-set approach.

## 4. Implemented but Incorrect / Risky

### 4.1 Critical: `POST /scrape/start` rate-limit decorator is currently broken
- `app/api/v1/endpoints/scrape.py:64` defines `request` as body model (`StartScrapeRequest`).
- SlowAPI requires a parameter named `request` of type `starlette.requests.Request`.
- Verified from slowapi implementation at `venv/Lib/site-packages/slowapi/extension.py:709` and runtime behavior.

Impact:
- Endpoint can raise runtime exception: `parameter 'request' must be an instance of starlette.requests.Request`.

### 4.2 High: `/tasks/current` route can be shadowed by `/tasks/{task_id}`
- Dynamic route declared first: `app/api/v1/endpoints/scrape.py:124`.
- Static route declared second: `app/api/v1/endpoints/scrape.py:153`.
- Route matching can hit `{task_id}` first for `/tasks/current`.

Impact:
- `/tasks/current` may return validation error path handling instead of current-task logic.

### 4.3 High: Watchdog misses stuck `PERMISSION_GRANTED` tasks
- `updated_at` is nullable with no insert default: `app/models/scrape_task.py:111`.
- Watchdog filter uses `ScrapeTask.updated_at < cutoff`: `app/services/watchdog.py:44`.
- Fresh tasks with `updated_at = NULL` will not satisfy `< cutoff`.

Impact:
- Tasks stuck before first state update may never be auto-failed, violating cleanup intent.

### 4.4 Medium-High: Migration/state evolution mismatch risk
- Old enum values introduced in `002`: `LLM_ANALYZED`, `OUTPUT_GENERATION`, `FINALIZED` (`alembic/versions/002_create_scrape_tasks.py:23-29`).
- New model uses `COMPLETED`/`FAILED` etc (`app/models/scrape_task.py:30-35`).
- Index in `003` excludes only `COMPLETED`/`FAILED` (`alembic/versions/003_update_task_states.py:50-53`).

Impact:
- Existing `FINALIZED` rows from older versions could still count as “active” under new partial index and block new tasks.
- Enum/domain drift can cause operational confusion and migration fragility.

### 4.5 Medium: “Per-user rate limiting” is not fully wired
- Key function expects `request.state.user`: `app/core/rate_limit.py:23-26`.
- No middleware/dependency sets `request.state.user`.

Impact:
- Limits effectively fall back to IP-based throttling, not authenticated-user throttling.

### 4.6 Medium: token subject conversion can throw 500 for malformed subject
- `int(payload.sub)` without guard: `app/api/deps.py:88`, `app/api/deps.py:123`, `app/api/v1/endpoints/auth.py:204`.

Impact:
- Malformed-but-decodable token payload can trigger server error instead of clean 401.

## 5. Half Implemented / Incomplete

### 5.1 LLM processing is a stub
- Explicitly marked stub: `app/services/llm_processor.py:2-5`, `app/services/llm_processor.py:26`.
- Returns mocked analysis after sleep.

Status: Half implemented.

### 5.2 Rate-limit settings and auth-specific limit constant are incomplete in usage
- `AUTH_RATE_LIMIT` exists but is not applied to auth endpoints: `app/core/rate_limit.py:42`.

Status: Half implemented.

### 5.3 Config fields not fully used by business logic
- `DEFAULT_DAILY_CREDITS`, `SCRAPE_CREDIT_COST`, `LLM_TIMEOUT`, `MAX_CONCURRENT_JOBS` declared (`app/core/config.py:95-104`) but not consistently enforced in runtime paths.

Status: Half implemented.

### 5.4 API schema docs and endpoint behavior mismatch
- `GET /tasks/current` response model allows `None` but implementation returns 404 when absent (`app/api/v1/endpoints/scrape.py:155`, `app/api/v1/endpoints/scrape.py:172-176`).

Status: Partially consistent.

## 6. Documentation and Project Claims Drift

### 6.1 README overstates currently implemented features
- Claims Playwright support (`README.md:12`) but no Playwright dependency/integration exists.
- Claims architecture doc link (`README.md:130`) but `docs/architecture.md` is missing.

### 6.2 Internal docs include outdated state-machine terminology
- `docs/learning/01_scrape_tasks_design.md` and some review files still center older states like `FINALIZED`, `LLM_ANALYZED`, `OUTPUT_GENERATION`.

Impact:
- Onboarding and implementation understanding can diverge from runtime reality.

## 7. Testing and Validation Readiness

Current state:
- `tests/` contains only `tests/__init__.py`.
- `pytest` is not installed in active env (`No module named pytest`).
- Syntax compilation succeeds (`python3 -m compileall app`).

Verdict:
- Project is not test-ready yet. Test framework and baseline test scaffold are the immediate next gap.

## 8. Full Inventory: Implemented vs Half-Implemented

### Implemented
- FastAPI app and router structure
- Auth register/login/refresh
- User and ScrapeTask models
- Alembic migrations 001-004
- Admission service
- Task state transitions
- Scraper service
- Background execution orchestration
- Scheduler and credit reset
- Health endpoints

### Half Implemented
- LLM integration (stub only)
- Rate-limiting strategy (partially wired and currently broken on `/scrape/start`)
- Config-driven governance (several config values declared but not enforced)
- Endpoint docs/behavior consistency (`/tasks/current`)
- Automated testing setup

## 9. Overall Assessment

The project has a strong MVP backend architecture with clear layering and good domain decomposition.  
However, there are a few high-impact correctness issues in endpoint wiring and lifecycle handling that should be fixed before test-writing and before production use.

Primary blockers to address first:
1. Fix `POST /scrape/start` SlowAPI request parameter wiring.
2. Reorder or constrain `/tasks/current` vs `/tasks/{task_id}` routing.
3. Fix watchdog queries to handle `updated_at IS NULL` (or use `created_at` fallback).
4. Resolve enum/index migration drift around legacy terminal states.
