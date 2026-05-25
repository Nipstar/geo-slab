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

# Voice + structured data live in style.py. See /STYLE.md for the
# human-readable companion. Edit both together if voice changes.
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
from style import (  # noqa: E402
    score_band,
    SCORE_CARD_DESCRIPTIONS,
    INDUSTRY_VALUES,
    revenue_impact_line,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def score_verdict(score: int) -> str:
    return score_band(score)["verdict"]


def score_summary(score: int) -> str:
    return score_band(score)["summary"]


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
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;700;800&family=DM+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        @page {{ size: A4; margin: 0; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        :root {{
            --coral: #CD5C3C;
            --cream: #E8DCC8;
            --sage: #C8D8D0;
            --charcoal: #2C2C2C;
            --black: #000000;
            --off-white: #FAF8F5;
            --shadow: 8px 8px 0 var(--black);
        }}
        html {{ scroll-behavior: smooth; }}
        body {{
            background: var(--cream);
            color: var(--charcoal);
            font-family: 'DM Sans', sans-serif;
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
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
            font-size: 15px;
            color: var(--cream);
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }}
        .header-meta {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: var(--coral);
        }}
        /* Page-break safety — never strand headings, never split key blocks */
        h1, h2, h3 {{
            page-break-after: avoid;
            break-after: avoid-page;
        }}
        /* Why AI Search Matters — primer above the fold */
        .why-section {{
            padding: 28px 56px;
            background: var(--charcoal);
            color: var(--cream);
            border-bottom: 3px solid var(--black);
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .why-eyebrow {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: var(--coral);
            display: block;
            margin-bottom: 10px;
        }}
        .why-heading {{
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
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
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
            font-size: 30px;
            line-height: 1;
            color: var(--coral);
            display: block;
        }}
        .why-stat-label {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--cream);
            opacity: 0.75;
            margin-top: 6px;
            display: block;
        }}
        .why-revenue {{
            margin-top: 22px;
            padding-top: 18px;
            border-top: 1px solid rgba(232,220,200,0.18);
            font-size: 14px;
            line-height: 1.6;
            color: var(--cream);
            opacity: 0.95;
            max-width: 800px;
        }}
        .why-revenue strong {{ color: var(--coral); }}
        /* Hero */
        .hero {{
            padding: 48px 56px 40px;
            border-bottom: 3px solid var(--black);
            display: grid;
            grid-template-columns: 340px 1fr;
            gap: 64px;
            align-items: start;
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .hero-score-block {{}}
        .scan-label {{
            display: block;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            color: var(--coral);
            margin-bottom: 20px;
        }}
        .score-big {{
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
            font-size: 144px;
            line-height: 0.85;
            color: var(--coral);
            display: block;
        }}
        .score-denom {{
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            font-size: 40px;
            color: var(--charcoal);
            opacity: 0.3;
            display: block;
            margin-top: 8px;
        }}
        .hero-right {{ padding-top: 16px; }}
        .verdict {{
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
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
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            background: var(--charcoal);
            color: var(--cream);
            padding: 6px 12px;
            letter-spacing: 0.02em;
        }}
        /* Score grid */
        .score-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            border-bottom: 3px solid var(--black);
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .score-cell {{
            border-right: 3px solid var(--black);
            border-bottom: 3px solid var(--black);
            padding: 20px 22px 22px;
            background: var(--off-white);
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .score-cell:nth-child(3n) {{ border-right: none; }}
        .score-cell:nth-last-child(-n+3) {{ border-bottom: none; }}
        .score-cell.low {{ background: var(--coral); }}
        .score-cell.low .cell-label,
        .score-cell.low .cell-num {{ color: var(--cream); }}
        .score-cell.low .cell-denom {{ color: rgba(255,255,255,0.4); }}
        .score-cell.low .cell-bar {{ background: rgba(255,255,255,0.15); }}
        .score-cell.low .cell-bar-fill {{ background: var(--cream); }}
        .cell-label {{
            display: block;
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--charcoal);
            opacity: 0.55;
            margin-bottom: 12px;
            line-height: 1.4;
        }}
        .cell-num {{
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
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
        .cell-desc {{
            font-size: 11px;
            line-height: 1.45;
            color: var(--charcoal);
            opacity: 0.72;
            margin-top: 12px;
        }}
        .score-cell.low .cell-desc {{ color: var(--cream); opacity: 0.85; }}
        /* Section */
        .section {{
            border-bottom: 3px solid var(--black);
            padding: 32px 56px;
        }}
        .section-label {{
            display: block;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            color: var(--coral);
            margin-bottom: 16px;
        }}
        h2 {{
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
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
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
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
            font-family: 'JetBrains Mono', monospace;
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
            padding: 12px 28px;
            background: rgba(255,255,255,0.35);
            display: flex;
            align-items: baseline;
            gap: 16px;
            font-size: 14px;
            line-height: 1.45;
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .working-item:last-child {{ border-bottom: 3px solid var(--black); }}
        .check {{
            font-family: 'JetBrains Mono', monospace;
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
            padding: 11px 22px;
            display: flex;
            align-items: baseline;
            gap: 14px;
            font-size: 13px;
            line-height: 1.45;
            color: var(--charcoal);
            opacity: 0.78;
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .teaser-item:nth-child(even) {{ border-right: none; }}
        .teaser-item:nth-last-child(-n+2) {{ border-bottom: none; }}
        .bullet {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: var(--coral);
            flex-shrink: 0;
        }}
        /* Proof — live AI result block (coral panel) */
        .proof-section {{
            background: var(--coral);
            color: var(--cream);
            padding: 44px 56px 40px;
            border-bottom: 3px solid var(--black);
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .proof-eyebrow {{
            display: block;
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.18em;
            color: var(--cream);
            opacity: 0.85;
            margin-bottom: 12px;
        }}
        .proof-headline {{
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
            font-size: 30px;
            line-height: 1.1;
            color: var(--cream);
            margin-bottom: 14px;
            max-width: 760px;
        }}
        .proof-body {{
            font-size: 15px;
            line-height: 1.55;
            color: var(--cream);
            opacity: 0.95;
            max-width: 720px;
            margin-bottom: 14px;
        }}
        .proof-caveat {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: var(--cream);
            opacity: 0.65;
            max-width: 720px;
        }}
        /* Samples — 3 follow-up queries */
        .samples-section {{
            background: var(--charcoal);
            color: var(--cream);
            padding: 36px 56px;
            border-bottom: 3px solid var(--black);
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .samples-section .section-label {{ color: var(--coral); }}
        .samples-heading {{
            font-family: 'DM Sans', sans-serif;
            font-weight: 500;
            font-size: 15px;
            line-height: 1.5;
            color: var(--cream);
            opacity: 0.9;
            max-width: 740px;
            margin: 6px 0 18px;
        }}
        .samples-list {{
            list-style: none;
            display: grid;
            gap: 8px;
            max-width: 720px;
        }}
        .samples-list li {{
            font-family: 'DM Sans', sans-serif;
            font-size: 15px;
            font-weight: 500;
            color: var(--cream);
            border-left: 3px solid var(--coral);
            padding: 8px 0 8px 14px;
        }}
        /* CTA */
        .cta-section {{
            background: var(--coral);
            border-bottom: 3px solid var(--black);
            padding: 48px 56px;
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 40px;
            align-items: center;
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .cta-right {{ flex-shrink: 0; }}
        .cta-left {{}}
        .cta-eyebrow {{
            display: block;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            color: var(--cream);
            margin-bottom: 16px;
        }}
        .cta-heading {{
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
            font-size: 42px;
            line-height: 1.02;
            color: var(--cream);
            margin-bottom: 18px;
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
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
            font-size: 52px;
            line-height: 1;
            color: var(--cream);
            display: block;
            margin-bottom: 20px;
            white-space: nowrap;
        }}
        .cta-prompt {{
            font-size: 14px;
            line-height: 1.55;
            color: var(--cream);
            opacity: 0.95;
            margin-top: 16px;
            font-weight: 500;
            max-width: 540px;
        }}
        .cta-button {{
            display: inline-block;
            background: var(--cream);
            color: var(--coral);
            text-decoration: none;
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
            font-size: 15px;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            padding: 13px 22px;
            border: 3px solid var(--black);
            box-shadow: 6px 6px 0 var(--black);
            transition: transform 0.12s, box-shadow 0.12s;
            text-align: center;
            white-space: nowrap;
            max-width: 100%;
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
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
            font-size: 18px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--charcoal);
        }}
        .footer-meta {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: var(--charcoal);
            opacity: 0.4;
            text-align: right;
        }}
        /* Print */
        @media print {{
            .cta-button {{ box-shadow: none; }}
        }}
        /* Print — force desktop layout regardless of viewport */
        @media print {{
            .teaser-grid {{ grid-template-columns: 1fr 1fr; }}
            .teaser-item {{ border-right: 3px solid var(--black); }}
            .teaser-item:nth-child(even) {{ border-right: none; }}
            .teaser-item:nth-last-child(-n+2) {{ border-bottom: none; }}
        }}
        /* Mobile — breakpoint below A4 print width so PDFs render desktop layout */
        @media (max-width: 760px) {{
            .site-header {{ padding: 0 24px; }}
            .hero {{ grid-template-columns: 1fr; gap: 32px; padding: 48px 24px 40px; }}
            .score-big {{ font-size: 100px; }}
            .score-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .score-cell:nth-child(3n) {{ border-right: 3px solid var(--black); }}
            .score-cell:nth-child(2n) {{ border-right: none; }}
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
        desc = escape(SCORE_CARD_DESCRIPTIONS.get(key, ""))
        cells.append(f"""\
        <div class="score-cell{cls}">
            <span class="cell-label">{label}</span>
            <div class="cell-num">{val}<span class="cell-denom">/100</span></div>
            <div class="cell-bar"><div class="cell-bar-fill" style="width:{val}%"></div></div>
            <p class="cell-desc">{desc}</p>
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
    working    = list(data.get('working', []))
    cta_url    = data.get('cta_url', 'https://antekautomation.com/contact')
    cta_price  = escape(data.get('cta_price', ''))
    cta_label  = escape(data.get('cta_label', 'Book a walkthrough'))
    industry   = (data.get('industry') or '').strip()
    deal_low   = int(data.get('avg_deal_value_low') or 0)
    deal_high  = int(data.get('avg_deal_value_high') or 0)
    live_query    = data.get('live_query') or None
    sample_queries = data.get('sample_queries') or []

    verdict  = score_verdict(score)
    summary  = score_summary(score)
    revenue_line = revenue_impact_line(industry, deal_low, deal_high)
    n_issues = len(problems)
    issue_word = "issue" if n_issues == 1 else "issues"
    if n_issues == 0:
        working.insert(0, "No issues identified in this scan — you're ahead of most.")

    score_cells    = build_score_cells(scores)
    problem_items  = build_problem_items(problems)
    working_items  = build_working_items(working)
    teaser_items   = build_teaser_items()

    if n_issues > 0:
        problems_block = f"""<section class="section">
        <span class="section-label">Top {n_issues} {issue_word} identified</span>
        <h2>what's holding you back</h2>
        <div class="problem-list">
{problem_items}
        </div>
    </section>"""
    else:
        problems_block = ""

    # ── Live proof + sample queries blocks (page 4 above CTA) ────────────
    proof_block = ""
    if live_query:
        q_text = escape(live_query.get("query", ""))
        provider = escape(live_query.get("provider", "Perplexity"))
        tested_at = escape(live_query.get("tested_at", ""))
        cited = bool(live_query.get("prospect_cited"))
        firms = [escape(f) for f in live_query.get("firms_cited") or []][:3]
        if cited:
            firms_other = [f for f in firms if f][:2]
            firms_str = " and ".join(firms_other) if firms_other else "two other firms"
            headline = (
                f"When someone asks ChatGPT &ldquo;{q_text}&rdquo;, you're in the answer "
                f"&mdash; alongside {firms_str}."
            )
            body_text = (
                f"You're sharing the citation with {len(firms_other) or 'a few'} other firms. "
                f"With the gaps in this report fixed, you'd be the primary answer, not one of three."
            )
        else:
            firms_str = ", ".join(firms) if firms else "competitors with stronger AI signals"
            headline = (
                f"Right now, when someone asks ChatGPT &ldquo;{q_text}&rdquo;, "
                f"your firm doesn't appear in the answer."
            )
            body_text = (
                f"The firms cited are: {firms_str}. That's where this month's enquiries are going."
            )
        proof_block = f"""<section class="proof-section">
        <span class="proof-eyebrow">The question your prospects are asking</span>
        <div class="proof-headline">{headline}</div>
        <p class="proof-body">{body_text}</p>
        <p class="proof-caveat">Tested via {provider} on {tested_at}. Results vary by user and update over time &mdash; this is one snapshot.</p>
    </section>"""

    samples_block = ""
    if sample_queries:
        items = "\n".join(
            f'            <li>&ldquo;{escape(q)}&rdquo;</li>' for q in sample_queries[:3]
        )
        samples_block = f"""<section class="samples-section">
        <span class="section-label">Three more questions, answered live</span>
        <h3 class="samples-heading">On a 15-minute call I'll open ChatGPT, Claude, and Perplexity and run these. We'll see, together, where you show up and where you don't.</h3>
        <ul class="samples-list">
{items}
        </ul>
    </section>"""

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
        <p class="why-revenue">{revenue_line}</p>
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

    {problems_block}

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

    <!-- PROOF (live AI result + sample queries) -->
    {proof_block}
    {samples_block}

    <!-- CTA -->
    <section class="cta-section">
        <div class="cta-left">
            <span class="cta-eyebrow">Want the full picture?</span>
            <div class="cta-heading">Walk me through my full report.</div>
            <p class="cta-body">Your full GEO audit covers all 50 pages, six categories, and a prioritised fix plan. The call is me walking you through it, plus the live AI queries above. 15 minutes. No slides.</p>
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
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"file://{html_path.resolve()}", wait_until="networkidle")
        # Wait for web fonts (Outfit, DM Sans, JetBrains Mono) to be loaded so the
        # PDF doesn't fall back to system fonts mid-render.
        try:
            page.evaluate("document.fonts.ready")
        except Exception:
            pass
        page.emulate_media(media="print")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            prefer_css_page_size=True,
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
