# Phase 0 Bug Fixes & Stability Improvements

## Purpose & context
This document outlines the fixes implemented in Phase 0 to address several P0/P1 bugs in the ScrapGPT backend. These bugs fundamentally broke the state machine and core pipeline by introducing SQLAlchemy nested transaction errors, bypassed state invariants, and caused endpoints to crash on perfectly valid (or gracefully invalid) input. 

This task exists to enforce the system's core invariants, specifically ensuring that a task transitions atomically and reliably from one state to another without crashing or being silently swallowed by a race condition.

## Design decisions
1. **Isolated Transition Transactions:** The primary decision was to stop passing `db: AsyncSession` around from the pipeline orchestrator (`task_executor.py`) to individual transition functions (`task_state.py`).
   - *Why:* Because SQLAlchemy 2.0 strictly forbids `db.begin()` on a session that already has an active transaction. The orchestrator fetching the task auto-began a transaction, breaking the inner `db.begin()`.
   - *Alternative rejected:* Removing `db.begin()` from transitions and just committing on the outer session. Rejected because if an external call (like scraping) crashed in the orchestrator, we would have uncommitted state or potentially corrupt partial transactions. Isolated sessions enforce true atomicity per phase.
2. **Watchdog Terminal Guard Enforcement:** The watchdog was directly mutating `task.state = TaskState.FAILED`.
   - *Why:* This bypassed the state machine entirely. If a task raced to `COMPLETED` between the watchdog's `SELECT` and `COMMIT`, the watchdog would illegally overwrite a terminal state.
   - *Decision:* The watchdog now explicitly calls `transition_to_failed()` which inherently protects against overwriting a terminal state.
3. **Database Enum Drift:** We chose to write a pure SQL migration to `ALTER TYPE` and rebuild the Postgres enum, rather than squashing migrations.
   - *Why:* This cleanly brings the database into alignment with the Python models without forcing a complete DB wipe, respecting whatever state existed.

## Code walkthrough
- **`app/services/task_state.py`**: The home of all transitions. Every function here (`transition_to_scraping`, `transition_to_llm_processing`, etc.) now wraps its logic in `async with async_session_factory() as db: async with db.begin():`. This guarantees it has full, isolated control over the atomic commit. It also subtracts `settings.SCRAPE_CREDIT_COST` instead of a hardcoded `1`.
- **`app/services/task_executor.py`**: The pipeline orchestrator. It was stripped of its outer session and now relies solely on the transition functions to persist state. If an external API call fails, the catch block safely calls `transition_to_failed`.
- **`app/services/watchdog.py`**: Sweeps for stuck tasks. Added `func.coalesce(ScrapeTask.updated_at, ScrapeTask.created_at)` because new tasks might have a `NULL` `updated_at`, rendering them invisible to timeouts.
- **`app/api/v1/endpoints/scrape.py`**: API route parsing. Reordered `/tasks/current` above `/tasks/{task_id}` to prevent FastAPI from assigning the literal string "current" to `task_id`. Added `payload` and moved `request: Request` to the front of `start_scrape` to satisfy `SlowAPI` limitations.
- **`app/core/rate_limit.py`**: Standardized per-user rate limiting. It manually decodes the JWT `sub` from the `Authorization` header because standard FastAPI middleware cannot easily resolve `Depends` injections.

## Lifecycle & flow
1. User requests a scrape. `start_scrape` accepts the request, triggers a rate limit check (via IP or JWT), and enqueues a background task (`execute_scrape_pipeline`).
2. The orchestrator opens a short-lived session purely to grab the URL.
3. It calls `transition_to_scraping()`, which opens its *own* transaction, verifies the task isn't terminal, sets it to `SCRAPING`, and commits.
4. The orchestrator runs the physical scrape.
5. If successful, `transition_to_scraped()` does the same.
6. The Watchdog runs concurrently. If the task stalls, it queries it, passes the ID to `transition_to_failed()`, which opens a transaction, verifies the task hasn't suddenly finished, and marks it `FAILED`.

## Concurrency & failure analysis
- **Crash Safety:** If the pipeline crashes mid-scrape, the state remains strictly `SCRAPING`. The outer transaction no longer exists, meaning there is no "pending" state that gets rolled back into oblivion. The Watchdog will eventually pick it up and mark it `FAILED`.
- **Race Conditions:** If the Watchdog attempts to fail a task at the exact millisecond it finishes, `transition_to_failed()` locks the row (via the update), checks if it is in `TERMINAL_STATES`, and safely rejects the failure attempt.
- **Transactions:** Because each transition creates its own physical session, we cannot suffer from "already in transaction" errors or savepoint exhaustion.

## Things to be careful about
- **Orphaned Reads:** `task_executor.py` reads the URL using a short-lived session, then the session closes. The `task` object is immediately expired/detached. Do not attempt to access lazy-loaded attributes on it after the session closes.
- **State Machine Integrity:** Never manually set `task.state = ...` anywhere in the application. Always route through `task_state.py`.

## Future evolution
- As the pipeline grows, we may want to introduce a formal `Queue` (like Celery/Redis) instead of relying on FastAPI `BackgroundTasks`. The current atomic state transitions natively support this move, as they are fully decoupled from the orchestrator's state.

## Summary
The pipeline is now fundamentally safe against crashes and race conditions. By isolating database transactions into the individual state machine transitions, we ensure that every phase is permanently recorded, and the Watchdog correctly respects terminal boundaries.
