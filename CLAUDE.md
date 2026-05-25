# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

**GEO SLAB** by Antek Automation — a Claude Code skill system for Generative Engine Optimization (GEO). Optimizes websites for 9 AI-powered search engines (ChatGPT, Claude, Perplexity, Gemini, Google AI Overviews, Grok, DeepSeek, Meta AI, Mistral). Installs as skills, subagents, and Python utilities into `~/.claude/`.

**Product name:** GEO SLAB
**Owner:** Antek Automation (antekautomation.com)
**Brand:** All reports, footers, and client deliverables use "GEO SLAB by Antek Automation" branding. Neo brutalist design language throughout.

## Installation & Setup

```bash
# Install from local clone (auto-installs Playwright Chromium — required for full audit)
./install.sh

# Install Python dependencies manually
pip install -r requirements.txt

# Required: Playwright Chromium for /geo audit browser render phase
python3 -m playwright install chromium

# Uninstall
./uninstall.sh
```

Playwright is **required**, not optional — `/geo audit` runs `browser_render_audit.py` against up to 5 critical pages for SSR-gap detection, CWV measurement, cloaking checks, and screenshots. The full audit fails the browser-render step without it.

`install.sh` copies skills → `~/.claude/skills/`, agents → `~/.claude/agents/`, scripts → `~/.claude/skills/geo/scripts/`, schema templates → `~/.claude/skills/geo/schema/`, and any `hooks/` → `~/.claude/skills/geo/hooks/` (chmod +x).

The Flask dashboard in `webapp/` is **not** installed by `install.sh` — it runs in place from the repo. See [Web Dashboard](#web-dashboard) below.

## Running the Python Scripts Directly

Scripts expect to be run from `~/.claude/skills/geo/scripts/` after install, but can be tested from `scripts/` in this repo:

```bash
python3 scripts/fetch_page.py <url>
python3 scripts/citability_scorer.py <url>
python3 scripts/brand_scanner.py <domain>
python3 scripts/llmstxt_generator.py <url>
python3 scripts/generate_pdf_report.py data.json GEO-REPORT.pdf
python3 scripts/live_ai_query.py --company-name "Brand" --url "https://..." --industry "tech"
```

### Optional API Keys for Enhanced Features

All keys optional. Toolkit degrades gracefully — each key unlocks richer live data. Export to `~/.zshrc` or drop into `.env.local` at repo root (auto-loaded via `python-dotenv`).

```bash
# PageSpeed Insights — Lighthouse scores + real-user Core Web Vitals (CrUX field data)
# Wired into geo-technical audit. Free tier: 25k req/day, 240/min.
export PSI_API_KEY="..."                # https://console.cloud.google.com (enable PageSpeed Insights API)

# Brand scanning — SerpAPI for live Google search results across all platforms
export SERPAPI_API_KEY="..."            # https://serpapi.com (free: 100 searches/month)

# Brand scanning — Google Places API for GBP data (rating, reviews, categories)
export GOOGLE_PLACES_API_KEY="..."      # https://console.cloud.google.com (enable Places API New)

# Firecrawl for JS-heavy site scraping
pip install firecrawl-py
export FIRECRAWL_API_KEY="fc-..."

# Live AI visibility — OpenRouter (one key, 7 providers, no SDK install needed)
export OPENROUTER_API_KEY="sk-or-..."   # https://openrouter.ai/keys

# Live AI visibility — native provider SDKs (override OpenRouter when set)
pip install openai anthropic google-generativeai
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_GENERATIVE_AI_API_KEY="..."
export PERPLEXITY_API_KEY="pplx-..."    # no OpenRouter fallback — only native
```

**Live-AI provider priority** (live_ai_query.py): native key > OpenRouter > skipped.

## Architecture

### Execution Flow

User invokes `/geo <command> <url>` → `geo/SKILL.md` routes the command → delegates to sub-skills in `skills/` and/or subagents in `agents/`.

For `/geo audit`, the orchestration is:
1. **Discovery** (sequential) — fetch homepage, detect business type, crawl up to 50 pages
2. **Parallel analysis** — 5 subagents run simultaneously, each using one or more sub-skills
3. **Synthesis** — composite GEO Score (0-100) calculated, `GEO-AUDIT-REPORT.md` written

### Three-Layer Structure

| Layer | Location | Purpose |
|-------|----------|---------|
| Main skill | `geo/SKILL.md` | Entry point, command routing, orchestration logic |
| Sub-skills (17) | `skills/geo-*/SKILL.md` | Specialized analysis components invoked by skill or agent |
| Subagents (5+1) | `agents/geo-*.md` | Parallel workers that bundle related sub-skills |

Sub-skills split into three roles:
- **Parallel-audit skills** (run via subagents during `/geo audit`): geo-citability, geo-crawlers, geo-llmstxt, geo-brand-mentions, geo-platform-optimizer, geo-technical, geo-content, geo-schema, geo-live-visibility, geo-browser-render.
- **Direct-call skills** (invoked from `geo/SKILL.md`, no subagent): geo-audit (orchestrator), geo-report, geo-report-pdf, geo-compare, geo-proposal, geo-prospect.
- **Launcher skill**: geo-dashboard — boots the Flask webapp (`webapp/app.py`) on port 5050.

### Subagent → Sub-skill Mapping

| Agent | Sub-skills Used |
|-------|----------------|
| `geo-ai-visibility.md` | geo-citability, geo-crawlers, geo-llmstxt, geo-brand-mentions |
| `geo-platform-analysis.md` | geo-platform-optimizer |
| `geo-technical.md` | geo-technical, geo-browser-render |
| `geo-content.md` | geo-content |
| `geo-schema.md` | geo-schema |
| `geo-live-visibility.md` *(optional)* | geo-live-visibility (requires AI API keys) |

### Python Utilities

All scripts in `scripts/` are standalone utilities the skills call via `Bash`:
- `fetch_page.py` — HTTP fetching and HTML parsing. Auto-switches to Firecrawl when `FIRECRAWL_API_KEY` set (full JS rendering); falls back to `requests` + BeautifulSoup otherwise.
- `citability_scorer.py` — Passage-level AI citation readiness scoring
- `brand_scanner.py` — Brand mention detection across platforms
- `llmstxt_generator.py` — llms.txt validation and generation
- `render_geo_report.py` — Neo brutalist HTML report generator (JSON → HTML); canonical template
- `generate_pdf_report.py` — Playwright PDF printer; imports `render_geo_report.py` then prints via headless Chromium
- `browser_render_audit.py` — Headless-Chromium audit: cookie wall, SSR gap, CWV, UA-differential cloaking, desktop+mobile screenshots. Python 3.9+ required (`from __future__ import annotations`). Cap of 5 URLs enforced.
- `generate_prospect_report.py` — Lite/prospect HTML report; `--pdf` flag adds Playwright PDF output
- `live_ai_query.py` — Live AI visibility querying; queries ChatGPT, Claude, Gemini, Perplexity APIs directly (or via OpenRouter fallback)
- `pagespeed.py` — PageSpeed Insights client. Runs mobile + desktop in parallel, parses Lighthouse scores + CWV (CrUX field data preferred, lab fallback), extracts top opportunities. 24h on-disk cache at `~/.geo-slab/cache/psi/`. Called by `geo-technical` agent.

**Prospecting pipeline scripts** (⚠️ experimental — see "Prospecting (Experimental)" below):
- `bootstrap_keywords.py` — LLM-generated keyword seeds from a vertical + location.
- `discover_prospects.py` — SerpAPI driver: pulls positions 9–13 across keyword list, optional Google Places enrichment.
- `batch_audit.py` — Parallel lite-audit runner over a prospects CSV.
- `score_prospects.py` — Pitchability scoring (GEO gap × business signal × contactability).
- `generate_outreach.py` — LLM-drafted email + LinkedIn + voice opener per prospect.
- `render_proposal.py` — HTML proposal renderer for prospects.
- `find_decision_makers.py` — **Experimental.** Scrapes public team pages (static + Playwright fallback) for partners/directors/heads. Extracts JSON-LD `Person`, decodes Cloudflare email tokens, falls back to Google search URLs for LinkedIn. Misses non-standard team-page structures.

### Schema Templates

`schema/` contains ready-to-deploy JSON-LD templates: `organization.json`, `local-business.json`, `article-author.json`, `software-saas.json`, `product-ecommerce.json`, `website-searchaction.json`. Skills inject these as starting points for client recommendations.

## Output Files Convention

All generated reports (HTML, PDF, Markdown) go into `reports/<domain>/` — **never the repo root**. This keeps the working directory tidy.

```
reports/
  warnergoodman.co.uk/
    GEO-AUDIT-REPORT.md
    GEO-REPORT-warnergoodman.co.uk.html
    GEO-REPORT-warnergoodman.co.uk.pdf
  antekautomation.com/
    GEO-PROSPECT-antekautomation.com.html
    GEO-PROSPECT-antekautomation.com.pdf
```

| Command | Output |
|---------|--------|
| `/geo audit <url>` | `reports/<domain>/GEO-AUDIT-REPORT.md` |
| `/geo quick <url>` | 60-second snapshot, console only (no file) |
| `/geo report <url>` | `reports/<domain>/GEO-REPORT-<domain>.md` |
| `/geo report-pdf <url>` | `reports/<domain>/GEO-REPORT-<domain>.html` + `.pdf` |
| `/geo schema` | `reports/<domain>/GEO-SCHEMA-REPORT.md` + JSON-LD |
| `/geo llmstxt` | `reports/<domain>/llms.txt` |
| `/geo brands <url>` | `reports/<domain>/GEO-BRANDS-<domain>.md` |
| `/geo content <url>` | `reports/<domain>/GEO-CONTENT-<domain>.md` |
| `/geo compare <domain>` | `reports/<domain>/GEO-COMPARE-<domain>-<YYYY-MM>.md` |
| `/geo proposal <domain>` | `reports/<domain>/GEO-PROPOSAL-<domain>.md` |
| `/geo live <url>` | `reports/<domain>/live-visibility.json` |
| `/geo prospect <url>` (lite) | `reports/<domain>/GEO-PROSPECT-<domain>.html` + `.pdf` |
| `/geo prospecting <kw_file> <loc>` ⚠️ experimental | `prospects/<run_id>/{prospects,audited,scored,outreach,contacts}.csv` + `reports/*.html` + `summary.md` |
| `/geo dashboard` | Launches Flask webapp on `http://localhost:5050` (no file output) |

Always pass the output path explicitly to the report scripts:
```bash
python3 scripts/render_geo_report.py data.json reports/<domain>/GEO-REPORT-<domain>.html
python3 scripts/generate_pdf_report.py data.json reports/<domain>/GEO-REPORT-<domain>.pdf
python3 scripts/generate_prospect_report.py --data data.json --output reports/<domain>/ --pdf
```

## GEO Score Formula

```
GEO_Score = (Citability × 0.25) + (Brand × 0.20) + (EEAT × 0.20) + (Technical × 0.15) + (Schema × 0.10) + (Platform × 0.10)
```

## Scoring Heuristics (when tuning)

- **Citability passages**: optimal 134–167 words, self-contained, fact-rich, directly answer question. `citability_scorer.py` thresholds tuned around this band — change with care.
- **AI crawlers checked**: `geo-crawlers` / `fetch_page.py` parse robots.txt for 14+ bots — GPTBot, ClaudeBot, PerplexityBot, Google-Extended, FacebookBot, Applebot-Extended, Bytespider, CCBot, etc. Add new bots to crawler list when vendors publish UAs.
- **Prospect (lite) flow**: `/geo prospect` → `geo-prospect` skill → `generate_prospect_report.py --pdf`. Distinct from `/geo audit` — lighter data, top-of-funnel client deliverable, no parallel subagents.

## Web Dashboard

Browser CRM for prospect management + audit-artifact viewing. Vanilla **Flask + HTMX**, neo brutalist palette to match the report PDFs.

```bash
cd webapp && pip install -r requirements-webapp.txt && python app.py
# → http://localhost:5050
```

- Entry: `webapp/app.py` (templates in `webapp/templates/`, CSS in `webapp/static/css/slab.css`)
- Auto-discovers existing audit artifacts under `reports/<domain>/`
- Persists prospects to `~/.geo-slab/prospects.json` (lives outside the repo)
- Separate deps file: `webapp/requirements-webapp.txt` (not in root `requirements.txt`)
- Slash-command entrypoint: `/geo dashboard` (handled by `geo-dashboard` skill)

## Voice + STYLE.md (mandatory for any client-facing output)

`STYLE.md` at repo root is the single source of truth for the voice of every client-facing report. Score-band copy, sub-score descriptions, issue translations, good-news items, banned filler words, and £-impact-by-sector templates all live there. The structured-data companion is `scripts/style.py` — both files must stay in sync.

**Hard rule:** before generating any sentence a prospect or client will read (lite prospect report, full audit PDF, proposal, monthly delta, audit synthesis), open `STYLE.md`. Apply the issue translations, score bands, and tone rules. Grep for banned words and US spellings before shipping. A report that surfaces raw technical jargon (`llms.txt`, `JSON-LD`, `robots.txt`, `E-E-A-T`, `schema.org`, `GEO`) without the plain-English wrapper is not ready.

Each report skill (`geo-report`, `geo-report-pdf`, `geo-proposal`, `geo-compare`, `geo-audit`) carries a mandatory STYLE.md read in its frontmatter.

## Reference Docs (deeper than this file)

`docs/` holds the long-form technical reference — read these instead of grepping the codebase when a topic is broad:

- `docs/architecture.md` — system design, audit flow, parallel-agent orchestration
- `docs/scoring-methodology.md` — composite GEO Score formula, per-category weightings
- `docs/skills-and-agents.md` — full inventory of skills, agents, scripts, schemas
- `docs/commands-reference.md` — every `/geo` slash command

`examples/` contains sample audit JSON + finished HTML/PDF deliverables — use as fixtures when iterating on `render_geo_report.py` or `generate_pdf_report.py`.

## Prospecting (Experimental)

`/geo prospecting` builds an outbound list rather than auditing a single known URL. Lives in `skills/geo-prospecting/` + `agents/geo-prospecting.md`. Scripts:

```
bootstrap_keywords → discover_prospects → batch_audit → score_prospects
                                                       ↓
                                          generate_outreach + find_decision_makers
```

**Status:** discovery + audit + scoring are stable. Outreach generation is workable but unpolished. Decision-maker scraping (`find_decision_makers.py`) works for standard team-page structures (heading + photo + title) but **misses non-standard layouts** — Cloudflare-obfuscated emails are decoded, but JS-only people directories, category-card pages (e.g. Duncan Lewis), and span/div layouts without recognisable card classes return zero. Email pattern detection only fires when a published `@firm.tld` mailto exists somewhere on a scraped page; without one, no emails are generated.

Use as a first-pass list builder. Expect to:
1. Manually verify Google-search fallback URLs to pull real LinkedIn profiles.
2. Scrape `/contact/` pages by hand for any missing firms.
3. Fall back to paid enrichment (Blitz / Apollo / PredictLeads) for firms the scraper missed.

Outputs land in `prospects/<run_id>/` — not `reports/`. The `prospects/` directory is gitignored.

## Adding a New Sub-Skill

1. Create `skills/geo-<name>/SKILL.md` with YAML frontmatter (`name`, `description`, `allowed-tools`)
2. Reference it in `geo/SKILL.md` command table and sub-skills list
3. If it should run during full audits, add it to the relevant agent in `agents/`
4. `install.sh` auto-discovers any `skills/*/` directory — no install script changes needed
