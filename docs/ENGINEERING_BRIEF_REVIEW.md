# Engineering Brief Review

Date: 2026-06-10

Scope: independent code-first audit of the "ScrapGPT Engineering Briefing" claim set. The briefing was treated as untrusted input. Evidence below comes from the current working tree unless explicitly described as historical documentation.

Targeted validation run:

```powershell
venv\Scripts\python.exe -m pytest tests\api\v1\test_projects_phase25.py tests\services\test_crawl_scope.py tests\services\test_frontier_preview.py tests\services\test_project_workflow.py tests\core\test_scheduler.py tests\core\test_logging_security.py -q
```

Result: 122 passed, 32 warnings.

Important scope note: I did not run the live Phase 2.5 E2E harness (`tests/validation/run_validation.py`) because this task was a review of the briefing, not a full product certification run. The repository contains historical 8/8 evidence in `docs/reviews/03_phase25_validation.md`; that is not the same as a fresh 8/8 run on this dirty working tree.

## Executive Verdict

The briefing is directionally accurate and useful, but it overstates readiness in several places. It correctly identifies the two most important current risks: legacy `/scrape` SSRF exposure and missing crawl-page lease recovery. It also correctly identifies the watchdog gap for project extraction states.

The main corrections are:

- `ProjectState` currently has 13 states, not 12 (`app/models/job.py:18`).
- "Production-ready" is used too broadly. Several areas are production-ready only under the documented single-instance/self-hosted assumptions.
- Phase 2.5 "8/8 scenarios passed" is supported by historical validation docs and the validation harness, but was not freshly proven by this review.
- Some roadmap/documentation inaccuracies are intentional target-state content in `strategic_redesign.md`, not necessarily documentation bugs.
- The briefing misses a serious extraction reliability issue: if all crawled pages are blocked or fail, extraction can still advance to `COMPLETED` with zero records because per-page failures are isolated and project-level completion is based on crawl loop completion.

## 1. Current Project State

| Claim | Status | Evidence |
| --- | --- | --- |
| ScrapGPT is a self-hosted BYOK AI-assisted web extraction platform. | VERIFIED | BYOK provider config stores encrypted provider keys (`app/models/provider_config.py:31`), provider APIs exist (`app/api/v1/endpoints/providers.py`), and project workflow APIs exist under `/projects` (`app/api/v1/endpoints/projects.py`). README describes the current self-hosted workflow (`README.md:7`, `README.md:13`). |
| Primary workflow is URL -> Analyze -> Choose Fields -> Preview -> Extract -> Results. | VERIFIED | Frontend routes and `ProjectDetailPage` wire analyze, spec editing, preview, extract, trust/results panels (`frontend/src/pages/NewProjectPage.tsx`, `frontend/src/pages/ProjectDetailPage.tsx:157`, `frontend/src/pages/ProjectDetailPage.tsx:421`, `frontend/src/pages/ProjectDetailPage.tsx:487`, `frontend/src/pages/ProjectDetailPage.tsx:515`, `frontend/src/pages/ProjectDetailPage.tsx:647`). Backend has matching endpoints (`app/api/v1/endpoints/projects.py:201`, `app/api/v1/endpoints/projects.py:304`, `app/api/v1/endpoints/projects.py:346`, `app/api/v1/endpoints/projects.py:428`, `app/api/v1/endpoints/projects.py:484`). |
| Backend stack is FastAPI, SQLAlchemy async, PostgreSQL, Alembic. | VERIFIED | `requirements.txt:13`, `requirements.txt:28`, `requirements.txt:32`; async DB setup in `app/db/database.py`; Alembic migrations exist under `alembic/versions/`. |
| Frontend stack is React 18, Vite, TanStack Query, Tailwind. | VERIFIED | `frontend/package.json:15`, `frontend/package.json:17`, `frontend/package.json:18`, `frontend/package.json:40`; Tailwind config in `frontend/tailwind.config.ts:4`. |
| Background work uses FastAPI BackgroundTasks plus APScheduler watchdog. | VERIFIED | Project and legacy endpoints enqueue background tasks (`app/api/v1/endpoints/projects.py:428`, `app/api/v1/endpoints/scrape.py:75`). Scheduler registers one watchdog job (`app/core/scheduler.py:41`, `tests/core/test_scheduler.py:10`). |
| There are two parallel pipelines: project workflow and legacy `/scrape`. | VERIFIED | `/projects` router in `app/api/v1/endpoints/projects.py`; `/scrape` router in `app/api/v1/endpoints/scrape.py:38`; legacy frontend route remains at `frontend/src/App.tsx:38`. |
| Phase 2.5 is complete and validated 8/8. | PARTIALLY VERIFIED | Code and tests for Phase 2.5 are present: `tests/api/v1/test_projects_phase25.py`, `tests/validation/run_validation.py`, `docs/reviews/03_phase25_validation.md`. Focused tests passed in this review. Historical live E2E evidence says 8/8 passed (`docs/reviews/03_phase25_validation.md`). I did not rerun the live harness. |
| Next phase is Phase 3 visual interaction. | VERIFIED | `docs/product/strategic_redesign.md:554` names "Phase 3 - Full UI + Visual Interaction". This is roadmap status, not implementation status. |

## 2. Implemented Capabilities

| Capability claim | Status | Evidence and correction |
| --- | --- | --- |
| Auth with JWT and bcrypt, password-confirmed key reveal. | VERIFIED | Security helpers in `app/core/security.py`; reveal route verifies password before decrypting (`app/api/v1/endpoints/providers.py:145`, `app/api/v1/endpoints/providers.py:160`). |
| BYOK provider management with Fernet-encrypted keys, advisory-lock writes, capability detection, redaction. | VERIFIED | Fernet encrypt/decrypt in `app/services/provider_service.py:73`, `app/services/provider_service.py:78`; advisory lock in `app/services/provider_service.py:169`; capability detection and stored flags in `app/services/provider_service.py:441`; redaction helpers in `app/services/provider_service.py:83`. |
| SSRF-safe URL validation. | VERIFIED for project/fetcher paths; INCORRECT for legacy `/scrape`. | Validator blocks schemes and private/metadata ranges (`app/services/url_validator.py:89`). Fetcher validates redirects (`app/services/fetcher.py:89`, `app/services/fetcher.py:123`). Legacy `/scrape` only uses Pydantic `HttpUrl` and then calls `scrape_url()` (`app/api/v1/endpoints/scrape.py:42`, `app/api/v1/endpoints/scrape.py:93`, `app/services/scraper.py:42`) with no `validate_url()` call. |
| Robots checks. | VERIFIED | `execute_project_extraction()` checks robots before fetching pages (`app/services/project_extraction.py:283`). Robots service exists in `app/services/robots_service.py`. |
| Fetcher static plus browser, content-type allowlist, byte cap, Windows threaded browser fallback. | VERIFIED | Static fetch and redirect validation in `app/services/fetcher.py:89`; unsupported content-type path at `app/services/fetcher.py:134`; max bytes tests in `tests/services/test_fetcher.py`; Windows threaded path at `app/services/fetcher.py:173`. |
| DOM summary builder is functional with 10K cap, repeated containers, tables, data attributes. | VERIFIED | `app/services/dom_summary.py:11`, `app/services/dom_summary.py:60`, `app/services/dom_summary.py:71`, `app/services/dom_summary.py:96`, `app/services/dom_summary.py:122`. |
| Analyzer is cached, versioned, structured/content, provider abstraction, JSON retries. | VERIFIED | `ANALYZER_VERSION = "1"` at `app/services/analyzer.py:24`; cache lookup/store by hash/provider/model/version at `app/services/analyzer.py:95` and `app/services/analyzer.py:115`; schema selection and `max_retries=3` at `app/services/analyzer.py:82` and `app/services/analyzer.py:174`. |
| Project state machine is production-ready with 12 states. | PARTIALLY VERIFIED | The model-level state machine is real (`app/models/job.py:105`, `app/models/job.py:291`), but the count is wrong: `ProjectState` has 13 values (`app/models/job.py:18`). |
| Crawl scope system with four modes and confirmation gate. | VERIFIED | `CrawlScopeMode` has `CURRENT_PAGE`, `PAGINATION`, `DATASET`, `FULL_SITE` (`app/models/job.py:59`). Confirmation logic raises `ScopeConfirmationError` (`app/services/crawl_scope.py:152`, `app/services/crawl_scope.py:210`). API and executor both enforce it (`app/services/project_extraction.py:78`, `app/services/project_extraction.py:238`). |
| Frontier preview persisted with scope-aware classification and scope hash. | VERIFIED | Model exists (`app/models/job.py:458`). Endpoints exist (`app/api/v1/endpoints/projects.py:373`, `app/api/v1/endpoints/projects.py:407`). Tests cover create/get/staleness-related contract in `tests/api/v1/test_projects_phase25.py`. |
| Extraction quality/trust summary persisted. | VERIFIED | `ExtractionSpec.quality_summary` exists (`app/models/job.py:332`); extraction computes and stores it (`app/services/project_extraction.py:434`); project response exposes it (`app/api/v1/endpoints/projects.py:147`). |
| Deterministic CSS extraction with repeated containers, fallback, type coercion. | VERIFIED | Repeated-container extraction in `app/services/extractor.py:98`; fallback extraction in `app/services/extractor.py:168`; coercion in `app/services/extractor.py:54`. |
| Same-site BFS crawl is sequential in-process with page-level isolation. | VERIFIED | Crawl loop selects pending pages and processes sequentially (`app/services/project_extraction.py:269`, `app/services/project_extraction.py:273`). Per-page fetch/validation failures mark only that page failed (`app/services/project_extraction.py:387`). |
| Paginated results endpoint. | VERIFIED | `/records-page` endpoint returns `total`, `has_more`, `next_skip`, `columns` (`app/api/v1/endpoints/projects.py:484`). |
| Export CSV/JSON/XLSX. | VERIFIED | Export endpoint and stdlib XLSX writer exist (`app/api/v1/endpoints/projects.py:530`, `app/api/v1/endpoints/projects.py:581`). |
| Structured logging is production-ready. | PARTIALLY VERIFIED | The implementation is strong: context injection, URL sanitization, extra-field redaction, exception redaction, and middleware cleanup are implemented (`app/core/logging_config.py:115`, `app/core/logging_config.py:130`, `app/core/logging_config.py:80`, `app/core/logging_config.py:91`, `app/core/logging_config.py:248`, `app/core/logging_config.py:306`, `app/main.py:126`). Focused logging security tests passed. "Production-ready" depends on deployment log handling and retention policies outside this codebase. |
| Watchdog covers legacy tasks and Job QUEUED/ANALYZING but not project extraction states. | VERIFIED | `cleanup_stuck_tasks()` covers legacy task states (`app/services/watchdog.py:24`). `cleanup_stuck_jobs()` only queries `JobState.QUEUED` and `JobState.ANALYZING` (`app/services/watchdog.py:139`). No sweep covers `DISCOVERING`, `EXTRACTING`, or `EXPORTING`. |
| Health/readiness. | VERIFIED | Readiness service and endpoint exist (`app/services/readiness.py`, `app/api/v1/endpoints/health.py`). |
| Rate limiting is in-memory. | VERIFIED | SlowAPI limiter uses `storage_uri="memory://"` (`app/core/rate_limit.py:37`). |
| Job admission with provider preflight and advisory lock. | VERIFIED | Project admission uses provider checks in `app/services/job_admission.py`; legacy task admission uses per-user advisory lock (`app/services/admission.py:40`). |
| Frontend provider/project/scope/frontier/trust/results components exist. | VERIFIED | `frontend/src/pages/ProvidersPage.tsx`, `frontend/src/pages/ProjectDetailPage.tsx`, `frontend/src/components/project/ScopeSelector.tsx`, `frontend/src/components/project/FrontierPreviewPanel.tsx`, `frontend/src/components/project/TrustSummaryPanel.tsx`, `frontend/src/components/project/PaginatedResultsTable.tsx`. |
| Legacy job routes redirect to projects. | VERIFIED | `frontend/src/App.tsx:34`, `frontend/src/App.tsx:36`, `frontend/src/App.tsx:48`. |

## 3. Missing Capabilities

| Missing capability claim | Status | Evidence and notes |
| --- | --- | --- |
| Visual field selection is missing. | VERIFIED | No iframe/click-to-select UI or CSS path generator is present; roadmap places this in Phase 3 (`docs/product/strategic_redesign.md:554`, `docs/product/strategic_redesign.md:593`). |
| SSE live progress stream is missing. | VERIFIED | Roadmap lists `/projects/{id}/stream` (`docs/product/strategic_redesign.md:433`), but no such route exists in `app/api/v1/endpoints/projects.py`. |
| Concurrent crawler workers and durable crash resume are missing. | VERIFIED | Extraction loop is sequential (`app/services/project_extraction.py:269`). `CRAWL_CONCURRENCY` exists in settings (`app/core/config.py:110`) but is not used for concurrent claiming in this executor. |
| CrawlPage lease reaper is missing. | VERIFIED | `lease_expires_at` is written and cleared (`app/services/project_extraction.py:278`, `app/services/project_extraction.py:383`, `app/services/project_extraction.py:390`), but watchdog only calls task/job cleanup (`app/services/watchdog.py:215`). |
| Template routing / DOM fingerprinting is missing. | VERIFIED | `ExtractionSpec.url_patterns` exists (`app/models/job.py:326`), but no template fingerprint/routing engine is present. |
| Selector repair is missing. | VERIFIED | No service or endpoint for AI selector repair exists. Extraction reports selector warnings but does not repair selectors (`app/services/extractor.py:87`). |
| Content-mode chunking is missing. | VERIFIED | `ExtractedRecord` has no `content_blocks` column (`app/models/job.py:412`). Content extraction returns a single `content` value (`app/services/extractor.py:194`). |
| AI normalization is missing. | VERIFIED | Normalization is local type coercion only (`app/services/extractor.py:54`). |
| Per-page retry endpoint is missing. | VERIFIED | No `/pages/{page_id}/retry` route exists in `app/api/v1/endpoints/projects.py`. |
| Watchdog for project extraction states is missing. | VERIFIED | See watchdog evidence above. |
| Provider key rotation command is missing. | VERIFIED | Provider encryption exists, but no management command/script for rotation is present. |
| Docker/docker-compose is missing. | VERIFIED | No `docker-compose.yml` or Dockerfile appears in `rg --files`; roadmap lists Docker as future setup (`docs/product/strategic_redesign.md:635`). |
| User profile management is missing. | VERIFIED | Auth endpoints exist, but no `/users/me` route was found. |
| Authenticated-content browser sessions are missing. | VERIFIED | Browser fetch can render public pages, but no target-site login/session capture workflow exists. |

## 4. Critical Invariants

| Invariant claim | Status | Evidence and correction |
| --- | --- | --- |
| Owner-check before mutation/read. | VERIFIED for reviewed project/provider/job paths | Projects use `_owned_project()` and return 404 on user mismatch (`app/api/v1/endpoints/projects.py:195`). Providers use `_get_owned_provider_or_404()` (`app/api/v1/endpoints/providers.py:38`). Jobs similarly check `job.user_id` (`app/api/v1/endpoints/jobs.py:180`). |
| Provider keys encrypted at rest and not in normal responses; reveal requires password. | VERIFIED | Encrypted key field is stored (`app/models/provider_config.py:31`), encryption/decryption are Fernet (`app/services/provider_service.py:73`, `app/services/provider_service.py:78`), reveal verifies password (`app/api/v1/endpoints/providers.py:145`). Tests assert responses omit key blobs (`tests/api/v1/test_providers_extended.py:114`, `tests/api/v1/test_providers_extended.py:241`). |
| No credit system. | VERIFIED for current model and services | No credit columns in `User`; rate/admission are count-based. Note: old migration `004_system_state.py` exists historically, but current code does not use a credit system. |
| Scope confirmation gate enforced in API and executor. | VERIFIED | `start_project_extraction()` and `execute_project_extraction()` both call `assert_scope_confirmed()` (`app/services/project_extraction.py:78`, `app/services/project_extraction.py:238`). |
| Frontier and extraction share classifier. | VERIFIED | Extraction calls `discover_links_for_scope()` through `select_links_to_enqueue()` (`app/services/project_extraction.py:101`). Frontier service uses the same crawl-scope module. |
| `extract_anyway` bypasses preview check, not scope confirmation. | VERIFIED | API checks preview first, then calls `start_project_extraction()` which enforces scope (`app/api/v1/endpoints/projects.py:436`, `app/services/project_extraction.py:78`). Tests cover this (`tests/api/v1/test_projects_phase25.py:274`). |
| `records-page` is preferred and has pagination metadata. | VERIFIED | Endpoint exists and returns metadata (`app/api/v1/endpoints/projects.py:484`). README also documents it (`README.md:90`). |
| State machine enforced at model layer. | VERIFIED | `transition_to()` raises `ValueError` on invalid transition (`app/models/job.py:293`). |
| `raw_data` never modified after write. | PARTIALLY VERIFIED | Code paths reviewed write `raw_data` when creating `ExtractedRecord` (`app/services/project_extraction.py:360`) and list/export records without updating them. This is not enforced by an immutable database constraint. |
| Normalization is structural/additive. | VERIFIED for current code | `normalized_data` is created from extracted values through `_coerce_value()` (`app/services/extractor.py:54`). No AI normalization pipeline exists. |

## 5. Risks and Technical Debt

| Risk claim | Status | Evidence and assessment |
| --- | --- | --- |
| Legacy `/scrape` SSRF vulnerability. | VERIFIED, high severity | `/scrape/start` validates only with `HttpUrl` (`app/api/v1/endpoints/scrape.py:42`) and stores the URL (`app/api/v1/endpoints/scrape.py:93`). The executor calls `scrape_url()` (`app/services/task_executor.py:65`), and `scrape_url()` uses `httpx.AsyncClient(follow_redirects=True)` without `validate_url()` or per-hop validation (`app/services/scraper.py:42`, `app/services/scraper.py:44`). This is a real deployment blocker if `/scrape` remains reachable. |
| CrawlPage lease reaper missing. | VERIFIED, high severity | Lease timestamps are written but no reset sweep exists. A process crash after setting `FETCHING` can strand pages indefinitely. |
| Watchdog gap for `DISCOVERING/EXTRACTING/EXPORTING`. | VERIFIED, medium/high severity | `cleanup_stuck_jobs()` covers only `QUEUED` and `ANALYZING` (`app/services/watchdog.py:139`). |
| Rate limiter in-memory only. | VERIFIED | `storage_uri="memory://"` in `app/core/rate_limit.py:40`. |
| APScheduler in-process only. | VERIFIED | Global `AsyncIOScheduler` in `app/core/scheduler.py:18`; no external scheduler lock. |
| CORS default excludes Vite. | VERIFIED, with nuance | Default is `http://localhost:3000,http://localhost:8000` (`app/core/config.py:86`), while Vite dev runs on `127.0.0.1:5173` (`frontend/package.json:7`). The briefing mentions `http://localhost:5173`; the actual dev origin is `http://127.0.0.1:5173`. |
| Hand-rolled XLSX generation risk. | VERIFIED low severity | `_xlsx_bytes()` builds XLSX using `zipfile` and XML strings (`app/api/v1/endpoints/projects.py:581`). It escapes cell text (`app/api/v1/endpoints/projects.py:625`), but this is still a limited implementation. |
| Job/Project compatibility aliases are confusing. | VERIFIED | `Job = Project`, `JobState = ProjectState`, enum name remains `job_state` (`app/models/job.py:219`, `app/models/job.py:512`). |
| No provider key rotation tool. | VERIFIED | No rotation command exists, while encryption is central (`app/services/provider_service.py:73`). |
| Frontend test coverage thin. | PARTIALLY VERIFIED | There are frontend tests and no dedicated `ProjectDetailPage.test.tsx` was found. I did not count all frontend tests in this review. |

## 6. Documentation Inaccuracies

| Documentation claim from briefing | Status | Evidence and nuance |
| --- | --- | --- |
| `strategic_redesign.md` describes `crawl_pages.task_id`, but code uses `project_id`. | VERIFIED | Roadmap target text says `task_id` (`docs/product/strategic_redesign.md:351`), current model uses `project_id` (`app/models/job.py:382`). |
| Roadmap CrawlPage states differ from code. | VERIFIED | Roadmap target states include `QUEUED`, `EXTRACTING`, etc. (`docs/product/strategic_redesign.md:352`); current enum has `PENDING`, `FETCHING`, `FETCHED`, `EXTRACTED`, `BLOCKED`, `FAILED` (`app/models/job.py:50`). |
| Roadmap mentions missing `content_hash`, `is_seed`, `content_blocks`, `normalization_enabled`, `access_basis`. | VERIFIED | Current models do not include those fields (`app/models/job.py:312`, `app/models/job.py:378`, `app/models/job.py:412`). |
| Endpoint table missing frontier-preview and records-page. | OUTDATED | Current `strategic_redesign.md` does include `/projects/{id}/frontier-preview` and `/projects/{id}/records-page` (`docs/product/strategic_redesign.md:410` area includes current endpoints; README and STATUS also include them). If the briefing was based on an older copy, this point is now outdated. |
| Phase 0.5 says to add lease expiry job but code does not. | VERIFIED | Roadmap says add lease expiry job (`docs/product/strategic_redesign.md:194`); scheduler only registers watchdog cleanup (`app/core/scheduler.py:41`). |
| Strategic redesign is a forward roadmap, not current-state truth. | VERIFIED | The doc explicitly says it is forward-looking (`docs/product/strategic_redesign.md:5`). Treating all target table definitions as current implementation would be incorrect. |

## 7. Recommended Priorities

I agree with the briefing's top three risk-reduction priorities:

1. Fix or remove the legacy `/scrape` SSRF exposure.
2. Add crawl-page lease recovery.
3. Extend watchdog coverage for stuck project extraction states.

I partially disagree with the relative ordering of doc cleanup versus reliability work. Correcting endpoint tables and CORS defaults is useful, but it should not compete with SSRF and stuck-extraction recovery.

I disagree with treating `openpyxl` replacement as a near-term recommendation. The hand-rolled XLSX implementation is a valid low-risk technical debt item, but adding a dependency should remain lower priority than extraction correctness and recovery.

I agree that Phase 3 visual field selection should wait until the reliability gaps above are closed.

## Missing Risks Not Called Out Clearly Enough

- Extraction can complete with zero records after page-level failures. `execute_project_extraction()` marks individual pages `FAILED` for fetch/validation errors (`app/services/project_extraction.py:387`) and then can still transition the project through `EXPORTING` to `COMPLETED` (`app/services/project_extraction.py:409`, `app/services/project_extraction.py:472`). This may be acceptable as "partial success", but the UX/API needs to make all-failed extraction unmistakable.
- `CRAWL_CONCURRENCY` exists in settings but the executor is sequential. This can mislead operators reading config (`app/core/config.py:110`, `app/services/project_extraction.py:269`).
- Browser SSRF protection is stronger than a naive browser fetch, but DNS rebinding risk is still acknowledged in comments because validation and browser TCP connection are separate steps (`app/services/url_validator.py:135`, `app/services/fetcher.py:302`). The route-level mitigation helps, but this remains a sensitive area.
- Historical Phase 2.5 validation was run on `project-workflow-migration` (`docs/reviews/03_phase25_validation.md`), while the current branch is `feature/logging-observability`. Treat the historical report as evidence, not a guarantee.
- The working tree is dirty. This review assessed the current dirty tree; deleted logging docs/tests and untracked replacements exist according to `git status`.

## Missing Strengths Not Called Out Clearly Enough

- The logging security remediation is stronger than the briefing implies. Arbitrary string extras, nested dict/list strings, message args, URL fields, and exception text are routed through redaction/sanitization (`app/core/logging_config.py:142`, `app/core/logging_config.py:177`, `app/core/logging_config.py:205`, `app/core/logging_config.py:221`, `app/core/logging_config.py:248`, `app/core/logging_config.py:306`). The targeted logging security tests passed in this review.
- Middleware cleanup is directly covered by real-app tests, not only copied middleware tests (`tests/core/test_logging_security.py:1197`).
- Phase 2.5 API contract tests are substantial for the backend surface: scope updates, confirmation errors, frontier preview, records pagination, and quality exposure are all covered in `tests/api/v1/test_projects_phase25.py`.
- Fetcher tests cover content-type rejection, truncation metadata, browser unavailable behavior, private-IP browser route blocking, blank Playwright exception formatting, and threaded browser path (`tests/services/test_fetcher.py`).

## Recommended Next Priorities

1. Close the legacy `/scrape` SSRF exposure before any public deployment.
2. Add recovery for expired `CrawlPage` leases so crashed extraction pages do not remain `FETCHING`.
3. Add watchdog coverage or equivalent recovery for projects stuck in `DISCOVERING`, `EXTRACTING`, and `EXPORTING`.
4. Clarify extraction outcomes when all pages fail or zero records are produced.
5. Update docs only where they are intended to describe current behavior; keep roadmap target-state tables clearly labeled.
6. After those reliability items, proceed to Phase 3 visual interaction.
