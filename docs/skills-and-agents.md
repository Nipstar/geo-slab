# Skills, Agents, Scripts & Schemas

Inventory of every component in GEO SLAB.

## Orchestrator

### `geo`
Path: `geo/SKILL.md`. Entry point for all `/geo <command>` invocations. Routes to sub-skills (direct) or fans out to subagents (parallel). Owns the composite GEO Score formula and report-rendering hand-off.

## Sub-skills (16)

### geo-audit
Path: `skills/geo-audit/`. Full-audit orchestrator. Runs Phase 1 discovery, dispatches the parallel agent fan-out, aggregates results, and writes `GEO-AUDIT-REPORT.md` + `audit-data.json` to `reports/<domain>/`.

### geo-citability
Path: `skills/geo-citability/`. Passage-level AI citation readiness. Calls `scripts/citability_scorer.py` to score each content block against the 134–167-word optimal-passage rubric. Output: 0–100 score + per-passage rewrite suggestions.

### geo-crawlers
Path: `skills/geo-crawlers/`. AI crawler access analysis. Parses robots.txt for 14+ bots (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, FacebookBot, Applebot-Extended, Bytespider, CCBot, Amazonbot, Diffbot, anthropic-ai, ChatGPT-User, OAI-SearchBot, Cohere-AI). Reports allow/block per bot.

### geo-llmstxt
Path: `skills/geo-llmstxt/`. Validates existing `llms.txt` or generates a new one from a site crawl. Implements the emerging llms.txt convention (https://llmstxt.org).

### geo-brand-mentions
Path: `skills/geo-brand-mentions/`. Brand presence scanner across AI-cited platforms. Uses `scripts/brand_scanner.py` with optional SerpAPI + Google Places API enrichment. Output: Brand Authority Score (0–100).

### geo-platform-optimizer
Path: `skills/geo-platform-optimizer/`. Per-platform readiness scoring across Google AI Overviews, ChatGPT, Perplexity, Gemini, Bing Copilot, Grok, DeepSeek, Meta AI, Mistral. Each platform gets its own checklist.

### geo-schema
Path: `skills/geo-schema/`. Structured-data detect / validate / generate. Parses JSON-LD, RDFa, Microdata. Emits ready-to-paste templates from `schema/` rebuilt with the page-specific data.

### geo-technical
Path: `skills/geo-technical/`. Technical SEO foundations: Core Web Vitals (INP), SSR detection, robots.txt sanity, sitemap.xml, canonical tags, mobile responsiveness, security headers.

### geo-content
Path: `skills/geo-content/`. Content quality + E-E-A-T assessment. Author signal extraction, original-data detection, AI-content heuristics, readability scoring.

### geo-report
Path: `skills/geo-report/`. Generates the client-ready Markdown report from `audit-data.json`. Composes findings, action plan, methodology appendix.

### geo-report-pdf
Path: `skills/geo-report-pdf/`. Wraps `scripts/render_geo_report.py` (HTML render) + `scripts/generate_pdf_report.py` (Playwright print). Output: `GEO-REPORT-<domain>.html` + `.pdf`.

### geo-compare
Path: `skills/geo-compare/`. Monthly delta tracking. Diffs two `audit-data.json` snapshots, highlights category movements, frames progress narrative.

### geo-proposal
Path: `skills/geo-proposal/`. Auto-generates a tiered service proposal from audit data. Pricing scales by score tier (Critical sites get higher monthly retainers).

### geo-live-visibility
Path: `skills/geo-live-visibility/`. Live AI visibility test. Calls `scripts/live_ai_query.py` to query ChatGPT, Claude, Gemini, Perplexity APIs directly. Requires at least one provider key.

### geo-prospect
Path: `skills/geo-prospect/`. Lite prospect deliverable — top problems only, no fixes, with a CTA back to the full audit. Uses `scripts/generate_prospect_report.py --pdf`.

### geo-dashboard
Path: `skills/geo-dashboard/`. Documents how to launch the Flask web dashboard at `webapp/`. Surfaces `/geo dashboard` inside Claude Code so users discover the CRM workflow.

## Subagents (5 core + 1 optional)

Subagents bundle one or more sub-skills and run in parallel during `/geo audit`.

### geo-ai-visibility
Path: `agents/geo-ai-visibility.md`. Bundles: geo-citability, geo-crawlers, geo-llmstxt, geo-brand-mentions. The "everything an AI sees" pillar.

### geo-platform-analysis
Path: `agents/geo-platform-analysis.md`. Bundles: geo-platform-optimizer. Dedicated agent so the 9-platform scan doesn't bottleneck the visibility agent.

### geo-technical
Path: `agents/geo-technical.md`. Bundles: geo-technical. Crawls Core Web Vitals + SSR + security in parallel.

### geo-content
Path: `agents/geo-content.md`. Bundles: geo-content. Extracts author/expertise signals, runs readability and AI-content checks.

### geo-schema
Path: `agents/geo-schema.md`. Bundles: geo-schema. Detects + validates structured data; suggests fixes from `schema/` templates.

### geo-live-visibility *(optional)*
Path: `agents/geo-live-visibility.md`. Bundles: geo-live-visibility. Joins the audit fan-out only if AI provider API keys are configured. Never fabricates results.

## Python scripts (8)

All under `scripts/`. Standalone utilities the skills call via `Bash`.

| Script | Purpose | Key dependencies |
|--------|---------|------------------|
| `fetch_page.py` | HTTP/HTML page fetcher with crawler-UA spoofing. Auto-switches to Firecrawl when `FIRECRAWL_API_KEY` set. | `requests`, `beautifulsoup4`, `firecrawl-py` (optional) |
| `citability_scorer.py` | Passage-level citation-readiness scorer. Local, no API. | `nltk` / stdlib regex |
| `brand_scanner.py` | Brand mention detection across Reddit, YouTube, Wikipedia, etc. | SerpAPI key (optional), Google Places API key (optional) |
| `llmstxt_generator.py` | llms.txt validate + generate. | stdlib |
| `render_geo_report.py` | Neo brutalist HTML report generator (JSON → HTML). Canonical CSS template. | `jinja2` |
| `generate_pdf_report.py` | Playwright PDF printer. Imports `render_geo_report.py`, prints via headless Chromium. | `playwright`, Chromium |
| `generate_prospect_report.py` | Lite prospect HTML report. `--pdf` flag adds Playwright PDF. | `jinja2`, `playwright` (for PDF) |
| `live_ai_query.py` | Live AI visibility — queries ChatGPT, Claude, Gemini, Perplexity APIs. | `openai`, `anthropic`, `google-generativeai`, `requests` |

## Schema templates (6)

All under `schema/`. Drop-in JSON-LD templates the `geo-schema` skill injects as starting points.

| Template | Use case |
|----------|----------|
| `organization.json` | Universal company entity. Always recommended. |
| `local-business.json` | Service-area + brick-and-mortar. Adds geo, hours, sameAs. |
| `article-author.json` | Article + Person schema. Critical for E-E-A-T on publishers. |
| `software-saas.json` | SoftwareApplication. Pricing, ratings, app category. |
| `product-ecommerce.json` | Product. Price, availability, aggregateRating, offers. |
| `website-searchaction.json` | WebSite + SearchAction. Enables sitelinks search box. |

## When to use what

| You want to... | Run |
|----------------|-----|
| Audit a whole site | `/geo audit <url>` |
| Score a single page for AI citations | `/geo citability <url>` |
| Check if AI bots can read the site | `/geo crawlers <url>` |
| Sanity-check schema on a page | `/geo schema <url>` |
| Generate a client-ready PDF report | `/geo report-pdf <url>` |
| Pitch a new prospect | `/geo prospect <url>` |
| Track a client's progress month-over-month | `/geo compare <domain>` |
| Test what AI models actually say about a brand | `/geo live <url>` |
| Manage prospects + notes in a browser | `/geo dashboard` |
