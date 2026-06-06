# docs/

## Product & Roadmap

- [product/strategic_redesign.md](product/strategic_redesign.md) — **Active roadmap.** Full product vision, architecture decisions, phased plan (Phases 0.5–6), data model, API surface, risks. Start here.

## Historical Reference

- [archive/project_master.md](archive/project_master.md) — Phase 0 reference. Original credit-based system — architecture, setup, and testing for the pre-redesign codebase. Superseded by `product/strategic_redesign.md`.

## Decision Logs

Added after every non-trivial implementation task. Explain the *why*, not just the *what*.

- [learning/01_scrape_tasks_design.md](learning/01_scrape_tasks_design.md) — Why: partial unique index, state machine design, concurrency safety.
- [learning/02_admission_and_credits.md](learning/02_admission_and_credits.md) — Why: credit deduction at LLM phase, not at admission.
- [learning/03_async_scrape_pipeline.md](learning/03_async_scrape_pipeline.md) — Why: always-finalize guarantee, background task pattern, watchdog.
- [learning/04_pipeline_fixes.md](learning/04_pipeline_fixes.md) — Why: credit reset CAS, transaction isolation, ownership validation.
- [learning/05_phase0_security_fixes.md](learning/05_phase0_security_fixes.md) — Why: rate-limit key uses verify_token, refresh endpoint rate-limited.

## Operations

- [ops/health.md](ops/health.md) — Operator guide for `/health/ready` — probe steps, reason codes, debugging.
