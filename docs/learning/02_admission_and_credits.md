# 02: Admission Gate & Credit Deduction Strategy

> **ARCHIVED — Phase 0.5 removed the credit system entirely.**
> Credits, `credits_remaining`, `daily_credit_limit`, `credits_reset_at`, and
> `system_state` were dropped in migration `005`. The partial unique index was also
> dropped. Admission now checks `MAX_CONCURRENT_JOBS_PER_USER` (configurable count,
> default 3) with no credit gate. See `docs/learning/06_phase_0_5_provider_foundation.md`
> for the current admission design.
>
> This document is kept as historical context for why the credit approach was
> rejected in favour of a self-hosted resource-control model.

---

> **Files:** `app/services/admission.py`, `app/services/task_state.py`
> **Core Decision (historical):** Credits deducted at LLM phase, not at admission

---

## Purpose & Context

### What problem this solves

When a user starts a scrape job, we need to:

1. Verify they have credits (gate)
2. Verify they don't already have an active task (one-at-a-time)
3. Create the task
4. Eventually charge them (but only if we actually use expensive resources)

### The two-stage approach

**Admission** (at request time):

- Checks credits >= 1 (gate only, no deduction)
- Checks no active task exists
- Creates task in `PERMISSION_GRANTED` state
- Returns 202 immediately

**Credit deduction** (at LLM phase, in background):

- Happens atomically with the `SCRAPED → LLM_PROCESSING` transition
- Same transaction: state change + credit decrement
- If credits somehow hit 0 between admission and LLM phase, task fails gracefully

---

## Why Deduct at LLM Phase (Not Admission)

This was a deliberate design choice. Three options were considered:

| Timing           | Pros                                                    | Cons                                      |
| ---------------- | ------------------------------------------------------- | ----------------------------------------- |
| At admission     | Simple, predictable                                     | User pays for failed scrapes (unfair)     |
| At completion    | User only pays for success                              | Users can spam expensive scrapes for free |
| **At LLM phase** | Fair: scrape succeeded, about to use expensive resource | Slightly more complex                     |

**Chosen: LLM phase.** Rationale:

- Scraping can fail for reasons outside user's control (target down, bot block, timeout)
- If we charged at admission, every transient failure costs the user a credit
- By the time we reach LLM phase, we have content — we're about to spend real resources
- Failures before this point cost nothing; failures after cost a credit (we already consumed resources)

---

## Admission Service (`app/services/admission.py`)

### What it does

```python
async def admit_scrape_task(user, url, db) -> AdmissionResult:
```

1. Check `user.credits_remaining > 0` — if not, return `INSUFFICIENT_CREDITS`
2. Create `ScrapeTask(state=PERMISSION_GRANTED)`
3. Try to flush — if partial unique index rejects, return `ALREADY_HAS_ACTIVE_TASK`
4. Commit and return `AdmissionSuccess(task)`

### What it does NOT do

- Does not deduct credits (that happens later)
- Does not start the pipeline (endpoint does that via BackgroundTasks)
- Does not validate the URL beyond what Pydantic already did

### Error handling

The admission function returns a result object, not an exception:

```python
AdmissionResult = AdmissionSuccess | AdmissionError
```

The endpoint translates errors to HTTP codes:

- `INSUFFICIENT_CREDITS` → 402
- `ALREADY_HAS_ACTIVE_TASK` → 409

---

## Atomic Credit Deduction (`app/services/task_state.py`)

### Where it happens

```python
async def transition_to_llm_processing(task_id, user_id, db):
    async with db.begin():
        # 1. Validate task state and ownership
        # 2. Atomic credit deduction:
        result = await db.execute(text("""
            UPDATE users
            SET credits_remaining = credits_remaining - 1
            WHERE id = :user_id AND credits_remaining > 0
        """), {"user_id": user_id})

        if result.rowcount == 0:
            task.state = TaskState.FAILED
            task.error = "Insufficient credits"
            # Transaction commits FAILED state
            return

        # 3. State change (same transaction)
        task.state = TaskState.LLM_PROCESSING
        # Transaction commits both changes atomically
```

### Why this is safe

- `UPDATE WHERE credits > 0` is atomic — no TOCTOU race
- Credit deduction and state change are in the same transaction
- Either both happen or neither happens
- If credits hit 0 between admission and here, task fails cleanly

---

## Concurrency Analysis

### Two requests from same user

```
Request A: admit_scrape_task → INSERT succeeds
Request B: admit_scrape_task → INSERT fails (unique index)
```

Database handles it. Only one task created.

### Credit race (user has 1 credit, two tasks somehow reach LLM phase)

This can't happen because of the one-active-task invariant. But even if it could:

```
Task A: UPDATE credits SET credits - 1 WHERE credits > 0 → rowcount = 1 (wins)
Task B: UPDATE credits SET credits - 1 WHERE credits > 0 → rowcount = 0 (fails)
```

The atomic UPDATE prevents double-deduction.

---

## Key Invariants

1. **Credits checked at admission** — blocks obviously-broke users early
2. **Credits deducted at LLM phase** — only charges when we're about to use expensive resources
3. **Deduction is atomic** — `UPDATE WHERE credits > 0` in same transaction as state change
4. **No partial state** — transaction ensures both credit deduction and state change succeed or both fail
5. **One active task per user** — partial unique index prevents concurrent tasks

---

## Things To Be Careful About

### ⚠️ Don't deduct credits anywhere else

`transition_to_llm_processing` is the ONLY place credits are deducted. If you add a new credit-consuming feature, follow the same pattern.

### ⚠️ The admission credit check is a gate, not a guarantee

Between admission and LLM phase, credits could theoretically change (admin adjustment, concurrent edge case). The LLM-phase deduction handles this gracefully by failing the task.

### ⚠️ Don't bypass admission for task creation

```python
# WRONG: Creates task without any checks
task = ScrapeTask(user_id=user.id, url=url)
db.add(task)

# RIGHT: Use admission function
result = await admit_scrape_task(user, url, db)
```

---

## Summary

The admission service is the single entry point for task creation. It gates on credits and active-task count but does NOT deduct credits. Credit deduction happens later, atomically with the LLM-phase state transition. This design ensures users aren't charged for failed scrapes while still preventing abuse.
