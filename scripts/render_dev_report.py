#!/usr/bin/env python3
"""
GEO SLAB — Developer / Agency Technical Report Renderer.

Sibling to render_geo_report.py. Same JSON input — different audience.

Where the client renderer pulls `client_summary` (plain English) and prints a
report a managing partner can read cover-to-cover without ever seeing the word
"JSON-LD", this renderer pulls `technical_findings` and prints the exact
instructions a developer or agency needs to act:

    [Plain-English fix]                  [Technical instruction]

Output is intentionally less brand-heavy than the client report — mono labels,
code blocks, a tighter colour palette, file paths and headers rendered as-is.

Usage:
    python render_dev_report.py data.json [output.html]

JSON schema (additions over the client renderer):
    {
      ...,
      "technical_findings": [
        {
          "slug":     "no_entity_schema",
          "severity": "CRITICAL",
          "title":    "No Organisation / LegalService JSON-LD",
          "detail":   "Only Yoast defaults present. Schema types: WebPage, ...",
          "fix":      "Inject Organisation + LegalService JSON-LD sitewide ..."
        }
      ],
      "client_summary": [
        {"slug": "no_entity_schema", "title": "AI can't confirm ...", "description": "..."}
      ]
    }
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html import escape as he
from pathlib import Path

# Voice / labels — same source of truth as the client renderer.
sys.path.insert(0, str(Path(__file__).parent))
from style import (  # noqa: E402
    score_band as _score_band,
    score_label as _score_label,
    DEV_LABELS,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def domain_from_url(url: str) -> str:
    return re.sub(r"https?://(www\.)?", "", url).rstrip("/").split("/")[0]


def score_verdict(score: int) -> str:
    return _score_band(score)["verdict"]


def score_label(score: int) -> str:
    return _score_label(score)


# ── Component builders ──────────────────────────────────────────────────────

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _client_lookup(data: dict) -> dict:
    """Index client_summary entries by slug so the two-column layout can pair them."""
    cs = data.get("client_summary") or data.get("findings") or []
    out = {}
    for entry in cs:
        slug = entry.get("slug") or ""
        if slug:
            out[slug] = entry
    return out


def technical_rows_html(tech_findings: list, client_index: dict) -> str:
    """Render the two-column hand-off table.

    Left = plain-English fix headline (from client_summary by slug, if present).
    Right = technical instruction (detail + fix from technical_findings).
    """
    if not tech_findings:
        return '<p class="empty">No technical findings recorded. Re-run the audit to populate this section.</p>'

    sorted_findings = sorted(
        tech_findings,
        key=lambda f: SEVERITY_ORDER.get(f.get("severity", "MEDIUM").upper(), 9),
    )

    rows = []
    for i, f in enumerate(sorted_findings, 1):
        sev = f.get("severity", "MEDIUM").upper()
        sev_cls = sev.lower()
        slug = f.get("slug") or ""
        tech_title = he(f.get("title", ""))
        tech_detail = he(f.get("detail", ""))
        tech_fix = he(f.get("fix", ""))

        client = client_index.get(slug, {})
        client_title = he(client.get("title") or f.get("title", ""))
        client_desc = he(client.get("description") or "")

        rows.append(f'''
        <article class="hand-off-row sev-{sev_cls}">
            <div class="row-meta">
                <div class="row-num">{i:02d}</div>
                <div class="row-sev">{sev}</div>
                <div class="row-slug">{he(slug)}</div>
            </div>
            <div class="row-client">
                <h3>{client_title}</h3>
                <p>{client_desc}</p>
            </div>
            <div class="row-tech">
                <h4>Technical detail</h4>
                <pre class="tech-detail">{tech_detail}</pre>
                <h4>Fix instruction</h4>
                <pre class="tech-fix">{tech_fix}</pre>
            </div>
        </article>''')
    return "".join(rows)


def category_scores_table(scores: dict) -> str:
    rows = []
    for label, score in scores.items():
        display = DEV_LABELS.get(label, label)
        rows.append(
            f'<tr><td>{he(display)}</td>'
            f'<td class="num">{score}/100</td>'
            f'<td>{score_label(score)}</td></tr>'
        )
    return "".join(rows)


def platforms_table(platforms: dict) -> str:
    rows = []
    for name, score in platforms.items():
        rows.append(
            f'<tr><td>{he(name)}</td>'
            f'<td class="num">{score}/100</td>'
            f'<td>{score_label(score)}</td></tr>'
        )
    return "".join(rows)


# ── CSS ─────────────────────────────────────────────────────────────────────

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }

:root {
    --ink:        #111;
    --paper:      #FAF8F5;
    --rule:       #111;
    --coral:      #D9533A;
    --sage:       #5F7A6E;
    --amber:      #C28526;
    --mute:       #6E6E6E;
    --pre-bg:     #1C1C1C;
    --pre-ink:    #E8DFD0;
}

html { scroll-behavior: smooth; }

body {
    background: var(--paper);
    color: var(--ink);
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 14px;
    line-height: 1.55;
}

main { padding: 56px 64px 88px; max-width: 980px; margin: 0 auto; }

.title-band {
    border-bottom: 3px solid var(--rule);
    padding-bottom: 32px;
    margin-bottom: 40px;
}

.title-band .kicker {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: var(--coral);
    margin-bottom: 16px;
    display: block;
}

h1 {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900;
    font-size: 56px;
    line-height: 0.95;
    margin-bottom: 12px;
}

.title-meta {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--mute);
    margin-top: 12px;
}

.title-meta span + span { margin-left: 24px; }

h2 {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900;
    font-size: 28px;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    margin: 40px 0 16px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--rule);
}

p.intro {
    font-size: 14px;
    color: var(--mute);
    margin-bottom: 20px;
    max-width: 720px;
}

table.scores {
    width: 100%;
    border-collapse: collapse;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    margin-bottom: 24px;
}
table.scores th, table.scores td {
    border: 1px solid var(--rule);
    padding: 8px 12px;
    text-align: left;
}
table.scores th { background: var(--ink); color: var(--paper); }
table.scores td.num { font-variant-numeric: tabular-nums; }

.hand-off-row {
    display: grid;
    grid-template-columns: 110px 1fr 1.6fr;
    gap: 18px;
    border: 1.5px solid var(--rule);
    margin-bottom: 14px;
    padding: 16px 18px;
    background: #fff;
    page-break-inside: avoid;
}

.hand-off-row.sev-critical { border-left: 6px solid var(--coral); }
.hand-off-row.sev-high     { border-left: 6px solid var(--amber); }
.hand-off-row.sev-medium   { border-left: 6px solid var(--sage); }
.hand-off-row.sev-low      { border-left: 6px solid var(--mute); }

.row-meta {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--mute);
}

.row-num {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900;
    font-size: 32px;
    color: var(--ink);
    line-height: 1;
    margin-bottom: 6px;
}

.row-sev {
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--coral);
    margin-bottom: 6px;
}

.hand-off-row.sev-high   .row-sev { color: var(--amber); }
.hand-off-row.sev-medium .row-sev { color: var(--sage); }
.hand-off-row.sev-low    .row-sev { color: var(--mute); }

.row-slug { word-break: break-all; }

.row-client h3 {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900;
    font-size: 19px;
    line-height: 1.15;
    margin-bottom: 8px;
    color: var(--ink);
}

.row-client p { font-size: 13.5px; color: #333; }

.row-tech h4 {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--mute);
    margin: 0 0 4px;
}
.row-tech h4 + pre { margin-bottom: 10px; }

pre.tech-detail, pre.tech-fix {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11.5px;
    line-height: 1.5;
    background: var(--pre-bg);
    color: var(--pre-ink);
    padding: 10px 12px;
    border: 1px solid var(--ink);
    white-space: pre-wrap;
    word-break: break-word;
}

p.empty {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    color: var(--mute);
    padding: 24px;
    border: 1px dashed var(--mute);
    text-align: center;
}

footer {
    margin-top: 60px;
    padding-top: 24px;
    border-top: 2px solid var(--rule);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: var(--mute);
    display: flex;
    justify-content: space-between;
    gap: 24px;
}

@media print {
    body { font-size: 12.5px; }
    main { padding: 32px 32px 56px; max-width: none; }
    h1 { font-size: 42px; }
    .hand-off-row { grid-template-columns: 90px 1fr 1.5fr; padding: 12px 14px; }
    pre.tech-detail, pre.tech-fix { font-size: 10.5px; }
}
"""


# ── Builder ─────────────────────────────────────────────────────────────────

def build_html(data: dict) -> str:
    brand = he(data.get("brand_name", "Unknown"))
    url = he(data.get("url", ""))
    domain = domain_from_url(data.get("url", ""))
    date = he(data.get("date", ""))
    geo_score = data.get("geo_score", 0)
    pages = data.get("pages_audited", None)

    scores = data.get("scores", {})
    platforms = data.get("platforms", {})

    tech = data.get("technical_findings") or []
    client_index = _client_lookup(data)

    pages_meta = f'<span>{pages} pages audited</span>' if pages else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{brand} — Developer Hand-off</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;700;900&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<main>

    <section class="title-band">
        <span class="kicker">For your developer or agency — {domain}</span>
        <h1>{brand}<br>Developer Hand-off</h1>
        <p class="intro">
            Technical companion to the client report. Same findings — translated into the language a web team or agency
            needs to act. Every entry pairs the plain-English fix headline (left) with the implementation detail and fix
            instruction (right). Composite GEO score: <strong>{geo_score}/100</strong> — {score_label(geo_score)}.
        </p>
        <p class="title-meta">
            <span>{url}</span>
            {pages_meta}
            <span>{date}</span>
        </p>
    </section>

    <h2>Category scores</h2>
    <table class="scores">
        <thead><tr><th>Category</th><th>Score</th><th>Band</th></tr></thead>
        <tbody>{category_scores_table(scores)}</tbody>
    </table>

    {('<h2>Per-platform scores</h2><table class="scores"><thead><tr><th>Platform</th><th>Score</th><th>Band</th></tr></thead><tbody>' + platforms_table(platforms) + '</tbody></table>') if platforms else ''}

    <h2>Hand-off — fix list</h2>
    <p class="intro">
        Sorted by severity. Plain-English headline on the left for context — the page the client read. Implementation
        detail and fix instruction on the right. Slugs match <code>scripts/style.py:ISSUE_COPY</code>.
    </p>
    {technical_rows_html(tech, client_index)}

    <footer>
        <span>GEO SLAB by Antek Automation — antekautomation.com</span>
        <span>Developer hand-off — confidential</span>
        <span>{date}</span>
    </footer>

</main>
</body>
</html>"""


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GEO SLAB — Developer hand-off HTML report")
    parser.add_argument("input", nargs="?", default="-", help="JSON data file path, or '-' for stdin")
    parser.add_argument("output", nargs="?", default=None, help="Output HTML file path (default: stdout)")
    args = parser.parse_args()

    raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
    data = json.loads(raw)
    html = build_html(data)

    if args.output:
        Path(args.output).write_text(html, encoding="utf-8")
        size = Path(args.output).stat().st_size
        print(f"Dev HTML report written: {args.output} ({size:,} bytes)", file=sys.stderr)
    else:
        print(html)


if __name__ == "__main__":
    main()
