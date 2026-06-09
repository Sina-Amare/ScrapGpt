# ScrapGPT Docs

## Recommended Reading Path

Read these in order to understand what exists now and how it was built:

1. [STATUS.md](STATUS.md) — current runnable product surface, verification snapshot, and what is not implemented yet.
2. [product/strategic_redesign.md](product/strategic_redesign.md) — product vision and remaining roadmap.
3. [learning/02_phase_0_5_provider_foundation.md](learning/02_phase_0_5_provider_foundation.md) — BYOK provider model, credit removal, encrypted keys.
4. [learning/03_showcase_frontend_phase05.md](learning/03_showcase_frontend_phase05.md) — first frontend shell and provider/task UX.
5. [learning/06_phase1_analysis_jobs.md](learning/06_phase1_analysis_jobs.md) — Phase 1 analysis jobs: URL safety, robots, fetcher, DOM summary, cached LLM analysis, frontend jobs UI.
6. [learning/07_frontend_robustness_and_polish.md](learning/07_frontend_robustness_and_polish.md) — final Phase 1 UX polish and browser error handling.
7. [learning/08_project_workflow_migration.md](learning/08_project_workflow_migration.md) — Project workflow migration: Analyze → Fields → Preview → Extract → Results.
8. [learning/09_phase2_real_extraction_engine.md](learning/09_phase2_real_extraction_engine.md) — real selector preview, same-site crawling, persisted records, and CSV/JSON/XLSX export.
9. [learning/10_phase25_scope_frontier_trust.md](learning/10_phase25_scope_frontier_trust.md) — crawl scope, frontier preview, scope confirmation, trust signals, paginated results, and validation.

Use the remaining learning docs when you need detail about the older legacy scrape pipeline or security fixes.

## Product & Roadmap

- [STATUS.md](STATUS.md) — Current implementation snapshot: what works, what is not built yet, and last verified commands.
- [product/strategic_redesign.md](product/strategic_redesign.md) — **Active roadmap.** Full product vision, architecture decisions, phased plan (Phases 0.5–6), data model, API surface, risks. Start here.

## Historical Reference

- [archive/project_master.md](archive/project_master.md) — Phase 0 reference. Original credit-based system — architecture, setup, and testing for the pre-redesign codebase. Superseded by `product/strategic_redesign.md`.

## Decision Logs

Added after every non-trivial implementation task. Explain the *why*, not just the *what*.

- [learning/01_phase0_security_fixes.md](learning/01_phase0_security_fixes.md) — Why: verified JWT rate-limit keying, refresh route limit, watchdog guard, ownership non-mutation.
- [learning/02_phase_0_5_provider_foundation.md](learning/02_phase_0_5_provider_foundation.md) — Why: remove credits, add BYOK provider configs, encrypt provider keys.
- [learning/03_showcase_frontend_phase05.md](learning/03_showcase_frontend_phase05.md) — Why: first React frontend shell and backend-connected control surface.
- [learning/04_polish_and_tests.md](learning/04_polish_and_tests.md) — Why: frontend polish and test hardening before Phase 1.
- [learning/05_task_deletion_and_results_view.md](learning/05_task_deletion_and_results_view.md) — Why: task result viewing and terminal-task deletion.
- [learning/06_phase1_analysis_jobs.md](learning/06_phase1_analysis_jobs.md) — Why: Phase 1 analysis jobs, SSRF-safe fetch, robots, DOM summary, cached LLM analysis.
- [learning/07_frontend_robustness_and_polish.md](learning/07_frontend_robustness_and_polish.md) — Why: layout robustness, honest analysis-state copy, legacy nav demotion, browser error quality.
- [learning/08_project_workflow_migration.md](learning/08_project_workflow_migration.md) — Why: migrate from jobs to projects and preserve compatibility while adding spec/preview/results contracts.
- [learning/09_phase2_real_extraction_engine.md](learning/09_phase2_real_extraction_engine.md) — Why: replace seed/sample extraction with deterministic selector execution and bounded same-site crawling.
- [learning/10_phase25_scope_frontier_trust.md](learning/10_phase25_scope_frontier_trust.md) — Why: add explicit crawl intent, preview what will be crawled, block unconfirmed broad crawls, and expose extraction quality.

## Reviews & Validation

- [reviews/01_codebase_audit.md](reviews/01_codebase_audit.md) — Code-first project audit before Phase 2.5.
- [reviews/02_product_ux_strategy.md](reviews/02_product_ux_strategy.md) — Product UX and architecture strategy review.
- [reviews/03_phase25_validation.md](reviews/03_phase25_validation.md) — Post-Step-4 validation report with 8/8 E2E scenarios passing.

## Operations

- [ops/health.md](ops/health.md) — Operator guide for `/health/ready` — probe steps, reason codes, debugging.
