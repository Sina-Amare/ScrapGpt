# 04: Pipeline Bug Fixes — Credit Reset, Transactions, Security

> **Scope:** Credit reset bypass, transaction bugs, ownership validation  
> **Impact:** Production-critical fixes for reliability and security

---

## Issues Fixed

### 1. Credit Reset Bypass (HIGH)

**Problem:** Lazy credit reset was removed from admission flow. Users with 0 credits got stuck indefinitely.

**Fix:** Implemented scheduled midnight UTC reset with multi-instance safety.

```python
# app/core/scheduler.py
async def try_reset_all_credits():
    today = datetime.now(timezone.utc).date().isoformat()

    # Atomic check-and-set prevents duplicate resets
    result = await db.execute(text("""
        UPDATE system_state
        SET value = :today, updated_at = NOW()
        WHERE key = 'last_credit_reset' AND value != :today
    """), {"today": today})

    if result.rowcount == 0:
        return  # Already reset by another instance

    # This instance wins - reset all credits
    await db.execute(text("""
        UPDATE users SET credits_remaining = daily_credit_limit
    """))
```

**Key design:** First instance after midnight wins, others skip.

---

### 2. Admission Credit Check (HIGH)

**Problem:** Users with 0 credits could start tasks that would fail at LLM phase.

**Fix:** Block at admission if credits = 0.

```python
# app/services/admission.py
if user.credits_remaining <= 0:
    return AdmissionError(
        error_type=AdmissionErrorType.INSUFFICIENT_CREDITS,
        message="Insufficient credits. Credits reset daily at 00:00 UTC.",
    )
```

---

### 3. Transaction Bug (MEDIUM)

**Problem:** `db.commit()` called inside `async with db.begin()` block.

```python
# BEFORE (BUG)
async with db.begin():
    if result.rowcount == 0:
        task.state = TaskState.FAILED
        await db.commit()  # WRONG - inside managed block
```

**Fix:** Let context manager handle commit/rollback.

```python
# AFTER (FIXED)
async with db.begin():
    if result.rowcount == 0:
        task.state = TaskState.FAILED
        # Context manager commits on exit

await db.refresh(task)
if task.state == TaskState.FAILED:
    return TransitionResult(success=False, ...)
```

---

### 4. Ownership Validation (MEDIUM)

**Problem:** Task executor trusted caller-provided `user_id` without verification.

**Fix:** Validate task ownership before processing.

```python
# app/services/task_state.py
if task.user_id != user_id:
    logger.error("security.ownership_mismatch", ...)
    return TransitionResult(
        success=False,
        error="Task ownership mismatch",
    )
```

---

### 5. Hardcoded Timeouts (LOW)

**Problem:** Timeouts hardcoded, ignoring config.

**Fix:** Use settings.

```python
# Before
SCRAPE_TIMEOUT = 60.0

# After
timeout=settings.SCRAPE_TIMEOUT
```

---

## Files Changed

| File                                   | Change                       |
| -------------------------------------- | ---------------------------- |
| `alembic/versions/004_system_state.py` | NEW: system_state table      |
| `app/core/scheduler.py`                | NEW: APScheduler + reset job |
| `app/core/config.py`                   | Added timeout settings       |
| `app/main.py`                          | Scheduler start/stop         |
| `app/services/admission.py`            | Credit check at admission    |
| `app/services/task_state.py`           | Transaction fix + ownership  |
| `app/services/scraper.py`              | Configurable timeout         |
| `app/services/watchdog.py`             | Configurable timeout         |
| `requirements.txt`                     | Added apscheduler            |

---

## User-Facing Policy

> **Credits reset daily at 00:00 UTC.**

All error messages and API responses reflect this.

---

## Multi-Instance Safety

```
Instance A (starts at 00:00:01 UTC):
  1. Check system_state.last_credit_reset
  2. Value = "2024-12-30" (yesterday)
  3. UPDATE SET value = "2024-12-31" (today) WHERE value != today
  4. rowcount = 1 → WINS
  5. Reset all credits

Instance B (starts at 00:00:02 UTC):
  1. Check system_state.last_credit_reset
  2. Already updated by A
  3. UPDATE WHERE value != today → rowcount = 0
  4. Skip (already done)
```

---

## Risks Avoided

| Risk                     | Mitigation                        |
| ------------------------ | --------------------------------- |
| Duplicate credit reset   | DB-locked check-and-set           |
| Wrong user charged       | Ownership validation              |
| Transaction corruption   | Proper context manager usage      |
| Users stuck at 0 credits | Admission check + scheduled reset |

---

## Verification Commands

Run these to verify:

```bash
# Verify imports
python -c "from app.core.scheduler import start_scheduler; print('OK')"

# Verify migration
alembic upgrade head

# Check system_state initialized
psql -c "SELECT * FROM system_state"
```
