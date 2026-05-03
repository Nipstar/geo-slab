# Architecture

How GEO SLAB is wired together.

## Overview

GEO SLAB installs into Claude Code as a system of **skills**, **agents**, and **Python scripts** rooted in `~/.claude/`. The user invokes commands via `/geo <command>`; the orchestrator skill at `geo/SKILL.md` routes the request to one or more sub-skills, optionally fanning out to parallel subagents for full audits.

```
User → /geo <cmd>
       │
       ▼
   geo/SKILL.md   (orchestrator, routing logic)
       │
       ├── direct-call sub-skill (e.g. /geo report, /geo proposal)
       │
       └── parallel subagent fan-out (e.g. /geo audit)
              │
              ├── geo-ai-visibility    (citability + crawlers + llms.txt + brands)
              ├── geo-platform-analysis (9-platform readiness)
              ├── geo-technical        (Core Web Vitals, SSR, security)
              ├── geo-content          (E-E-A-T, readability)
              ├── geo-schema           (JSON-LD detection + generation)
              └── geo-live-visibility  (optional — needs AI API keys)
                     │
                     ▼
              Each agent invokes its bundled sub-skill(s) and
              calls Python utilities in scripts/ for HTTP fetch,
              passage scoring, brand mention scanning, etc.
```

## Skill orchestration model

Two roles for sub-skills:

- **Parallel-audit skills** — invoked via subagents during `/geo audit`. Run concurrently to cut wall time. These produce structured findings the orchestrator merges. Members: `geo-citability`, `geo-crawlers`, `geo-llmstxt`, `geo-brand-mentions`, `geo-platform-optimizer`, `geo-technical`, `geo-content`, `geo-schema`, `geo-live-visibility`.
- **Direct-call skills** — invoked from `geo/SKILL.md` without a subagent. Sequential, single-purpose. Members: `geo-audit` (orchestrator), `geo-report`, `geo-report-pdf`, `geo-compare`, `geo-proposal`, `geo-prospect`, `geo-dashboard`.

## Full audit flow (`/geo audit <url>`)

1. **Discovery (sequential)**
   - Fetch homepage HTML via `scripts/fetch_page.py` (Firecrawl auto-switch when `FIRECRAWL_API_KEY` set)
   - Detect business type (SaaS, Local, E-commerce, Publisher, Agency, Other) from on-page signals
   - Crawl up to 50 key pages from sitemap.xml or internal links
2. **Parallel analysis** — launch 5 core agents simultaneously via Task tool. Optional 6th `geo-live-visibility` joins fan-out if AI provider keys are configured.
3. **Synthesis (sequential)**
   - Collect agent reports
   - Compute composite GEO Score (formula in [scoring-methodology.md](scoring-methodology.md))
   - Build prioritized action plan: Quick Wins, Medium-Term, Strategic
   - Render output to `reports/<domain>/GEO-AUDIT-REPORT.md`

## Quick audit flow (`/geo quick <url>`)

Skips parallel fan-out. Single-pass page fetch + 60-second snapshot of crawlers, citability, brand presence. Console-only output (no file).

## Live visibility flow (`/geo live <url>`)

`scripts/live_ai_query.py` directly queries ChatGPT, Claude, Gemini, Perplexity APIs with brand-relevant prompts. Parses responses for:

- Direct brand mentions
- Competitor mentions (share of voice)
- Citation links pointing back to the site

Output: `reports/<domain>/live-visibility.json`. Requires at least one of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, `PERPLEXITY_API_KEY`.

## Data storage convention

All generated artifacts live under `reports/<domain>/`. Never the repo root.

```
reports/
  example.com/
    GEO-AUDIT-REPORT.md
    audit-data.json                  ← machine-readable, drives report renderers
    GEO-REPORT-example.com.html      ← neo brutalist HTML, self-contained
    GEO-REPORT-example.com.pdf       ← Playwright print of the HTML
    live-visibility.json             ← only if /geo live ran
    GEO-PROPOSAL-example.com.md      ← only if /geo proposal ran
    GEO-COMPARE-example.com-2026-04.md
    GEO-PROSPECT-example.com.html    ← lite prospect deliverable
    GEO-PROSPECT-example.com.pdf
```

`audit-data.json` is the canonical source. All renderers (HTML report, PDF, prospect lite, comparison) consume it.

## Webapp architecture

`webapp/` is a Flask + HTMX dashboard for prospect/CRM workflow. Independent of the Claude Code skill layer — runs as a long-lived local server.

- **Persistence**: `~/.geo-slab/prospects.json` (single JSON file, stdlib only)
- **Artifact source**: `reports/<domain>/` (treated read-only — webapp does not regenerate audits)
- **Auto-discovery**: `find_artefacts(domain)` scans the reports directory and exposes audit JSON, HTML report, PDF, proposal markdown via dashboard routes
- **Stack**: Flask 3.x, Jinja2, HTMX (CDN), `markdown` (proposal rendering). Vanilla CSS, no framework.

Run via `cd webapp && python app.py` → http://localhost:5050.

## File layout

```
.
├── geo/SKILL.md                # orchestrator, command routing
├── skills/                     # 16 sub-skills (15 GEO + geo-dashboard)
│   ├── geo-audit/
│   ├── geo-citability/
│   ├── geo-crawlers/
│   ├── geo-llmstxt/
│   ├── geo-brand-mentions/
│   ├── geo-platform-optimizer/
│   ├── geo-schema/
│   ├── geo-technical/
│   ├── geo-content/
│   ├── geo-report/
│   ├── geo-report-pdf/
│   ├── geo-compare/
│   ├── geo-proposal/
│   ├── geo-live-visibility/
│   ├── geo-prospect/
│   └── geo-dashboard/
├── agents/                     # 5 core + 1 optional parallel agents
├── scripts/                    # 8 standalone Python utilities
├── schema/                     # 6 JSON-LD templates
├── webapp/                     # Flask dashboard
├── docs/                       # this folder
├── examples/                   # sample audit JSON, HTML, PDF
├── reports/                    # generated client artifacts (gitignored)
├── install.sh / uninstall.sh   # symlink skills/agents into ~/.claude/
└── requirements.txt            # main Python deps
```

## Install model

`install.sh` symlinks (or copies, depending on flag) directories into `~/.claude/`:

| Source | Destination |
|--------|-------------|
| `skills/` | `~/.claude/skills/` |
| `agents/` | `~/.claude/agents/` |
| `scripts/` | `~/.claude/skills/geo/scripts/` |
| `schema/` | `~/.claude/skills/geo/schema/` |

`webapp/` is intentionally **not** installed — it is a runtime tool, not a skill.
