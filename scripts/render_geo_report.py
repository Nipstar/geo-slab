#!/usr/bin/env python3
"""
GEO SLAB — Neo Brutalist Audit Report Generator (Antek Automation)
Converts a JSON audit data file into a full, client-ready HTML report.

Usage:
    python render_geo_report.py data.json [output.html]
    cat data.json | python render_geo_report.py - [output.html]

JSON schema:
{
    "url": "https://example.com",
    "brand_name": "Example Co",
    "date": "8 April 2026",
    "geo_score": 47,
    "pages_audited": 12,                   // optional, default omitted
    "verdict": "Short punchy verdict",     // optional, auto-generated if absent
    "summary": ["para1", "para2", "para3"],// optional, or single string
    "scores": {
        "AI Citability": 62,
        "Brand Authority": 38,
        "Content E-E-A-T": 72,
        "Technical GEO": 44,
        "Schema & Structured Data": 4,
        "Platform Optimization": 29
    },
    "platforms": {
        "Google AI Overviews": 34,
        "ChatGPT Web Search": 22,
        "Perplexity AI": 28,
        "Google Gemini": 32,
        "Bing Copilot": 29,
        "Grok (xAI)": 25,
        "DeepSeek": 30,
        "Meta AI": 27,
        "Mistral (Le Chat)": 20
    },
    "platform_callout": "...",             // optional callout text below platforms
    "findings": [
        {
            "severity": "CRITICAL",        // CRITICAL | HIGH | MEDIUM | LOW
            "title": "Finding title",
            "description": "Detail text."
        }
    ],
    "quick_wins": [
        {"title": "...", "description": "...", "time": "30 min"}
        // or plain strings: "Fix the meta description (30 min)"
    ],
    "medium_term": [ ... ],
    "strategic": [ ... ]
}
"""

import sys
import json
import re
import argparse
from pathlib import Path
from html import escape as he


# ── Score helpers ─────────────────────────────────────────────────────────────

# Voice — score-band copy lives in style.py / STYLE.md. Both files
# must stay in sync. Don't hard-code verdicts or labels here.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).parent))
from style import score_band as _score_band, score_label as _score_label  # noqa: E402


def score_verdict(score: int) -> str:
    return _score_band(score)["verdict"]


def score_label(score: int) -> str:
    return _score_label(score)


def domain_from_url(url: str) -> str:
    return re.sub(r'https?://(www\.)?', '', url).rstrip('/').split('/')[0]


# ── Component builders ────────────────────────────────────────────────────────

CELL_CLASS = {
    "critical": " critical",
    "poor": "",
    "fair": "",
    "good": "",
}

def score_cell_class(score: int) -> str:
    return " critical" if score < 30 else ""


def score_cells_html(scores: dict) -> str:
    cells = []
    for label, score in scores.items():
        cls = score_cell_class(score)
        cells.append(f'''
        <div class="score-cell{cls}">
            <span class="cell-label">{he(label)}</span>
            <div class="cell-number">{score}<span class="cell-denom">/100</span></div>
            <div class="cell-bar"><div class="cell-bar-fill" style="width:{score}%"></div></div>
        </div>''')
    return "".join(cells)


def platform_cells_html(platforms: dict) -> str:
    cells = []
    for name, score in platforms.items():
        low_cls = ' class="platform-score low"' if score < 50 else ' class="platform-score"'
        cells.append(f'''
                <div class="platform-cell">
                    <span class="platform-name">{he(name)}</span>
                    <div{low_cls}>{score}</div>
                    <div class="platform-bar"><div class="platform-bar-fill" style="width:{score}%"></div></div>
                </div>''')
    return "".join(cells)


def findings_html(findings: list) -> str:
    items = []
    for i, f in enumerate(findings, 1):
        sev = f.get("severity", "MEDIUM").upper()
        is_crit = " is-critical" if sev == "CRITICAL" else ""
        title = he(f.get("title", ""))
        desc = he(f.get("description", ""))
        items.append(f'''
                <div class="problem-item{is_crit}">
                    <div class="problem-num">{i:02d}</div>
                    <div class="problem-content">
                        <h3>{title}</h3>
                        <p>{desc}</p>
                    </div>
                </div>''')
    return "".join(items)


def _action_item(num: int, item, alt: bool) -> str:
    """Render one action item. item can be a dict or a plain string."""
    alt_cls = ""  # handled via nth-child in CSS
    if isinstance(item, str):
        # Try to split "Title — description (time)" or just use as description
        title = item
        desc = ""
        time_str = ""
        # Extract time hint like "(30 min)" or "30 min" at end
        m = re.search(r'\(([^)]{3,20})\)\s*$', item)
        if m:
            time_str = m.group(1)
            title = item[:m.start()].rstrip(" —")
        desc = ""
    else:
        title = he(item.get("title", ""))
        desc = he(item.get("description", ""))
        time_str = he(item.get("time", ""))

    time_cell = f'<div class="action-time">{time_str}</div>' if time_str else '<div class="action-time"></div>'
    desc_html = f'<p>{desc}</p>' if desc else ""
    return f'''
                <div class="action-item">
                    <div class="action-num">{num:02d}</div>
                    <div class="action-content">
                        <h3>{title}</h3>
                        {desc_html}
                    </div>
                    {time_cell}
                </div>'''


def action_list_html(items: list) -> str:
    return "".join(_action_item(i + 1, item, i % 2 == 1) for i, item in enumerate(items))


def summary_html(summary) -> str:
    if isinstance(summary, list):
        return "".join(f"<p>{he(p)}</p>" for p in summary)
    elif isinstance(summary, str):
        return f"<p>{he(summary)}</p>"
    return ""


# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
        * { margin: 0; padding: 0; box-sizing: border-box; }

        :root {
            --coral: #D97757;
            --cream: #E8DFD0;
            --sage: #C5D8CC;
            --charcoal: #1A1A1A;
            --black: #000000;
            --off-white: #FAF8F5;
            --border: 3px solid var(--black);
            --shadow: 8px 8px 0 var(--black);
        }

        html { scroll-behavior: smooth; }

        body {
            background: var(--cream);
            color: var(--charcoal);
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 16px;
            line-height: 1.65;
        }

        /* ─── FIXED HEADER ─── */
        .site-header {
            position: fixed;
            top: 0; left: 0; right: 0;
            z-index: 100;
            background: var(--charcoal);
            border-bottom: 3px solid var(--black);
            padding: 0 48px;
            height: 56px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 24px;
        }

        .header-brand {
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 16px;
            color: var(--cream);
            text-transform: uppercase;
            letter-spacing: 0.1em;
            white-space: nowrap;
        }

        .header-nav { display: flex; gap: 28px; }

        .header-nav a {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 10px;
            color: var(--cream);
            text-decoration: none;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            opacity: 0.55;
            transition: opacity 0.15s;
        }

        .header-nav a:hover { opacity: 1; }

        .header-score {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 13px;
            color: var(--coral);
            white-space: nowrap;
        }

        main { padding-top: 56px; }

        /* ─── HERO ─── */
        .hero {
            padding: 80px 64px 72px;
            border-bottom: 3px solid var(--black);
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 64px;
            align-items: start;
        }

        .label {
            display: block;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            color: var(--coral);
            margin-bottom: 20px;
        }

        h1 {
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: clamp(80px, 12vw, 140px);
            line-height: 0.88;
            margin-bottom: 32px;
        }

        .score-big { color: var(--coral); display: block; }
        .score-sub {
            color: var(--charcoal);
            font-size: clamp(32px, 4vw, 52px);
            opacity: 0.35;
            display: block;
            font-weight: 700;
            letter-spacing: 0.02em;
        }

        .hero-right { padding-top: 20px; }

        .hero-verdict {
            font-size: 22px;
            font-weight: 600;
            line-height: 1.35;
            margin-bottom: 24px;
            color: var(--charcoal);
        }

        .hero-body { font-size: 16px; line-height: 1.7; color: var(--charcoal); opacity: 0.85; }
        .hero-body p { margin-bottom: 14px; }
        .hero-body p:last-child { margin-bottom: 0; }

        /* ─── SCORE GRID ─── */
        .score-grid {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            border-bottom: 3px solid var(--black);
        }

        .score-cell {
            border-right: 3px solid var(--black);
            padding: 28px 24px 24px;
            background: var(--off-white);
            transition: background 0.15s;
        }

        .score-cell:last-child { border-right: none; }
        .score-cell:hover { background: var(--sage); }

        .score-cell.critical { background: var(--coral); }
        .score-cell.critical .cell-label,
        .score-cell.critical .cell-number { color: var(--cream); }
        .score-cell.critical .cell-denom { color: var(--cream); opacity: 0.45; }
        .score-cell.critical .cell-bar { background: rgba(255,255,255,0.2); }
        .score-cell.critical .cell-bar-fill { background: var(--cream); }

        .cell-label {
            display: block;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--charcoal);
            opacity: 0.55;
            margin-bottom: 14px;
            line-height: 1.4;
        }

        .cell-number {
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 56px;
            line-height: 1;
            color: var(--charcoal);
        }

        .cell-denom { font-size: 24px; font-weight: 700; opacity: 0.3; }

        .cell-bar { height: 3px; background: rgba(0,0,0,0.12); margin-top: 16px; position: relative; }
        .cell-bar-fill { position: absolute; top: 0; left: 0; height: 100%; background: var(--charcoal); }

        /* ─── SECTION ─── */
        .section { border-bottom: 3px solid var(--black); padding: 72px 64px; }

        h2 {
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: clamp(48px, 7vw, 84px);
            line-height: 0.92;
            margin-bottom: 12px;
        }

        .section-intro {
            font-size: 17px;
            color: var(--charcoal);
            opacity: 0.75;
            margin-bottom: 48px;
            max-width: 640px;
            line-height: 1.65;
        }

        /* ─── PLATFORMS ─── */
        .platform-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            border: 3px solid var(--black);
            box-shadow: var(--shadow);
            margin-bottom: 40px;
        }

        .platform-cell { border-right: 3px solid var(--black); border-bottom: 3px solid var(--black); padding: 28px 20px 24px; background: var(--off-white); }
        .platform-cell:nth-child(3n) { border-right: none; }
        .platform-cell:nth-last-child(-n+3) { border-bottom: none; }

        .platform-name {
            display: block;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            opacity: 0.5;
            margin-bottom: 14px;
            line-height: 1.5;
        }

        .platform-score {
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 60px;
            line-height: 1;
        }

        .platform-score.low { color: var(--coral); }

        .platform-bar { height: 3px; background: rgba(0,0,0,0.1); margin-top: 16px; position: relative; }
        .platform-bar-fill { position: absolute; top: 0; left: 0; height: 100%; background: var(--coral); }

        .callout {
            background: var(--sage);
            border: 3px solid var(--black);
            box-shadow: var(--shadow);
            padding: 28px 32px;
        }

        .callout p { font-size: 16px; line-height: 1.65; max-width: 760px; }

        /* ─── PROBLEMS ─── */
        .problem-list { display: grid; }

        .problem-item {
            border: 3px solid var(--black);
            border-bottom: none;
            padding: 36px 40px;
            display: grid;
            grid-template-columns: 72px 1fr;
            gap: 32px;
            align-items: start;
            background: var(--off-white);
            transition: transform 0.12s, box-shadow 0.12s;
        }

        .problem-item:last-child { border-bottom: 3px solid var(--black); }

        .problem-item:hover {
            transform: translate(-4px, -4px);
            box-shadow: 4px 4px 0 var(--black);
            z-index: 1;
            position: relative;
        }

        .problem-item.is-critical { background: var(--coral); }
        .problem-item.is-critical .problem-num,
        .problem-item.is-critical h3,
        .problem-item.is-critical p,
        .problem-item.is-critical code { color: var(--cream); }
        .problem-item.is-critical code { background: rgba(0,0,0,0.2); }

        .problem-num {
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 64px;
            line-height: 1;
            color: var(--charcoal);
            opacity: 0.15;
            padding-top: 4px;
        }

        .problem-content h3 {
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 30px;
            line-height: 1;
            margin-bottom: 16px;
            color: var(--charcoal);
        }

        .problem-content p { font-size: 15.5px; line-height: 1.65; margin-bottom: 12px; color: var(--charcoal); }
        .problem-content p:last-child { margin-bottom: 0; }

        code {
            background: var(--charcoal);
            color: var(--cream);
            padding: 1px 6px;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 13px;
        }

        /* ─── ACTIONS ─── */
        .action-list { display: grid; }

        .action-item {
            border: 3px solid var(--black);
            border-bottom: none;
            padding: 28px 36px;
            display: grid;
            grid-template-columns: 52px 1fr 100px;
            gap: 24px;
            align-items: start;
            background: var(--off-white);
        }

        .action-item:last-child { border-bottom: 3px solid var(--black); }
        .action-item:nth-child(even) { background: var(--cream); }

        .action-num {
            font-family: 'IBM Plex Mono', monospace;
            font-weight: 500;
            font-size: 22px;
            color: var(--coral);
            padding-top: 3px;
        }

        .action-content h3 {
            font-family: 'Barlow Condensed', sans-serif;
            font-weight: 900;
            font-size: 24px;
            line-height: 1;
            margin-bottom: 10px;
            color: var(--charcoal);
        }

        .action-content p { font-size: 15px; line-height: 1.65; color: var(--charcoal); opacity: 0.8; }

        .action-time {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--charcoal);
            opacity: 0.4;
            padding-top: 6px;
            text-align: right;
        }

        /* ─── SECTION STRIPES ─── */
        .section-week    { border-left: 6px solid var(--coral);    padding-left: 58px; }
        .section-month   { border-left: 6px solid var(--sage);     padding-left: 58px; }
        .section-quarter { border-left: 6px solid var(--charcoal); padding-left: 58px; }

        /* ─── FOOTER ─── */
        .site-footer {
            padding: 40px 64px;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 11px;
            color: var(--charcoal);
            opacity: 0.4;
            display: flex;
            justify-content: space-between;
            gap: 32px;
        }

        /* ─── PRINT ─── */
        @media print {
            .site-header { position: static; }
            main { padding-top: 0; }
            .problem-item:hover { transform: none; box-shadow: none; }
            .score-grid { grid-template-columns: repeat(3, 1fr); }
            .platform-grid { grid-template-columns: repeat(3, 1fr); }
            .platform-cell { border-bottom: 3px solid var(--black); }
            .platform-cell:nth-child(3n) { border-right: none; }
            .platform-cell:nth-last-child(-n+3) { border-bottom: none; }
        }

        /* ─── MOBILE ─── */
        @media (max-width: 900px) {
            .site-header { padding: 0 24px; }
            .header-nav { display: none; }
            .hero { grid-template-columns: 1fr; gap: 32px; padding: 48px 24px; }
            .score-grid { grid-template-columns: repeat(3, 1fr); }
            .platform-grid { grid-template-columns: 1fr; }
            .platform-cell { border-right: none; border-bottom: 3px solid var(--black); }
            .platform-cell:last-child { border-bottom: none; }
            .section { padding: 48px 24px; }
            .section-week, .section-month, .section-quarter { border-left: none; padding-left: 24px; }
            .problem-item { grid-template-columns: 48px 1fr; gap: 16px; padding: 24px; }
            .action-item { grid-template-columns: 40px 1fr; padding: 20px 24px; }
            .action-time { display: none; }
            .site-footer { flex-direction: column; padding: 32px 24px; }
        }
"""


# ── Main builder ──────────────────────────────────────────────────────────────

def build_html(data: dict) -> str:
    brand = he(data.get("brand_name", "Unknown"))
    url = he(data.get("url", ""))
    domain = domain_from_url(data.get("url", ""))
    date = he(data.get("date", ""))
    geo_score = data.get("geo_score", 0)
    pages = data.get("pages_audited", None)
    pages_label = f"{domain} — {pages} pages audited" if pages else domain

    verdict = he(data.get("verdict", score_verdict(geo_score)))
    summary = data.get("summary", "")
    scores = data.get("scores", {})
    platforms = data.get("platforms", {})
    platform_callout = data.get("platform_callout", "")
    findings = data.get("findings", [])
    quick_wins = data.get("quick_wins", [])
    medium_term = data.get("medium_term", [])
    strategic = data.get("strategic", [])

    # Count critical findings for header
    n_critical = sum(1 for f in findings if f.get("severity", "").upper() == "CRITICAL")
    n_high = sum(1 for f in findings if f.get("severity", "").upper() == "HIGH")

    callout_block = ""
    if platform_callout:
        callout_block = f'<div class="callout"><p>{he(platform_callout)}</p></div>'

    week_section = ""
    if quick_wins:
        week_section = f"""
        <!-- ─── THIS WEEK ─── -->
        <section class="section section-week" id="week">
            <span class="label">Quick wins — implement this week</span>
            <h2>this week</h2>
            <p class="section-intro">High impact, low effort. None of these require a developer.</p>
            <div class="action-list">{action_list_html(quick_wins)}</div>
        </section>"""

    month_section = ""
    if medium_term:
        month_section = f"""
        <!-- ─── THIS MONTH ─── -->
        <section class="section section-month" id="month">
            <span class="label">30-day actions — schema and infrastructure</span>
            <h2>this month</h2>
            <p class="section-intro">These are the changes that move your score into the 60s and beyond.</p>
            <div class="action-list">{action_list_html(medium_term)}</div>
        </section>"""

    quarter_section = ""
    if strategic:
        quarter_section = f"""
        <!-- ─── THIS QUARTER ─── -->
        <section class="section section-quarter" id="quarter">
            <span class="label">Strategic initiatives — 60–90 days</span>
            <h2>this quarter</h2>
            <p class="section-intro">Longer-term but highest-lasting impact on AI visibility.</p>
            <div class="action-list">{action_list_html(strategic)}</div>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your GEO Audit — {brand}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;700;900&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>{CSS}</style>
</head>
<body>

    <header class="site-header">
        <div class="header-brand">{brand} — GEO Audit</div>
        <nav class="header-nav">
            <a href="#score">Score</a>
            <a href="#platforms">Platforms</a>
            <a href="#problems">Problems</a>
            {"<a href='#week'>This week</a>" if quick_wins else ""}
            {"<a href='#month'>This month</a>" if medium_term else ""}
            {"<a href='#quarter'>This quarter</a>" if strategic else ""}
        </nav>
        <div class="header-score">{geo_score}/100 — {date}</div>
    </header>

    <main>

        <!-- ─── HERO ─── -->
        <section class="hero" id="score">
            <div class="hero-left">
                <span class="label">{he(pages_label)}</span>
                <h1>
                    <span class="score-big">{geo_score}</span>
                    <span class="score-sub">out of 100</span>
                </h1>
            </div>
            <div class="hero-right">
                <p class="hero-verdict">{verdict}</p>
                <div class="hero-body">{summary_html(summary)}</div>
            </div>
        </section>

        <!-- ─── CATEGORY SCORES ─── -->
        <div class="score-grid" id="categories">
            {score_cells_html(scores)}
        </div>

        <!-- ─── PLATFORM SCORES ─── -->
        <section class="section" id="platforms">
            <span class="label">Where each AI platform scores you</span>
            <h2>platform by platform</h2>
            <p class="section-intro">All nine platforms are looking for the same signals. Here is how you score on each.</p>
            <div class="platform-grid">
                {platform_cells_html(platforms)}
            </div>
            {callout_block}
        </section>

        <!-- ─── KEY PROBLEMS ─── -->
        <section class="section" id="problems">
            <span class="label">What's actually broken</span>
            <h2>the problems</h2>
            <p class="section-intro">{n_critical} critical. {n_high} high priority. Here is what matters most.</p>
            <div class="problem-list">
                {findings_html(findings)}
            </div>
        </section>

        {week_section}
        {month_section}
        {quarter_section}

    </main>

    <footer class="site-footer">
        <span>GEO SLAB by Antek Automation — antekautomation.com</span>
        <span>{url} — {date}</span>
        <span>Confidential</span>
    </footer>

</body>
</html>"""


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GEO SLAB — Generate neo brutalist GEO audit HTML report")
    parser.add_argument("input", nargs="?", default="-",
                        help="JSON data file path, or '-' for stdin (default: stdin)")
    parser.add_argument("output", nargs="?", default=None,
                        help="Output HTML file path (default: stdout)")
    args = parser.parse_args()

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(args.input).read_text(encoding="utf-8")

    data = json.loads(raw)
    html = build_html(data)

    if args.output:
        Path(args.output).write_text(html, encoding="utf-8")
        size = Path(args.output).stat().st_size
        print(f"HTML report written: {args.output} ({size:,} bytes)", file=sys.stderr)
    else:
        print(html)


if __name__ == "__main__":
    main()
