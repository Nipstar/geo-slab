#!/usr/bin/env python3
"""
GEO SLAB — Neo Brutalist Proposal Renderer (Antek Automation)
Hardcoded tier: Standard.

Usage:
    python render_proposal.py audit-data.json output.html
"""

import sys
import json
import re
import argparse
from pathlib import Path
from html import escape as he


def score_label(s):
    if s >= 75: return "Good"
    if s >= 60: return "Fair"
    if s >= 40: return "Poor"
    return "Critical"


def score_cell_class(s):
    return " critical" if s < 30 else ""


def domain_from_url(u):
    return re.sub(r'https?://(www\.)?', '', u).rstrip('/').split('/')[0]


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

        .site-header {
            position: fixed; top: 0; left: 0; right: 0; z-index: 100;
            background: var(--charcoal);
            border-bottom: 3px solid var(--black);
            padding: 0 48px; height: 56px;
            display: flex; align-items: center; justify-content: space-between; gap: 24px;
        }
        .header-brand {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: 16px; color: var(--cream);
            text-transform: uppercase; letter-spacing: 0.1em; white-space: nowrap;
        }
        .header-nav { display: flex; gap: 28px; }
        .header-nav a {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 10px; color: var(--cream); text-decoration: none;
            text-transform: uppercase; letter-spacing: 0.12em;
            opacity: 0.55; transition: opacity 0.15s;
        }
        .header-nav a:hover { opacity: 1; }
        .header-score {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 13px; color: var(--coral); white-space: nowrap;
        }
        main { padding-top: 56px; }

        .hero {
            padding: 80px 64px 72px;
            border-bottom: 3px solid var(--black);
            display: grid; grid-template-columns: 1fr 1fr; gap: 64px; align-items: start;
        }
        .label {
            display: block; font-family: 'IBM Plex Mono', monospace;
            font-size: 11px; text-transform: uppercase; letter-spacing: 0.15em;
            color: var(--coral); margin-bottom: 20px;
        }
        h1 {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: clamp(64px, 9vw, 112px); line-height: 0.9; margin-bottom: 32px;
        }
        h1 .h1-line1, h1 .h1-line2 { display: block; }
        h1 .h1-line2 { color: var(--coral); }

        .hero-right { padding-top: 20px; }
        .hero-verdict { font-size: 22px; font-weight: 600; line-height: 1.35; margin-bottom: 24px; }
        .hero-body { font-size: 16px; line-height: 1.7; opacity: 0.85; }
        .hero-body p { margin-bottom: 14px; }
        .hero-body p:last-child { margin-bottom: 0; }

        .meta-strip {
            display: grid; grid-template-columns: repeat(4, 1fr);
            border-bottom: 3px solid var(--black);
        }
        .meta-cell {
            padding: 28px 24px; border-right: 3px solid var(--black);
            background: var(--off-white);
        }
        .meta-cell:last-child { border-right: none; }
        .meta-label {
            font-family: 'IBM Plex Mono', monospace; font-size: 10px;
            text-transform: uppercase; letter-spacing: 0.1em;
            opacity: 0.55; margin-bottom: 8px;
        }
        .meta-value {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: 26px; line-height: 1.1;
        }

        .score-grid {
            display: grid; grid-template-columns: repeat(6, 1fr);
            border-bottom: 3px solid var(--black);
        }
        .score-cell {
            border-right: 3px solid var(--black);
            padding: 28px 24px 24px; background: var(--off-white);
        }
        .score-cell:last-child { border-right: none; }
        .score-cell.critical { background: var(--coral); }
        .score-cell.critical .cell-label,
        .score-cell.critical .cell-number { color: var(--cream); }
        .score-cell.critical .cell-denom { color: var(--cream); opacity: 0.45; }
        .score-cell.critical .cell-bar { background: rgba(255,255,255,0.2); }
        .score-cell.critical .cell-bar-fill { background: var(--cream); }
        .cell-label {
            display: block; font-family: 'IBM Plex Mono', monospace;
            font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em;
            opacity: 0.55; margin-bottom: 14px; line-height: 1.4;
        }
        .cell-number {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: 52px; line-height: 1;
        }
        .cell-denom { font-size: 22px; font-weight: 700; opacity: 0.3; }
        .cell-bar { height: 3px; background: rgba(0,0,0,0.12); margin-top: 16px; position: relative; }
        .cell-bar-fill { position: absolute; top: 0; left: 0; height: 100%; background: var(--charcoal); }
        .cell-status {
            font-family: 'IBM Plex Mono', monospace; font-size: 10px;
            text-transform: uppercase; letter-spacing: 0.08em;
            margin-top: 10px; opacity: 0.55;
        }

        .section { border-bottom: 3px solid var(--black); padding: 72px 64px; }
        h2 {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: clamp(44px, 6vw, 72px); line-height: 0.92; margin-bottom: 12px;
        }
        .section-intro {
            font-size: 17px; opacity: 0.75;
            margin-bottom: 40px; max-width: 720px; line-height: 1.65;
        }
        .section p + p { margin-top: 14px; }

        /* TIER BLOCK */
        .tier-block {
            border: 3px solid var(--black);
            box-shadow: var(--shadow);
            background: var(--off-white);
            padding: 0;
            margin-bottom: 48px;
        }
        .tier-head {
            padding: 32px 40px;
            border-bottom: 3px solid var(--black);
            background: var(--coral);
            color: var(--cream);
        }
        .tier-eyebrow {
            font-family: 'IBM Plex Mono', monospace; font-size: 11px;
            text-transform: uppercase; letter-spacing: 0.15em;
            opacity: 0.85; margin-bottom: 10px;
        }
        .tier-title {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: 48px; line-height: 1; margin-bottom: 12px;
        }
        .tier-pitch { font-size: 16px; line-height: 1.55; max-width: 780px; opacity: 0.95; }

        .tier-body { padding: 40px; }
        .tier-body h3 {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: 22px; text-transform: uppercase; letter-spacing: 0.05em;
            margin-bottom: 16px;
        }
        .tier-body h3 + h3 { margin-top: 32px; }
        .tier-incl { list-style: none; padding: 0; }
        .tier-incl li {
            position: relative; padding: 10px 0 10px 28px;
            font-size: 15px; line-height: 1.55;
            border-bottom: 1px dashed rgba(0,0,0,0.18);
        }
        .tier-incl li:last-child { border-bottom: none; }
        .tier-incl li::before {
            content: ""; position: absolute; left: 0; top: 18px;
            width: 12px; height: 3px; background: var(--coral);
        }

        .timeline {
            display: grid; grid-template-columns: 1fr; margin-top: 12px;
            border: 3px solid var(--black);
        }
        .timeline-row {
            display: grid; grid-template-columns: 56px 140px 1fr 140px;
            gap: 24px; padding: 28px 32px;
            border-bottom: 3px solid var(--black);
            background: var(--off-white);
            align-items: start;
        }
        .timeline-row:last-child { border-bottom: none; }
        .timeline-row:nth-child(even) { background: var(--cream); }
        .timeline-num {
            font-family: 'IBM Plex Mono', monospace; font-weight: 500;
            font-size: 22px; color: var(--coral);
        }
        .timeline-phase {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: 22px; text-transform: uppercase; letter-spacing: 0.04em;
            line-height: 1.1;
        }
        .timeline-phase small {
            display: block; font-family: 'IBM Plex Mono', monospace;
            font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em;
            opacity: 0.55; margin-top: 6px; font-weight: 500;
        }
        .timeline-focus { font-size: 15px; line-height: 1.55; }
        .timeline-impact {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: 26px; color: var(--coral); text-align: right; line-height: 1;
        }
        .timeline-impact small {
            display: block; font-family: 'IBM Plex Mono', monospace;
            font-size: 9px; text-transform: uppercase; letter-spacing: 0.1em;
            color: var(--charcoal); opacity: 0.5; margin-top: 6px; font-weight: 500;
        }

        .projection {
            margin-top: 32px;
            padding: 32px 40px;
            background: var(--sage);
            border: 3px solid var(--black);
            display: flex; gap: 32px; align-items: center; justify-content: space-between;
            flex-wrap: wrap;
        }
        .projection-label {
            font-family: 'IBM Plex Mono', monospace; font-size: 11px;
            text-transform: uppercase; letter-spacing: 0.15em; opacity: 0.7;
        }
        .projection-num {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: 64px; line-height: 1;
        }
        .projection-num small { font-size: 26px; opacity: 0.45; }
        .projection-arrow {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: 48px; color: var(--coral);
        }

        /* PROBLEMS */
        .problem-list { display: grid; }
        .problem-item {
            border: 3px solid var(--black); border-bottom: none;
            padding: 32px 36px;
            display: grid; grid-template-columns: 72px 1fr; gap: 28px;
            align-items: start; background: var(--off-white);
        }
        .problem-item:last-child { border-bottom: 3px solid var(--black); }
        .problem-item.is-critical { background: var(--coral); }
        .problem-item.is-critical .problem-num,
        .problem-item.is-critical h3,
        .problem-item.is-critical p { color: var(--cream); }
        .problem-num {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: 56px; line-height: 1; opacity: 0.15; padding-top: 4px;
        }
        .problem-content h3 {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: 26px; line-height: 1.05; margin-bottom: 12px;
        }
        .problem-content p { font-size: 15px; line-height: 1.6; }

        /* ALT TIERS */
        .alt-grid {
            display: grid; grid-template-columns: 1fr 1fr; gap: 0;
            border: 3px solid var(--black);
        }
        .alt-cell {
            padding: 32px 36px; background: var(--off-white);
        }
        .alt-cell:first-child { border-right: 3px solid var(--black); }
        .alt-name {
            font-family: 'IBM Plex Mono', monospace; font-size: 11px;
            text-transform: uppercase; letter-spacing: 0.15em;
            color: var(--coral); margin-bottom: 10px;
        }
        .alt-cell h3 {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: 32px; line-height: 1; margin-bottom: 14px;
        }
        .alt-cell p { font-size: 15px; line-height: 1.6; }

        /* STATS */
        .stats-grid {
            display: grid; grid-template-columns: repeat(3, 1fr);
            border: 3px solid var(--black); box-shadow: var(--shadow);
        }
        .stat-cell {
            padding: 32px 28px; border-right: 3px solid var(--black);
            border-bottom: 3px solid var(--black); background: var(--off-white);
        }
        .stat-cell:nth-child(3n) { border-right: none; }
        .stat-cell:nth-last-child(-n+3) { border-bottom: none; }
        .stat-num {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: 44px; line-height: 1; color: var(--coral);
            margin-bottom: 10px;
        }
        .stat-text { font-size: 14px; line-height: 1.5; opacity: 0.85; }

        /* NEXT STEPS */
        .steps {
            display: grid; grid-template-columns: repeat(2, 1fr);
            gap: 0; border: 3px solid var(--black);
        }
        .step {
            padding: 28px 32px; border-right: 3px solid var(--black);
            border-bottom: 3px solid var(--black); background: var(--off-white);
        }
        .step:nth-child(2n) { border-right: none; }
        .step:nth-last-child(-n+2) { border-bottom: none; }
        .step-num {
            font-family: 'IBM Plex Mono', monospace; font-size: 12px;
            color: var(--coral); margin-bottom: 8px;
            letter-spacing: 0.1em;
        }
        .step h3 {
            font-family: 'Barlow Condensed', sans-serif; font-weight: 900;
            font-size: 22px; line-height: 1.05; margin-bottom: 8px;
        }
        .step p { font-size: 14.5px; line-height: 1.55; opacity: 0.85; }

        /* FOOTER */
        .site-footer {
            padding: 40px 64px;
            font-family: 'IBM Plex Mono', monospace; font-size: 11px;
            opacity: 0.4;
            display: flex; justify-content: space-between; gap: 32px;
        }

        @media print {
            .site-header { position: static; }
            main { padding-top: 0; }
            .score-grid { grid-template-columns: repeat(3, 1fr); }
            .alt-grid, .steps { grid-template-columns: 1fr; }
            .stats-grid { grid-template-columns: 1fr; }
            .meta-strip { grid-template-columns: repeat(2, 1fr); }
        }

        @media (max-width: 900px) {
            .site-header { padding: 0 24px; }
            .header-nav { display: none; }
            .hero { grid-template-columns: 1fr; gap: 32px; padding: 48px 24px; }
            .meta-strip { grid-template-columns: repeat(2, 1fr); }
            .meta-cell:nth-child(2) { border-right: none; }
            .score-grid { grid-template-columns: repeat(2, 1fr); }
            .section { padding: 48px 24px; }
            .timeline-row { grid-template-columns: 1fr; gap: 12px; padding: 24px; }
            .timeline-impact { text-align: left; }
            .alt-grid, .steps { grid-template-columns: 1fr; }
            .alt-cell:first-child, .step { border-right: none; }
            .stats-grid { grid-template-columns: 1fr; }
            .stat-cell { border-right: none; }
            .problem-item { grid-template-columns: 48px 1fr; gap: 16px; padding: 24px; }
            .site-footer { flex-direction: column; padding: 32px 24px; }
        }
"""


# ── Hardcoded Standard tier content ──────────────────────────────────────

STANDARD_TIER = {
    "eyebrow": "Recommended Service",
    "title": "Standard — Full GEO Optimization Program",
    "pitch": "Your foundations are too strong for a heavy Premium intervention, but the gaps span four categories and won't close from a one-off retainer. The Standard program runs a structured 6-month sequence with monthly measurement.",
    "included": [
        "Monthly GEO audit and score tracking with the /geo compare delta report",
        "llms.txt maintenance and expansion as new service pages, portfolios, and blog content go live",
        "Schema.org monitoring across the whole site — Article/BlogPosting, FAQPage on every service page, Person schema for the team page, sameAs corrections, ongoing validation",
        "Weekly content recommendations for AI citability — rewriting service-page blocks into the 134–167 word optimal-length band plus new cornerstone definition pages",
        "Platform-specific optimization across all 9 AI engines — AI Overviews, ChatGPT, Perplexity, Gemini, Bing Copilot, Grok, DeepSeek, Meta AI, Mistral",
        "Brand mention strategy and tracking — Wikidata entity build, GBP claim and optimisation for both offices, Trustpilot and G2 seeding, press outreach for Wikipedia notability",
        "Bi-weekly strategy calls with the Antek Automation lead and a shared progress dashboard",
        "Competitor visibility monitoring against your top three regional rivals, refreshed every month",
    ],
}

TIMELINE_PHASES = [
    {
        "num": "01",
        "phase": "Foundation",
        "weeks": "Weeks 1–2",
        "focus": "Critical fixes — robots.txt unblocks (ClaudeBot, anthropic-ai, FacebookBot, Amazonbot), cookie banner rework so AI crawlers see hydrated DOM, PSI quick wins (defer unused CSS/JS, hero PNG defer, explicit image dims), sitemap host fix, LinkedIn canonical, claim both Google Business Profiles.",
        "impact": "+10–14",
    },
    {
        "num": "02",
        "phase": "Optimization",
        "weeks": "Weeks 3–8",
        "focus": "FAQPage schema on every service page, Article schema on blog posts, Person schema on team page, restructure top 10 long-form blocks into 150-word Q&A sub-answers, build 3 cornerstone definition pages, seed Trustpilot + G2 review pages.",
        "impact": "+12–18",
    },
    {
        "num": "03",
        "phase": "Growth",
        "weeks": "Months 3–6",
        "focus": "Wikidata entity build, press outreach for Wikipedia notability, YouTube content programme (highest correlation with AI citation rates), monthly citability sweeps, ongoing measurement and reporting.",
        "impact": "+8–12",
    },
]

ALT_TIERS = [
    {
        "name": "Lighter Alternative",
        "title": "Basic — Monthly GEO Monitoring",
        "desc": "Fixed-scope monthly audit, llms.txt and schema monitoring, the /geo compare delta report, and email support. Right for the maintenance phase after Standard has done the heavy lifting — not the right shape for closing a 22-point gap from a Poor score.",
    },
    {
        "name": "Heavier Alternative",
        "title": "Premium — Complete GEO Transformation",
        "desc": "Everything in Standard plus daily AI visibility monitoring, in-house content production (4–6 long-form articles a month), full Wikipedia and Wikidata entity build, community presence strategy on Reddit and industry forums, dedicated Slack channel, and quarterly executive briefing.",
    },
]

MARKET_STATS = [
    {"num": "$4.3B", "text": "Projected GEO market by 2031 (34% CAGR from $850M in 2025)"},
    {"num": "4.4×", "text": "Higher conversion rate of AI-referred traffic versus traditional organic search"},
    {"num": "1.5B", "text": "Monthly users reached by Google AI Overviews across 200+ countries"},
    {"num": "900M", "text": "Weekly active users searching with ChatGPT"},
    {"num": "50%", "text": "Projected drop in traditional search traffic by 2028 (Gartner)"},
    {"num": "23%", "text": "Share of marketers currently investing in GEO — early-mover advantage is open"},
]

NEXT_STEPS = [
    {"num": "STEP 01", "title": "Review this proposal", "desc": "Send any questions and flag areas you want expanded before the review call."},
    {"num": "STEP 02", "title": "Schedule a 30-minute review call", "desc": "Walk through findings, sequence the priorities, and align on the Standard scope."},
    {"num": "STEP 03", "title": "Confirm scope and timeline", "desc": "We can begin Phase 1 within five working days of agreement."},
    {"num": "STEP 04", "title": "Phase 1 kickoff", "desc": "Immediate action on the seven quick wins plus Core Web Vitals work."},
]


def score_cells_html(scores):
    out = []
    for k, v in scores.items():
        cls = score_cell_class(v)
        out.append(f"""
            <div class="score-cell{cls}">
                <span class="cell-label">{he(k)}</span>
                <div class="cell-number">{v}<span class="cell-denom">/100</span></div>
                <div class="cell-bar"><div class="cell-bar-fill" style="width:{v}%"></div></div>
                <div class="cell-status">{score_label(v)}</div>
            </div>""")
    return "".join(out)


def findings_html(findings, limit=3):
    items = []
    for i, f in enumerate(findings[:limit], 1):
        sev = f.get("severity", "MEDIUM").upper()
        is_crit = " is-critical" if sev == "CRITICAL" else ""
        items.append(f"""
                <div class="problem-item{is_crit}">
                    <div class="problem-num">{i:02d}</div>
                    <div class="problem-content">
                        <h3>{he(f.get('title',''))}</h3>
                        <p>{he(f.get('description',''))}</p>
                    </div>
                </div>""")
    return "".join(items)


def tier_incl_html():
    return "".join(f"<li>{he(s)}</li>" for s in STANDARD_TIER["included"])


def timeline_html():
    rows = []
    for p in TIMELINE_PHASES:
        rows.append(f"""
            <div class="timeline-row">
                <div class="timeline-num">{p['num']}</div>
                <div class="timeline-phase">{he(p['phase'])}<small>{he(p['weeks'])}</small></div>
                <div class="timeline-focus">{he(p['focus'])}</div>
                <div class="timeline-impact">{he(p['impact'])}<small>Score impact</small></div>
            </div>""")
    return "".join(rows)


def alt_html():
    out = []
    for t in ALT_TIERS:
        out.append(f"""
            <div class="alt-cell">
                <div class="alt-name">{he(t['name'])}</div>
                <h3>{he(t['title'])}</h3>
                <p>{he(t['desc'])}</p>
            </div>""")
    return "".join(out)


def stats_html():
    return "".join(f"""
            <div class="stat-cell">
                <div class="stat-num">{he(s['num'])}</div>
                <div class="stat-text">{he(s['text'])}</div>
            </div>""" for s in MARKET_STATS)


def steps_html():
    return "".join(f"""
            <div class="step">
                <div class="step-num">{he(s['num'])}</div>
                <h3>{he(s['title'])}</h3>
                <p>{he(s['desc'])}</p>
            </div>""" for s in NEXT_STEPS)


def build_html(data):
    brand = he(data.get("brand_name", "Unknown"))
    url = he(data.get("url", ""))
    domain = domain_from_url(data.get("url", ""))
    date = he(data.get("date", ""))
    geo_score = data.get("geo_score", 0)
    pages = data.get("pages_audited", None)
    summary = data.get("summary", [])
    scores = data.get("scores", {})
    findings = data.get("findings", [])
    n_crit = sum(1 for f in findings if f.get("severity","").upper()=="CRITICAL")
    n_high = sum(1 for f in findings if f.get("severity","").upper()=="HIGH")

    if isinstance(summary, list):
        summary_p = "".join(f"<p>{he(p)}</p>" for p in summary[:3])
    else:
        summary_p = f"<p>{he(summary)}</p>"

    verdict = f"You scored {geo_score}/100 — {score_label(geo_score)}. The foundations are strong; four high-impact failures are blocking AI engines from citing you."

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GEO Proposal — {brand}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;700;900&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>{CSS}</style>
</head>
<body>

    <header class="site-header">
        <div class="header-brand">{brand} — GEO Proposal</div>
        <nav class="header-nav">
            <a href="#summary">Summary</a>
            <a href="#performance">Performance</a>
            <a href="#problems">Problems</a>
            <a href="#service">Service</a>
            <a href="#timeline">Timeline</a>
            <a href="#next">Next steps</a>
        </nav>
        <div class="header-score">{geo_score}/100 — {date}</div>
    </header>

    <main>

        <section class="hero" id="summary">
            <div class="hero-left">
                <span class="label">Prepared for {brand} · {date}</span>
                <h1><span class="h1-line1">geo</span><span class="h1-line2">proposal.</span></h1>
            </div>
            <div class="hero-right">
                <p class="hero-verdict">{he(verdict)}</p>
                <div class="hero-body">{summary_p}</div>
            </div>
        </section>

        <div class="meta-strip">
            <div class="meta-cell">
                <div class="meta-label">Prepared for</div>
                <div class="meta-value">{brand}</div>
            </div>
            <div class="meta-cell">
                <div class="meta-label">Website</div>
                <div class="meta-value">{he(domain)}</div>
            </div>
            <div class="meta-cell">
                <div class="meta-label">Date</div>
                <div class="meta-value">{date}</div>
            </div>
            <div class="meta-cell">
                <div class="meta-label">Prepared by</div>
                <div class="meta-value">Antek Automation</div>
            </div>
        </div>

        <section class="section" id="performance">
            <span class="label">Your current GEO performance</span>
            <h2>where you stand</h2>
            <p class="section-intro">Overall GEO Score: <strong>{geo_score}/100 — {score_label(geo_score)}</strong>. Six categories make up the composite. E-E-A-T and Schema already hit Good. The other four are the levers that move the headline number.</p>
            <div class="score-grid" style="border: 3px solid var(--black); box-shadow: var(--shadow); margin-top: 8px;">
                {score_cells_html(scores)}
            </div>
        </section>

        <section class="section" id="problems">
            <span class="label">What we found</span>
            <h2>three problems blocking you</h2>
            <p class="section-intro">{n_crit} critical issues, {n_high} high-priority issues, and a stack of quick wins. The three below are the headline failures the program addresses first.</p>
            <div class="problem-list">
                {findings_html(findings, 3)}
            </div>
        </section>

        <section class="section" id="service">
            <span class="label">Recommended service</span>
            <h2>the standard program</h2>
            <p class="section-intro">Built for a Poor-band score with strong foundations. Six-month structured sequence with monthly measurement and bi-weekly strategy calls.</p>
            <div class="tier-block">
                <div class="tier-head">
                    <div class="tier-eyebrow">{he(STANDARD_TIER['eyebrow'])}</div>
                    <div class="tier-title">{he(STANDARD_TIER['title'])}</div>
                    <p class="tier-pitch">{he(STANDARD_TIER['pitch'])}</p>
                </div>
                <div class="tier-body">
                    <h3>What's included</h3>
                    <ul class="tier-incl">{tier_incl_html()}</ul>
                </div>
            </div>
        </section>

        <section class="section" id="timeline">
            <span class="label">Implementation timeline</span>
            <h2>six months · three phases</h2>
            <p class="section-intro">Each phase has a defined focus and a target score lift. Cumulative projection lands {brand} in the Good band by month six.</p>
            <div class="timeline">{timeline_html()}</div>
            <div class="projection">
                <div>
                    <div class="projection-label">Today</div>
                    <div class="projection-num">{geo_score}<small>/100</small></div>
                </div>
                <div class="projection-arrow">→</div>
                <div>
                    <div class="projection-label">Projected after 6 months</div>
                    <div class="projection-num">75–80<small>/100</small></div>
                </div>
                <div>
                    <div class="projection-label">Band shift</div>
                    <div class="projection-num" style="color: var(--coral); font-size: 32px;">Poor → Good</div>
                </div>
            </div>
        </section>

        <section class="section" id="alternatives">
            <span class="label">Alternative service options</span>
            <h2>lighter · heavier</h2>
            <p class="section-intro">The Standard program is the recommendation. These two flank it for context.</p>
            <div class="alt-grid">{alt_html()}</div>
        </section>

        <section class="section" id="market">
            <span class="label">Why GEO matters now</span>
            <h2>the market</h2>
            <p class="section-intro">The AI search landscape is shifting faster than any reset since mobile. The numbers below are why the next twelve months matter more than the previous five.</p>
            <div class="stats-grid">{stats_html()}</div>
            <p style="margin-top: 32px; font-size: 16px; line-height: 1.65; max-width: 760px;">For an agency, the asymmetry is sharper still. The prompts that bring you clients — <em>"best Hampshire web agency"</em>, <em>"WordPress agency near me"</em>, <em>"SEO agency Reading"</em> — are AI-first prompts now. The agencies that optimise for AI citation in 2026 will be the ones the engines recommend by name in 2027.</p>
        </section>

        <section class="section" id="next">
            <span class="label">Next steps</span>
            <h2>four steps to start</h2>
            <p class="section-intro">Phase 1 can begin within five working days of agreement.</p>
            <div class="steps">{steps_html()}</div>
        </section>

    </main>

    <footer class="site-footer">
        <span>GEO SLAB by Antek Automation — antekautomation.com</span>
        <span>{url} — {date}</span>
        <span>Confidential</span>
    </footer>

</body>
</html>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    html = build_html(data)
    Path(args.output).write_text(html, encoding="utf-8")
    print(f"Proposal HTML written: {args.output} ({Path(args.output).stat().st_size:,} bytes)", file=sys.stderr)


if __name__ == "__main__":
    main()
