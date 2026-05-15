# ScrapGPT — Master Plan

Last updated: 2026-05-15

## Vision

An interactive, AI-powered web scraping platform where users paste a URL, AI analyzes the page structure, users select what to extract, and the system handles multi-page crawling with smart recovery — all through a beautiful GUI.

---

## Honest Assessment: Where We Are vs. Where We Want to Be

### What exists today

A backend-only API that:

- Accepts a URL, scrapes it (text extraction via BeautifulSoup), runs it through an LLM stub, and returns a JSON blob.
- Has auth, credits, a state machine, and a watchdog.
- Has no frontend, no page analysis, no element selection, no multi-page crawling, no checkpointing, and no real AI integration.

### What we're building

An interactive, AI-powered scraping _platform_ where:

1. Users see a GUI, paste a URL, and the system validates it.
2. AI analyzes the page structure and presents selectable elements.
3. Users pick what to extract and choose export formats.
4. The system handles multi-page crawling (including non-sequential URLs).
5. Smart recovery/checkpointing handles interruptions.

---

## Constraints

- **AI Provider:** Google Gemini API (free tier via AI Studio). No paid APIs.
- **Model:** Gemini 1.5 Flash (15 RPM, 1,500 req/day, 1M tokens/min on free tier).
- **Infrastructure:** Single-host deployment (for now).

---

## Phase 0: Stabilize the Foundation (1-2 days)

Before building anything new, fix the broken things:

1. **Fix SlowAPI parameter collision** on `POST /scrape/start` — rename body param to `payload`, put `request: Request` first.
2. **Fix route shadowing** on `/scrape/tasks/current` — move static route above dynamic one.
3. **Fix watchdog NULL-skip bug** — use `COALESCE(updated_at, created_at)` in the filter.
4. **Squash migration enum drift** — reset to a clean baseline migration (no production data exists).

**Why first:** Don't build new features on broken plumbing.

---

## Phase 1: Gemini AI Integration — The Brain (3-4 days)

Replace the LLM stub with Google's Gemini API.

### New modules

- `app/services/ai/gemini_client.py` — Async wrapper around the Gemini REST API (via httpx). Handles rate limiting (15 RPM), retries, and token tracking.
- `app/services/ai/page_analyzer.py` — Takes raw HTML, sends cleaned version to Gemini, gets back a JSON schema of detected data patterns (tables, lists, repeated elements, links).
- `app/services/ai/link_discoverer.py` — Given a page's HTML and user intent, uses Gemini to identify navigation patterns and extract target URLs.
- `app/services/ai/data_extractor.py` — Given HTML + user-selected fields, extracts structured data using Gemini's structured output mode.

### Key design decisions

- **Gemini 1.5 Flash** — free, fast, 1M token context window handles full HTML pages.
- **Pre-process HTML before sending to Gemini.** Strip scripts/styles/SVGs with BeautifulSoup first. Saves tokens, improves accuracy.
- **Use structured output.** Gemini supports `response_mime_type: "application/json"` with a schema. Use for all extraction calls.
- **Built-in rate limiter.** Token-bucket or semaphore in the client that queues requests near the 15 RPM limit.
- **Cache analysis results.** If the same site structure is scraped again, reuse the schema.

### Config additions

```python
GEMINI_API_KEY: str
GEMINI_MODEL: str = "gemini-1.5-flash"
GEMINI_RPM_LIMIT: int = 15
GEMINI_DAILY_REQUEST_LIMIT: int = 1500
```

---

## Phase 2: Frontend — The Interface (5-7 days)

### Tech stack

React + Vite + TypeScript + Tailwind CSS + shadcn/ui

Why: Vite is fast, Tailwind + shadcn/ui gives polished accessible UI without custom CSS, React has the ecosystem for interactive components.

### Pages/Views

1. **Dashboard** — Active task, recent scrapes, credit balance.
2. **New Scrape** — URL input → validation → page preview → element selection → config → start.
3. **Task Monitor** — Real-time progress (SSE), logs, partial results.
4. **Results** — View extracted data, export (CSV, JSON, Excel).

### Critical UX flow (New Scrape page)

```
Step 1: Enter URL
  → Backend validates (HEAD request, checks robots.txt)
  → Shows page preview (screenshot or iframe sandbox)

Step 2: AI Analysis
  → Backend sends page to Gemini for structure analysis
  → Frontend shows detected data patterns as selectable cards:
    "I found: a table with 50 rows (Name, Price, Rating),
     a list of 20 links to detail pages,
     pagination with 12 pages"

Step 3: Configure Extraction
  → User selects which patterns to extract
  → User picks export format (CSV, JSON, Excel)
  → For multi-page: user confirms page count or sets a limit

Step 4: Start & Monitor
  → Task queued, progress shown in real-time
```

### Frontend project structure

```
frontend/
├── src/
│   ├── components/     # Reusable UI components
│   ├── pages/          # Route-level pages
│   ├── hooks/          # Custom React hooks (useTask, useAuth, etc.)
│   ├── services/       # API client (axios/fetch wrapper)
│   ├── stores/         # State management (zustand or context)
│   └── types/          # TypeScript interfaces
├── package.json
└── vite.config.ts
```

---

## Phase 3: Multi-Page Crawling Engine (4-5 days)

### Architecture

```
ScrapeJob (parent)
├── CrawlPhase: discover all target URLs
│   ├── AI analyzes page for navigation patterns
│   ├── Follows pagination / sitemaps / link patterns
│   └── Builds URL queue (with deduplication)
├── ExtractionPhase: scrape each URL
│   ├── Processes URLs from queue (respects rate limits)
│   ├── Extracts data using the schema from analysis
│   └── Checkpoints after each page
└── ExportPhase: compile and format results
```

### New models

```python
class ScrapeJob(Base):
    """Parent job — one per user request."""
    id, user_id, status, config (JSONB),
    total_pages_discovered, pages_completed, pages_failed,
    checkpoint_data (JSONB), created_at, updated_at

class ScrapePage(Base):
    """One page within a job."""
    id, job_id, url, status (PENDING/SCRAPING/DONE/FAILED),
    raw_html, extracted_data (JSONB),
    attempt_count, last_error, created_at
```

### Crawl strategies (AI-detected)

1. **Pagination** — Next/prev links, page numbers, "load more" patterns.
2. **Sitemap** — Parse sitemap.xml if available.
3. **Link following** — AI identifies which links lead to detail pages.
4. **API discovery** — Gemini analyzes if there's a hidden API endpoint.

### AI's role in crawling

Send Gemini the first page's HTML and ask: "Identify the navigation pattern for reaching all similar pages. Are there pagination links? A sitemap? A pattern in the URLs?" Gemini returns a structured strategy that the crawler follows programmatically.

---

## Phase 4: Checkpointing & Recovery (2-3 days)

### Design

- After each page is successfully scraped and extracted, update `ScrapePage.status = DONE` and persist `extracted_data`.
- `ScrapeJob.checkpoint_data` stores: last processed URL, queue position, partial results summary.
- On failure/interruption: job moves to `PAUSED` state.
- On resume: load checkpoint, skip completed pages, continue.

### Implementation

```python
class CheckpointManager:
    async def save_checkpoint(self, job_id, page_id, queue_position): ...
    async def load_checkpoint(self, job_id) -> CheckpointData: ...
    async def resume_from_checkpoint(self, job_id): ...
```

### Failure handling

- **Individual page failure:** Retry 3x with exponential backoff, then mark FAILED and continue.
- **Server crash:** Watchdog detects stuck job, marks it PAUSED. User can resume from dashboard.
- **Partial results always available:** Even if 50/100 pages are done, user can export what's collected.

---

## Phase 5: Real-Time Progress & Export (2-3 days)

### Server-Sent Events for live updates

```python
@router.get("/scrape/jobs/{job_id}/stream")
async def stream_progress(job_id: int, user: User = Depends(get_current_user)):
    async def event_generator():
        while True:
            job = await get_job(job_id)
            yield f"data: {job.progress_json()}\n\n"
            if job.is_terminal:
                break
            await asyncio.sleep(1)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Export formats

- CSV (pandas or csv module)
- JSON (native)
- Excel (.xlsx via openpyxl)
- Partial export mid-job

---

## Phase 6: Polish & Hardening (ongoing)

- URL validation (HEAD request + robots.txt check before scraping)
- Respect `robots.txt` and rate-limit requests to target sites
- User-configurable delay between requests
- Error reporting in UI (which pages failed and why)
- Job history and re-run capability
- Playwright fallback for JS-rendered pages
- Test suite (unit + integration)

---

## Revised Tech Stack

| Concern    | Choice                                                  |
| ---------- | ------------------------------------------------------- |
| Backend    | FastAPI (keep)                                          |
| Database   | PostgreSQL (keep)                                       |
| AI/LLM     | Google Gemini 1.5 Flash (free via AI Studio)            |
| Scraping   | httpx + BeautifulSoup (keep) + Playwright (JS fallback) |
| Frontend   | React + Vite + TypeScript + Tailwind + shadcn/ui        |
| Real-time  | Server-Sent Events                                      |
| Export     | pandas + openpyxl                                       |
| Task queue | BackgroundTasks for now; Arq/Celery later if needed     |

---

## Architecture Changes from Current Codebase

1. **Data model evolution.** `ScrapeTask` (single URL) → `ScrapeJob` (parent) + `ScrapePage` (children). Keep the old model for backward compatibility during transition, then deprecate.

2. **State machine expansion.** Current: `PERMISSION_GRANTED → SCRAPING → SCRAPED → LLM_PROCESSING → COMPLETED`. New: `VALIDATING → ANALYZING → AWAITING_CONFIG → CRAWLING → EXTRACTING → EXPORTING → COMPLETED` (with `PAUSED` and `FAILED` from any non-terminal state).

3. **Credits model rethink.** Currently 1 credit = 1 task. With multi-page jobs: 1 credit = 1 page (or remove credits entirely for personal use — they add complexity without value for a single user).

4. **Keep the auth system** — it's well-built and useful if shared with others.

---

## Free Tier Math

- A 100-page scrape job needs ~102 Gemini calls (1 analysis + 1 link discovery + 100 extraction).
- At 15 RPM: ~7 minutes per job. Acceptable with good progress reporting.
- ~14 full 100-page jobs per day on the free tier. Plenty for personal use.
- Build rate limiter into Gemini client from day one.

---

## Execution Timeline

| Week | Focus                                | Deliverable                                                    |
| ---- | ------------------------------------ | -------------------------------------------------------------- |
| 1    | Phase 0 + Phase 1                    | Bug fixes + working Gemini integration that can analyze a page |
| 2    | Phase 2 (frontend scaffold)          | Basic React app with auth, URL input, and API connection       |
| 3    | Phase 2 (continued) + Phase 1 wiring | AI analysis results shown in UI, element selection working     |
| 4    | Phase 3                              | Multi-page crawling engine with AI-driven link discovery       |
| 5    | Phase 4 + Phase 5                    | Checkpointing, recovery, real-time progress, export            |
| 6    | Phase 6                              | Polish, edge cases, testing                                    |

---

## Future Ideas (out of scope for now)

- Webhook / SSE for task completion notifications
- Retry policy for transient scrape failures
- Persistent job queue (Celery / Arq) for horizontal scaling
- Per-task cost telemetry
- Admin endpoints for ops
- Scheduled/recurring scrapes
- Browser extension for "scrape this page" quick-start
