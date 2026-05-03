# Commands Reference

Every `/geo` slash command, with usage, args, output paths, and examples.

## Categories

- **Audit & analysis** — `/geo audit`, `/geo quick`, `/geo page`, `/geo citability`, `/geo crawlers`, `/geo llmstxt`, `/geo brands`, `/geo platforms`, `/geo schema`, `/geo technical`, `/geo content`, `/geo live`
- **Reporting** — `/geo report`, `/geo report-pdf`, `/geo prospect`
- **Client lifecycle** — `/geo proposal`, `/geo compare`
- **Workflow** — `/geo dashboard`

All commands accept a URL or domain. Outputs land under `reports/<domain>/` (never the repo root) unless noted.

---

## /geo audit

Full GEO + SEO audit with parallel subagent fan-out.

| Property | Value |
|----------|-------|
| Args | `<url>` |
| Output | `reports/<domain>/GEO-AUDIT-REPORT.md` + `audit-data.json` |
| Runtime | ~3–6 min (depends on site size, parallel agent count, API keys) |

```
/geo audit https://example.com
```

Phases: Discovery → 5–6 parallel agents → Synthesis → composite GEO Score (0–100) + prioritized action plan.

---

## /geo quick

60-second visibility snapshot. Console only, no file.

| Property | Value |
|----------|-------|
| Args | `<url>` |
| Output | inline summary |

```
/geo quick https://example.com
```

Single-pass page fetch. Skips parallel fan-out. Quick triage.

---

## /geo page

Deep single-page GEO analysis (one URL, not whole site).

| Property | Value |
|----------|-------|
| Args | `<url>` |
| Output | `reports/<domain>/GEO-PAGE-ANALYSIS.md` |

```
/geo page https://example.com/blog/best-article
```

---

## /geo citability

Score content for AI citation readiness using `citability_scorer.py`.

| Property | Value |
|----------|-------|
| Args | `<url>` |
| Output | `reports/<domain>/GEO-CITABILITY-SCORE.md` |

```
/geo citability https://example.com/guide
```

Scores each passage (134–167 word optimal band) and suggests rewrites.

---

## /geo crawlers

Check AI crawler access via robots.txt analysis.

| Property | Value |
|----------|-------|
| Args | `<url>` |
| Output | `reports/<domain>/GEO-CRAWLER-ACCESS.md` |

```
/geo crawlers https://example.com
```

Checks 14+ AI bots (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, FacebookBot, Applebot-Extended, Bytespider, CCBot, Amazonbot, Diffbot, anthropic-ai, ChatGPT-User, OAI-SearchBot, Cohere-AI).

---

## /geo llmstxt

Analyze existing `llms.txt` or generate a new one.

| Property | Value |
|----------|-------|
| Args | `<url>` |
| Output | `reports/<domain>/llms.txt` (deploy-ready) |

```
/geo llmstxt https://example.com
```

---

## /geo brands

Scan brand mentions across AI-cited platforms.

| Property | Value |
|----------|-------|
| Args | `<url>` |
| Output | `reports/<domain>/GEO-BRANDS-<domain>.md` |
| Optional API keys | `SERPAPI_API_KEY`, `GOOGLE_PLACES_API_KEY` |

```
/geo brands https://example.com
```

Without API keys: pattern-match + manual-check URL generation. With keys: live SERP + GBP data.

---

## /geo platforms

Platform-specific optimization across 9 AI platforms.

| Property | Value |
|----------|-------|
| Args | `<url>` |
| Output | `reports/<domain>/GEO-PLATFORM-OPTIMIZATION.md` |

```
/geo platforms https://example.com
```

Per-platform readiness rubric: Google AI Overviews, ChatGPT, Perplexity, Gemini, Bing Copilot, Grok, DeepSeek, Meta AI, Mistral.

---

## /geo schema

Detect, validate, generate structured data.

| Property | Value |
|----------|-------|
| Args | `<url>` |
| Output | `reports/<domain>/GEO-SCHEMA-REPORT.md` + generated JSON-LD files |

```
/geo schema https://example.com
```

Generates ready-to-paste JSON-LD from templates in [`schema/`](../schema/) populated with page-specific data.

---

## /geo technical

Traditional technical SEO audit with GEO-relevant signals.

| Property | Value |
|----------|-------|
| Args | `<url>` |
| Output | `reports/<domain>/GEO-TECHNICAL-AUDIT.md` |

```
/geo technical https://example.com
```

Core Web Vitals (INP), SSR, robots.txt, sitemap, mobile, security.

---

## /geo content

Content quality + E-E-A-T assessment.

| Property | Value |
|----------|-------|
| Args | `<url>` |
| Output | `reports/<domain>/GEO-CONTENT-<domain>.md` |

```
/geo content https://example.com
```

Author signals, original-data detection, AI-content heuristics, readability.

---

## /geo report

Generate the client-ready Markdown deliverable.

| Property | Value |
|----------|-------|
| Args | `<url>` |
| Output | `reports/<domain>/GEO-REPORT-<domain>.md` |

```
/geo report https://example.com
```

Typically run after `/geo audit` so `audit-data.json` exists.

---

## /geo report-pdf

Generate professional HTML + PDF report. Neo brutalist palette, charts, gauges.

| Property | Value |
|----------|-------|
| Args | `<url>` |
| Output | `reports/<domain>/GEO-REPORT-<domain>.html` + `.pdf` |
| Requires | Playwright + Chromium installed |

```
/geo report-pdf https://example.com
```

Renders via `scripts/render_geo_report.py`, prints to PDF via `scripts/generate_pdf_report.py`.

---

## /geo prospect

Lite prospect deliverable — top problems only, no fixes, full-audit CTA.

| Property | Value |
|----------|-------|
| Args | `<url>` |
| Output | `reports/<domain>/GEO-PROSPECT-<domain>.html` + `.pdf` |

```
/geo prospect https://example.com
```

For cold outreach. Generates a teaser report that motivates the prospect to engage for the full audit.

---

## /geo proposal

Auto-generate a tiered service proposal from audit data.

| Property | Value |
|----------|-------|
| Args | `<domain>` |
| Output | `reports/<domain>/GEO-PROPOSAL-<domain>.md` |
| Requires | existing `audit-data.json` for the domain |

```
/geo proposal example.com
```

Pricing scales by score tier (Critical → higher monthly retainer; Good → maintenance package).

---

## /geo compare

Monthly delta tracking — compare two audits over time.

| Property | Value |
|----------|-------|
| Args | `<domain>` |
| Output | `reports/<domain>/GEO-COMPARE-<domain>-<YYYY-MM>.md` |
| Requires | at least 2 dated `audit-data.json` snapshots |

```
/geo compare example.com
```

Highlights category movements, frames progress narrative for client check-ins.

---

## /geo live

Live AI visibility test — query ChatGPT, Claude, Gemini, Perplexity APIs directly.

| Property | Value |
|----------|-------|
| Args | `<url>` |
| Output | `reports/<domain>/live-visibility.json` |
| Requires | at least one of: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, `PERPLEXITY_API_KEY` |

```
/geo live https://example.com
```

Measures real-time brand visibility. Discovers competitor share-of-voice. Never fabricates results when keys are missing.

---

## /geo dashboard

Launch the Flask web dashboard for prospect / CRM workflow.

| Property | Value |
|----------|-------|
| Args | none |
| Output | http://localhost:5050 |
| Requires | `cd webapp && pip install -r requirements-webapp.txt` first |

```
/geo dashboard
```

Returns instructions for starting the webapp. Dashboard reads from `~/.geo-slab/prospects.json` and auto-discovers artifacts in `reports/<domain>/`.
