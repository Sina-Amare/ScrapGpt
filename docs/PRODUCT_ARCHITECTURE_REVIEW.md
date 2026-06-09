# ScrapGPT — Product, UX, and Architecture Review

**Review date:** 2026-06-09
**Reviewer scope:** code in `app/`, `alembic/`, `frontend/src/`, plus external research on Firecrawl, Apify, ScrapeGraphAI, Crawl4AI, and adjacent literature.
**Methodology:** every claim about ScrapGPT cites a file path; every claim about competitors cites a documented source. No implementation tasks are proposed in this document — only product, UX, and architecture analysis with recommended directions.

This review is a companion to `docs/CODEBASE_AUDIT_REPORT.md`. That document catalogues the current state; this one challenges the assumptions baked into the current state and proposes a long-term direction.

---

## Executive Summary

ScrapGPT today is a single-user, BYOK, deterministic web extraction tool. The core architectural thesis — _AI understands the site once, code extracts every page_ — is sound. The execution has reached a first working end-to-end loop (analyze → spec → preview → extract → export) and the basics are good. But the product is making five implicit bets about user intent and about competitive positioning that I believe are wrong, and that will compound as the product scales. Specifically:

1. **Crawl scope is implicit.** Today the crawler treats every same-origin link as fair game. The user has no first-class way to say "this page only", "this dataset", "this category", or "this whole site". `url_patterns` is a free-text glob list that the user has to write after the fact. The example you raised (calories.info) shows that this is not an edge case — it is the normal case.
2. **The AI sees a lossy structural summary, not the page.** The DOM summary is 10,000 characters with hard caps on headings, links, classes, tables, and data-attrs. For the kind of sites the product wants to win on (e-commerce, B2B directories, listings with rich metadata) this is exactly the information the AI needs and does not get.
3. **"AI tells you what to extract" is a feature, not the product.** Competitors like Firecrawl have already absorbed the schema-generation step into their core. The schema is now a _format_ choice the user makes, not a _discovery_ product.
4. **"Non-technical UX" is underspecified.** The strategy doc lists visual field selection, click-to-extract, and confidence explanations as Phase 3. None of these are implemented. The current path is a toggle between "Default to AI's guess" and "Edit raw JSONB". That is technical UX with extra steps.
5. **The roadmap is in the wrong order.** Phases 4 (normalization) and 5 (auth sessions, OSS packaging) are listed before any attempt to make the analysis itself more reliable. Quality of the dataset should be the next differentiator, not packaging.

The recommendations in §5 are organized by when they should happen, not by which team owns them, and they are deliberately not implementation tickets. The most important single decision ScrapGPT needs to make in the next 90 days is **what the crawl-scope object model is**. Everything downstream — UX, schema, exports, pricing, OSS packaging — flows from that choice.

---

## 1. The Crawl Scope Problem

### 1.1 The bug, restated precisely

The crawler at `app/services/project_extraction.py:131-272` calls `discover_same_site_links` (`app/services/url_normalizer.py:73-101`) for every fetched page. That function's only filters are:

- `same_origin(url, root_url)` — must match scheme + netloc of the seed (`url_normalizer.py:43-46`).
- `_matches_patterns(url, patterns)` — optional `include` / `exclude` globs from `extraction_spec.url_patterns` (`url_normalizer.py:49-70`).

There is no concept of: dataset, category, page type, section of a site, "only this URL", or "stop at this depth". Every same-origin link is a valid candidate, capped only by `page_limit` (`spec.page_limit`, capped by `MAX_PAGES_PER_JOB`, default 500).

The example you gave — `https://www.calories.info/food/potato-products` linking to Pizza, Meat, Beer, Fruit — is the **default behavior**, not a bug to be patched. The crawler will find all of them, follow the unique same-origin links, and discover the whole site. If the user wanted only the 200 potato-product pages they would have to either (a) manually write exclude globs after the fact, (b) inspect the running crawl and stop it, or (c) accept a 10x larger dataset and filter downstream.

This is simultaneously:

- A **bug** in the sense that the user is not warned that "this single page" is going to become a site crawl.
- A **UX problem** because the user has no in-product surface to declare their intent.
- An **architecture problem** because the concept of "scope" is not represented in the data model, the spec, the state machine, the README, or the strategy doc.

The crawl-scope object is missing. Until it exists, every other UI affordance, schema decision, and extraction run is guessing.

### 1.2 Is this a UX problem, a bug, or an architecture problem?

It is all three, in this order of severity:

1. **Architecture first.** The data model has no `crawl_scope` object. `extraction_spec.url_patterns` is the closest thing, but it is treated as a post-hoc free-text glob list with no semantics. The four things the user actually wants to express — "this page only", "this dataset via pagination", "this category", "the whole site" — are not enum values anywhere in the schema (`app/schemas/project.py:1-150`).

2. **UX second.** Even with the same code, a clear pre-crawl UI that asks "what is the scope of this run?" and offers four named modes would convert the calories.info situation from "user gets a 10x dataset" to "user picks 'this dataset' and the crawler looks for pagination + category links". The `Advanced` drawer in `NewProjectPage` already exists, but the API surface (`ProjectAdvancedOptions` in `app/schemas/project.py:13-39`) only exposes extraction_mode, workflow_mode, render_mode, and provider_config_id. There is no scope field.

3. **Bug surface.** Once scope is in the model, the "bug" becomes the default for users who do not set scope explicitly. That default itself needs a definition: today the implicit default is "BFS same-origin until limit", which is rarely what the user wants.

### 1.3 What does the data model need?

A first-class `CrawlScope` object on `extraction_specs` (or a sibling table) with at least:

| Field                | Type          | Meaning                                                                                     |
| -------------------- | ------------- | ------------------------------------------------------------------------------------------- |
| `mode`               | enum          | `SINGLE_PAGE` \| `PAGINATED_DATASET` \| `CATEGORY` \| `SUBDOMAIN` \| `WEBSITE`              |
| `include_paths`      | list[str]     | glob or regex on URL path; additive to mode's default                                       |
| `exclude_paths`      | list[str]     | glob or regex on URL path; takes precedence over include                                    |
| `include_subdomains` | bool          | default false; equivalent to Firecrawl's `allowSubdomains`                                  |
| `max_depth`          | int           | max link depth from the seed (Firecrawl's `maxDiscoveryDepth`)                              |
| `max_pages`          | int           | already exists as `page_limit`; rename or alias                                             |
| `respect_sitemap`    | bool          | Firecrawl's `sitemap` mode: `skip` \| `include` \| `only`                                   |
| `discover_via`       | list[str]     | `html_links` \| `sitemap_xml` \| `llms_txt` \| `pagination_hint` (see §1.6)                 |
| `page_type_filter`   | optional enum | `listing` \| `detail` \| `search` \| any; gate discovered links by their inferred page type |

The semantics of each `mode` are:

- **SINGLE_PAGE**: no link discovery, only the seed is fetched. This is the default for content-mode projects.
- **PAGINATED_DATASET**: BFS but only along pagination patterns the AI identifies (`?page=`, `/page/2`, "next" link, `?offset=`). Same-origin allowed; sibling categories discouraged. Equivalent to: follow the explicit pagination selector from the analysis and stop when the selector stops appearing.
- **CATEGORY**: BFS constrained by include/exclude paths, typically all pages under `/food/potato-products/`. Sibling categories (`/food/pizza/`, `/food/meat/`) are excluded unless an `include_path` adds them.
- **SUBDOMAIN**: as CATEGORY but includes subdomains.
- **WEBSITE**: same-origin BFS, every page, with `crawlEntireDomain=true` semantics (sibling/parent pages allowed).

The user's intent on the calories.info example would map to **PAGINATED_DATASET** with the AI's `pagination_selector` as the navigation primitive and an implicit `exclude` of `/food/<other-category>/`. Today, the system has none of this.

### 1.4 Should crawl scope be part of extraction_specs?

Yes, but it should be its own object (`CrawlScope`) with a 1:1 relationship to `ExtractionSpec`, not a field on it. The reasons:

- Crawl scope decisions and field-selection decisions are conceptually orthogonal. A user might want to experiment with selectors on a single page (SINGLE_PAGE), then flip to CATEGORY. They should not have to re-PATCH their field spec to do so.
- Different `CrawlScope` values have different default behaviors for `url_patterns`, `max_pages`, `respect_sitemap`, etc. Bundling them in the same object makes versioning hard.
- The state machine should be able to track scope changes as a distinct audit trail from field changes. If a user changes scope mid-run, that is a bigger decision than changing a selector.

Concretely: a `crawl_scopes` table with a 1:1 FK to `extraction_specs`, holding the fields above, plus a `crawl_scope_history` table (or a JSONB change log on `extraction_specs`) so the watchdog and the UI can show "scope changed from PAGINATED_DATASET to CATEGORY at 14:22".

### 1.5 Should scope be inferred by AI, declared by the user, or both?

**Both, in a specific order, with the user holding the veto.** Reasons:

- The user is the only one who knows their intent. "I want this dataset" is not derivable from the page — the same page is "the entire site" to one user and "this one page" to another. The example you gave is dispositive: the same page produces 3 records and 300 records depending on user intent, and the page itself cannot tell the difference.
- AI inference is useful as a **suggestion** and as a **constraint solver**. The user can pick "Same dataset / related pages" from four named choices and the AI can:
  1. Pre-fill the include/exclude paths based on the seed URL's directory.
  2. Pre-fill the pagination hint from `pagination_selector` if the analysis found one.
  3. Warn if the inferred scope suggests the dataset will be much larger than the user's `page_limit` implies (e.g. "We estimate 3,400 pages in the meat category; you set 500").
- The user must always have a final say. "Use AI's defaults" is a checkbox, not the default.

The UX flow this implies: the New Extraction screen offers a 4-tile scope picker (SINGLE_PAGE / PAGINATED_DATASET / CATEGORY / WEBSITE), each with one sentence of plain-language explanation, and an "Advanced" toggle that exposes the include/exclude path fields. After the analysis completes, the user sees the AI's suggested scope and can accept or override.

### 1.6 What do the best scraping products do?

I read the public docs for Firecrawl, Apify, and ScrapeGraphAI. The pattern is consistent: **scope is a first-class object with named primitives, not an AI inference.**

- **Firecrawl** ([`/api-reference/endpoint/crawl-post`](https://docs.firecrawl.dev/api-reference/endpoint/crawl-post)) exposes `includePaths` (regex on path), `excludePaths` (regex on path), `maxDiscoveryDepth`, `limit`, `crawlEntireDomain` (boolean, default false), `allowExternalLinks` (boolean, default false), `sitemap` (`skip` / `include` / `only`), `ignoreQueryParameters`, `regexOnFullURL`, `allowSubdomains`. Notice that this is a long list of explicit knobs; Firecrawl does not try to infer intent. The `includePaths` and `excludePaths` are regex patterns on the path; users write them.
- **Apify Website Content Crawler** ([`apify.com/apify/website-content-crawler`](https://apify.com/apify/website-content-crawler)) exposes `startUrls`, `includeUrlGlobs`, `excludeUrlGlobs`, `maxCrawlDepth`, `maxCrawlPages`, `useSitemaps`, `useLlmsTxt`, `respectRobotsTxtFile`, `keepUrlFragments`, `ignoreCanonicalUrl`, plus the heavyweight `pageFunction` for users who need to fully script per-page behavior. Notice the use of `llms.txt` — a recent emerging standard. (See §1.7.)
- **ScrapeGraphAI SmartCrawler** ([`docs.scrapegraphai.com/services/smartcrawler`](https://docs.scrapegraphai.com/services/smartcrawler)) exposes `depth`, `breadth`, `max_pages`, and a `rules` object with `same_domain` (boolean, default true), `include_paths`, `exclude_paths`, `exclude` (regex on full URL), and `sitemap` (boolean).

The shared shape across the three:

1. **Same-domain flag** (boolean).
2. **Include/exclude path patterns** (regex or glob).
3. **Depth and page-count limits**.
4. **Sitemap opt-in**.
5. **External link opt-in** (mostly off by default).

None of the three try to infer "what the user really meant". They give the user primitives, and they let the user write a regex if they need fine control. ScrapGPT should follow the same pattern. The AI can suggest values; the user confirms.

Two additional primitives from the research are worth borrowing:

- **`llms.txt` discovery** (Apify). An emerging convention where sites publish `/llms.txt` listing the URLs they want LLMs to read. For CATEGORY and WEBSITE scopes, this would be a high-signal source of "intended scope". Support it.
- **Sitemap mode** (Firecrawl). Three states: `skip` (don't use sitemap), `include` (mix sitemap with HTML discovery), `only` (sitemap only, no HTML discovery). This maps well onto ScrapGPT's scope modes: SINGLE_PAGE → no sitemap, PAGINATED_DATASET → `include` is wrong (no global sitemap helps), CATEGORY → `include` is fine, WEBSITE → `include` is the right default.

### 1.7 The role of `llms.txt` and sitemap.xml

These two are not "AI inferring scope" — they are publishers declaring scope on their own site. `llms.txt` is particularly interesting because it is a publisher-asserted list of "this is the site as I want it read by an LLM". For any site that publishes one, the crawler should respect it as a high-signal source.

- WEBSITE scope: prefer `llms.txt` if present, else `sitemap.xml`, else BFS.
- CATEGORY scope: filter the publisher-declared URLs by the category path; fall back to BFS.
- PAGINATED_DATASET scope: ignore `llms.txt` (it's a site list, not a paginated dataset), follow the discovered pagination selector.
- SINGLE_PAGE scope: no discovery at all.

Apify's `useLlmsTxt` boolean is the right level of abstraction here. ScrapGPT should support it the same way, scoped by the current `CrawlScope` mode.

### 1.8 The best long-term design for ScrapGPT

In priority order:

1. **First-class `CrawlScope` object** with the four-mode enum above. Migrations are additive (new table, FK on `extraction_specs.id`).
2. **Pre-crawl UI** that asks for scope before the analysis runs. The user can defer to "AI suggestion" but cannot skip the step.
3. **AI pre-fills the scope** based on the seed URL and the page structure. The pre-fill is editable.
4. **`llms.txt` and `sitemap.xml` integration** as first-class discovery sources, gated by scope.
5. **A "scope history" change log** on `extraction_specs` so the user can see when and how scope changed across re-runs.
6. **A guard rail at the boundary of CATEGORY → WEBSITE**: the UI should ask "do you really mean the whole site?" with a one-sentence impact estimate ("about 3,400 pages based on sitemap + BFS estimate").
7. **An explicit "I want this page only" affordance** at the top of the New Extraction flow. Today the only way to limit scope is to set `page_limit=1`, which the user has no way of knowing to do.

The most important single sentence in this report: **scope is the missing primitive; the rest of the product is downstream of getting it right.**

---

## 2. The AI Analysis Context Problem

### 2.1 What the AI actually sees today

`build_dom_summary` (`app/services/dom_summary.py:122-208`) produces a 10,000-character string that the analyzer prompt embeds verbatim. The string is composed of:

- The page title.
- The meta description.
- Up to 8 H1–H3 headings.
- Up to 3 JSON-LD `application/ld+json` objects (only the keys `@type`, `name`, `description`).
- Up to 15 class names that appear 3+ times.
- For up to 5 of those classes, one 900-character HTML sample of the first matching element.
- Up to 3 tables with up to 3 rows each, joined by `|`.
- Up to 20 distinct `data-*` attributes (first occurrence of each, truncated to 120 chars).
- Up to 12 anchor links (text + href, href truncated to 80 chars).
- Up to 4 pagination candidates (anchor or button whose text contains `next|prev|page|more|load|→|»`).
- A 600-character body-text snippet from `<body>`.

The whole string is hard-capped at 10,000 characters (`_MAX_SUMMARY_CHARS` in `app/services/dom_summary.py:11`).

The analyzer prompt embeds this summary as the **entire** description of the page. From `_STRUCTURED_PROMPT` in `app/services/analyzer.py:26-53`:

> "You are a web scraping analyst. Analyze the following page structure and identify extractable data fields. {dom_summary}. Return a JSON object with this exact schema (no extra keys) ..."

There is no fallback to send the raw HTML, no opt-in to send the raw HTML, and no provider-side mechanism to expand the summary on demand.

### 2.2 What information is currently lost

Concretely, against the kinds of sites ScrapGPT is most likely to win on (e-commerce product pages, B2B directories, real-estate listings, job boards, recipe sites, dataset catalogues), the following information is regularly **absent** from the LLM's view:

- **Stock / availability badges** that are visually rendered but only expressed as `data-*` attributes on the 4th+ child element. The summary keeps only the first 20 distinct `data-*` keys and only the first occurrence of each.
- **Price components** (sale price, original price, currency, discount percentage) that are nested in three or four sibling elements inside a single price container. The summary takes one 900-char HTML sample of the _first_ element matching a repeated class, so the second sibling — the original price — is invisible.
- **Seller / vendor metadata** rendered as small text adjacent to a product title. The summary's 12-link cap, 8-heading cap, and 200-char `_text(el)` truncation per element are all small enough to drop this.
- **Author / date / category breadcrumbs** in long-tail sites. Only 3 JSON-LD objects, only 8 headings, and 200-char snippets leave the AI to guess.
- **Variant selectors** (size, color, model) that are inside deeply nested containers, especially on apparel and electronics sites.
- **Badges** ("Free shipping", "On sale", "Verified seller") rendered as small icons with text in `aria-label` or `title`. The summary's `_text(el)` strips them.
- **Structured-data attributes** beyond `@type`, `name`, `description` — no `offers`, `price`, `availability`, `brand`, `sku`, `mpn`, `aggregateRating`.
- **Hidden DOM** — off-canvas tabs, modals, expandable sections. These exist as DOM but are often `display:none` and the summary does not look at them at all.
- **Repeated container 2nd-Nth siblings**: the summary takes one 900-char sample per class, but the AI needs to see the _range_ of values in the container. A 200-row product listing's variation is the data the user wants; the summary shows one.
- **Element-relative XPath/selector resolution context**: when the LLM is asked to return CSS selectors _relative to the repeated container_, it has to infer the container boundaries from the 900-char sample alone. This is the single biggest source of bad selectors in the current pipeline.

The pattern is consistent: **everything that lives outside the first occurrence of a repeated container is invisible**. For a listing page, the second and third items in the list are exactly as informative as the first. The summary treats the first item as the whole list.

### 2.3 What kinds of websites are most affected

Empirically (based on what AI extraction products in 2024-2025 typically struggle with — see for example Zyte's "AI won't fix your data quality" and ScrapeWise's "Self-Healing Scraper Infrastructure"):

- **E-commerce** with rich metadata: hardest hit. Variants, badges, original-vs-sale prices, multi-seller listings, sponsored content, shipping badges. Today's summary routinely misses half of these.
- **B2B directories** (Crunchbase-style, supplier catalogues, real-estate listings): less affected by the link/heading caps, more affected by the JSON-LD limit and the table sample cap.
- **News and article aggregators**: minor issue. The metadata that matters (title, author, date, body) usually fits the summary.
- **Forums and Q&A sites**: mid-affected. Threads and metadata are not in the heading/link budget.
- **Documentation sites, wikis**: barely affected. The summary's existing structure works.
- **Dashboards, SPAs that need auth**: not affected by the summary because the summary fails to render at all (the page returns a shell). This is a different problem.

The "most affected" category — e-commerce — is also the highest-value category for the product. The misalignment is sharp.

### 2.4 Is the current summary too aggressive?

Yes, by a wide margin. The 10,000-character cap is conservative. A mid-sized product listing page is 100-500 KB of HTML, but the _meaningful structural content_ (headings, repeated containers, tables, JSON-LD, microdata) is typically 30-80 KB. The summary is capturing perhaps 1-2% of the meaningful content.

Three specific caps are the worst offenders:

1. **One 900-char sample per repeated class** (`_repeated_container_samples`). The AI needs to see _all_ items, not one. A single sample biases the schema toward the first row's idiosyncrasies.
2. **12 links** (`_MAX_LINKS`). Many product listings have 100+ links per page.
3. **8 headings** (`_MAX_HEADINGS`). Article pages and category pages can have 30+ headings.

### 2.5 Is the current summary sufficient?

No, for the sites that matter most. The summary is sufficient for the "wiki" / "documentation" / "single-article" use case, but the product's stated positioning is "BYOK AI-assisted web data extraction" — the data-extraction use case — where the summary loses critical information.

It is also worth noting that the summary is sufficient for **schema _generation_** but insufficient for **selector _precision_**. The two-step pattern (AI proposes selectors → user tests them on the seed page) depends on the AI generating selectors that are _general_ across all instances of a repeated container. With one sample per container, the AI cannot see variance — a selector that works on the first row may miss a variation in the third.

### 2.6 Alternative A: DOM Summary (current)

What it is: a structural digest of the page, capped at 10,000 characters.

- **Extraction quality:** moderate. Loses the second-and-later items in repeated containers. Loses microdata. Loses hidden DOM. Loses deep nested attributes.
- **Cost:** lowest. ~3-4K tokens for the prompt, cheap across all providers.
- **Latency:** lowest. The summary builder is O(n) in HTML size; the LLM call processes ~3K tokens.
- **Reliability:** high. The summary never sees anything surprising; it is by design a structured abstraction.
- **Scalability:** high. Cheap to call on every crawl of every page (although ScrapGPT only calls it once, on the seed).

**Verdict:** fine for cheap analysis, insufficient for selector precision, insufficient for rich datasets.

### 2.7 Alternative B: Full HTML

What it is: send the entire HTML to the LLM, with light preprocessing (noise strip).

- **Extraction quality:** high. The LLM sees everything the user sees, plus attributes, microdata, hidden DOM (when not `display:none`). Variance in repeated containers is preserved.
- **Cost:** highest. A 500 KB product listing page becomes ~125K tokens — over 100x the current cost. Even a 50 KB article is ~12K tokens. Real LLM calls would be 1-3 cents per page, multiplied by every page in the crawl. On a 500-page crawl that is $5-15 per project.
- **Latency:** highest. Larger prompts mean longer TTFT (time-to-first-token) and longer total response time.
- **Reliability:** mixed. The LLM is more capable but the context window becomes a real constraint; very large pages may overflow the model's context. Also, providers are more likely to time out or return partial responses.
- **Scalability:** worst. Cost scales linearly with HTML size. A site with 200 KB pages would bankrupt the user at scale.

**Verdict:** best quality, worst economics. Not viable for a BYOK product that calls the LLM once per project — the economics flip from "1 LLM call" to "1 LLM call per page" because users would need to re-analyze on a different page if the seed page turned out to be unrepresentative.

### 2.8 Alternative C: Rich Structural Summary (recommended direction)

What it is: a structured digest of the page that preserves **variance** and **microdata**, not just one example. A draft shape:

- All `application/ld+json` blocks parsed and re-serialized in compact form (no 3-object cap, no `@type|name|description` filter — keep `offers`, `price`, `availability`, `brand`, etc.).
- All `<table>` elements with up to 20 rows, all columns, header and body rows clearly separated.
- For each repeated container (3+ matches with a class): up to **5** full HTML samples of _different_ items, not one. The sample selector should prefer items at different positions (first, last, 25%, 50%, 75%) to capture variance.
- All `data-*` attributes across the entire page, deduplicated, with first 3 occurrences shown.
- All `<a>` links: text + href + aria-label, no hard cap on count, dedup by href.
- All headings (H1-H6), no cap.
- All `<script type="application/ld+json">` and `<meta property="og:*">` and `<meta name="twitter:*">` and JSON-LD in `<script>`.
- All microdata (`itemscope`/`itemprop`/`itemtype`), serialized compactly.
- A compact "structural fingerprint" of the repeated container: e.g. "30 elements with class `.product-card`; first 3 HTML samples (varying); pattern observed: title=h3, price=p.price, link=a.href".
- A 2000-character body-text snippet.
- 30,000-50,000 character cap (3-5x the current cap).

- **Extraction quality:** substantially higher. The LLM sees variance, microdata, and full containers.
- **Cost:** moderate. ~10-15K tokens, 3-4x the current cost. On a 500-page crawl where the LLM is called once on the seed, this is still 1-2 cents per project. Manageable.
- **Latency:** moderate. ~3-5 seconds per call, similar to today.
- **Reliability:** high. More signal, but the structure is still bounded.
- **Scalability:** high. The cap is large enough to be useful but bounded to keep costs predictable.

**Verdict:** the right balance for a BYOK product. Trades a small multiple of cost for substantially better extraction quality. The structural fingerprint is a separate AI-friendly artifact that lets the model see "this is a listing of 30 items, here's how they vary".

### 2.9 Alternative D: Hybrid — Summary + targeted full-HTML chunks

What it is: send the rich structural summary by default, but allow the LLM (or a follow-up call) to request specific sections of the full HTML. A two-call pattern:

- **Call 1**: Rich structural summary. LLM returns the schema.
- **Call 2** (only when the user's preview is unsatisfactory, or for high-stakes fields): LLM is given a specific chunk selector (`data-*="product-variants"`, or the 5th occurrence of `.product-card`, etc.) and the full HTML for that chunk.

- **Extraction quality:** highest. The LLM can ask for what it needs.
- **Cost:** lower than full-HTML-everywhere, higher than rich-summary-only. The second call is small.
- **Latency:** higher than rich-summary only. Two calls in series.
- **Reliability:** high but operationally complex. The two-call protocol needs careful design.
- **Scalability:** moderate. The two-call pattern is harder to cache, harder to monitor, harder to make transparent to users.

**Verdict:** the right long-term answer for _high-value_ extractions, but premature for an early-stage product. The richness of the rich summary in Alternative C may be sufficient for 80% of cases; the two-call pattern becomes a power-user feature for the other 20%.

### 2.10 Recommendation

**Move to Alternative C now, with a clear upgrade path to Alternative D for high-value extractions.** Concretely:

1. Expand the DOM summary caps (1,000 → 5,000 per repeated container sample count, 5 → 20 for tables, 12 → 100 for links, 8 → all headings).
2. Stop filtering JSON-LD to `@type|name|description` — emit the parsed JSON-LD objects whole, up to a token budget.
3. Add microdata + OpenGraph + Twitter Card extraction.
4. Add a "structural fingerprint" of repeated containers: count, position range sampled, attribute distribution, child-element distribution.
5. Add an opt-in "send full HTML to LLM" toggle for power users, with a price estimate. This is the Alternative D on-ramp.
6. Show the user a token-cost estimate before they confirm the analysis call.

Do not jump to Alternative B (full HTML everywhere). The economics do not work for a BYOK product, and the user already trusts deterministic extraction. The AI's job is to give the user a good schema; the AI does not need to see every byte.

### 2.11 A second-order observation: cache invalidation

`ANALYZER_VERSION = "1"` in `app/services/analyzer.py:24` is the cache key for `analysis_cache`. Bumping this invalidates the cache. The current `build_dom_summary` is the only thing that produces the input the LLM sees. When the summary changes (e.g. moving to Alternative C), the cache must be invalidated or every old analysis will be returned for new pages.

This is a solved problem — the version key handles it — but the product team should expect a one-time cache flush on any summary change. The cost of that flush is real (every re-analysis costs tokens), so summarize changes should be batched.

---

## 3. Long-Term Competitive Advantage

### 3.1 What ScrapGPT actually is, today

The product is a single-binary BYOK extraction CLI/API/UI. It runs against the user's own PostgreSQL, with the user's own AI provider credentials, and produces a dataset the user owns. The "competitive set" is therefore not just the SaaS products; it is also:

- **Hand-written scripts** in Python/JS with httpx + BeautifulSoup + an LLM call. This is the most relevant competitor for a technical user.
- **SaaS AI extraction**: Firecrawl, Apify (with their scraping agents), ScrapeGraphAI, Browse AI, Jina Reader.
- **Open-source crawlers**: Crawl4AI, Scrapy + GPT pipelines.
- **No-code tools**: Browse AI, Bardeen, Axiom.

The product's positioning is "BYOK + self-hosted + AI does the schema + deterministic extraction". That positioning is a niche. It appeals to:

- Privacy-sensitive users (regulated industries, EU data residency).
- Cost-sensitive users (BYOK means no SaaS markup).
- Technical users who want a deployable, auditable system.
- Teams that already pay for LLM provider credits and want to use them productively.

It does **not** appeal to non-technical users. The product is currently marketed as "non-technical friendly" in the strategy doc, but the actual product flow is: register, add a provider key, paste a URL, edit JSONB field specs by hand, debug selector failures. That is not a non-technical user experience.

### 3.2 The actual differentiator

Today, ScrapGPT's actual differentiator is **honest cost transparency combined with a clear architectural commitment**:

- BYOK means the cost of running 500-page extraction is "the user's own LLM credits" plus "one PostgreSQL". For a Firecrawl `/extract` call on a 500-page site, the cost is hidden behind their pricing.
- Deterministic extraction means: once a schema works, it works forever. SaaS competitors that call an LLM per page have variable cost and variable quality; ScrapGPT does not.
- Open-source means: no vendor lock-in, no per-record pricing, no rate limits from the SaaS side.

This is real differentiation. It is most relevant for:

- Compliance-sensitive data extraction (legal records, financial filings).
- High-volume recurring extraction (daily product prices across thousands of SKUs).
- Cost-sensitive startups and academic use.

But it is **narrow** differentiation. Firecrawl can match BYOK tomorrow if they want to. Crawl4AI already matches it on openness. The cost advantage is eroded as LLM prices fall. The deterministic advantage is eroded if SaaS competitors cache good schemas.

### 3.3 What could become the strongest differentiator

Three things, in order of defensibility:

1. **Dataset quality at scale.** The product that wins long-term is the one whose output is the most accurate and the most stable. The current pipeline has good quality on a single page; it has no mechanism for quality on a 10,000-page crawl. A "data observability" layer — error rates per selector per page, drift detection, schema evolution — would be defensible because it requires deep integration with the extraction pipeline. See §4.

2. **A crawl-scope model that matches user mental models.** If ScrapGPT nails the SINGLE_PAGE / PAGINATED_DATASET / CATEGORY / WEBSITE primitive (see §1), it becomes the easiest product in the space to use correctly. The current "BFS same-origin" is what every other tool also does, and it is what every user also gets bitten by. Solving this well is a moat because it is a UX problem that requires deep extraction-pipeline integration.

3. **A dataset operations layer.** Once a user has extracted a dataset, they need to know it is correct, deduped, complete, and current. Today the user downloads a CSV and figures it out in a spreadsheet. A "data observability" layer that runs over `extracted_records` — completeness per field, distinct value distributions, time-of-fetch histograms, drift detection across re-runs — would be a moat because no SaaS competitor exposes this on top of their per-call extraction.

In order of ease-of-build: scope first (1), data observability third (3), dataset ops later (3 is the long-term play). All three are defensible against Firecrawl/Crawl4AI because they require deep extraction-pipeline integration, not just LLM calls.

### 3.4 What parts of the roadmap are commodity?

Most of the published roadmap is commodity in the sense that Firecrawl, Apify, or Crawl4AI already do them:

- **Markdown output (Firecrawl)**, **JSON-LD extraction**, **sitemap support (Firecrawl, Apify)**, **JS rendering (Playwright — universal)**, **multi-format export**, **chunked JSONL for RAG (Firecrawl, LangChain loaders)**, **bot-evasion** (most SaaS competitors), **scheduled re-crawling (Apify schedules)**, **Docker packaging**, **structured outputs with a JSON schema (Firecrawl `/extract`, OpenAI Structured Outputs, ScrapeGraphAI)**.
- **Visual field selection** (Browse AI's core product) — ScrapGPT lists this for Phase 3, but it's a feature every competitor already has.

The roadmap items that _are_ differentiating, in the sense that they are not yet standard across competitors:

- **A first-class crawl-scope primitive** (see §1).
- **A data-observability layer** on top of extraction runs (see §3.3).
- **Stable selectors across re-runs** (drift detection, schema evolution, automatic healing — see §4.1).
- **Multi-page-template fingerprinting** — the CrawlScope mode `PAGINATED_DATASET` is a step toward this.

### 3.5 A note on the AI-extraction competitive landscape

Every serious competitor in 2024-2025 has converged on the same architectural thesis as ScrapGPT: _use an LLM to understand the page, then extract deterministically_. What differs is:

- **Distribution model**: hosted (Firecrawl, Apify) vs. BYOK (ScrapGPT) vs. self-hosted open-source (Crawl4AI).
- **Scope primitives**: who has the better scope model (see §1).
- **Schema ergonomics**: schema-first (user provides JSON schema) vs. prompt-first (user describes the desired output in English) vs. auto-detect (AI proposes both schema and selectors) — ScrapGPT is in the third camp.
- **Output formats**: markdown vs. structured JSON vs. both.
- **Operational concerns**: caching, retries, observability, pricing transparency.

ScrapGPT's camp (auto-detect schema + deterministic extraction + BYOK) is currently underserved. The closest competitor in this niche is **Crawl4AI**'s `LLMExtractionStrategy`, which has a similar shape. Crawl4AI is open-source but its LLM strategy is pluggable rather than the default; the deterministic-then-llm-for-refinement is more typical in Crawl4AI's defaults. ScrapGPT's distinctive bet is "AI does the schema, code does the data" — and that bet is the right one, but only if the schema and the data are both high quality.

The biggest threat is **not** Firecrawl's technical capability (ScrapGPT can match or exceed it) but **Firecrawl's distribution**. They are well-funded, well-marketed, and they have the developer mindshare. ScrapGPT's survival strategy is to be the best at the niches Firecrawl is weakest in: BYOK/self-hosted, auditability, large recurring crawls, cost transparency, scope primitives.

---

## 4. Future Risks

The risks below are ranked by impact. Each risk names the failure mode, the current mitigation (if any), and the trigger condition.

### 4.1 Risk: Poor selector quality (high impact, high probability)

**Failure mode:** AI generates a CSS selector that works on the first row of a listing but fails on the 3rd, 17th, or 200th row because the site has template variation. Result: silent undercount of records, possibly 10-30% of pages yielding zero records.

**Current mitigation:** None. `retry_count` is incremented on failure but the page is not requeued. The user has no per-selector error rate. The state machine has no "low-yield" state.

**Trigger:** Any e-commerce or B2B site with template variation across product types (electronics with vs. without specs, real-estate with vs. without agent info, jobs with vs. without salary).

**Likelihood:** Very high. This is the dominant cause of "ScrapGPT missed half the records" complaints.

**Mitigation direction:** Per-selector yield tracking. After extraction, surface the per-field success rate ("title: 100%, price: 47%, stock_badge: 12%"). If any field is below a threshold, the project state moves to a new `NEEDS_REVIEW` state with a per-field action list ("selector .price failed on 53% of records, here are 5 sample pages where it failed"). The user accepts the result or asks the AI to re-suggest a selector for that field.

### 4.2 Risk: Poor crawl scope detection (high impact, certain)

**Failure mode:** The user submits a category page expecting 200 records and gets 3,000 because the crawler BFS'd the whole site. The dataset is wrong and the user is unhappy.

**Current mitigation:** None. There is no scope UI. `url_patterns` is a free-text glob list.

**Trigger:** Every category-style seed URL on a site with sibling categories.

**Likelihood:** Certain. The user has no way to prevent it.

**Mitigation direction:** See §1 — a `CrawlScope` object with named modes and a pre-crawl UI that asks the user to confirm.

### 4.3 Risk: Poor AI understanding (high impact, high probability)

**Failure mode:** The DOM summary omits the field the user cares about (price, stock, seller). The AI proposes a schema that misses the field. The user notices in preview and has to PATCH the spec manually. This is a slow leak of user trust.

**Current mitigation:** None. The summary is lossy by design. The cache hides repeat issues.

**Trigger:** Any site where the important fields are nested, attribute-only, or off-canvas.

**Likelihood:** Very high. The current summary is too aggressive (see §2.4).

**Mitigation direction:** Move to the rich structural summary in §2.8 (Alternative C). Surface the summary in the UI so the user can see what the AI saw. Add a "what did the AI miss?" feedback button.

### 4.4 Risk: Excessive crawling (high impact, medium probability)

**Failure mode:** A user starts a project, walks away, and the crawler fetches thousands of pages they did not intend. The user is unhappy, the site may rate-limit or block ScrapGPT, and the LLM credits are spent.

**Current mitigation:** `page_limit` (default 500). `MIN_CRAWL_DELAY_MS` (default 500ms). The watchdog is 60s and force-fails stuck projects.

**Trigger:** WEBSITE scope (once implemented) without a confirmation step. Or a misconfigured `CrawlScope` with `max_pages=10000`.

**Likelihood:** Medium. The `page_limit` is a real backstop, but the user can set it too high.

**Mitigation direction:** Per-project budget in tokens and requests. Show the user a live cost counter during the crawl. Add a soft-cap warning at 80% of `page_limit` and a hard pause at 100% with a one-click "continue with confirmation" option.

### 4.5 Risk: User trust issues from silent undercounts (high impact, high probability)

**Failure mode:** The user receives a dataset of 200 records when the source has 500. The system reports 200 records as success. The user discovers the undercount weeks later in their own analysis.

**Current mitigation:** The `_progress` payload includes `crawl_pages_total` and `crawl_pages_extracted` etc. (`app/schemas/project.py:98-107`). The user can see the counts, but not the **expected** count.

**Trigger:** Every project where the per-page extraction rate is below 100% of available rows.

**Likelihood:** High.

**Mitigation direction:** The system should know the **expected** record count (from the AI's `estimated_pages` and from counting repeated containers in the HTML) and surface a yield ratio: "expected ~500 records, got 312 (62% yield), 24 pages failed extraction, click here for diagnostics". This is the dataset-observability layer.

### 4.6 Risk: Incorrect datasets due to silent selector drift (high impact, high probability)

**Failure mode:** The site changes its template. The selectors that worked yesterday now return empty. The crawl completes but produces zero records. The user has no signal.

**Current mitigation:** None. There is no scheduled re-crawl, no per-selector success tracking, and no schema-evolution detection.

**Trigger:** Every site eventually.

**Likelihood:** High. Sites change templates constantly.

**Mitigation direction:** Per-selector yield tracking (overlaps with §4.1). Scheduled re-crawl as a first-class feature. When yield drops, the project auto-transitions to `NEEDS_REVIEW` and asks the user to re-analyze. This is the self-healing-scraper concept (ScrapeWise calls it "self-healing infrastructure") applied to ScrapGPT's per-page state model.

### 4.7 Risk: AGPL/proprietary-licensing conflicts from competitor inspiration (medium impact, low probability)

**Failure mode:** ScrapGPT adopts a primitive from a competitor whose docs are open but whose underlying implementation is AGPL or proprietary, and a user complains.

**Current mitigation:** None.

**Trigger:** Any "borrow the design" moment.

**Likelihood:** Low. The competitors use open primitives (CSS selectors, sitemap, llms.txt) that are not encumbered.

**Mitigation direction:** Document the license posture of every borrowed primitive. The primitives themselves (regex, glob, sitemap, llms.txt) are all unencumbered.

### 4.8 Risk: LLM provider lock-in (medium impact, low probability)

**Failure mode:** The schema and prompts are tuned for one provider's output format. Switching providers produces worse results, and the user is effectively locked in.

**Current mitigation:** `call_json_model` (`app/services/provider_service.py:381-429`) is provider-agnostic. LiteLLM abstracts the wire format. Pydantic validation normalizes output.

**Trigger:** Future schema additions that assume a specific provider's "field naming" conventions.

**Likelihood:** Low. The current pipeline is well-abstracted.

**Mitigation direction:** Periodic cross-provider testing in CI. Document the model names the analyzer has been validated against.

### 4.9 Risk: Cost surprises from LLM provider pricing changes (medium impact, medium probability)

**Failure mode:** LLM provider raises prices. The user's per-project cost doubles. The user has no per-project cost cap.

**Current mitigation:** None. The user has a per-pipeline timeout but no per-project cost cap.

**Trigger:** LLM provider price change.

**Likelihood:** Medium. LLM prices have been falling but are not stable.

**Mitigation direction:** Per-project cost cap. Show the user the running cost in tokens and USD during the analysis call and the crawl.

### 4.10 Risk: Multi-instance / multi-tenant deploys (medium impact, low probability)

**Failure mode:** A user tries to run ScrapGPT in a multi-tenant SaaS-of-ScrapGPT configuration. The current BackgroundTasks and APScheduler are single-process; the advisory locks are per-connection.

**Current mitigation:** None. The product is positioned as self-hosted single-tenant.

**Trigger:** A power user tries to deploy ScrapGPT for a team or a small agency.

**Likelihood:** Low for the current market, but the absence of multi-tenant capability may block future growth.

**Mitigation direction:** Document the single-process constraint. Add a "scale mode" guide that uses Celery + Redis.

---

## 5. Recommendations

These recommendations are organized by when they should happen. They are product and architecture decisions, not implementation tickets. Each recommendation names the _what_, the _why_, and the _expected impact_ — but does not enumerate the _how_ in implementation detail.

### 5.1 Do now (next 90 days)

**R1. Make crawl scope a first-class object. The single most important decision.**

Introduce a `CrawlScope` model (or 1:1 table) on `extraction_specs` with the four-mode enum from §1.3. Add a pre-crawl UI screen that offers a 4-tile picker (SINGLE_PAGE / PAGINATED_DATASET / CATEGORY / SUBDOMAIN / WEBSITE), pre-fills include/exclude paths based on the seed URL, and shows a one-sentence impact estimate. Migrate `page_limit` to `max_pages` on the new object; keep `extraction_spec.page_limit` as a fallback default. Update `discover_same_site_links` to take a `CrawlScope` and apply its rules. Update `execute_project_extraction` to call the new scope-aware link discovery.

**Expected impact:** eliminates the calories.info class of bug; aligns ScrapGPT with Firecrawl/Apify/ScrapeGraphAI on scope primitives; makes the rest of the product (selector quality, drift detection, dataset ops) meaningful because the dataset is now defined as the user intended.

**R2. Expand the DOM summary to a "rich structural summary".**

Implement the Alternative C in §2.8. Expand `_MAX_SUMMARY_CHARS` to 30,000-50,000. Replace the single 900-char repeated-container sample with 5 samples at different positions. Stop filtering JSON-LD keys. Add microdata + OpenGraph + Twitter Card extraction. Add a "structural fingerprint" of repeated containers. Add the `ANALYZER_VERSION` bump to "2".

**Expected impact:** substantially better schema quality on the highest-value sites (e-commerce, B2B). Caches for ANALYZER_VERSION=1 are invalidated once; the new cache is the meaningful one going forward.

**R3. Make per-page yield visible to the user.**

Add a `field_yield` object to the project's `progress` payload: per-field success rate across all pages in the crawl. Surface this in the project workspace, not just in the extracted records. If any field is below 70% yield, surface a yellow callout: "field `price` succeeded on 47% of records; click here to see sample failures".

**Expected impact:** makes silent undercounts loud. Without this, the user's first signal of bad data is weeks later. This is the cheapest dataset-quality intervention available.

**R4. Add a strict bug-fix for the legacy `/scrape` SSRF vulnerability.**

Call `validate_url` from `app/api/v1/endpoints/scrape.py:91` and change `scraper.scrape_url` to use `follow_redirects=False` with per-hop validation. This is a security-critical fix and the only material exploit in the codebase. Effort: low; impact: prevents a public internet-facing SSRF.

**R5. Update the README and STATUS.md to match the code.**

The README and `docs/STATUS.md` describe Phase 1 `jobs` as the primary object; the code has `projects` as the primary object. Update both to reflect the current state. Effort: 1-2 hours; impact: removes onboarding confusion for new developers.

### 5.2 Do after validation (next 90-180 days, after the validation plan in `CODEBASE_AUDIT_REPORT.md` §12 has been run)

**R6. Add a `NEEDS_REVIEW` project state for low-yield extractions.**

Extend the project state machine with `NEEDS_REVIEW` as a non-terminal state, reached when any field's yield falls below a threshold (default 50%). The state machine already supports additional non-terminal states (it has `PAUSED` for the same purpose). The watchdog can be extended to flag a project as `NEEDS_REVIEW` after extraction if the per-field yield is low. The user is prompted to re-analyze or to override the threshold.

**Expected impact:** converts silent undercounts into actionable signals. This is the foundation for the §4.1 mitigation.

**R7. Add a per-selector success tracking layer.**

In `crawl_pages` or a new `selector_outcomes` table, record per-selector success/failure per page. After extraction, the system can produce a per-selector yield report and surface it in the UI. This is the data substrate for the §4.6 mitigation and the dataset-observability layer in §3.3.

**Expected impact:** the foundation for self-healing selectors, drift detection, and the dataset-ops layer. Without it, every other quality intervention is blind.

**R8. Add `llms.txt` and `sitemap.xml` integration as first-class discovery sources.**

In `execute_project_extraction`, before HTML link discovery, check for `llms.txt` at the seed's origin. If present, use it as a high-signal source for the CATEGORY and WEBSITE scope modes. Same for `sitemap.xml` (gated by `CrawlScope.respect_sitemap`). Both should be filtered against `CrawlScope.include_paths` / `exclude_paths`.

**Expected impact:** better scope adherence out of the box. A site that publishes `llms.txt` is telling the AI exactly what it should crawl. Honoring that signal reduces the calories.info failure mode.

**R9. Add a per-project cost cap (LLM tokens, LLM USD, pages fetched).**

Add a `cost_budget` object to the project: `max_llm_tokens`, `max_llm_usd`, `max_pages`, `max_runtime_minutes`. The analysis call estimates cost before firing. The crawl pauses at 80% and stops at 100%. The user can override per-run.

**Expected impact:** prevents cost surprises. Without this, the only signal that the project is too expensive is the user's monthly LLM bill.

**R10. Add the validation plan from `CODEBASE_AUDIT_REPORT.md` §12 as a hard prerequisite before any new feature work.**

Specifically: end-to-end project workflow with a real provider; re-run flow verification; cancel-during-extraction; cross-user 404 enforcement; SSRF attempt attempts on both pipelines; robots.txt BLOCKED; LLM provider returns invalid JSON; watchdog timeout; crash mid-page. These are not features — they are correctness gates. Without them, R1 through R9 are built on a foundation that may have hidden defects. Effort: 1-2 days of focused testing.

**Expected impact:** turns a 161-test mocked suite into a tested, exercised system. Without this, every feature ships with unverified assumptions about the surrounding pipeline.

### 5.3 Future phases (after R1-R10 are validated)

**R11. Selector self-healing.**

When per-selector yield drops below threshold (§4.1), the project transitions to `NEEDS_REVIEW`. The user is offered two options: (a) accept the lower yield and re-run, or (b) ask the AI to re-suggest a selector for the failing fields. Option (b) takes the failing pages, runs a focused prompt against a small batch of them ("these 5 pages all return empty for `.price`; find a better selector"), and the AI proposes one. The user accepts. This is the self-healing concept from the broader AI-scraping literature, applied to per-selector rather than per-page.

**Expected impact:** dramatic reduction in user maintenance burden. Sites change templates; selectors should track.

**R12. Multi-page template fingerprinting.**

Use the `PAGINATED_DATASET` mode in `CrawlScope` to detect that the crawl is hitting pages with a different DOM structure (e.g. the 50th page of a listing has a different layout because the product is a video game, not a book). When the AI sees structural divergence, it flags it and offers the user the option to either (a) accept the divergence, (b) re-analyze for the new page type, or (c) skip the divergent pages. This is the "template routing" idea from the strategy doc, applied as an exception flow rather than a separate code path.

**Expected impact:** handles the long tail of mixed-template sites without requiring a separate model per template.

**R13. RAG export formats (markdown, chunked JSONL, vector-DB-ready).**

The strategy doc lists this as Phase 4. Worth doing _after_ the dataset-quality work because the value of clean RAG exports is moot if the underlying data is wrong. When the time comes, follow the open conventions: markdown with frontmatter for metadata, chunked JSONL with one record per chunk, vector-DB-ready JSONL with the source URL and metadata per line.

**Expected impact:** unlocks the RAG use case properly. Today only CSV/JSON/XLSX is exported.

**R14. Authenticated content / session management.**

Phase 5 in the strategy doc. This is the largest product expansion: the user pastes cookies for a domain, the crawler uses them on subsequent requests, the AI sees the auth-rendered DOM. Until now, the product has been "extraction for the public web". Adding auth turns it into "extraction for the user's data". This is a major scope expansion; it should be done _after_ the data-quality foundation is solid, not before.

**Expected impact:** a new product category. But the auth UX is hard, the rate-limit/ban-risk is high, and the user is now trusting ScrapGPT with their credentials. The product should earn this trust by being reliable on the unauthenticated case first.

**R15. Multi-tenant / multi-instance capability.**

The current single-process architecture will not support a SaaS-of-ScrapGPT or a team-shared deployment. The migration is: replace `BackgroundTasks` with Celery or arq, replace `APScheduler` with a dedicated worker process, replace the in-memory `Limiter` with Redis, and document the multi-worker advisory lock contract. This is a 1-2 month effort and should be done when the product has clear multi-user demand, not before.

**Expected impact:** unlocks team and SaaS deployments. Not needed for single-user self-hosted.

---

## 6. Closing thoughts

ScrapGPT is at the kind of inflection point where the next 90 days determine the long-term product, more than the previous 12 months did. The product has the right architectural thesis and a working first loop. What it lacks is a small number of high-leverage decisions:

- A first-class crawl-scope primitive (§1).
- A richer LLM input (§2).
- Visible data quality (§4).

If those three land, ScrapGPT has a defensible niche in a crowded market. If they don't, the product will continue to be a reasonable open-source project but will not become the AI extraction tool of choice for any clear audience.

The single most important sentence in this review: **scope is the missing primitive.** Everything else is downstream.

---

_End of review._
