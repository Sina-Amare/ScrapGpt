# 09 — Phase 2 Real Extraction Engine

## Problem / Purpose

Phase 1 made the full product loop visible, but extraction still materialized
the AI's `sample_values`. That proved the workflow, not the data pipeline.

Phase 2 replaces that placeholder with real deterministic extraction:

```text
Analyze → Field Selection → Preview selectors → Crawl same-site pages → Extract records → Export
```

The core product decision remains unchanged: AI understands the page once, then
code extracts records from every fetched page.

---

## What Changed

### Backend

| File | Purpose |
| ---- | ------- |
| `app/services/extractor.py` | Executes saved CSS selectors against HTML and returns raw + normalized payloads. |
| `app/services/url_normalizer.py` | Normalizes URLs, strips tracking params, filters same-origin links, and applies optional glob patterns. |
| `app/services/project_preview.py` | Preview now fetches the seed page and runs selectors for real sample rows. |
| `app/services/project_extraction.py` | Background same-site crawl/extract executor that persists pages, records, and export metadata. |
| `app/services/dom_summary.py` | Richer summaries: repeated container HTML samples, table samples, `data-*` attributes, 15 repeated classes, 10,000-character cap. |
| `app/api/v1/endpoints/projects.py` | Extraction starts as a background task; progress includes page-state counts; export supports CSV, JSON, XLSX. |

### Frontend

`ProjectDetailPage` now shows:

- Page limit before extraction.
- Export format preference.
- Page-state counts: pending, fetching, extracted, blocked, failed.
- CSV, JSON, and XLSX download buttons.

Preview rows are no longer AI examples. They come from executing the saved
selectors against the seed page.

---

## Invariants

1. **AI is not called per page.** The crawler/extractor never calls LiteLLM.
   Provider usage remains bounded to analysis and future explicit repair flows.

2. **Raw data is preserved.** Every record stores `raw_data`. `normalized_data`
   is additive and may coerce obvious values such as numbers or booleans, but it
   does not replace raw data.

3. **Crawling is same-origin by default.** Discovered links must match the seed
   page origin and pass the existing URL validator before fetch.

4. **Robots and SSRF checks are reused.** Preview and extraction use
   `validate_url`, `check_robots`, and `fetch_url`, the same safety path as
   analysis.

5. **Extraction is bounded.** The effective page limit is
   `min(spec.page_limit, settings.MAX_PAGES_PER_JOB)`.

6. **Page failures are isolated.** A blocked or failed page records its own
   state in `crawl_pages`; other pages continue.

---

## Design Decisions

### Preview must execute selectors

Phase 1 preview was useful for UI flow but could mislead users because it showed
AI sample values. Phase 2 preview fetches the seed page and runs the saved
selectors. This gives the user a real check before committing to a larger crawl.

### Use BeautifulSoup CSS selectors first

No new dependency was added for CSS execution. BeautifulSoup's `select()` is
already available through `soupsieve` and is sufficient for the current selector
surface. If future selector needs exceed it, `lxml.cssselect` or Playwright
locator-based extraction can be evaluated.

### Sequential background crawl, not a worker pool yet

The executor runs in a FastAPI background task and processes pages sequentially
with `MIN_CRAWL_DELAY_MS`. This keeps Phase 2 reliable and easy to test while
preserving the page-state table needed for future concurrent workers.

The existing lease fields are still foundation-only. True crash recovery and
multi-worker claiming should be added when extraction moves to a durable queue.

### Same-origin BFS instead of template routing

The crawler discovers same-site links from fetched HTML and deduplicates
normalized URLs. URL pattern filtering is supported in the spec, but automatic
template routing and DOM fingerprinting are intentionally deferred. Selector
quality and data trust should be improved before adding template intelligence.

### Minimal XLSX without a dependency

XLSX export is generated with `zipfile` and minimal OpenXML parts. This avoids
adding `openpyxl` for a simple tabular export. If formatting, multiple sheets,
or large streaming workbooks become requirements, introduce a pinned dependency
then.

---

## Known Limits

- Extraction is sequential, not concurrent.
- Background tasks are process-local; a server crash can leave a project in an
  active state until future recovery logic handles leases.
- Selector repair is not implemented.
- Template routing and DOM structural fingerprinting are not implemented.
- Visual field selection is not implemented.
- Authenticated-content sessions are not implemented.
- Challenge handling detects/block-fails indirectly through fetch/results; no
  bypass is attempted.

---

## Verification

Commands run successfully after this phase:

```bash
venv\Scripts\python.exe -m pytest -q
cd frontend
npm test -- --run
npm run typecheck
npm run lint
npm run build
```

Results:

- Backend: 161 passed.
- Frontend tests: 31 passed.
- Frontend typecheck/lint/build: passed.
