# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

**GEO SLAB** by Antek Automation — a Claude Code skill system for Generative Engine Optimization (GEO). Optimizes websites for 9 AI-powered search engines (ChatGPT, Claude, Perplexity, Gemini, Google AI Overviews, Grok, DeepSeek, Meta AI, Mistral). Installs as skills, subagents, and Python utilities into `~/.claude/`.

**Product name:** GEO SLAB
**Owner:** Antek Automation (antekautomation.com)
**Brand:** All reports, footers, and client deliverables use "GEO SLAB by Antek Automation" branding. Neo brutalist design language throughout.

## Installation & Setup

```bash
# Install from local clone
./install.sh

# Install Python dependencies manually
pip install -r requirements.txt

# Optional: Playwright for screenshots
python3 -m playwright install chromium

# Uninstall
./uninstall.sh
```

`install.sh` copies skills → `~/.claude/skills/`, agents → `~/.claude/agents/`, scripts → `~/.claude/skills/geo/scripts/`, and schema templates → `~/.claude/skills/geo/schema/`.

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

```bash
# Brand scanning — SerpAPI for live Google search results across all platforms
export SERPAPI_API_KEY="your-key"       # https://serpapi.com (free: 100 searches/month)

# Brand scanning — Google Places API for GBP data (rating, reviews, categories)
export GOOGLE_PLACES_API_KEY="your-key" # https://console.cloud.google.com (enable Places API)

# Live AI visibility testing (install providers you want to query)
pip install openai anthropic google-generativeai
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_GENERATIVE_AI_API_KEY="..."
export PERPLEXITY_API_KEY="pplx-..."

# Firecrawl for JS-heavy site scraping
pip install firecrawl-py
export FIRECRAWL_API_KEY="fc-..."
```

All API keys are optional — the toolkit works without them using manual check instructions and URL generation. Each key adds progressively richer live data.

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
| Sub-skills (13) | `skills/geo-*/SKILL.md` | Specialized analysis components invoked by skill or agent |
| Subagents (5+1) | `agents/geo-*.md` | Parallel workers that bundle related sub-skills |

### Subagent → Sub-skill Mapping

| Agent | Sub-skills Used |
|-------|----------------|
| `geo-ai-visibility.md` | geo-citability, geo-crawlers, geo-llmstxt, geo-brand-mentions |
| `geo-platform-analysis.md` | geo-platform-optimizer |
| `geo-technical.md` | geo-technical |
| `geo-content.md` | geo-content |
| `geo-schema.md` | geo-schema |
| `geo-live-visibility.md` *(optional)* | geo-live-visibility (requires AI API keys) |

### Python Utilities

All scripts in `scripts/` are standalone utilities the skills call via `Bash`:
- `fetch_page.py` — HTTP fetching and HTML parsing (supports optional Firecrawl for JS-heavy sites)
- `citability_scorer.py` — Passage-level AI citation readiness scoring
- `brand_scanner.py` — Brand mention detection across platforms
- `llmstxt_generator.py` — llms.txt validation and generation
- `render_geo_report.py` — Neo brutalist HTML report generator (JSON → HTML); canonical template
- `generate_pdf_report.py` — Playwright PDF printer; imports `render_geo_report.py` then prints via headless Chromium
- `generate_prospect_report.py` — Lite/prospect HTML report; `--pdf` flag adds Playwright PDF output
- `live_ai_query.py` — Live AI visibility querying; queries ChatGPT, Claude, Gemini, Perplexity APIs directly

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
| `/geo report-pdf <url>` | `reports/<domain>/GEO-REPORT-<domain>.html` + `.pdf` |
| `/geo schema` | `reports/<domain>/GEO-SCHEMA-REPORT.md` + JSON-LD |
| `/geo llmstxt` | `reports/<domain>/llms.txt` |
| `/geo compare <domain>` | `reports/<domain>/GEO-COMPARE-<domain>-<YYYY-MM>.md` |
| `/geo proposal <domain>` | `reports/<domain>/GEO-PROPOSAL-<domain>.md` |
| `/geo live <url>` | `reports/<domain>/live-visibility.json` |
| Prospect/lite report | `reports/<domain>/GEO-PROSPECT-<domain>.html` + `.pdf` |

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

## Adding a New Sub-Skill

1. Create `skills/geo-<name>/SKILL.md` with YAML frontmatter (`name`, `description`, `allowed-tools`)
2. Reference it in `geo/SKILL.md` command table and sub-skills list
3. If it should run during full audits, add it to the relevant agent in `agents/`
4. `install.sh` auto-discovers any `skills/*/` directory — no install script changes needed
