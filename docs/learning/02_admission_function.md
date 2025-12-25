# 02: Admission Function — Atomic Task Creation with Credit Deduction

> **File:** `app/services/admission.py`  
> **Core Operation:** Create scrape task + deduct credit atomically

---

## Purpose & Context

### What problem this solves

When a user starts a scrape job, we need to:

1. Create a task record (permission to scrape)
2. Charge them one credit (payment)

Both must happen together or neither happens. Without atomicity:

- User could get a task without paying (lost revenue)
- User could pay without getting a task (unfair)

### Why this exists

The admission function is the **single entry point** for task creation. It encapsulates:

- Transaction management
- Invariant enforcement (one active task per user)
- Credit deduction
- Error mapping

### Invariants enforced

1. **One active task per user** — enforced by partial unique index
2. **No task without credit** — enforced by transaction rollback
3. **No credit loss on failure** — enforced by transaction rollback

---

## Design Decisions

### Decision 1: INSERT first, then credit deduction

```python
# Correct order
1. INSERT scrape_task  # Prove permission
2. UPDATE credits -= 1  # Pay for it
```

**Why not credit first?**

| Order           | Problem                                                                                                                                                       |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Credit → INSERT | If INSERT fails (unique violation), we rolled back credit anyway. But now "permission" depends on user.credits, not the task constraint. Mental model broken. |
| INSERT → Credit | Permission proven by task row. Credit is just payment. Consistent with our invariant design.                                                                  |

**Also:** INSERT first is more efficient. The partial unique index rejects fast (index lookup). Credit deduction requires a write lock on the user row — only acquire that lock when we know task creation will succeed.

### Decision 2: Atomic UPDATE for credit deduction

```sql
UPDATE users
SET credits_remaining = credits_remaining - 1
WHERE id = $1 AND credits_remaining > 0
```

**Why not SELECT then UPDATE?**

| Approach                                 | Problem                                                                           |
| ---------------------------------------- | --------------------------------------------------------------------------------- |
| `SELECT credits; if credits > 0: UPDATE` | TOCTOU race. Two requests both read `credits = 1`, both pass check, both proceed. |
| `UPDATE WHERE credits > 0`               | Atomic. Database checks and decrements in single operation. No race.              |

### Decision 3: Return result object, not exception

```python
async def admit_scrape_task(...) -> AdmissionResult:
    # Returns AdmissionSuccess or AdmissionError
```

**Why?**

- Caller decides how to handle (HTTPException, logging, retry)
- Makes error cases explicit in type signature
- Easier to test

---

## Code Walkthrough

### Error Types

```python
class AdmissionErrorType(str, Enum):
    ALREADY_HAS_ACTIVE_TASK = "ALREADY_HAS_ACTIVE_TASK"
    INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"
```

Only two failure modes. Simple, explicit.

### Credit Reset (Outside Transaction)

```python
async def ensure_credits_reset(user: User, db: AsyncSession) -> None:
    if user.ensure_credits_reset():
        await db.commit()
        await db.refresh(user)
```

**Why outside main transaction?**

- Credit reset is idempotent (safe to do multiple times)
- Doesn't need atomicity with task creation
- Holding transaction open during reset increases lock contention

### Main Function

```python
async def admit_scrape_task(
    user: User,
    url: str,
    db: AsyncSession,
) -> AdmissionResult:
```

**Step 1: INSERT task**

```python
task = ScrapeTask(
    user_id=user.id,
    url=url,
    state=TaskState.PERMISSION_GRANTED,
)
db.add(task)

try:
    await db.flush()  # Trigger INSERT
except IntegrityError as e:
    await db.rollback()
    if "ix_one_active_task_per_user" in str(e.orig):
        return AdmissionError(...)
    raise
```

**`flush()` vs `commit()`:**

- `flush()` sends SQL to database but doesn't commit
- Allows us to catch constraint violations before commit
- If credit deduction fails, we can still rollback the INSERT

**Why check for specific index name?**

- Could be other integrity errors (foreign key, etc.)
- Only map the partial unique index violation to "already has active task"
- Re-raise unexpected errors

**Step 2: Atomic credit deduction**

```python
result = await db.execute(
    text("""
        UPDATE users
        SET credits_remaining = credits_remaining - 1,
            updated_at = NOW()
        WHERE id = :user_id AND credits_remaining > 0
    """),
    {"user_id": user.id},
)

if result.rowcount == 0:
    await db.rollback()
    return AdmissionError(
        error_type=AdmissionErrorType.INSUFFICIENT_CREDITS,
        message="Not enough credits",
    )
```

**Why raw SQL instead of ORM?**

- ORM would require: load user → check credits → modify → flush
- That's TOCTOU again
- Raw `UPDATE WHERE` is truly atomic

**`rowcount == 0` means:**

- No rows matched `WHERE id = ? AND credits > 0`
- Either user doesn't exist (shouldn't happen) or credits = 0

**Step 3: Commit and return**

```python
await db.commit()
await db.refresh(user)
await db.refresh(task)

return AdmissionSuccess(
    task=task,
    credits_remaining=user.credits_remaining,
)
```

---

## Lifecycle & Flow

### Happy Path

```
1. User has 3 credits, no active task
2. ensure_credits_reset() → no reset needed
3. BEGIN TRANSACTION
4. INSERT scrape_task → succeeds (index allows)
5. UPDATE credits = 2 WHERE credits > 0 → 1 row affected
6. COMMIT
7. Return AdmissionSuccess(task, credits=2)
```

### User already has active task

```
1. User has 3 credits, one active task
2. BEGIN TRANSACTION
3. INSERT scrape_task → FAILS (unique index violation)
4. ROLLBACK
5. Return AdmissionError("Already have active task")
```

Credits unchanged. Task not created.

### Insufficient credits

```
1. User has 0 credits, no active task
2. BEGIN TRANSACTION
3. INSERT scrape_task → succeeds
4. UPDATE credits WHERE credits > 0 → 0 rows affected
5. ROLLBACK
6. Return AdmissionError("Not enough credits")
```

Task rolled back. Credits unchanged.

---

## Concurrency & Failure Analysis

### Race: Two requests for same user

```
Request A: INSERT task
Request B: INSERT task (same user)
```

**What happens:**

1. A's INSERT starts, acquires row lock in index
2. B's INSERT waits for lock
3. A's flush succeeds, proceeds to credit deduction
4. A commits
5. B's INSERT now fails (unique index violation)
6. B returns "Already have active task"

**Result:** Only one task created. Database handles it.

### Race: INSERT succeeds but credit deduction races

```
Request A: INSERT succeeds, about to UPDATE credits
Request B: Same user, different browser, tries to deduct credits for something else
```

**What happens:**

1. A's transaction holds write intent on task row
2. B's UPDATE on user row proceeds (different table)
3. A's UPDATE on user row waits for B if B has lock, or proceeds
4. Both UPDATEs are atomic — no double deduction possible

The `UPDATE WHERE credits > 0` ensures only one succeeds if only one credit remains.

### Crash scenarios

| Crash point                        | Result                                          |
| ---------------------------------- | ----------------------------------------------- |
| After INSERT, before credit UPDATE | Transaction uncommitted, rolled back on restart |
| After credit UPDATE, before COMMIT | Transaction uncommitted, rolled back on restart |
| After COMMIT                       | Success persisted, safe                         |

**No partial state is ever visible to other transactions.**

---

## Things to be Careful About

### ⚠️ Never bypass `admit_scrape_task` for task creation

```python
# WRONG: Creates task without deducting credit
task = ScrapeTask(user_id=user.id, url=url)
db.add(task)
await db.commit()

# RIGHT: Use admission function
result = await admit_scrape_task(user, url, db)
```

### ⚠️ Don't call `db.commit()` before `admit_scrape_task`

```python
# WRONG: Breaks transaction atomicity
await db.commit()  # Any pending changes committed
result = await admit_scrape_task(user, url, db)  # New transaction

# RIGHT: Let admit_scrape_task manage its own transaction
result = await admit_scrape_task(user, url, db)
```

### ⚠️ The user object must be attached to the session

```python
# WRONG: User from different session
user = await other_db.get(User, user_id)
result = await admit_scrape_task(user, url, db)  # user.id works, but refresh fails

# RIGHT: Get user from same session
user = await db.get(User, user_id)
result = await admit_scrape_task(user, url, db)
```

### ⚠️ Check result type before using

```python
result = await admit_scrape_task(user, url, db)

# WRONG: Assumes success
task = result.task  # AttributeError if AdmissionError

# RIGHT: Check type
if isinstance(result, AdmissionError):
    raise HTTPException(409, result.message)
task = result.task
```

---

## Future Evolution

### Safe extensions

| Change                                   | Impact                               |
| ---------------------------------------- | ------------------------------------ |
| Add more fields to ScrapeTask            | Safe, just update INSERT             |
| Add logging/metrics                      | Safe, add after commit               |
| Add different credit costs per task type | Modify UPDATE to use variable amount |

### Changes requiring rethinking

| Change                      | Why it's risky                                        |
| --------------------------- | ----------------------------------------------------- |
| Allow multiple active tasks | Must remove/modify unique index, admission logic      |
| Deferred credit deduction   | Breaks atomicity guarantee                            |
| External payment (Stripe)   | Payment happens before INSERT (can't rollback Stripe) |

---

## Summary

The admission function atomically creates a scrape task and deducts a credit using INSERT-then-UPDATE ordering within a single database transaction. The INSERT comes first because "permission is proven by existence of task row" — the partial unique index is the source of truth, not the credit balance. Credit deduction uses a conditional atomic `UPDATE WHERE credits > 0` to avoid TOCTOU races.

**Key points to remember:**

1. INSERT first, credit second — matches our invariant philosophy
2. `flush()` to catch unique violation before commit
3. `UPDATE WHERE credits > 0` is atomic — no read-before-write
4. `rowcount == 0` means insufficient credits
5. Caller handles the result type (success vs error)
6. Never bypass this function for task creation
