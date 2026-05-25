#!/usr/bin/env python3
"""
GEO Prospect Report Generator
Generates a lite HTML prospect report from GEO audit data.

Usage:
    python generate_prospect_report.py --data data.json [--output /path/]
    cat data.json | python generate_prospect_report.py --output /path/

Input JSON schema:
{
    "url": "https://example.com",
    "brand_name": "Example Co",
    "date": "6 April 2026",
    "geo_score": 59,
    "scores": {
        "ai_citability": 72,
        "brand_authority": 31,
        "content_eeat": 55,
        "technical": 72,
        "schema": 74,
        "platform_optimization": 52
    },
    "top_problems": [
        {
            "title": "No Wikipedia entry",
            "body": "AI models don't know you exist. Wikipedia and Wikidata are the primary trust anchors for entity verification. Without them, you won't appear in AI-generated recommendations."
        }
    ],
    "working": [
        "All major AI crawlers explicitly allowed in robots.txt",
        "Schema sameAs links across 9 platforms"
    ],
    "cta_url": "https://antekautomation.com/contact",
    "cta_price": "",
    "cta_label": "Book a 15-minute walkthrough"
}
"""

import json
import sys
import argparse
import re
from datetime import datetime
from pathlib import Path
from html import escape


# ── Helpers ──────────────────────────────────────────────────────────────────

def score_verdict(score: int) -> str:
    if score >= 75:
        return "Solid foundations. Clear opportunities remain."
    elif score >= 60:
        return "Mixed signals. AI models aren't sure about you yet."
    elif score >= 45:
        return "Significant gaps. AI search is largely passing you by."
    else:
        return "Critical issues. You're nearly invisible to AI search."


def score_summary(score: int) -> str:
    if score >= 75:
        return "You have good technical foundations but gaps in brand authority and content are holding you back. The fixes are specific and actionable."
    elif score >= 60:
        return "Your tech is functional but AI models can't verify who you are. Brand signals, editorial content, and entity data are the missing pieces."
    elif score >= 45:
        return "There are fundamental gaps across multiple areas. Without action, competitors with better GEO scores are capturing the AI search visibility that should be yours."
    else:
        return "Multiple critical issues are preventing AI models from finding, understanding, and citing your business. This needs attention now."


def domain_from_url(url: str) -> str:
    return re.sub(r'https?://(www\.)?', '', url).rstrip('/').split('/')[0]


# ── HTML Sections ─────────────────────────────────────────────────────────────

STATIC_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GEO Scan — {brand}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;700;900&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        :root {{
            --coral: #D97757;
            --cream: #E8DFD0;
            --sage: #C5D8CC;
            --charcoal: #1A1A1A;
            --black: #000000;
            --off-white: #FAF8F5;
            --shadow: 8px 8px 0 var(--black);
        }}
        html {{ scroll-behavior: smooth; }}
        body {{
            background: var(--cream);
            color: var(--charcoal);
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 16px;
            line-height: 1.65;
        }}
        /* Header */
        .site-header {{
            background: var(--charcoal);
            border-bottom: 3px solid var(--black);
            padding: 0 56px;
            height: 56px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .header-brand {{
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 15px;
            color: var(--cream);
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }}
        .header-meta {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 12px;
            color: var(--coral);
        }}
        /* Why AI Search Matters — primer above the fold */
        .why-section {{
            padding: 28px 56px;
            background: var(--charcoal);
            color: var(--cream);
            border-bottom: 3px solid var(--black);
        }}
        .why-eyebrow {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 10px;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: var(--coral);
            display: block;
            margin-bottom: 10px;
        }}
        .why-heading {{
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 30px;
            line-height: 1.05;
            margin-bottom: 14px;
            color: var(--cream);
        }}
        .why-body {{
            font-size: 14px;
            line-height: 1.6;
            opacity: 0.85;
            max-width: 760px;
            margin-bottom: 18px;
        }}
        .why-stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
            margin-top: 8px;
        }}
        .why-stat {{ border-left: 3px solid var(--coral); padding: 4px 0 4px 14px; }}
        .why-stat-num {{
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 30px;
            line-height: 1;
            color: var(--coral);
            display: block;
        }}
        .why-stat-label {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 10px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--cream);
            opacity: 0.75;
            margin-top: 6px;
            display: block;
        }}
        /* Hero */
        .hero {{
            padding: 48px 56px 40px;
            border-bottom: 3px solid var(--black);
            display: grid;
            grid-template-columns: 340px 1fr;
            gap: 64px;
            align-items: start;
        }}
        .hero-score-block {{}}
        .scan-label {{
            display: block;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            color: var(--coral);
            margin-bottom: 20px;
        }}
        .score-big {{
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 144px;
            line-height: 0.85;
            color: var(--coral);
            display: block;
        }}
        .score-denom {{
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 700;
            font-size: 40px;
            color: var(--charcoal);
            opacity: 0.3;
            display: block;
            margin-top: 8px;
        }}
        .hero-right {{ padding-top: 16px; }}
        .verdict {{
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 36px;
            line-height: 1.05;
            margin-bottom: 20px;
        }}
        .summary {{
            font-size: 16px;
            line-height: 1.7;
            opacity: 0.8;
            max-width: 520px;
            margin-bottom: 28px;
        }}
        .url-tag {{
            display: inline-block;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 12px;
            background: var(--charcoal);
            color: var(--cream);
            padding: 6px 12px;
            letter-spacing: 0.02em;
        }}
        /* Score grid */
        .score-grid {{
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            border-bottom: 3px solid var(--black);
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .score-cell {{
            border-right: 3px solid var(--black);
            padding: 24px 20px 20px;
            background: var(--off-white);
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .score-cell:last-child {{ border-right: none; }}
        .score-cell.low {{ background: var(--coral); }}
        .score-cell.low .cell-label,
        .score-cell.low .cell-num {{ color: var(--cream); }}
        .score-cell.low .cell-denom {{ color: rgba(255,255,255,0.4); }}
        .score-cell.low .cell-bar {{ background: rgba(255,255,255,0.15); }}
        .score-cell.low .cell-bar-fill {{ background: var(--cream); }}
        .cell-label {{
            display: block;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--charcoal);
            opacity: 0.55;
            margin-bottom: 12px;
            line-height: 1.4;
        }}
        .cell-num {{
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 48px;
            line-height: 1;
            color: var(--charcoal);
        }}
        .cell-denom {{
            font-size: 20px;
            font-weight: 700;
            opacity: 0.3;
        }}
        .cell-bar {{
            height: 3px;
            background: rgba(0,0,0,0.1);
            margin-top: 14px;
            position: relative;
        }}
        .cell-bar-fill {{
            position: absolute;
            top: 0; left: 0;
            height: 100%;
            background: var(--charcoal);
        }}
        /* Section */
        .section {{
            border-bottom: 3px solid var(--black);
            padding: 40px 56px;
        }}
        .section-label {{
            display: block;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            color: var(--coral);
            margin-bottom: 16px;
        }}
        h2 {{
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: clamp(44px, 6vw, 72px);
            line-height: 0.92;
            margin-bottom: 40px;
        }}
        /* Problems */
        .problem-list {{ display: grid; }}
        .problem-item {{
            border: 3px solid var(--black);
            border-bottom: none;
            padding: 32px 36px;
            background: var(--off-white);
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .problem-item:last-child {{ border-bottom: 3px solid var(--black); }}
        .problem-item:nth-child(even) {{ background: var(--cream); }}
        .problem-title {{
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 26px;
            line-height: 1;
            margin-bottom: 12px;
            color: var(--charcoal);
        }}
        .problem-body {{
            font-size: 15px;
            line-height: 1.65;
            color: var(--charcoal);
            opacity: 0.82;
            max-width: 720px;
        }}
        .no-fix-tag {{
            display: inline-block;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            background: var(--charcoal);
            color: var(--cream);
            padding: 3px 8px;
            margin-bottom: 12px;
            opacity: 0.4;
        }}
        /* Working */
        .working-section {{
            background: var(--sage);
            border-bottom: 3px solid var(--black);
            padding: 56px;
        }}
        .working-list {{ display: grid; gap: 0; margin-top: 8px; }}
        .working-item {{
            border: 3px solid var(--black);
            border-bottom: none;
            padding: 20px 28px;
            background: rgba(255,255,255,0.35);
            display: flex;
            align-items: baseline;
            gap: 16px;
            font-size: 15px;
            line-height: 1.5;
        }}
        .working-item:last-child {{ border-bottom: 3px solid var(--black); }}
        .check {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 14px;
            color: var(--charcoal);
            flex-shrink: 0;
        }}
        /* Teaser */
        .teaser-section {{
            border-bottom: 3px solid var(--black);
            padding: 56px;
            background: var(--off-white);
        }}
        .teaser-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0;
            border: 3px solid var(--black);
            box-shadow: var(--shadow);
            margin-top: 8px;
        }}
        .teaser-item {{
            border-right: 3px solid var(--black);
            border-bottom: 3px solid var(--black);
            padding: 20px 24px;
            display: flex;
            align-items: baseline;
            gap: 14px;
            font-size: 14px;
            line-height: 1.5;
            color: var(--charcoal);
            opacity: 0.7;
        }}
        .teaser-item:nth-child(even) {{ border-right: none; }}
        .teaser-item:nth-last-child(-n+2) {{ border-bottom: none; }}
        .bullet {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 12px;
            color: var(--coral);
            flex-shrink: 0;
        }}
        /* CTA */
        .cta-section {{
            background: var(--coral);
            border-bottom: 3px solid var(--black);
            padding: 48px 56px;
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 64px;
            align-items: center;
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .cta-left {{}}
        .cta-eyebrow {{
            display: block;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            color: var(--cream);
            margin-bottom: 16px;
        }}
        .cta-heading {{
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: clamp(36px, 5vw, 56px);
            line-height: 0.95;
            color: var(--cream);
            margin-bottom: 20px;
        }}
        .cta-body {{
            font-size: 15px;
            line-height: 1.65;
            color: var(--cream);
            opacity: 0.85;
            max-width: 500px;
        }}
        .cta-right {{}}
        .cta-price {{
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 52px;
            line-height: 1;
            color: var(--cream);
            display: block;
            margin-bottom: 20px;
            white-space: nowrap;
        }}
        .cta-button {{
            display: block;
            background: var(--cream);
            color: var(--coral);
            text-decoration: none;
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 20px;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            padding: 16px 32px;
            border: 3px solid var(--black);
            box-shadow: 6px 6px 0 var(--black);
            transition: transform 0.12s, box-shadow 0.12s;
            text-align: center;
            white-space: nowrap;
        }}
        .cta-button:hover {{
            transform: translate(-3px, -3px);
            box-shadow: 9px 9px 0 var(--black);
        }}
        /* Footer */
        .site-footer {{
            padding: 24px 56px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 32px;
            break-inside: avoid;
            page-break-inside: avoid;
            page-break-before: avoid;
        }}
        .footer-brand {{
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 18px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--charcoal);
        }}
        .footer-meta {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 11px;
            color: var(--charcoal);
            opacity: 0.4;
            text-align: right;
        }}
        /* Print */
        @media print {{
            .cta-button {{ box-shadow: none; }}
        }}
        /* Mobile */
        @media (max-width: 860px) {{
            .site-header {{ padding: 0 24px; }}
            .hero {{ grid-template-columns: 1fr; gap: 32px; padding: 48px 24px 40px; }}
            .score-big {{ font-size: 100px; }}
            .score-grid {{ grid-template-columns: repeat(3, 1fr); }}
            .score-cell:nth-child(3) {{ border-right: none; }}
            .section, .working-section, .teaser-section {{ padding: 48px 24px; }}
            .cta-section {{ grid-template-columns: 1fr; padding: 48px 24px; gap: 32px; }}
            .teaser-grid {{ grid-template-columns: 1fr; }}
            .teaser-item {{ border-right: none; }}
            .teaser-item:nth-last-child(-n+2) {{ border-bottom: 3px solid var(--black); }}
            .teaser-item:last-child {{ border-bottom: none; }}
            .site-footer {{ flex-direction: column; align-items: flex-start; padding: 32px 24px; }}
        }}
    </style>
</head>"""


def build_score_cells(scores: dict) -> str:
    """Build the 6-cell category score grid."""
    cells_config = [
        ("ai_citability",        "AI Citability"),
        ("brand_authority",      "Brand Authority"),
        ("content_eeat",         "Content E-E-A-T"),
        ("technical",            "Technical GEO"),
        ("schema",               "Schema"),
        ("platform_optimization","Platforms"),
    ]
    cells = []
    for key, label in cells_config:
        val = scores.get(key, 0)
        is_low = val < 45
        cls = ' low' if is_low else ''
        cells.append(f"""\
        <div class="score-cell{cls}">
            <span class="cell-label">{label}</span>
            <div class="cell-num">{val}<span class="cell-denom">/100</span></div>
            <div class="cell-bar"><div class="cell-bar-fill" style="width:{val}%"></div></div>
        </div>""")
    return '\n'.join(cells)


def build_problem_items(problems: list) -> str:
    """Build problem list items — title + body, no fix instructions."""
    items = []
    for p in problems:
        title = escape(p.get('title', ''))
        body = escape(p.get('body', ''))
        items.append(f"""\
        <div class="problem-item">
            <span class="no-fix-tag">Identified issue</span>
            <div class="problem-title">{title}</div>
            <div class="problem-body">{body}</div>
        </div>""")
    return '\n'.join(items)


def build_working_items(working: list) -> str:
    """Build working items checklist."""
    items = []
    for w in working:
        items.append(f"""\
        <div class="working-item">
            <span class="check">&#x2713;</span>
            <span>{escape(w)}</span>
        </div>""")
    return '\n'.join(items)


FULL_AUDIT_COVERS = [
    "All pages — full sitemap crawl (up to 50 pages)",
    "6 audit categories with weighted composite scoring",
    "Platform scores: ChatGPT, Perplexity, Gemini, Bing Copilot, Google AI Overviews",
    "NAP consistency check across GBP, schema, and directories",
    "Schema markup audit — every structured data type, property by property",
    "AI crawler access — robots.txt, meta tags, HTTP headers",
    "Brand authority scan — Wikipedia, Wikidata, Clutch, Reddit, press",
    "llms.txt assessment and generation recommendations",
    "Content E-E-A-T scoring across Experience, Expertise, Authoritativeness, Trust",
    "Prioritised fix plan: this week / this month / this quarter",
]

def build_teaser_items() -> str:
    items = []
    for item in FULL_AUDIT_COVERS:
        items.append(f"""\
        <div class="teaser-item">
            <span class="bullet">&#x2192;</span>
            <span>{escape(item)}</span>
        </div>""")
    return '\n'.join(items)


def render(data: dict) -> str:
    brand      = escape(data.get('brand_name', 'Your Business'))
    url        = data.get('url', '')
    date       = escape(data.get('date', datetime.now().strftime('%-d %B %Y')))
    score      = int(data.get('geo_score', 0))
    scores     = data.get('scores', {})
    problems   = data.get('top_problems', [])
    working    = data.get('working', [])
    cta_url    = data.get('cta_url', 'https://antekautomation.com/contact')
    cta_price  = escape(data.get('cta_price', ''))
    cta_label  = escape(data.get('cta_label', 'Book a 15-minute walkthrough'))

    verdict  = score_verdict(score)
    summary  = score_summary(score)
    n_issues = len(problems)
    issue_word = "issue" if n_issues == 1 else "issues"

    score_cells    = build_score_cells(scores)
    problem_items  = build_problem_items(problems)
    working_items  = build_working_items(working)
    teaser_items   = build_teaser_items()

    head = STATIC_HEAD.format(brand=brand)

    body = f"""\
<body>

    <header class="site-header">
        <div class="header-brand">{brand} — GEO Scan</div>
        <div class="header-meta">{score}/100 &mdash; {date}</div>
    </header>

    <!-- WHY AI SEARCH MATTERS -->
    <section class="why-section">
        <span class="why-eyebrow">Why this matters</span>
        <div class="why-heading">Your next client is asking ChatGPT, not Google.</div>
        <p class="why-body">AI search engines — ChatGPT, Claude, Perplexity, Gemini, Google AI Overviews — already answer questions that used to land on your website. They quote one or two firms in the answer and ignore the rest. Being optimised for Google is no longer the same as being visible. This scan checks whether AI engines can find you, trust you, and cite you when a prospect asks for a solicitor.</p>
        <div class="why-stats">
            <div class="why-stat">
                <span class="why-stat-num">58%</span>
                <span class="why-stat-label">of searches end without a click — answered by AI</span>
            </div>
            <div class="why-stat">
                <span class="why-stat-num">1–3</span>
                <span class="why-stat-label">firms cited in a typical AI answer</span>
            </div>
            <div class="why-stat">
                <span class="why-stat-num">9</span>
                <span class="why-stat-label">AI search engines now compete with Google</span>
            </div>
        </div>
    </section>

    <!-- HERO -->
    <section class="hero">
        <div class="hero-score-block">
            <span class="scan-label">GEO Prospect Scan &mdash; {escape(url)}</span>
            <span class="score-big">{score}</span>
            <span class="score-denom">out of 100</span>
        </div>
        <div class="hero-right">
            <div class="verdict">{verdict}</div>
            <p class="summary">{summary}</p>
            <span class="url-tag">{escape(domain_from_url(url))}</span>
        </div>
    </section>

    <!-- CATEGORY SCORES -->
    <div class="score-grid">
{score_cells}
    </div>

    <!-- PROBLEMS -->
    <section class="section">
        <span class="section-label">Top {n_issues} {issue_word} identified</span>
        <h2>what's holding you back</h2>
        <div class="problem-list">
{problem_items}
        </div>
    </section>

    <!-- WORKING -->
    <section class="working-section">
        <span class="section-label">What's working</span>
        <h2>the good news</h2>
        <div class="working-list">
{working_items}
        </div>
    </section>

    <!-- TEASER -->
    <section class="teaser-section">
        <span class="section-label">The full audit</span>
        <h2>what this scan doesn't cover</h2>
        <div class="teaser-grid">
{teaser_items}
        </div>
    </section>

    <!-- CTA -->
    <section class="cta-section">
        <div class="cta-left">
            <span class="cta-eyebrow">Want the full picture?</span>
            <div class="cta-heading">See your firm through<br>an AI's eyes — live.</div>
            <p class="cta-body">This scan is a snapshot. On a 15-minute call I'll open ChatGPT, Claude, and Perplexity and ask the questions your clients ask. We'll see together where you show up, where you don't, and which competitor is taking your share. No pitch, no slides. Just the live result and three concrete moves you can make this week.</p>
        </div>
        <div class="cta-right">
            {('<span class="cta-price">' + cta_price + '</span>') if cta_price else ''}
            <a href="{cta_url}" class="cta-button">{cta_label} &rarr;</a>
        </div>
    </section>

    <!-- FOOTER -->
    <footer class="site-footer">
        <div class="footer-brand">GEO SLAB</div>
        <div class="footer-meta">
            GEO Prospect Scan &mdash; {date}<br>
            Antek Automation &mdash; antekautomation.com
        </div>
    </footer>

</body>
</html>"""

    return head + '\n' + body


# ── Main ──────────────────────────────────────────────────────────────────────

def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    """Print an HTML file to PDF using Playwright headless Chromium."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "ERROR: Playwright is required for PDF output.\n"
            "  pip install playwright\n"
            "  playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file://{html_path.resolve()}", wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()


def main():
    parser = argparse.ArgumentParser(
        description='Generate a GEO prospect report HTML (and optionally PDF) from audit data JSON.'
    )
    parser.add_argument(
        '--data', '-d',
        help='Path to JSON data file. Reads from stdin if not provided.'
    )
    parser.add_argument(
        '--output', '-o',
        default='.',
        help='Output directory (default: current directory).'
    )
    parser.add_argument(
        '--pdf', action='store_true',
        help='Also generate a PDF version using Playwright.'
    )
    args = parser.parse_args()

    if args.data:
        with open(args.data, 'r') as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    html = render(data)

    domain   = domain_from_url(data.get('url', 'site'))
    safe_domain = re.sub(r'[^\w.-]', '-', domain)
    filename = f"GEO-PROSPECT-{safe_domain}.html"
    output_path = Path(args.output) / filename

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Prospect report written to: {output_path}")

    if args.pdf:
        pdf_path = output_path.with_suffix('.pdf')
        html_to_pdf(output_path, pdf_path)
        size_kb = round(pdf_path.stat().st_size / 1024)
        print(f"PDF report written to: {pdf_path} ({size_kb} KB)")

    return str(output_path)


if __name__ == '__main__':
    main()
