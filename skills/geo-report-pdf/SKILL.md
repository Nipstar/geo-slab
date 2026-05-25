---
name: geo-report-pdf
description: Generate a neo brutalist PDF report from GEO audit data using Playwright. Renders the HTML report via render_geo_report.py, then prints to PDF via headless Chromium — preserving all fonts, colours, and layout exactly.
version: 2.0.0
author: antek-automation
tags: [geo, pdf, report, client-deliverable, neo-brutalist]
---

# GEO PDF Report Generator

> **MANDATORY: Read `/STYLE.md` before generating any prose in this report.**
> Every client-facing sentence — score bands, sub-score descriptions, issue cards, good-news items, the £-impact line, the CTA — must be translated through the mappings defined in `/STYLE.md` and `scripts/style.py`. Do NOT output raw technical terms (`llms.txt`, `JSON-LD`, `robots.txt`, `E-E-A-T`, `schema.org`, `GEO`) without the plain-English wrapper. The banned-words list in `style.py:BANNED_WORDS` is non-negotiable. UK English throughout.

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
        "Platform Optimization": 59
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

## Generate Full Audit PDF

```bash
# From audit JSON → PDF
python3 ~/.claude/skills/geo/scripts/generate_pdf_report.py audit-data.json GEO-REPORT-brand.pdf

# Or pipe from stdin
cat audit-data.json | python3 ~/.claude/skills/geo/scripts/generate_pdf_report.py - GEO-REPORT-brand.pdf

# Output defaults to GEO-REPORT-<domain>.pdf if no output arg given
python3 ~/.claude/skills/geo/scripts/generate_pdf_report.py audit-data.json
```

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

1. Check for existing audit data: look for `GEO-AUDIT-REPORT.md` or a `reports/` subdirectory
2. If no audit data: tell user to run `/geo-audit <url>` first
3. Parse the markdown report to extract all scores, findings, action items, and platform data
4. Build the JSON structure (schema above)
5. Write JSON to `/tmp/geo-audit-data.json`
6. Determine output folder: `reports/<domain>/`; create if needed
7. Run the HTML generator:
   ```bash
   python3 ~/.claude/skills/geo/scripts/render_geo_report.py /tmp/geo-audit-data.json reports/<domain>/GEO-REPORT-<domain>.html
   ```
8. Run the PDF generator:
   ```bash
   python3 ~/.claude/skills/geo/scripts/generate_pdf_report.py /tmp/geo-audit-data.json reports/<domain>/GEO-REPORT-<domain>.pdf
   ```
9. Report both file paths and sizes to the user

## Design System

The neo brutalist style is enforced by `render_geo_report.py` CSS constants — **do not override**:

- **Fonts**: Barlow Condensed 900 (headlines), IBM Plex Sans (body), IBM Plex Mono (labels/tags)
- **Palette**: `--cream: #F5F0E8`, `--coral: #E8533A`, `--sage: #7A9E8E`, `--charcoal: #1C1C1C`, `--black: #0A0A0A`
- **Borders**: 3px solid black, no border-radius
- **Shadows**: 8px 8px 0 black (cards), 4px 4px 0 black (score cells)
- **Score states**: coral background on `.critical` cells (score < 30)
