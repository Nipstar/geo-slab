---
name: geo
description: >
  GEO-first SEO analysis tool. Optimizes websites for AI-powered search engines
  (ChatGPT, Claude, Perplexity, Gemini, Google AI Overviews, Grok, DeepSeek, Meta AI, Mistral) while maintaining
  traditional SEO foundations. Performs full GEO audits, citability scoring,
  AI crawler analysis, llms.txt generation, brand mention scanning, platform-specific
  optimization, schema markup, technical SEO, content quality (E-E-A-T), and
  client-ready GEO report generation. Use when user says "geo", "seo", "audit",
  "AI search", "AI visibility", "optimize", "citability", "llms.txt", "schema",
  "brand mentions", "GEO report", or any URL for analysis.
allowed-tools: Read, Grep, Glob, Bash, WebFetch, Write
---

# GEO-SEO Analysis Tool — Claude Code Skill (February 2026)

> **Philosophy:** GEO-first, SEO-supported. AI search is eating traditional search.
> This tool optimizes for where traffic is going, not where it was.

---

## Quick Reference

| Command | What It Does |
|---------|-------------|
| `/geo audit <url>` | Full GEO + SEO audit with parallel subagents |
| `/geo page <url>` | Deep single-page GEO analysis |
| `/geo citability <url>` | Score content for AI citation readiness |
| `/geo crawlers <url>` | Check AI crawler access (robots.txt analysis) |
| `/geo llmstxt <url>` | Analyze or generate llms.txt file |
| `/geo brands <url>` | Scan brand mentions across AI-cited platforms (SerpAPI + Google Places when configured) |
| `/geo platforms <url>` | Platform-specific optimization (all 9 AI platforms incl. Grok, DeepSeek, Meta AI, Mistral) |
| `/geo schema <url>` | Detect, validate, and generate structured data |
| `/geo technical <url>` | Traditional technical SEO audit |
| `/geo content <url>` | Content quality and E-E-A-T assessment |
| `/geo report <url>` | Generate client-ready GEO deliverable |
| `/geo report-pdf <url>` | Generate professional PDF report with charts and scores |
| `/geo compare <domain>` | Monthly delta tracking — compare two audits over time |
| `/geo proposal <domain>` | Auto-generate client GEO service proposal from audit data |
| `/geo live <url>` | Live AI visibility test — query ChatGPT, Claude, Gemini, Perplexity directly |
| `/geo quick <url>` | 60-second GEO visibility snapshot |
| `/geo prospect <url>` | Lite prospect deliverable — top problems, no fixes, full-audit CTA |
| `/geo prospecting <keywords_file> <location>` | **EXPERIMENTAL** — SERP-driven prospecting pipeline. Discovery + audit + scoring stable. Outreach generation + decision-maker scrape (`find_decision_makers.py`) still under iteration. |
| `/geo find <trade> <location>` | Discover prospects via Google Places (New) → SQLite. `python3 ~/.claude/skills/geo/scripts/places_prospector.py --trade "<trade>" --location "<location>" [--limit N] [--campaign tag] [--max-spend USD] [--dry-run]`. Dedupes on place_id + domain, skips no-website + chains. Writes to `~/.geo-slab/geo-slab.db` (status=found). |
| `/geo enrich <PRO-id\|--batch status>` | Companies House enrichment → SQLite. `python3 ~/.claude/skills/geo/scripts/companies_house.py --prospect PRO-001` or `--batch found [--limit N]`. Fuzzy-matches trading name → registered company (name token-sort + postcode-district signal, active only), pulls type/status/registered address/SIC/incorporation + primary active director. Sets `ch_match_confidence` (≥0.8 match, 0.5-0.8 review — see `--review`, <0.5 = probable sole trader) and `outreach_channel` (§8 PECR: corporate+email→email, else letter). Advances found→enriched. Add `--linkedin` to chain Apify LinkedIn enrichment (costed). |
| `/geo linkedin <PRO-id\|--batch [status]>` | **Costed** LinkedIn enrichment via Apify harvestapi actors. `python3 ~/.claude/skills/geo/scripts/apify_linkedin.py --prospect PRO-003` or `--batch checked --max-profiles N`. Shortlist only (needs a director; run after `/geo check`). Company page + headcount, then director profile + title — both name-match gated (rejects wrong-firm / namesake matches; no data beats bad data). Writes `li_*` columns. Env-overridable actor slugs. |
| `/geo check <PRO-id\|domain>` | **FREE lead-magnet check** (not a mini-audit). `python3 ~/.claude/skills/geo/scripts/visibility_check.py --prospect PRO-001 --location "<town>"` (or `--company --domain --industry --location`). Runs 5 prompts × 4 engines (ChatGPT/Claude/Gemini/Perplexity via OpenRouter), reports mention yes/no per platform + competitors AI named instead + blunt 0-100 score. Renders `reports/<domain>/AI-CHECK-<domain>.{html,pdf}`, logs to `checks` table, advances prospect to status=checked. Scope FROZEN — no citability/technical/schema/fixes (those are paid). |
| `/geo outreach <PRO-id\|--batch status>` | Generate cold outreach copy (email subject+body + LinkedIn connect note) in the Antek voice. `python3 ~/.claude/skills/geo/scripts/outreach_generator.py --prospect PRO-001` or `--batch checked [--out DIR]`. Deterministic templates (no LLM), personalised from the prospect's latest free check (engines that don't recommend them + top competitor). Suppression-checked. Persists one `outreach` row per channel; `--out` also writes per-prospect `.md` drafts. Drives to the free walkthrough — fixes stay paid. |
| `/geo mail <PRO-id ...\|--batch status>` | Build a **Stannp-ready postal batch** (Stannp API deferred → files you import by hand). `python3 ~/.claude/skills/geo/scripts/mail_batch.py --batch enriched --out prospects/mail/` or `--prospect PRO-002 PRO-005`. Renders one A4 letter PDF per prospect (the 2-page mailer, driven by the free-check findings) + `stannp_recipients.csv` (firstname/lastname/address1/address2/city/postcode/country). Only mails `outreach_channel='letter'` (use `--force` to override); suppression-checked. `--no-pdf` = CSV only. ⚠ Verify addresses in the CSV before a paid send — parse is heuristic. |
| `/geo funnel` | Prospecting funnel report from SQLite. `python3 ~/.claude/skills/geo/scripts/funnel_report.py [--campaign <tag>] [--json]`. Stage-by-stage counts + conversion (discovered → enriched → checked → contacted → walkthrough → Quick Check → Full Audit → retainer), check economics (spend, avg score, mention rate), outreach volume by channel, source split. `--campaign` matches the ad UTM/DB campaign tag. |
| `/geo dashboard` | Launch browser CRM at http://localhost:5050 |

---

## Market Context (Why GEO Matters)

| Metric | Value | Source |
|--------|-------|--------|
| GEO services market (2025) | $850M-$886M | Yahoo Finance / Superlines |
| Projected GEO market (2031) | $7.3B (34% CAGR) | Industry analysts |
| AI-referred sessions growth | +527% (Jan-May 2025) | SparkToro |
| AI traffic conversion vs organic | 4.4x higher | Industry data |
| Google AI Overviews reach | 1.5B users/month, 200+ countries | Google |
| ChatGPT weekly active users | 900M+ | OpenAI |
| Perplexity monthly queries | 500M+ | Perplexity |
| Gartner: search traffic drop by 2028 | -50% | Gartner |
| Marketers investing in GEO | Only 23% | Industry surveys |
| Brand mentions vs backlinks for AI | 3x stronger correlation | Ahrefs (Dec 2025) |

---

## Orchestration Logic

### Full Audit (`/geo audit <url>`)

**Phase 1: Discovery (Sequential)**
1. Fetch homepage HTML (curl or WebFetch)
2. Detect business type (SaaS, Local, E-commerce, Publisher, Agency, Other)
3. Extract key pages from sitemap.xml or internal links (up to 50 pages)

**Phase 2: Parallel Analysis (Delegate to Subagents)**
Launch these 5 core subagents simultaneously:

| Subagent | File | Responsibility |
|----------|------|---------------|
| geo-ai-visibility | `agents/geo-ai-visibility.md` | GEO audit, citability, AI crawlers, llms.txt, brand mentions |
| geo-platform-analysis | `agents/geo-platform-analysis.md` | Platform-specific optimization (9 platforms: AIO, ChatGPT, Perplexity, Gemini, Copilot, Grok, DeepSeek, Meta AI, Mistral) |
| geo-technical | `agents/geo-technical.md` | Technical SEO, Core Web Vitals, crawlability, indexability |
| geo-content | `agents/geo-content.md` | Content quality, E-E-A-T, readability, AI content detection |
| geo-schema | `agents/geo-schema.md` | Schema markup detection, validation, generation |

**Optional 6th subagent** (runs in parallel if AI API keys are configured):

| Subagent | File | Responsibility |
|----------|------|---------------|
| geo-live-visibility | `agents/geo-live-visibility.md` | Live AI brand visibility queries (requires OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.) |

If no AI provider API keys are configured, skip this subagent entirely. Never fabricate live visibility results.

**Phase 3: Synthesis (Sequential)**
1. Collect all subagent reports
2. Calculate composite GEO Score (0-100)
3. Generate prioritized action plan
4. Output client-ready report

### Scoring Methodology

| Category | Weight | Measured By |
|----------|--------|-------------|
| AI Citability & Visibility | 25% | Passage scoring, answer block quality, AI crawler access |
| Brand Authority Signals | 20% | Mentions on Reddit, YouTube, Wikipedia, LinkedIn; entity presence |
| Content Quality & E-E-A-T | 20% | Expertise signals, original data, author credentials |
| Technical Foundations | 15% | SSR, Core Web Vitals, crawlability, mobile, security |
| Structured Data | 10% | Schema completeness, JSON-LD validation, rich result eligibility |
| Platform Optimization | 10% | Platform-specific readiness (9 platforms: AIO, ChatGPT, Perplexity, Gemini, Copilot, Grok, DeepSeek, Meta AI, Mistral) |

---

## Business Type Detection

Analyze homepage for patterns:

| Type | Signals |
|------|---------|
| **SaaS** | Pricing page, "Sign up", "Free trial", "/app", "/dashboard", API docs |
| **Local Service** | Phone number, address, "Near me", Google Maps embed, service area |
| **E-commerce** | Product pages, cart, "Add to cart", price elements, product schema |
| **Publisher** | Blog, articles, bylines, publication dates, article schema |
| **Agency** | Portfolio, case studies, "Our services", client logos, testimonials |
| **Other** | Default — apply general GEO best practices |

Adjust recommendations based on detected type. Local businesses need LocalBusiness schema and Google Business Profile optimization. SaaS needs SoftwareApplication schema and comparison page strategy. E-commerce needs Product schema and review aggregation.

---

## Sub-Skills (16 Specialized Components)

| # | Skill | Directory | Purpose |
|---|-------|-----------|---------|
| 1 | geo-audit | `skills/geo-audit/` | Full audit orchestration and scoring |
| 2 | geo-citability | `skills/geo-citability/` | Passage-level AI citation readiness |
| 3 | geo-crawlers | `skills/geo-crawlers/` | AI crawler access and robots.txt |
| 4 | geo-llmstxt | `skills/geo-llmstxt/` | llms.txt standard analysis and generation |
| 5 | geo-brand-mentions | `skills/geo-brand-mentions/` | Brand presence on AI-cited platforms |
| 6 | geo-platform-optimizer | `skills/geo-platform-optimizer/` | Platform-specific AI search optimization |
| 7 | geo-schema | `skills/geo-schema/` | Structured data for AI discoverability |
| 8 | geo-technical | `skills/geo-technical/` | Technical SEO foundations |
| 9 | geo-content | `skills/geo-content/` | Content quality and E-E-A-T |
| 10 | geo-report | `skills/geo-report/` | Client-ready deliverable generation |
| 11 | geo-report-pdf | `skills/geo-report-pdf/` | Neo brutalist HTML + Playwright PDF report |
| 12 | geo-compare | `skills/geo-compare/` | Monthly delta tracking and progress reports |
| 13 | geo-proposal | `skills/geo-proposal/` | Auto-generate client service proposals |
| 14 | geo-live-visibility | `skills/geo-live-visibility/` | Live AI brand visibility testing |
| 15 | geo-prospect | `skills/geo-prospect/` | Lite prospect deliverable for cold outreach |
| 16 | geo-dashboard | `skills/geo-dashboard/` | Launch the Flask web dashboard / CRM |
| 17 | geo-browser-render | `skills/geo-browser-render/` | Headless-Chromium audit on critical pages (cookie wall, SSR gap, CWV, cloaking, screenshots) |
| 18 | geo-prospecting | `skills/geo-prospecting/` | SERP-driven prospect discovery → lite audit → pitchability score → outreach copy (UK + US) |

---

## Subagents (5 Core + 1 Optional)

| Agent | File | Skills Used |
|-------|------|-------------|
| geo-ai-visibility | `agents/geo-ai-visibility.md` | geo-citability, geo-crawlers, geo-llmstxt, geo-brand-mentions |
| geo-platform-analysis | `agents/geo-platform-analysis.md` | geo-platform-optimizer |
| geo-technical | `agents/geo-technical.md` | geo-technical, geo-browser-render |
| geo-content | `agents/geo-content.md` | geo-content |
| geo-schema | `agents/geo-schema.md` | geo-schema |
| geo-live-visibility *(optional)* | `agents/geo-live-visibility.md` | geo-live-visibility (requires AI API keys) |
| geo-prospecting | `agents/geo-prospecting.md` | geo-prospecting (SERP discovery → batch audit → pitchability → outreach) |

---

## Output Files

All commands generate structured output:

| Command | Output File |
|---------|------------|
| `/geo audit` | `GEO-AUDIT-REPORT.md` |
| `/geo page` | `GEO-PAGE-ANALYSIS.md` |
| `/geo citability` | `GEO-CITABILITY-SCORE.md` |
| `/geo crawlers` | `GEO-CRAWLER-ACCESS.md` |
| `/geo llmstxt` | `llms.txt` (ready to deploy) |
| `/geo brands` | `GEO-BRAND-MENTIONS.md` |
| `/geo platforms` | `GEO-PLATFORM-OPTIMIZATION.md` |
| `/geo schema` | `GEO-SCHEMA-REPORT.md` + generated JSON-LD |
| `/geo technical` | `GEO-TECHNICAL-AUDIT.md` |
| `/geo content` | `GEO-CONTENT-ANALYSIS.md` |
| `/geo report` | `GEO-CLIENT-REPORT.md` (presentation-ready) |
| `/geo report-pdf` | `GEO-REPORT.pdf` (professional PDF with charts) |
| `/geo compare` | `GEO-COMPARE-<domain>-<YYYY-MM>.md` |
| `/geo proposal` | `GEO-PROPOSAL-<domain>.md` |
| `/geo live` | `live-visibility.json` + inline report section |
| `/geo quick` | Inline summary (no file) |
| `/geo prospecting` | `prospects/<run_id>/` — `prospects.csv`, `audited.csv`, `scored.csv`, `outreach.csv`, `reports/*.html`, `summary.md` |

---

## PDF Report Generation

The `/geo report-pdf <url>` command generates a professional, branded PDF report:

### How It Works
1. Run the full audit or individual analyses first
2. Collect all scores and findings into a JSON structure
3. Execute the PDF generator: `python3 ~/.claude/skills/geo/scripts/generate_pdf_report.py data.json GEO-REPORT.pdf`

### What the PDF Includes
- **Cover page** with GEO score gauge visualization
- **Score breakdown** with color-coded bar charts
- **AI Platform Readiness** dashboard with horizontal bar chart
- **Crawler Access** status table with color-coded Allow/Block
- **Key Findings** categorized by severity (Critical/High/Medium/Low)
- **Prioritized Action Plan** (Quick Wins, Medium-Term, Strategic)
- **Methodology & Glossary** appendix

### Workflow
1. First run `/geo audit <url>` to collect all data
2. Then run `/geo report-pdf <url>` to generate the PDF
3. The tool will compile audit data into JSON, then generate the PDF
4. Output: `GEO-REPORT.pdf` in the current directory

---

## Quality Gates

- **Crawl limit:** Max 50 pages per audit (focus on quality over quantity)
- **Timeout:** 30 seconds per page fetch
- **Rate limiting:** 1-second delay between requests, max 5 concurrent
- **Robots.txt:** Always respect, always check
- **Duplicate detection:** Skip pages with >80% content similarity

---

## Quick Start Examples

```
# Full GEO audit of a website
/geo audit https://example.com

# Check if AI bots can see your site
/geo crawlers https://example.com

# Score a specific page for AI citability
/geo citability https://example.com/blog/best-article

# Generate an llms.txt file for your site
/geo llmstxt https://example.com

# Get a 60-second visibility snapshot
/geo quick https://example.com

# Generate a client-ready report
/geo report https://example.com
```
