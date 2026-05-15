# 01: ScrapeTask Schema & Invariant Enforcement

> **Files:** `app/models/scrape_task.py`, `alembic/versions/`
> **Invariant:** At most one non-terminal task per user

---

## Purpose & Context

### What problem this solves

Users submit URLs for scraping and AI analysis. Each job goes through multiple states before completion. We need to:

1. Track job progress through states
2. Prevent users from starting multiple jobs simultaneously (resource control)
3. Allow completed jobs to accumulate (history)

### Why this exists

Without this constraint, a user could:

- Spam unlimited scrape requests
- Overwhelm AI/LLM resources
- Create race conditions in downstream processing

The invariant "at most one non-terminal task per user" forces sequential processing per user while allowing parallel processing across different users.

### The invariant

```
For any user_id, COUNT(tasks WHERE state NOT IN ('COMPLETED', 'FAILED')) <= 1
```

This is enforced at the **database level**, not application level.

---

## Design Decisions

### Decision 1: Partial unique index (chosen)

```sql
CREATE UNIQUE INDEX ix_one_active_task_per_user
ON scrape_tasks (user_id)
WHERE state NOT IN ('COMPLETED', 'FAILED');
```

**Alternatives considered:**

| Option                                      | Description                         | Why rejected                                                                      |
| ------------------------------------------- | ----------------------------------- | --------------------------------------------------------------------------------- |
| Application-level check                     | `SELECT COUNT(*) ... BEFORE INSERT` | Race conditions: two requests could check simultaneously, both see 0, both insert |
| Full unique index on `(user_id, is_active)` | Add boolean column                  | Requires maintaining another field; partial index is cleaner                      |
| Database trigger                            | `BEFORE INSERT` trigger with check  | More code, same result, harder to debug                                           |

**Trade-off accepted:** Partial indexes are PostgreSQL-specific. If we migrate to MySQL, we'd need triggers.

### Decision 2: Enum for states

```python
class TaskState(str, enum.Enum):
    PERMISSION_GRANTED = "PERMISSION_GRANTED"
    SCRAPING = "SCRAPING"
    SCRAPED = "SCRAPED"
    LLM_PROCESSING = "LLM_PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
```

**Why `str, enum.Enum`?**

- `str` inheritance means `TaskState.COMPLETED == "COMPLETED"` is `True`
- JSON serialization works automatically
- PostgreSQL enum maps cleanly to string values

**Why native PostgreSQL enum (not VARCHAR)?**

- Type safety at database level
- Invalid values rejected by PostgreSQL
- Slight storage efficiency

### Decision 3: State machine with explicit transitions

```python
VALID_TRANSITIONS = {
    TaskState.PERMISSION_GRANTED: [TaskState.SCRAPING],
    TaskState.SCRAPING: [TaskState.SCRAPED, TaskState.FAILED],
    TaskState.SCRAPED: [TaskState.LLM_PROCESSING, TaskState.FAILED],
    TaskState.LLM_PROCESSING: [TaskState.COMPLETED, TaskState.FAILED],
    TaskState.COMPLETED: [],  # Terminal
    TaskState.FAILED: [],     # Terminal
}
```

Every transition is validated before execution. `FAILED` is reachable from any non-terminal state. `COMPLETED` is only reachable from `LLM_PROCESSING`.

### Decision 4: `ON DELETE CASCADE`

```sql
user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
```

When a user is deleted, all their tasks are deleted automatically. Orphaned tasks have no value.

---

## State Machine Flow

```
PERMISSION_GRANTED → SCRAPING → SCRAPED → LLM_PROCESSING → COMPLETED
                         ↓          ↓            ↓
                       FAILED     FAILED       FAILED
```

**Terminal states:** `COMPLETED`, `FAILED`

The pipeline guarantees every task reaches a terminal state ("always-finalize"). The watchdog catches any that get stuck.

---

## Concurrency & Failure Analysis

### Race condition: Two simultaneous INSERTs

```
Request A: INSERT ... (user_id=1, state='PERMISSION_GRANTED')
Request B: INSERT ... (user_id=1, state='PERMISSION_GRANTED')
```

**What happens:**

1. PostgreSQL acquires row-level lock on the index entry
2. Request A acquires lock first, INSERT succeeds
3. Request B waits for lock, then checks index, finds A's row
4. Request B fails with unique violation

**Result:** Only one task created. Database guarantees atomicity.

### Process crash scenarios

| Crash point                             | State after restart           |
| --------------------------------------- | ----------------------------- |
| During INSERT (before commit)           | No task exists, index clean   |
| During state transition (before commit) | Old state preserved           |
| After commit                            | New state persisted correctly |

---

## Things To Be Careful About

### ⚠️ Never rename enum values casually

Enum values are stored as strings in PostgreSQL. Changing them requires a database migration.

### ⚠️ The partial index condition must match terminal states

If you add a new terminal state (e.g., `CANCELLED`), update the index:

```sql
WHERE state NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')
```

### ⚠️ Raw SQL updates won't trigger `onupdate`

```python
# This sets updated_at (via SQLAlchemy):
task.state = TaskState.SCRAPED
await db.commit()

# This does NOT set updated_at:
await db.execute(text("UPDATE scrape_tasks SET state='SCRAPED' WHERE id=1"))
```

### ⚠️ Don't trust application-level checks alone

```python
# WRONG: Race condition possible
if not await has_active_task(user_id):
    await create_task(user_id)

# RIGHT: Let the database enforce via IntegrityError
try:
    await create_task(user_id)
except IntegrityError:
    raise HTTPException(409, "Already have active task")
```

---

## Summary

The `scrape_tasks` table uses a **partial unique index** to enforce that each user can have at most one non-terminal task. This enforcement happens at the **database level**, making it immune to application-level race conditions.

**Key points:**

1. The index only covers rows where `state NOT IN ('COMPLETED', 'FAILED')`
2. Terminal tasks are excluded from the constraint, allowing unlimited history
3. Concurrent INSERTs are handled atomically by PostgreSQL
4. Adding new intermediate states is safe; adding new terminal states requires index update
5. State transitions are validated by `VALID_TRANSITIONS` in application code
