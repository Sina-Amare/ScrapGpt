# Current Status — Known Issues

Last updated: 2026-05-15

For the full roadmap and what to build next, see [plan/MASTER_PLAN.md](plan/MASTER_PLAN.md).
For architecture details, see [architecture.md](architecture.md).

---

## Status Board

| Area                                 | Status                        |
| ------------------------------------ | ----------------------------- |
| FastAPI bootstrap, routing, lifespan | ✅ Done                       |
| Auth (register / login / refresh)    | ✅ Done                       |
| User + ScrapeTask data model         | ✅ Done                       |
| State machine + transitions          | ✅ Done                       |
| Admission (credits + one active)     | ✅ Done                       |
| Async pipeline orchestration         | ✅ Done                       |
| Scraper (httpx + BeautifulSoup)      | ✅ Done                       |
| Health / readiness                   | ✅ Done                       |
| Daily credit reset (multi-instance)  | ✅ Done                       |
| Watchdog (stuck-task cleanup)        | ⚠️ Has NULL-skip bug          |
| `POST /scrape/start` rate limiting   | 🔴 Broken (SlowAPI collision) |
| `/scrape/tasks/current` routing      | 🔴 Shadowed by `{task_id}`    |
| LLM integration                      | 🟡 Stub only                  |
| Frontend                             | 🟡 Not started                |
| Test suite                           | 🟡 Skeleton only              |

---

## Bugs to Fix (Phase 0)

These must be fixed before building new features.

### 1. SlowAPI parameter collision 🔴

**File:** `app/api/v1/endpoints/scrape.py:64-69`

The `request` param is the Pydantic body model, but SlowAPI expects `starlette.requests.Request`. Rename body to `payload`, put `request: Request` first.

### 2. Route shadowing 🔴

**File:** `app/api/v1/endpoints/scrape.py:124 vs 153`

`/tasks/{task_id}` is declared before `/tasks/current`. Move the static route above the dynamic one.

### 3. Watchdog NULL-skip 🔴

**File:** `app/services/watchdog.py:44`

`updated_at` is nullable with no insert default. Use `COALESCE(updated_at, created_at)` in the filter.

### 4. Migration enum drift 🟠

Old enum values (`FINALIZED`, `LLM_ANALYZED`, `OUTPUT_GENERATION`) exist in migration 002 but aren't used by the current model. Squash migrations to a clean baseline since there's no production data.

### 5. JWT `int()` cast can 500 🟠

**File:** `app/api/deps.py:88`

`int(payload.sub)` raises `ValueError` for malformed tokens. Wrap in try/except → 401.

---

## What's Next

See [plan/MASTER_PLAN.md](plan/MASTER_PLAN.md) — Phase 0 (bug fixes) then Phase 1 (Gemini AI integration).
