# ScrapGPT Product UX and Architecture Review

Date: June 9, 2026

Scope: crawl boundaries, AI analysis context, competitive positioning, future risks, and long-term product direction. This is a review document, not an implementation plan.

## Executive Summary

ScrapGPT's current architecture has a strong core idea: use AI to understand a seed page and produce an extraction configuration, then use deterministic selector execution for the actual crawl. That is a real architectural differentiator against tools that call an LLM on every page. The weakness is that ScrapGPT currently treats crawl discovery as a low-level same-origin crawl problem, while users think in terms of datasets, pages, pagination, categories, and sites.

The calories.info potato-products example exposes the gap clearly. Links to Pizza, Meat, Beer, and Fruit are valid same-origin URLs, but they may be outside the intended dataset. That is not only a crawler bug. It is a product and architecture modeling problem: the system lacks a first-class representation of user intent and crawl scope.

The second major issue is context quality. The current DOM summary is useful for cost and latency, but it is still a lossy compression of the page. It can hide nested fields, metadata, stock/seller/discount details, complete table schemas, embedded structured data, and secondary templates. The best long-term approach is not "full HTML always" or "summary only forever." It is a hybrid evidence model: rich structural summary by default, targeted raw fragments when uncertainty exists, and user-visible diagnostics before extraction.

The most important long-term direction is to make ScrapGPT a scope-aware, trust-centered extraction system. The winning product is not the one that crawls the most pages. It is the one that helps users define the right dataset boundary, shows what it will crawl, previews whether selectors work, and explains uncertainty before producing a dataset.

## Current Architecture Snapshot

Current primary workflow, based on `docs/STATUS.md` and the active code:

1. User creates a project from a URL in `/projects`.
2. Backend validates and fetches the seed URL.
3. `build_dom_summary()` compresses the page into a structural text summary.
4. `analyze_page()` sends that summary to the configured AI provider.
5. `default_spec_from_analysis()` converts candidate AI fields into an `ExtractionSpec`.
6. User selects fields and can run a selector preview on the seed page.
7. `execute_project_extraction()` crawls pages and executes saved CSS selectors.
8. Results are stored in `extracted_records` and exported as CSV, JSON, or XLSX.

Important current mechanics:

- `ExtractionSpec` stores `fields`, `content_config`, `url_patterns`, `page_limit`, and `export_format`.
- There is no semantic crawl-scope field today.
- `discover_same_site_links()` accepts all same-origin links unless optional include/exclude glob patterns reject them.
- `execute_project_extraction()` discovers links from every fetched page, inserts pending crawl pages, and stops only at `page_limit` or no pending pages.
- Preview executes selectors only on the seed page. It does not currently validate that the crawl frontier matches user intent.
- AI is used for initial analysis, not per-page extraction.

This makes the product efficient and explainable, but it also means the initial analysis and crawl boundary carry a lot of responsibility.

## 1. Crawl Scope Problem

### What The Calories.info Example Shows

The URL:

`https://www.calories.info/food/potato-products`

could mean several different user intents:

- Extract only this page.
- Extract this dataset across pagination.
- Extract related pages inside the same food category or taxonomy.
- Explore the whole site.

The current crawler sees a different question: "Which same-origin links can be crawled?" That can include links to Pizza, Meat, Beer, Fruit, and other sections. Same-origin is a technical safety boundary. It is not a product boundary.

### Bug, UX Problem, Or Architecture Problem?

It is all three, but not equally.

| Layer | Assessment | Why it matters |
|---|---|---|
| Bug | Partly | If the product promises "extract this dataset" and returns unrelated records, the behavior is wrong from the user's perspective. |
| UX problem | Strongly | The user is not asked what "this URL" means. Page limit is visible, but scope is not. |
| Architecture problem | Strongly | The persisted spec has low-level URL globs but no durable model for scope intent, scope confidence, candidate URL sets, or accepted/rejected link clusters. |

The architectural issue is the root. A UX control cannot be cleanly added if the backend model still treats scope as incidental link filtering.

### How Crawl Scope Should Be Represented

Crawl scope should become a first-class part of the extraction definition. It belongs with the extraction spec because it defines what the dataset means. The same selected fields applied to a different scope creates a different dataset.

A durable scope model should capture:

- `mode`: the semantic scope chosen by the user.
- `seed_url`: the page or dataset entry point.
- `allowed_url_rules`: generated or user-edited include/exclude constraints.
- `pagination_rule`: if the mode is pagination-only.
- `link_role_rules`: which links are pagination, detail pages, category links, unrelated navigation, downloads, etc.
- `max_depth` and `page_limit`: resource bounds, not intent substitutes.
- `ai_scope_suggestion`: AI recommendation with confidence and evidence.
- `user_confirmed`: whether the user accepted or changed the scope.

The important distinction: `url_patterns` are an implementation detail. Scope is the product concept. Users should not have to understand globs to avoid extracting the wrong dataset.

### Recommended Scope Modes

| Mode | User meaning | Crawler behavior | Default risk |
|---|---|---|---|
| Current page only | "Extract data visible on this URL." | Fetch seed URL only. No link discovery. | Low. May under-extract paginated datasets. |
| Dataset pagination only | "Extract this list/table across its pages." | Follow only detected pagination controls or equivalent page-param rules. Do not follow category/navigation/detail links unless explicitly configured. | Low to medium. Depends on pagination detection quality. |
| Same dataset / related pages | "Extract records belonging to this dataset, including detail pages or closely related listing pages." | Follow pagination plus AI/classifier-approved detail or sibling dataset URLs under a constrained path/pattern. | Medium. Requires good URL/template clustering and preview. |
| Full site exploration | "Explore this site broadly." | Same-origin crawl with explicit limits, robots checks, depth controls, and warnings. | High. Should be opt-in and visible. |

For early product safety, "current page only" and "dataset pagination only" should be the conservative defaults. Full same-site exploration should never be the silent default for structured extraction.

### Should Scope Be Inferred By AI?

AI should infer candidate scope, not decide scope silently.

AI is useful for:

- Detecting likely page type: listing, detail, category, search, article, documentation.
- Identifying pagination selectors and next-page patterns.
- Classifying link clusters as pagination, detail, category, navigation, footer, ads, social, downloads.
- Explaining likely risk: "This page links to unrelated food categories; same-site crawling may mix datasets."
- Suggesting a default mode with confidence.

AI should not be the final authority for broad crawling because the cost of being wrong is user trust and dataset correctness. The user should explicitly confirm scope before extraction, especially when the crawl can leave the seed page or pagination chain.

### Should Users Explicitly Choose Scope?

Yes, but the UI should not feel like a crawler configuration form.

The user-facing question should be closer to:

"What do you want to extract?"

Choices:

- This page only.
- This list across pages.
- This dataset, including item detail pages.
- The whole site.

Then show evidence:

- Sample URLs that will be included.
- Sample URLs that will be excluded.
- Detected pagination link.
- Detected detail/category/navigation link groups.
- Estimated page count or known uncertainty.

The key UX principle is confirmation with evidence, not blind configuration.

### What Comparable Products Do

Modern scraping products generally separate extraction configuration from crawl boundaries:

- Firecrawl exposes separate scrape, crawl, map, and extract concepts. Its crawl API supports limits, depth, sitemap behavior, include/exclude paths, and related crawl controls. This confirms that broad crawling is treated as an explicit mode with constraints, not as the default interpretation of a scrape URL.
- Crawlee and Apify-style crawler systems expose link enqueueing rules, selectors, globs, pseudo-URLs, strategies, and request limits. These are developer-facing primitives, but the principle is the same: the frontier is configured intentionally.
- Browse AI, ParseHub, and Octoparse use visual workflow concepts. Users train what to extract and define pagination/detail navigation through recorded actions or page templates. The product model is "this list, next page, this detail page," not "crawl any same-domain URL."

ScrapGPT should learn from both camps:

- From developer tools: explicit frontier constraints and reliable crawl primitives.
- From visual/no-code tools: user intent is represented as workflow semantics, not URL glob syntax.

### Best Long-Term Design For ScrapGPT

The best long-term model is "scope-aware extraction spec with AI-assisted frontier planning."

The extraction spec should represent both:

- What to extract: fields, content selectors, normalization, output format.
- Where to extract it: scope mode, link roles, URL rules, pagination/detail behavior, limits, and confirmation state.

The crawler should not discover all same-site links and hope selectors filter the result. It should build a crawl frontier from an accepted scope plan:

1. Analyze seed page.
2. Build link clusters and pagination/detail candidates.
3. Propose a scope mode and show included/excluded examples.
4. User accepts or changes scope.
5. Extraction crawls only the approved frontier class.

That would turn the calories.info case from a silent error into a clear product moment:

"This page links to other food categories. Do you want only Potato Products, all food categories, or the full site?"

## 2. AI Analysis Context Problem

### Current DOM Summary Approach

`build_dom_summary()` is designed to reduce cost and remove noisy HTML. It currently includes:

- URL.
- Up to 8 headings.
- Limited JSON-LD fields.
- Repeated element classes.
- HTML samples from repeated containers.
- Up to 3 table samples.
- Up to 20 `data-*` attributes.
- Up to 12 links.
- Pagination candidates.
- A 600-character body text snippet.
- A 10,000-character total cap.

This is directionally correct. It gives AI structure without sending the entire page. It also supports the current strategic choice: AI analyzes the site once, deterministic extraction runs later.

### What Information Is Currently Lost

Important losses:

- Full title and meta context may be lost because `head` and `meta` are removed before title/meta extraction.
- Script-embedded data is removed, including hydration JSON that often contains product price, stock, seller, variants, ratings, and IDs.
- JSON-LD is reduced to only `@type`, `name`, and `description`, losing offers, availability, brand, aggregateRating, price, SKU, breadcrumbs, images, and organization metadata.
- Only a few repeated container samples are included, so secondary card variants may be missed.
- Only the first few table rows are represented, which can hide columns, footnotes, nested rows, or repeated header structures.
- Link context is shallow. The AI sees sample links, but not a full link graph grouped by DOM region or semantic role.
- Hidden, expandable, tabbed, or interaction-gated fields may be omitted.
- Attributes beyond a small sample are lost, including ARIA labels, itemprop, microdata, canonical URLs, and alternate links.
- The 10,000-character cap can truncate the most useful evidence on dense pages.
- The summary is seed-page-only. It does not represent other templates that the crawler may later encounter.

### Websites Most Affected

The current summary is most likely to underperform on:

- Ecommerce product/listing pages with nested price, seller, availability, discount, variant, and shipping data.
- Marketplace pages where seller and fulfillment metadata are in nested cards or hydration blobs.
- Real estate, jobs, travel, events, and classifieds pages with dense repeated cards and detail pages.
- Sites using JavaScript frameworks where meaningful data is in embedded JSON rather than static DOM text.
- Table-heavy sites with many columns, merged headers, or pagination/filter state.
- Documentation and knowledge bases with sidebars, breadcrumbs, version selectors, and nested metadata.
- Search result pages where sponsored/organic/card types have different templates.

### Is The Current Summary Too Aggressive?

For simple pages, no. For production-quality structured extraction, yes.

The current summary is good enough for early demos and straightforward listing pages. It is not enough to reliably infer high-quality selectors and scope on complex, high-value sites. The issue is not just token count. It is evidence selection. The summary selects a small number of generic signals, but high-quality extraction needs field-specific evidence and link-role evidence.

### Is The Current Summary Sufficient?

It is sufficient as a baseline analysis input. It should not be treated as the complete page representation.

The product should move from "DOM summary" to "analysis evidence bundle." A good evidence bundle would include:

- Structural outline.
- Repeated item candidates with multiple raw examples.
- Full table schemas and representative rows.
- Metadata and structured data, including JSON-LD offers/ratings/breadcrumbs.
- Link clusters by DOM region and likely role.
- Pagination/detail/category/navigation candidates.
- Field-specific raw snippets when the model is uncertain.
- Render metadata and interaction hints.
- Template fingerprints from sampled pages when crawling beyond the seed page.

### Context Approach Comparison

| Approach | Extraction quality | Cost | Latency | Reliability | Scalability |
|---|---|---|---|---|---|
| A. DOM Summary -> AI | Good for simple listing/content pages. Weak on nested, metadata-heavy, and JS-hydrated pages. | Low. | Low. | Stable but can be confidently incomplete. | Strong. Token use is bounded. |
| B. Full HTML -> AI | Better chance of seeing hidden fields and metadata, but raw HTML is noisy and can distract models. | High, sometimes very high. | Higher. | More vulnerable to token limits, irrelevant boilerplate, prompt injection, and model variance. | Weak for self-hosted BYOK users and large pages. |
| C. Rich Structural Summary -> AI | Better field and scope detection if the summary preserves semantic evidence, link clusters, structured data, and representative fragments. | Medium. | Medium. | More reliable than thin summaries if deterministic preprocessing is strong. | Good. Still bounded and cacheable. |
| D. Hybrid | Best practical quality: summary by default, targeted raw fragments/full snippets only where needed. | Adaptive. Low on easy pages, higher on hard pages. | Adaptive. | Strongest if uncertainty triggers are explicit and preview validates output. | Best long-term fit. Cost grows with complexity, not page count. |

### Recommended AI Context Direction

ScrapGPT should adopt the hybrid approach.

The default should remain summary-based because ScrapGPT's differentiator depends on low AI cost and deterministic extraction. But the summary should become richer and progressive:

1. Start with a rich structural summary.
2. Detect uncertainty: low confidence, sparse fields, missing expected metadata, multiple templates, ambiguous pagination, many unrelated link clusters.
3. Add targeted raw fragments: complete repeated item samples, full table blocks, JSON-LD objects, selected link regions, and relevant script data.
4. Re-analyze only the uncertain part, not the entire site.
5. Validate through selector preview and field-level diagnostics.

The AI should be asked to cite evidence internally in structured form: which snippets support each field, which links support pagination, and which links are outside scope. That evidence can then be shown in product language.

## 3. Long-Term Competitive Advantage

### Current Differentiator Today

ScrapGPT's real differentiator is not "AI scraping." That phrase is too broad and already crowded.

The current differentiator is:

- Open-source, self-hosted, BYOK extraction.
- AI used sparingly for setup, not per page.
- Deterministic selector execution after analysis.
- A project workflow that already separates analysis, field selection, preview, extraction, records, and export.
- Raw and normalized data storage shape that can support trustworthy review later.

That is a credible foundation, but it is not yet enough to stand apart from mature tools.

### Strongest Potential Differentiator

The strongest long-term differentiator is trustworthy AI-assisted dataset definition.

Most scraping tools make one of two tradeoffs:

- Developer tools give precise crawl controls but require technical setup.
- No-code tools make setup visual but hide too much crawler/extraction uncertainty.
- AI-first tools can be impressive on a page but expensive or unreliable at crawl scale.

ScrapGPT can occupy a better position:

"AI proposes the dataset boundary and selectors, deterministic code executes them, and the user sees evidence before the crawl runs."

That could become meaningfully different if ScrapGPT makes these things first-class:

- Scope confirmation.
- URL frontier preview.
- Field quality diagnostics.
- Template-aware extraction.
- Selector repair with evidence.
- Raw-data preservation and normalized-data verification.
- Dual output modes: structured datasets and RAG-ready content.

### Roadmap Areas That Increase Differentiation

High differentiation:

- Semantic crawl scope and user-confirmed dataset boundaries.
- Visual field selection combined with deterministic selector generation.
- Template clustering and template-specific selectors.
- Selector quality scoring across sampled pages.
- AI-assisted selector repair that shows evidence and preserves user control.
- Hybrid context analysis with rich structural evidence.
- RAG/content export that preserves source URLs, headings, metadata, and chunk provenance.

Moderate differentiation:

- BYOK multi-provider setup.
- Local/self-hosted deployment with simple onboarding.
- Raw + normalized data review.
- Authenticated-content human-in-the-loop support.

Commodity features:

- Basic CSV/JSON/XLSX export.
- Same-site crawling.
- Page limits and crawl delays.
- Provider CRUD.
- Generic dashboard/history.
- Basic robots checks and URL validation.
- Legacy single-page scrape/summary flows.

Commodity does not mean unimportant. It means these features are table stakes and should not dominate the product vision.

## 4. Future Risks

### Ranked Risk Table

| Rank | Risk | Severity | Why it matters | Current exposure |
|---|---|---|---|---|
| 1 | Wrong crawl scope creates incorrect datasets | Very high | Users may export mixed or irrelevant records while believing the dataset is correct. This directly damages trust. | High, because same-origin discovery is default and scope is not explicit. |
| 2 | Poor selector quality silently drops or corrupts fields | Very high | Empty fields, shifted row alignment, or wrong values can be harder to detect than outright failures. | Medium-high. Preview helps seed page only; no cross-template diagnostics yet. |
| 3 | AI misses important fields due to lossy context | High | Seller, stock, discount, metadata, nested detail, and structured data may never become selectable fields. | Medium-high on complex pages. |
| 4 | Excessive crawling wastes resources or hits unrelated site sections | High | Self-hosted users pay with time, CPU, bandwidth, provider usage, and potential site blocking. | Medium-high. Page limit bounds damage but does not encode intent. |
| 5 | User trust erodes because uncertainty is hidden | High | Non-technical users need to know when the system is unsure. Silent confidence is worse than visible limitation. | Medium. Confidence exists, but scope confidence and frontier evidence do not. |
| 6 | Multi-template sites produce inconsistent records | Medium-high | Listing, detail, category, search, and article templates require different assumptions. | Medium. No template routing/fingerprinting yet. |
| 7 | Crash/retry behavior strands pages or loses progress | Medium | Page rows and leases exist, but durable lease recovery is not fully implemented. | Medium for long jobs; lower for small local runs. |
| 8 | Legacy workflow confuses product identity | Medium | `/scrape` and `/jobs` compatibility paths can blur what the primary product is. | Medium. Docs say `/projects` is primary, but old flows remain. |
| 9 | Provider/model variance changes analysis quality | Medium | BYOK means users may choose weak models and get poor specs. | Medium. Structured validation exists, but quality gating is limited. |
| 10 | Overbuilding broad crawler features before scope UX | Medium | Better crawling without better intent modeling can increase wrong-data risk. | Strategic risk, not immediate runtime risk. |

### Risk Interpretation

The biggest risks are not throughput risks. They are correctness and trust risks.

A crawler that fails loudly is frustrating. A crawler that succeeds with the wrong dataset is dangerous. ScrapGPT should optimize for "the user can tell what will be extracted" before optimizing for larger crawls.

## 5. Recommendations

These recommendations are intentionally phrased as product and architecture direction, not implementation tasks.

### Do Now

Define crawl scope as a core product concept.

ScrapGPT should stop describing extraction as "crawl same-site pages up to the page limit." The product language should become "choose the dataset boundary." Same-site crawling should be one explicit scope mode, not the default mental model.

Make extraction specs represent intent, not just selectors.

The spec should eventually persist scope mode, scope evidence, URL/link constraints, and confirmation state. This is the right layer because changing scope changes the dataset even if fields stay identical.

Default conservatively.

For structured extraction, the safest defaults are current page only or dataset pagination only. The product should require explicit user acceptance before following category, detail, or broad same-site links.

Treat AI as recommender, not authority.

AI should suggest scope and explain why, but broad crawling should require user confirmation. The system should expose uncertainty, especially when many same-origin links look unrelated to the seed dataset.

Reframe page limit.

Page limit is a resource cap, not a scope definition. It prevents runaway jobs but cannot prevent mixed datasets. The UI and architecture should not rely on it as the main safety control.

Upgrade the mental model of DOM summary.

The current summary should be considered a first evidence bundle, not the full analysis context. The product should plan for richer structural evidence and targeted snippets instead of debating summary-only versus full-HTML-only.

Prioritize diagnostics over automation.

Before expanding crawl power, ScrapGPT should be able to answer: "Which URLs will be crawled?", "Which selectors worked?", "Which fields are missing?", and "Which pages looked like a different template?"

### Do After Validation

Validate scope modes with real sites.

Use representative sites across ecommerce, calories/nutrition tables, real estate, jobs, documentation, and directories. The question is not only whether extraction works, but whether users choose the same scope the AI recommends.

Validate AI link-role classification.

Measure whether AI and deterministic heuristics can separate pagination, detail links, sibling dataset links, unrelated category links, and navigation links. This is central to the calories.info problem.

Validate richer context cost against quality.

Compare thin DOM summary, full HTML, rich structural summary, and hybrid evidence on real pages. The metric should be field discovery and selector correctness, not only AI confidence.

Validate preview as a trust mechanism.

A seed-page preview is useful but incomplete. The next validation question is whether users need a "frontier preview" and a "multi-page selector sample" before extraction.

Validate non-technical language.

Avoid exposing scope as "include glob" or "max depth" first. Test whether users understand "this page," "this list across pages," "this dataset including details," and "whole site."

### Future Phases

Template-aware extraction should become central.

When scope includes detail pages or related pages, ScrapGPT needs template fingerprints and template-specific selector behavior. A single seed-page selector set will not be enough.

Selector repair should be evidence-based.

Repair should not silently rewrite extraction behavior. It should explain what failed, show candidate replacements, preserve raw data, and respect user confirmation thresholds.

Hybrid analysis should become progressive.

Simple pages should stay cheap. Complex pages should earn more context: additional raw fragments, structured data, table schemas, and sampled templates.

Visual field selection should complement, not replace, AI.

The long-term product should let users click the data they want, while ScrapGPT generalizes selectors and validates them across pages. That is stronger than either pure AI or pure CSS editing.

Full-site exploration should be advanced and visibly risky.

Full-site crawl is useful for content/RAG and site audits, but it should be opt-in, constrained, and explained. It is rarely the right default for structured datasets.

Durable crawler recovery should matter more once scope is correct.

Lease recovery, multi-worker claiming, and concurrency are important. But scaling a crawler before fixing dataset scope can scale wrong results. Reliability work should follow the intent model, not replace it.

## Decision Guidance

ScrapGPT should not compete by becoming the broadest crawler first. It should compete by becoming the clearest tool for turning a URL into a trusted dataset.

The core product question should move from:

"How many same-site pages can we crawl?"

to:

"What dataset did the user intend, what evidence supports that boundary, and how do we prove the extracted records match it?"

That shift makes the architecture stronger:

- AI analysis becomes evidence generation.
- Extraction spec becomes a durable contract.
- Crawler frontier becomes a consequence of user-confirmed scope.
- Preview becomes a trust gate.
- Results become verifiable output, not just rows.

## References

Research consulted for product comparison and architecture patterns:

- Firecrawl documentation: scrape, crawl, map, and extract concepts, including crawl limits and path constraints. https://docs.firecrawl.dev/
- Firecrawl crawl API reference. https://docs.firecrawl.dev/api-reference/v2-endpoint/crawl-post
- Firecrawl scrape feature documentation. https://docs.firecrawl.dev/features/scrape
- Firecrawl extract feature documentation. https://docs.firecrawl.dev/features/extract
- Crawlee documentation for crawler flow and link enqueueing concepts. https://crawlee.dev/js/docs/introduction/crawling
- Crawlee `enqueueLinks` API reference for globs, strategies, and link discovery controls. https://crawlee.dev/js/api/core/function/enqueueLinks
- Apify documentation and Web Scraper concepts for request queues, link selectors, pseudo-URLs, and crawl limits. https://docs.apify.com/
- Browse AI documentation and product help for visual robot training, extracted lists, and pagination workflows. https://help.browse.ai/
- ParseHub documentation for visual project workflows, pagination, templates, and relative selection concepts. https://help.parsehub.com/
- Octoparse documentation for visual scraping workflows, pagination, loop items, and data extraction configuration. https://helpcenter.octoparse.com/
