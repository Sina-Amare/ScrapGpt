# ScrapGPT Validation and Advanced UX Review

Date: June 9, 2026

Scope: evidence-backed validation planning, Advanced Settings UX review, and roadmap guidance for technical hardening plus product simplification.

This report is standalone. It does not depend on earlier review documents.

## Executive Summary

ScrapGPT has a strong technical foundation: the current test suite passes locally, the frontend builds, and the primary project workflow is covered by API/service tests. That means the main concern is not whether the current implementation is broken at a basic engineering level. The concern is product correctness: the UI still exposes internal system choices before the product has clearly captured the user's goal.

The current long-term product flow should be:

`URL -> Understand Data -> Choose Fields -> Preview -> Extract -> Results`

The current UI partially follows that flow, but Advanced Settings leak implementation concepts into the first step. "Data type", "Page rendering", "AI provider", `workflow_mode`, page limit, export format, and raw JSON are all useful controls for some users or failure modes. They are not all appropriate as early setup decisions for non-technical users.

The most important product direction is to move from "configure system behavior" to "express user intent". Technical controls should remain available, but they should be placed where they match the user's task: output choices near Results, troubleshooting controls near Preview/fetch problems, provider selection in account/project preferences, and crawl budget near Extract.

## Evidence Classification

### Verified By Execution

These facts were validated in the local environment during this review:

| Evidence | Command | Result |
|---|---|---|
| Full backend test suite passes | `venv\Scripts\python.exe -m pytest -q` | `161 passed, 16 warnings` |
| Frontend tests pass | `npm.cmd test` from `frontend/` | `31 passed` |
| Frontend typecheck passes | `npm.cmd run typecheck` from `frontend/` | Passed with exit code 0 |
| Frontend lint passes | `npm.cmd run lint` from `frontend/` | Passed with exit code 0 |
| Frontend production build passes | `npm.cmd run build` from `frontend/` | Built successfully after sandbox escalation |
| Plain `npm` is not reliable in this PowerShell environment | `npm test`, `npm run typecheck` | Failed because `npm.ps1` execution is disabled; `npm.cmd` works |

Build note: the first sandboxed production build failed with an access-denied error while Vite/esbuild tried to load `vite.config.ts`. The same command passed outside the sandbox after approval. Treat this as an environment/sandbox execution issue, not a frontend build failure.

### Verified By Code Inspection

These facts were validated by reading the current code:

| Finding | Evidence |
|---|---|
| Project Advanced Options support `extraction_mode`, `workflow_mode`, `render_mode`, and `provider_config_id` | `app/schemas/project.py`, `app/api/v1/endpoints/projects.py` |
| New Project UI exposes Data type, Page rendering, and AI provider; it forces `workflow_mode: "GUIDED"` | `frontend/src/pages/NewProjectPage.tsx` |
| Extraction spec stores fields, content config, URL patterns, page limit, and export format | `app/models/job.py`, `app/schemas/project.py` |
| Project detail screen exposes Page limit and Export format in the Extraction section | `frontend/src/pages/ProjectDetailPage.tsx` |
| Project detail screen exposes raw system state, render mode, workflow mode, fetch metadata, analysis, and spec in an Advanced JSON panel | `frontend/src/pages/ProjectDetailPage.tsx` |
| Extraction currently describes itself as crawling same-site pages up to page limit | `frontend/src/pages/ProjectDetailPage.tsx`, `app/services/project_extraction.py` |
| Same-origin link discovery is the current default crawl behavior unless URL patterns filter it | `app/services/url_normalizer.py`, `app/services/project_extraction.py` |
| Preview validates saved selectors on the seed page, not the future crawl frontier | `app/services/project_preview.py` |
| Export format can also be selected from Results export buttons, so storing it in the spec is not the only user-facing path | `frontend/src/pages/ProjectDetailPage.tsx`, `app/api/v1/endpoints/projects.py` |

### Assumptions Requiring Future Validation

These recommendations are plausible but not proven by local tests alone:

| Assumption | Why it needs future validation |
|---|---|
| Non-technical users will understand scope choices such as "this page", "this list across pages", and "whole site" better than crawl terminology | Requires user observation or usability testing |
| AI can reliably classify pagination, detail links, category links, and navigation links on real websites | Requires real pages and provider-backed analysis |
| Moving provider selection out of the primary New Extraction form will improve completion for non-technical users | Requires UX testing |
| A frontier preview will meaningfully reduce wrong-dataset exports | Requires real extraction sessions and user feedback |
| Hybrid DOM evidence will improve field discovery without excessive cost | Requires fixture benchmarks and provider-backed comparison |

## Recommendation Labels

Every major recommendation in this report uses one or more labels:

- `Verified by execution`: backed by commands run locally.
- `Verified by code inspection`: backed by current code behavior.
- `Assumption requiring future validation`: directionally recommended but not proven yet.

## Agent-Executable Validation Plan

The goal of validation is not only "tests pass". The goal is to know which claims the agent can prove now, which should become automated checks, which require humans, and which require real AI provider credentials.

| Validation | Can agent execute now | Commands | Dependencies | Evidence to collect | Pass criteria | Fail criteria | Category |
|---|---:|---|---|---|---|---|---|
| Targeted backend workflow and safety tests | Yes | `venv\Scripts\python.exe -m pytest tests\services\test_url_validator.py tests\services\test_robots_service.py tests\services\test_fetcher.py tests\services\test_analyzer.py tests\services\test_project_workflow.py tests\api\v1\test_projects.py -q` | Local Python venv, test settings | Test count, failures, warnings | All selected tests pass | Any selected test fails or environment cannot import app | Immediate agent validation |
| Full backend suite | Yes | `venv\Scripts\python.exe -m pytest -q` | Local Python venv, test DB/test config used by suite | Full pass/fail count | Suite passes | Any failing test | Immediate agent validation |
| Frontend tests | Yes | From `frontend/`: `npm.cmd test` | `frontend/node_modules` installed | TAP output and pass count | All frontend tests pass | Any failing test or missing dependency | Immediate agent validation |
| Frontend typecheck | Yes | From `frontend/`: `npm.cmd run typecheck` | TypeScript dependencies installed | Exit code and compiler output | Exit code 0 | TypeScript error | Immediate agent validation |
| Frontend lint | Yes | From `frontend/`: `npm.cmd run lint` | ESLint dependencies installed | Exit code and lint output | Exit code 0 | Any lint error | Immediate agent validation |
| Frontend production build | Yes, but sandbox may block Vite/esbuild reads | From `frontend/`: `npm.cmd run build` | TypeScript/Vite dependencies installed; may require unsandboxed execution in this environment | Build output, bundle sizes, exit code | Build completes | Build error after environment access is resolved | Immediate agent validation |
| Current same-origin crawl behavior | Yes | Add/run a focused unit test around `discover_same_site_links()` using same-origin unrelated category links | No provider credentials; local test fixture only | Discovered URL list | Current behavior includes same-origin links unless filtered | Behavior differs from code inspection or test fixture is invalid | Should automate |
| Future scope-rule behavior | Not until scope model exists | Future pytest fixture around scope-aware discovery | Future scope model and fixtures | Included/excluded URL sets per scope mode | Page-only/pagination-only/category/full-site behave differently and predictably | Scope modes collapse into same-origin crawl or allow unrelated links silently | Should automate |
| DOM summary loss fixture | Yes | Future pytest fixture around `build_dom_summary()` with title, meta, JSON-LD offers, hydration JSON, nested fields | No provider credentials | Summary text and omitted evidence | Test documents what is lost today | Test cannot distinguish lost/preserved context | Should automate |
| Rich DOM evidence fixture | Not until richer evidence model exists | Future pytest fixture around evidence bundle builder | Future evidence builder | Preserved title/meta/JSON-LD/link clusters/fragments | Evidence bundle includes required signals under cap | Important signals missing without warning | Should automate |
| Local API smoke flow with mocked provider | Partly; current tests cover API surfaces, not a full live HTTP server run | Future command can start backend and use HTTP client against `/api/v1/projects` with provider calls stubbed or test provider | Local DB, auth setup, mocked provider path | HTTP status codes, project states, persisted rows | Analyze -> detail -> spec -> preview/extract path works with deterministic stubs | HTTP flow fails or requires real provider unexpectedly | Should automate |
| Database-backed project workflow | Yes through tests; broader live DB flow depends on local DB state | `venv\Scripts\python.exe -m pytest tests\api\v1\test_projects.py tests\services\test_project_workflow.py -q` | Local test DB/session fixtures | Project/spec/preview/record assertions | Project workflow tests pass | State/spec/extraction expectations fail | Immediate agent validation; expand automation |
| Real provider structured analysis | No | Run project analysis against known static pages using configured provider key | Real provider credentials, network, allowed website targets | Prompt/evidence input class, model, JSON output, confidence, fields, warnings | Provider returns valid structured output and useful fields | Invalid JSON, low-quality fields, missing important data | Requires real provider credentials |
| Real provider scope/link-role analysis | No | Future provider-backed benchmark over pages with known pagination/category/detail links | Real provider credentials, network, curated page set | AI classifications and confidence vs expected labels | Classifies link roles accurately enough for UX recommendation | Misclassifies unrelated links as dataset scope | Requires real provider credentials |
| Human scope comprehension | No | Moderated or lightweight usability test with 5-10 target users | Human participants, prototype or screenshots | Which scope users choose, confusion notes, task success | Users pick intended scope without technical explanation | Users misunderstand scope choices or default to unsafe broad crawl | Requires human review |
| Human Advanced Settings comprehension | No | Show current and proposed setup UI to non-technical users | Human participants, current UI/prototype | Explanation quality, confidence, hesitation points | Users understand goal-level choices | Users interpret implementation controls incorrectly | Requires human review |

### Validation Findings From This Pass

- `Verified by execution`: core backend and frontend checks pass locally.
- `Verified by execution`: use `npm.cmd`, not plain `npm`, in PowerShell automation on this machine.
- `Verified by code inspection`: current tests validate important infrastructure, but they do not yet validate crawl-scope intent or user comprehension.
- `Assumption requiring future validation`: real provider quality and human UX comprehension remain open.

## Advanced Settings UX Review

The product should optimize for this flow:

`URL -> Understand Data -> Choose Fields -> Preview -> Extract -> Results`

Advanced controls should appear only when they support the current step. Controls that are really troubleshooting, provider preference, or output formatting should move to those contexts.

### Summary Table

| Current setting | Purpose | User comprehension level | Risk of confusion | Implementation detail? | Recommended future design |
|---|---|---|---|---:|---|
| New Extraction: Data type (`STRUCTURED` / `CONTENT`) | Selects analysis/extraction mode | Medium if phrased as current labels; higher with examples | Medium | Partly | Keep concept, remove from Advanced, present as user goal |
| New Extraction: Page rendering (`AUTO` / `STATIC` / `BROWSER`) | Controls fetch/render strategy | Low for non-technical users | High | Yes | Infer automatically; move to troubleshooting |
| New Extraction: AI provider | Chooses provider config | Medium for technical users, low for non-technical users | Medium | Partly | Move to account/project preference; keep compact override |
| Schema/API: `workflow_mode` (`GUIDED` / `FAST`) | Determines post-analysis flow | Low | High | Yes | Hide; express as Review first / Extract now based on confidence |
| Extraction: Page limit | Caps crawl size/resource use | Medium | High if treated as scope | Partly | Keep as safety budget near Extract, not scope |
| Extraction: Export format | Chooses output file type | High | Low, but wrong timing | No | Move to Results/export area |
| Project Detail: Advanced raw JSON | Debugs internal state | Low for non-technical users; high for developers | High | Yes | Keep developer-only/debug, not workflow step |
| Legacy Jobs advanced controls | Compatibility with older workflow | Low for current product users | High | Yes | De-emphasize legacy; do not use as model for product UX |

### Data Type

Current setting: `Data type` with options `Structured data` and `Content / knowledge base`.

Problem solved: It chooses between structured tabular extraction and content/RAG extraction. In code, this maps to `extraction_mode`, which changes analyzer schema and extraction behavior.

Is it understandable to a non-technical user: Partly. "Structured data" and "Content / knowledge base" are better than enum names, but they still ask the user to understand an internal product mode before ScrapGPT has inspected the URL.

Is it exposing an implementation detail: Partly. The distinction is real product intent, but the current placement under Advanced makes it feel like system configuration.

Should it remain visible: Yes, but not as an advanced setting.

Should it be inferred automatically: Yes as a recommendation, not as an irreversible hidden decision. ScrapGPT can infer likely mode from page type and show a user-language confirmation.

Should it move elsewhere: Yes. Move into the first-class "Understand Data" step or present it as a goal picker before/after URL analysis.

Should it be removed entirely: No. Structured datasets and content/knowledge extraction are genuinely different user goals.

Should it use user-language: Yes.

Recommended future design:

- Present as "What do you want from this URL?"
- Options:
  - "Rows in a table" for product lists, directories, jobs, events, prices.
  - "Clean pages for a knowledge base" for articles, docs, blogs, support pages.
- After analysis, show "ScrapGPT thinks this is a data table/list" with the ability to switch.

Evidence label: `Verified by code inspection` for current behavior; `Assumption requiring future validation` for improved comprehension.

### Page Rendering

Current setting: `Page rendering` with options `Automatic`, `Static HTML only`, and `Browser rendering`.

Problem solved: It controls whether fetching uses static HTTP, browser rendering, or auto fallback for JavaScript-heavy pages.

Is it understandable to a non-technical user: Low. "Static HTML" and "Browser rendering" are implementation concepts.

Is it exposing an implementation detail: Yes.

Should it remain visible: Not in the initial New Extraction form for the default user.

Should it be inferred automatically: Yes. `AUTO` already exists and should remain the default.

Should it move elsewhere: Yes. Move to a troubleshooting area after analysis/preview if the page looks empty, wrong, or JavaScript-rendered.

Should it be removed entirely: No. Technical users and debugging flows need it.

Should it use user-language: Yes.

Recommended future design:

- Default silently to automatic.
- If fetch metadata indicates sparse content, browser fallback, or browser failure, show a contextual prompt:
  - "This page may need browser loading."
  - "Try loading the page like a browser."
  - "Use faster basic loading for simple pages."
- Keep exact render mode enum only in developer/debug settings.

Evidence label: `Verified by code inspection` for current exposure and fetch-mode mapping; `Assumption requiring future validation` for UX improvement.

### AI Provider

Current setting: `AI provider`, with "Default provider" and configured provider choices.

Problem solved: It lets users choose which BYOK provider/model will analyze the page.

Is it understandable to a non-technical user: Low to medium. Users may understand "AI provider" if they configured one, but choosing models during extraction distracts from the data goal.

Is it exposing an implementation detail: Partly. Provider choice is a real BYOK product concern, but it is not the user's immediate extraction intent.

Should it remain visible: Yes for technical users, but not as a prominent first-run decision.

Should it be inferred automatically: Yes. Use the default provider resolution path unless the user deliberately changes it.

Should it move elsewhere: Yes. Primary home should be provider settings/account defaults, with a compact per-project override.

Should it be removed entirely: No.

Should it use user-language: Yes.

Recommended future design:

- New Extraction should say "Using default AI provider: X" only if helpful.
- Offer a small "Change" action for advanced users.
- If no provider exists, block with clear setup guidance before the URL workflow.
- Avoid presenting provider/model selection as equivalent to data extraction choices.

Evidence label: `Verified by code inspection` for current UI/API behavior; `Assumption requiring future validation` for placement.

### Workflow Mode

Current setting: `workflow_mode` exists in schema/API and legacy job surfaces. Project UI currently sends `workflow_mode: "GUIDED"` when Advanced is open and defaults to `GUIDED` otherwise.

Problem solved: It controls whether a project lands in a review-first flow or can proceed faster when confidence is high.

Is it understandable to a non-technical user: Low. "Guided" and "Fast" are product states, not user goals unless explained carefully.

Is it exposing an implementation detail: Yes.

Should it remain visible: No for non-technical project creation.

Should it be inferred automatically: Yes. The system should decide whether "Extract now" is safe based on confidence, warnings, preview state, and scope clarity.

Should it move elsewhere: If kept, it belongs in developer/automation preferences, not the default UI.

Should it be removed entirely: Not from API yet, because compatibility may need it. It should be removed from the primary UX vocabulary.

Should it use user-language: Yes.

Recommended future design:

- Replace `FAST` / `GUIDED` language with:
  - "Review first" when uncertainty exists.
  - "Extract now" only when analysis confidence, field quality, and scope confidence are high.
- Never let "fast" bypass scope confirmation for broad crawls.

Evidence label: `Verified by code inspection` for current schema and project UI behavior; `Assumption requiring future validation` for user-language impact.

### Page Limit

Current setting: `Page limit` appears in the Project Detail Extraction section.

Problem solved: It caps crawl size and resource use. Backend also caps it with `MAX_PAGES_PER_JOB`.

Is it understandable to a non-technical user: Medium. Users understand a numeric limit, but may mistake it for scope.

Is it exposing an implementation detail: Partly. It is both a user safety control and crawler resource control.

Should it remain visible: Yes, but with different framing.

Should it be inferred automatically: A default should be inferred, but users should be able to adjust it.

Should it move elsewhere: It belongs in Extract, not URL setup. It should sit next to scope confirmation and estimated pages.

Should it be removed entirely: No.

Should it use user-language: Yes.

Recommended future design:

- Rename/reframe as "Safety limit" or "Maximum pages to visit".
- Pair it with scope:
  - "Scope: this list across pages"
  - "Estimated: about 12 pages"
  - "Safety limit: 25 pages"
- Warn that page limit does not define dataset scope.

Evidence label: `Verified by code inspection` for current cap behavior; `Assumption requiring future validation` for naming.

### Export Format

Current setting: `Export format` appears in the Extraction section and is also available from Results export buttons.

Problem solved: It chooses output format: CSV, JSON, XLSX.

Is it understandable to a non-technical user: High.

Is it exposing an implementation detail: No.

Should it remain visible: Yes, but not during extraction setup.

Should it be inferred automatically: A default CSV is fine, but the user should choose at download time.

Should it move elsewhere: Yes. Move to Results/export.

Should it be removed entirely: No.

Should it use user-language: Current labels are acceptable.

Recommended future design:

- Remove export format from the saved extraction setup path unless there is a strong reason to pre-generate one format.
- Keep export buttons in Results.
- If persisted export jobs exist later, configure export after extraction, not before understanding data.

Evidence label: `Verified by code inspection` for current duplicated placement; recommendation is product judgment.

### Raw Advanced JSON Panel

Current setting: Project Detail has a "Show advanced" panel displaying internal JSON: system state, render mode, workflow mode, fetch metadata, analysis, and spec.

Problem solved: It helps developers inspect backend state and debug analysis/spec issues.

Is it understandable to a non-technical user: Low.

Is it exposing an implementation detail: Yes.

Should it remain visible: Yes only as a developer/debug affordance.

Should it be inferred automatically: Not applicable.

Should it move elsewhere: It can remain at the bottom of the detail page, but should be clearly framed as "Developer details" or "Debug details".

Should it be removed entirely: No. It is useful in an early-stage self-hosted tool.

Should it use user-language: The collapsed button should; the JSON itself can remain raw.

Recommended future design:

- Rename "Show advanced" to "Developer details".
- Keep it collapsed by default.
- Do not use this panel as the only way to understand warnings, scope, or selector quality.

Evidence label: `Verified by code inspection`.

### Legacy Jobs Advanced Controls

Current setting: Legacy `/jobs` surfaces still include mode/render/provider concepts and display raw state badges.

Problem solved: Compatibility with earlier workflow.

Is it understandable to a non-technical user: Low to medium.

Is it exposing an implementation detail: Yes.

Should it remain visible: Only while compatibility is required.

Should it be inferred automatically: For primary `/projects`, yes. Legacy can remain unchanged until removed.

Should it move elsewhere: De-emphasize routes and avoid treating legacy UX as product precedent.

Should it be removed entirely: Eventually, once migration/compatibility constraints are gone.

Should it use user-language: If it remains user-facing, yes.

Recommended future design:

- Keep `/projects` as the product source of truth.
- Treat `/jobs` as compatibility until removed.
- Do not copy legacy advanced controls into the long-term UX.

Evidence label: `Verified by code inspection`; removal timing is an `Assumption requiring future validation`.

## Alignment With Long-Term Product Flow

### URL

Current state:

- User enters a URL.
- Advanced settings can be opened immediately.
- The form asks for extraction mode, render mode, and provider before ScrapGPT has shown what it understands about the page.

Recommendation:

- Keep URL entry simple.
- Ask for user goal only if necessary: "Rows in a table" vs "Knowledge/content pages."
- Do not ask for render mode during first-run setup.

Evidence: `Verified by code inspection` for current UI; UX simplification is an `Assumption requiring future validation`.

### Understand Data

Current state:

- AI analysis runs and produces fields/confidence/warnings.
- It does not yet produce a first-class crawl-scope plan.

Recommendation:

- This step should become the place where ScrapGPT explains:
  - What kind of page it found.
  - What dataset boundary it thinks the user wants.
  - What links look like pagination, detail pages, categories, or unrelated navigation.
  - What uncertainty remains.

Evidence: current analysis shape is `Verified by code inspection`; scope comprehension needs future validation.

### Choose Fields

Current state:

- Users can select fields, rename labels, choose field types, mark required fields, and inspect confidence/sample values.

Recommendation:

- This aligns with the long-term vision.
- Keep selector internals hidden by default.
- Add future multi-page quality evidence rather than more raw configuration.

Evidence: `Verified by code inspection`.

### Preview

Current state:

- Preview executes saved selectors against the seed page.
- It does not preview the crawl frontier or selector quality across multiple page templates.

Recommendation:

- Preview should validate both:
  - Field extraction quality.
  - Scope/frontier quality.
- A future preview should show sample included/excluded URLs and sample records from more than one page when scope leaves the seed URL.

Evidence: seed-page preview behavior is `Verified by code inspection`; broader preview value is an `Assumption requiring future validation`.

### Extract

Current state:

- Extraction is started after preview.
- UI says extraction crawls same-site pages up to page limit.

Recommendation:

- Extract should show the accepted scope, estimated page count, and safety budget.
- The user should not have to infer scope from page limit.

Evidence: current extraction copy and backend crawl behavior are `Verified by code inspection`.

### Results

Current state:

- Results table appears after completion.
- Export buttons are available for CSV, JSON, and XLSX.

Recommendation:

- Results is the correct place for export format choice.
- Keep extraction setup focused on data correctness, not output file preference.

Evidence: `Verified by code inspection`.

## Roadmap

### Do Now

| Recommendation | Evidence label |
|---|---|
| Treat the current local suite as a baseline quality gate: backend full suite, frontend tests, typecheck, lint, and build | `Verified by execution` |
| Standardize local frontend commands on `npm.cmd` in Windows/PowerShell docs or agent instructions | `Verified by execution` |
| Reframe Advanced Settings as goal/troubleshooting/preference controls, not first-step product choices | `Verified by code inspection` |
| Move Data type out of "Advanced" conceptually and present it as user goal language | `Verified by code inspection` plus `Assumption requiring future validation` |
| Keep Page rendering automatic by default and reserve manual render mode for troubleshooting | `Verified by code inspection` |
| Keep AI provider override available but secondary to default provider resolution | `Verified by code inspection` |
| Reframe Page limit as a safety budget, not crawl scope | `Verified by code inspection` |
| Move Export format conceptually to Results/export | `Verified by code inspection` |
| Keep raw JSON details as developer-only debug output | `Verified by code inspection` |

### After Validation

| Recommendation | Evidence label |
|---|---|
| Add automated crawl-scope fixture tests using pages with pagination, detail links, and unrelated same-origin category links | `Assumption requiring future validation` |
| Add DOM summary/evidence fixture tests that prove which metadata, JSON-LD, and hydration fields are preserved or lost | `Assumption requiring future validation` |
| Add a local API smoke flow with mocked provider behavior to validate project creation through preview/extract without real credentials | `Assumption requiring future validation` |
| Test user-language labels for extraction mode and scope with non-technical users | `Assumption requiring future validation` |
| Run provider-backed benchmarks over representative sites before trusting AI scope inference | `Assumption requiring future validation` |

### Future Phases

| Recommendation | Evidence label |
|---|---|
| Add first-class crawl scope to extraction intent, separate from page limit and URL globs | `Verified by code inspection` for current absence; future design requires validation |
| Add frontier preview before broad extraction | `Verified by code inspection` for current gap; UX impact requires validation |
| Add template-aware selector quality checks across sampled pages | `Verified by code inspection` for current seed-page-only preview; future behavior requires validation |
| Add hybrid analysis evidence bundles instead of relying only on the current compressed DOM summary | `Verified by code inspection` for current summary limits; provider quality requires validation |
| Keep durable crawler recovery and multi-worker hardening on the roadmap, but do not let crawler scale outrun scope correctness | `Verified by code inspection` for current lease fields and sequential execution; scale strategy requires validation |

## Final Assessment

The current codebase is healthy enough to support deeper product iteration. The local suite passes, frontend quality gates pass, and the architecture already separates analysis, field selection, preview, extraction, and results.

The main risk is not basic implementation quality. The main risk is asking users to make system-level decisions before ScrapGPT has helped them express intent. Advanced settings should become secondary, contextual, and user-language driven.

The best direction is:

1. Keep the technical controls for power users.
2. Move them out of the primary path unless they map directly to a user goal.
3. Add validation around crawl scope and DOM evidence before expanding crawler power.
4. Use provider-backed and human validation where local tests cannot prove product understanding.

