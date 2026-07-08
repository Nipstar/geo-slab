#!/usr/bin/env python3
"""
GEO SLAB — Free AI Visibility Check report renderer.

One page. Neo brutalist system (coral / cream / sage / charcoal, Outfit +
DM Sans + JetBrains Mono, zero border-radius, hard offset shadows) to match
the other GEO SLAB deliverables.

Frozen scope (spec §7): verdict, per-platform mention grid, competitor list,
walkthrough CTA. No scores beyond the blunt visibility number, no fixes.

    from render_check_report import render
    render(result_dict, Path("reports/acme.com"), pdf=True)

Standalone:
    python3 render_check_report.py check.json reports/acme.com/
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

CORAL = "#CD5C3C"
CREAM = "#E8DCC8"
SAGE = "#C8D8D0"
CHARCOAL = "#2C2C2C"
CONTACT_URL = "https://antekautomation.com/contact"
PHONE = "0333 038 9960"


def _verdict_colour(platforms_mentioned: int) -> str:
    if platforms_mentioned <= 1:
        return CORAL
    if platforms_mentioned == 2:
        return CHARCOAL
    return SAGE


def render_html(result: dict) -> str:
    e = html.escape
    company = e(result["company"])
    town = e(result.get("town", ""))
    industry = e(result.get("industry", ""))
    date = e(result["run_at"][:10])
    tested = result["platforms_tested"]
    mentioned = result["platforms_mentioned"]
    verdict_colour = _verdict_colour(mentioned)

    # Platform grid
    cards = []
    for p in result["platforms"]:
        if not p["tested"]:
            mark, tone, note = "—", "#999", "Not reached"
        elif p["mentioned"]:
            mark, tone = "✓", SAGE
            note = e(p["snippet"][:140]) if p["snippet"] else "Mentioned"
        else:
            mark, tone = "✗", CORAL
            note = "Did not come up"
        cards.append(f"""
        <div class="card" style="border-color:{tone}">
          <div class="card-head"><span class="mark" style="color:{tone}">{mark}</span>{e(p['platform'])}</div>
          <p class="card-note">{note}</p>
        </div>""")
    grid = "\n".join(cards)

    # Competitors — gate to genuine rival firms only: no directories, no page
    # labels, and never the prospect's own name variant (self-mention).
    import prospect_config
    valid_names = set(prospect_config.valid_competitors(
        [c["name"] for c in result["competitors"]], brand=result["company"]))
    comps = [c for c in result["competitors"] if c["name"] in valid_names]
    if comps:
        rows = "\n".join(
            f'<li><span class="comp-name">{e(c["name"])}</span>'
            f'<span class="comp-count">named {c["mentions"]}×</span></li>'
            for c in comps
        )
        competitors_block = f"""
        <section class="block">
          <h2>Who AI recommended instead</h2>
          <ul class="comp-list">{rows}</ul>
        </section>"""
    else:
        competitors_block = ""

    # Proof transcript — the verbatim questions and AI answers. This is what
    # makes the report usable in a meeting: receipts, not just a score.
    proof_plats = []
    brand_lower = result["company"].lower()
    for p in result["platforms"]:
        if not p.get("tested"):
            continue
        qa = []
        for r in p.get("responses", []):
            ans = (r.get("response") or "").strip()
            if not ans:
                ans, tone, tag = "No answer returned.", "#999", "no answer"
            elif r.get("mentioned"):
                tone, tag = SAGE, "named you"
            else:
                tone, tag = CORAL, "did not name you"
            if len(ans) > 900:
                ans = ans[:900].rsplit(" ", 1)[0] + " …"
            qa.append(
                f'<div class="qa">'
                f'<div class="q">{e(r["prompt"])}</div>'
                f'<div class="qtag" style="color:{tone}">{tag}</div>'
                f'<div class="a">{e(ans)}</div></div>')
        proof_plats.append(
            f'<div class="proof-plat"><h3>{e(p["platform"])} '
            f'<span class="model">{e(p.get("model",""))}</span></h3>{"".join(qa)}</div>')
    proof_block = f"""
        <section class="block proof">
          <h2>What we asked, and what the AI said</h2>
          <p class="proof-intro">The exact questions put to each engine on {date}, and their answers word for word. This is what a prospective client sees when they ask AI to recommend {industry} in {town}.</p>
          {"".join(proof_plats)}
        </section>""" if proof_plats else ""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Visibility Check — {company}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@600;800&family=DM+Sans:wght@400;500&family=JetBrains+Mono:wght@600&display=swap" rel="stylesheet">
<style>
  @page {{ size:A4; margin:0; }}
  * {{ margin:0; padding:0; box-sizing:border-box; border-radius:0 !important; }}
  body {{ font-family:'DM Sans',sans-serif; background:{CREAM}; color:{CHARCOAL}; line-height:1.4; padding:26px 34px; }}
  .page {{ max-width:740px; margin:0 auto; }}
  header {{ border-bottom:4px solid {CHARCOAL}; padding-bottom:12px; margin-bottom:18px;
            display:flex; justify-content:space-between; align-items:flex-end; }}
  h1 {{ font-family:'Outfit',sans-serif; font-weight:800; font-size:23px; text-transform:uppercase; letter-spacing:-0.5px; }}
  .sub {{ font-family:'JetBrains Mono',monospace; font-size:11px; color:#555; margin-top:4px; }}
  .brand {{ font-family:'Outfit',sans-serif; font-weight:600; font-size:12px; text-align:right; }}
  .verdict {{ background:{verdict_colour}; color:#fff; padding:20px; margin-bottom:18px;
              box-shadow:7px 7px 0 {CHARCOAL}; }}
  .verdict .big {{ font-family:'Outfit',sans-serif; font-weight:800; font-size:25px; line-height:1.15; }}
  .verdict .score {{ font-family:'JetBrains Mono',monospace; font-size:12px; margin-top:8px; opacity:0.9; }}
  h2 {{ font-family:'Outfit',sans-serif; font-weight:600; font-size:14px; text-transform:uppercase;
        letter-spacing:0.5px; margin-bottom:10px; }}
  .block {{ margin-bottom:18px; }}
  .grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:10px; }}
  .card {{ background:#fff; border:3px solid; padding:12px; box-shadow:4px 4px 0 {CHARCOAL}; }}
  .card-head {{ font-family:'Outfit',sans-serif; font-weight:600; font-size:15px; display:flex; align-items:center; gap:8px; }}
  .mark {{ font-size:20px; font-weight:800; }}
  .card-note {{ font-size:12px; color:#555; margin-top:6px; font-style:italic; }}
  .comp-list {{ list-style:none; }}
  .comp-list li {{ display:flex; justify-content:space-between; padding:7px 12px; background:#fff;
                   border:2px solid {CHARCOAL}; margin-bottom:6px; }}
  .comp-name {{ font-family:'Outfit',sans-serif; font-weight:600; font-size:14px; }}
  .comp-count {{ font-family:'JetBrains Mono',monospace; font-size:11px; color:{CORAL}; }}
  .proof {{ page-break-before:always; }}
  .proof-intro {{ font-size:12px; color:#555; margin-bottom:14px; }}
  .proof-plat {{ margin-bottom:16px; }}
  .proof-plat h3 {{ font-family:'Outfit',sans-serif; font-weight:800; font-size:14px; text-transform:uppercase;
                    letter-spacing:0.3px; border-bottom:2px solid {CHARCOAL}; padding-bottom:5px; margin-bottom:10px; }}
  .proof-plat h3 .model {{ font-family:'JetBrains Mono',monospace; font-weight:400; font-size:9px; color:#888; text-transform:none; letter-spacing:0; }}
  .qa {{ background:#fff; border:2px solid {CHARCOAL}; padding:10px 12px; margin-bottom:9px; box-shadow:3px 3px 0 {CHARCOAL}; page-break-inside:avoid; }}
  .qa .q {{ font-family:'Outfit',sans-serif; font-weight:600; font-size:12.5px; margin-bottom:3px; }}
  .qa .q::before {{ content:"Q  "; font-family:'JetBrains Mono',monospace; color:{CORAL}; font-weight:600; }}
  .qa .qtag {{ font-family:'JetBrains Mono',monospace; font-size:9px; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px; }}
  .qa .a {{ font-size:11.5px; color:#333; white-space:pre-wrap; }}
  .cta {{ background:{CHARCOAL}; color:{CREAM}; padding:20px; box-shadow:7px 7px 0 {CORAL}; }}
  .cta h2 {{ color:{CREAM}; }}
  .cta p {{ font-size:13px; margin-bottom:12px; }}
  .cta a {{ color:{SAGE}; font-family:'JetBrains Mono',monospace; font-weight:600; text-decoration:none; }}
  footer {{ margin-top:18px; font-family:'JetBrains Mono',monospace; font-size:10px; color:#777; text-align:center; }}
</style></head>
<body><div class="page">
  <header>
    <div>
      <h1>AI Visibility Check</h1>
      <div class="sub">{company} · {industry} · {town} · {date}</div>
    </div>
    <div class="brand">GEO SLAB<br><span style="color:{CORAL}">by Antek Automation</span></div>
  </header>

  <div class="verdict">
    <div class="big">AI mentioned you on {mentioned} of {tested} platforms.</div>
    <div class="score">Visibility score: {result['visibility_score']}/100 · asked ChatGPT, Claude, Gemini and Perplexity who they recommend for {industry} in {town}</div>
  </div>

  <section class="block">
    <h2>What each engine said</h2>
    <div class="grid">{grid}</div>
  </section>

  {competitors_block}

  {proof_block}

  <section class="cta">
    <h2>See it live</h2>
    <p>Book a 15-minute walkthrough. We run these checks live and show you exactly what the AI engines see when someone looks for a {industry} in {town}.</p>
    <a href="{CONTACT_URL}">{CONTACT_URL}</a> &nbsp; · &nbsp; <a href="tel:03330389960">{PHONE}</a>
  </section>

  <footer>Based on {result['prompts_total']} genuine live AI responses captured {date} via ChatGPT, Claude, Gemini and Perplexity. No results are estimated or fabricated.<br>GEO SLAB by Antek Automation · antekautomation.com</footer>
</div></body></html>"""


def render(result: dict, out_dir: Path, pdf: bool = True) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    domain = result["domain"]
    html_content = render_html(result)
    html_path = out_dir / f"AI-CHECK-{domain}.html"
    html_path.write_text(html_content, encoding="utf-8")
    paths = {"html": str(html_path)}
    if pdf:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from generate_pdf_report import html_to_pdf
        pdf_path = out_dir / f"AI-CHECK-{domain}.pdf"
        html_to_pdf(html_content, str(pdf_path))
        paths["pdf"] = str(pdf_path)
    return paths


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: render_check_report.py <check.json> <out_dir> [--no-pdf]", file=sys.stderr)
        sys.exit(2)
    result = json.loads(Path(sys.argv[1]).read_text())
    paths = render(result, Path(sys.argv[2]), pdf="--no-pdf" not in sys.argv)
    print(json.dumps(paths, indent=2))


if __name__ == "__main__":
    main()
