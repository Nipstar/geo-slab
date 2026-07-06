#!/usr/bin/env python3
"""
2-page A4 postal mailer variant of the GEO prospect report — built for Stannp
direct mail. Page 1 = address zone + salutation + score + top 3 problems.
Page 2 = what's working + full-report teaser + QR to book a walkthrough.

Reuses the prospect-data.json (same top_problems / working / scores the screen
report uses, already run through STYLE.md voice). QR is fetched once from the
free qrserver API and base64-embedded, so the PDF is self-contained/offline.

    python3 render_prospect_mailer.py --data prospect-data.json --output DIR/ \
        --director "Mr Simon Allenby" \
        --recipient "Clifford Fry & Co|St Marys House, Netherhampton|Salisbury|SP2 8PU" \
        --qr-url https://antekautomation.com/contact --pdf

--recipient uses '|' as the line separator. --pdf prints via headless Chrome.
ponytail: single self-contained template; QR via hosted API (no installable qr lib available here).
"""
from __future__ import annotations
import argparse, base64, json, os, sys, urllib.request, urllib.parse, subprocess, tempfile
from datetime import datetime
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from style import score_band  # noqa: E402

COVERS = [
    "Where you're losing AI-driven enquiries, in plain English",
    "Your score across all six visibility areas",
    "Which of the nine AI engines you're missing from",
    "The three fixes worth doing first",
]


def qr_data_uri(url: str) -> str:
    api = ("https://api.qrserver.com/v1/create-qr-code/?size=420x420&margin=0&qzone=1&data="
           + urllib.parse.quote(url, safe=""))
    try:
        with urllib.request.urlopen(api, timeout=20) as r:
            return "data:image/png;base64," + base64.b64encode(r.read()).decode()
    except Exception:
        return ""  # renderer degrades to a text link if the QR service is unreachable


def domain_of(url: str) -> str:
    return url.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/").split("/")[0]


def build_html(d: dict, director: str, recipient: list[str], qr_uri: str, qr_url: str,
               sender: dict, sign_name: str) -> str:
    brand = escape(d.get("brand_name", "your firm"))
    _ind = (d.get("industry") or "").strip()
    trade = escape(_ind.rstrip("s") if _ind else "business like yours")
    art = "an" if trade[:1].lower() in "aeiou" else "a"  # a/an by leading vowel
    score = int(d.get("geo_score", 0))
    band = score_band(score)
    problems = d.get("top_problems", [])[:3]
    working = d.get("working", [])[:3]
    date = datetime.now().strftime("%-d %B %Y")
    dom = domain_of(d.get("url", ""))

    prob_html = "".join(
        f'<div class="prob"><div class="prob-n">{i}</div><div class="prob-b">'
        f'<div class="prob-t">{escape(p.get("title",""))}</div>'
        f'<div class="prob-d">{escape(p.get("body",""))}</div></div></div>'
        for i, p in enumerate(problems, 1))
    work_html = "".join(f'<li>{escape(w)}</li>' for w in working)
    covers_html = "".join(f'<li>{escape(c)}</li>' for c in COVERS)
    recip_html = "<br>".join(escape(x) for x in recipient if x)
    salute = escape(director) if director else "the partners"
    qr_block = (f'<img class="qr" src="{qr_uri}" alt="QR code">' if qr_uri
                else f'<div class="qr-fallback">{escape(qr_url)}</div>')
    phone = sender.get("phone", "").strip()
    call_line = f" Or call us on {escape(phone)}." if phone else ""
    sign_contact = " &nbsp;&middot;&nbsp; ".join(
        x for x in [escape(phone) if phone else "", escape(sender['web'])] if x)

    return f"""<!DOCTYPE html><html lang="en-GB"><head><meta charset="utf-8">
<style>
@page {{ size: A4; margin: 0; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
:root {{ --coral:#D97757; --cream:#E8DFD0; --ink:#1A1A1A; --off:#FAF8F5; --bd:2.5px solid #000; }}
html,body {{ font-family:'Helvetica Neue',Arial,sans-serif; color:var(--ink); background:#fff; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
.page {{ width:210mm; height:297mm; padding:15mm 16mm; position:relative; page-break-after:always; overflow:hidden; }}
.page:last-child {{ page-break-after:auto; }}
.top {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12mm; }}
.recipient {{ font-size:11pt; line-height:1.45; }}
.sender {{ text-align:right; font-size:8.5pt; line-height:1.4; color:#444; max-width:62mm; }}
.sender strong {{ color:var(--ink); font-size:9.5pt; }}
.date {{ font-size:9.5pt; color:#444; margin-bottom:6mm; }}
.salute {{ font-size:12pt; margin-bottom:4mm; }}
.lead {{ font-size:11pt; line-height:1.5; margin-bottom:7mm; }}
.scorebar {{ display:flex; align-items:center; gap:6mm; border:var(--bd); box-shadow:5px 5px 0 #000; padding:6mm 7mm; margin-bottom:6mm; background:var(--cream); }}
.score-num {{ font-size:46pt; font-weight:800; color:var(--coral); line-height:0.9; }}
.score-num small {{ font-size:15pt; color:var(--ink); font-weight:700; }}
.score-verdict {{ font-size:11pt; font-weight:700; line-height:1.35; }}
.score-sub {{ font-size:9.5pt; color:#333; margin-top:2mm; line-height:1.35; }}
.h {{ font-size:13pt; font-weight:800; text-transform:uppercase; letter-spacing:0.3px; margin:0 0 4mm; padding-bottom:2mm; border-bottom:var(--bd); }}
.prob {{ display:flex; gap:5mm; margin-bottom:4.5mm; }}
.prob-n {{ flex:0 0 9mm; height:9mm; background:var(--coral); color:#fff; font-weight:800; font-size:13pt; display:flex; align-items:center; justify-content:center; border:2px solid #000; }}
.prob-t {{ font-size:11pt; font-weight:800; margin-bottom:1mm; }}
.prob-d {{ font-size:10pt; line-height:1.4; color:#222; }}
ul.tick {{ list-style:none; }}
ul.tick li {{ font-size:10.5pt; line-height:1.4; padding-left:7mm; position:relative; margin-bottom:3mm; }}
ul.tick li::before {{ content:"\\2713"; position:absolute; left:0; color:var(--coral); font-weight:800; }}
ul.covers {{ list-style:none; }}
ul.covers li {{ font-size:10.5pt; line-height:1.4; padding-left:6mm; position:relative; margin-bottom:2.5mm; }}
ul.covers li::before {{ content:"\\2192"; position:absolute; left:0; color:var(--coral); font-weight:800; }}
.cta {{ display:flex; gap:7mm; align-items:center; border:var(--bd); box-shadow:5px 5px 0 #000; padding:7mm; background:var(--off); margin-top:6mm; }}
.qr {{ width:34mm; height:34mm; flex:0 0 34mm; }}
.qr-fallback {{ font-size:9pt; word-break:break-all; }}
.cta-t {{ font-size:14pt; font-weight:800; margin-bottom:2mm; }}
.cta-d {{ font-size:10pt; line-height:1.45; }}
.signoff {{ margin-top:8mm; font-size:10.5pt; line-height:1.5; }}
.foot {{ position:absolute; bottom:9mm; left:16mm; right:16mm; border-top:var(--bd); padding-top:2.5mm; font-size:8pt; color:#555; display:flex; justify-content:space-between; }}
.eyebrow {{ font-size:8.5pt; font-weight:800; letter-spacing:1.5px; text-transform:uppercase; color:var(--coral); margin-bottom:3mm; }}
</style></head><body>

<section class="page">
  <div class="top">
    <div class="recipient">{recip_html}</div>
    <div class="sender"><strong>{escape(sender['name'])}</strong><br>{escape(sender['details'])}</div>
  </div>
  <div class="date">{date}</div>
  <div class="salute">Dear {salute},</div>
  <div class="lead">We ran {brand} through the same checks the AI search engines now use when someone asks them to recommend {art} {trade}. The result is below. It is not good news, but every gap is fixable, and most of the value is in a handful of quick changes.</div>
  <div class="scorebar">
    <div class="score-num">{score}<small>/100</small></div>
    <div><div class="score-verdict">{escape(band['verdict'])}</div>
    <div class="score-sub">{escape(band['summary'])}</div></div>
  </div>
  <div class="eyebrow">Three things costing you enquiries</div>
  {prob_html}
  <div class="foot"><span>AI search visibility report &mdash; {brand}</span><span>GEO SLAB by Antek Automation</span></div>
</section>

<section class="page">
  <div class="eyebrow">First, the good news</div>
  <div class="h">What you're already doing right</div>
  <ul class="tick">{work_html}</ul>
  <div class="h" style="margin-top:9mm;">What the free walkthrough covers</div>
  <p style="font-size:10.5pt; line-height:1.45; margin-bottom:4mm;">This letter is a two-minute summary. Book a free 15-minute walkthrough and I'll show you:</p>
  <ul class="covers">{covers_html}</ul>
  <p style="font-size:9.5pt; line-height:1.4; color:#555; margin-top:4mm;">The detailed technical report your web team needs to make the fixes is a paid follow-on &mdash; we can talk about that on the call if it's useful.</p>
  <div class="cta">
    {qr_block}
    <div><div class="cta-t">Scan to book your free 15-minute walkthrough</div>
    <div class="cta-d">No slides, no pitch &mdash; I walk you through your results and the two or three fixes that would move the needle most.{call_line}</div></div>
  </div>
  <div class="signoff">Kind regards,<br><br><strong>{escape(sign_name)}</strong><br>{escape(sender['name'])}<br>{sign_contact}</div>
  <div class="foot"><span>{escape(dom)}</span><span>GEO SLAB by Antek Automation</span></div>
</section>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--output", default=".")
    ap.add_argument("--director", default="")
    ap.add_argument("--recipient", default="", help="'|'-separated address lines")
    ap.add_argument("--qr-url", default="")
    ap.add_argument("--sender-name", default="Antek Automation")
    ap.add_argument("--sender-details", default="Antek Automation\\nHampshire, UK")
    ap.add_argument("--phone", default="")
    ap.add_argument("--web", default="antekautomation.com")
    ap.add_argument("--sign-name", default="Andrew Norman")
    ap.add_argument("--pdf", action="store_true")
    a = ap.parse_args()

    d = json.load(open(a.data, encoding="utf-8"))
    qr_url = a.qr_url or d.get("cta_url", "https://antekautomation.com/contact")
    recipient = [x.strip() for x in a.recipient.split("|")] if a.recipient else []
    sender = {"name": a.sender_name, "details": a.sender_details.replace("\\n", ", "),
              "phone": a.phone, "web": a.web}
    qr_uri = qr_data_uri(qr_url)
    html = build_html(d, a.director, recipient, qr_uri, qr_url, sender, a.sign_name)

    dom = domain_of(d.get("url", "report"))
    outdir = Path(a.output)
    outdir.mkdir(parents=True, exist_ok=True)
    html_path = outdir / f"GEO-MAILER-{dom}.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"Mailer HTML: {html_path}")

    if a.pdf:
        pdf_path = outdir / f"GEO-MAILER-{dom}.pdf"
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        chrome = chrome if os.path.exists(chrome) else "google-chrome"
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={pdf_path}", f"file://{html_path.resolve()}"],
                       check=True, capture_output=True)
        print(f"Mailer PDF: {pdf_path}")


if __name__ == "__main__":
    main()
