---
name: geo-report-pdf
description: Generate a neo brutalist PDF report from GEO audit data using Playwright. Renders the HTML report via render_geo_report.py, then prints to PDF via headless Chromium — preserving all fonts, colours, and layout exactly.
version: 2.0.0
author: antek-automation
tags: [geo, pdf, report, client-deliverable, neo-brutalist]
---

# GEO PDF Report Generator

> **MANDATORY: Read `/STYLE.md` before generating any prose in the client PDF.**
>
> This skill emits TWO separate PDFs from the same audit data:
> - `GEO-REPORT-<domain>.pdf` — client-facing, plain English only (managing partner / owner / marketing director reads this). Pulls from `client_summary`.
> - `GEO-DEV-REPORT-<domain>.pdf` — developer / agency hand-off, technical instructions. Pulls from `technical_findings`.
>
> The audit data is identical for both — the agents emit two parallel layers and each renderer consumes its own field. The partner can forward the dev PDF without ever showing the client PDF to their developer, and vice versa.
>
> Never put raw technical terms (`llms.txt`, `JSON-LD`, `robots.txt`, `E-E-A-T`, `schema.org`, `LCP`, `HSTS`, `sameAs`, `Yoast`, etc.) in the client PDF. Run `scripts/voice_check.py` against the client PDF before delivery — any banned term fails the build. UK English throughout.

## Purpose

Generates a client-ready PDF from GEO audit data. The PDF is produced by:

1. Building the neo brutalist HTML via `render_geo_report.py`
2. Printing that HTML to PDF via Playwright headless Chromium

This means the PDF looks **identical** to the HTML report — Barlow Condensed headlines, IBM Plex Mono labels, cream/coral/sage/charcoal palette, 3px solid borders, 8px box shadows.

## Prerequisites

```bash
pip install playwright
playwright install chromium
```

Scripts are at `~/.claude/skills/geo/scripts/` after install, or at `scripts/` in the repo.

## JSON Input Schema

Both the full-audit (`render_geo_report.py`) and prospect (`generate_prospect_report.py`) scripts share the same approach. For the **full audit PDF**:

```json
{
    "url": "https://example.com",
    "brand_name": "Example Company",
    "date": "2026-04-08",
    "geo_score": 65,
    "scores": {
        "AI Citability": 62,
        "Brand Authority": 78,
        "Content E-E-A-T": 74,
        "Technical GEO": 72,
        "Schema": 45,
        "Platform Optimisation": 59
    },
    "platforms": {
        "Google AI Overviews": 68,
        "ChatGPT": 62,
        "Perplexity": 55,
        "Gemini": 60,
        "Bing Copilot": 50
    },
    "summary": ["Sentence 1 of executive summary.", "Sentence 2."],
    "findings": [
        {
            "severity": "CRITICAL",
            "title": "Finding Title",
            "description": "Description of the finding."
        }
    ],
    "quick_wins": [
        {"title": "Add llms.txt", "description": "Guide AI crawlers to key pages.", "time": "1 hour"},
        "Or plain string items also work"
    ],
    "medium_term": ["..."],
    "strategic": ["..."]
}
```

## Generate Full Audit PDFs (BOTH client + developer)

Every audit run must emit both PDFs. Always invoke the two generators in sequence and run the voice check against the client PDF.

```bash
# 1) Client PDF — plain English (pulls client_summary)
python3 ~/.claude/skills/geo/scripts/generate_pdf_report.py \
  reports/<domain>/data.json reports/<domain>/GEO-REPORT-<domain>.pdf

# 2) Developer PDF — technical hand-off (pulls technical_findings)
python3 ~/.claude/skills/geo/scripts/generate_dev_pdf_report.py \
  reports/<domain>/data.json reports/<domain>/GEO-DEV-REPORT-<domain>.pdf

# 3) Voice gate — fails if any banned tech term leaked into the client PDF
python3 ~/.claude/skills/geo/scripts/voice_check.py \
  reports/<domain>/GEO-REPORT-<domain>.pdf
```

If voice_check fails, fix the offending entry in the agent's `client_summary` output (translate via `scripts/style.py:ISSUE_COPY`) and re-render the client PDF only — the dev PDF doesn't need regeneration.

## Generate Prospect (Lite) PDF

```bash
# HTML only
python3 ~/.claude/skills/geo/scripts/generate_prospect_report.py --data prospect-data.json --output reports/example.com/

# HTML + PDF together
python3 ~/.claude/skills/geo/scripts/generate_prospect_report.py --data prospect-data.json --output reports/example.com/ --pdf
```

## Output Folder Convention

All reports (HTML and PDF) must be written to `reports/<domain>/` — **never to the repo root**. This keeps the working directory tidy.

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

Both scripts accept an `--output` / positional argument pointing to the output directory. Always pass `reports/<domain>/` as the output directory.

## Workflow for /geo-report-pdf

1. Check for existing audit data: look for `GEO-AUDIT-REPORT.md` or a `reports/<domain>/data.json`
2. If no audit data: tell user to run `/geo audit <url>` first
3. Parse the markdown report to extract scores, platforms, AND both layers — `client_summary` and `technical_findings`
4. Build the JSON structure (schema above) including both layers
5. Write JSON to `reports/<domain>/data.json`
6. Render both PDFs:
   ```bash
   # Client PDF
   python3 ~/.claude/skills/geo/scripts/render_geo_report.py \
     reports/<domain>/data.json reports/<domain>/GEO-REPORT-<domain>.html
   python3 ~/.claude/skills/geo/scripts/generate_pdf_report.py \
     reports/<domain>/data.json reports/<domain>/GEO-REPORT-<domain>.pdf

   # Developer PDF
   python3 ~/.claude/skills/geo/scripts/render_dev_report.py \
     reports/<domain>/data.json reports/<domain>/GEO-DEV-REPORT-<domain>.html
   python3 ~/.claude/skills/geo/scripts/generate_dev_pdf_report.py \
     reports/<domain>/data.json reports/<domain>/GEO-DEV-REPORT-<domain>.pdf
   ```
7. Run the voice gate against the client PDF:
   ```bash
   python3 ~/.claude/skills/geo/scripts/voice_check.py \
     reports/<domain>/GEO-REPORT-<domain>.pdf
   ```
8. Report all four file paths + sizes to the user

## Design System

The neo brutalist style is enforced by `render_geo_report.py` CSS constants — **do not override**:

- **Fonts**: Barlow Condensed 900 (headlines), IBM Plex Sans (body), IBM Plex Mono (labels/tags)
- **Palette**: `--cream: #F5F0E8`, `--coral: #E8533A`, `--sage: #7A9E8E`, `--charcoal: #1C1C1C`, `--black: #0A0A0A`
- **Borders**: 3px solid black, no border-radius
- **Shadows**: 8px 8px 0 black (cards), 4px 4px 0 black (score cells)
- **Score states**: coral background on `.critical` cells (score < 30)
