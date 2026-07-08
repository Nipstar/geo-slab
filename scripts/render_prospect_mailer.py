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
import prospect_config  # noqa: E402

_ASSETS = Path(__file__).parent / "assets"


def _asset(name: str) -> str:
    """Read a base64/CSS asset; return '' if missing so the letter still renders
    (system-font fallback / no logo) without the brand assets present."""
    p = _ASSETS / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


# Ported from the standalone neo-brutalist letter design. Kept as a plain string
# (not an f-string) so the CSS braces need no escaping.
_LETTER_CSS = """
:root{
  --terracotta:#D97757; --terracotta-dark:#B85B3E; --cream-light:#FAF8F5;
  --cream-mid:#E8DFD0; --peach:#F5E6D3; --sage:#C5D8CC; --charcoal:#1A1A1A;
  --charcoal-soft:#4A4A4A; --white:#FFFFFF;
  --font-display:'Outfit','Arial Black',system-ui,sans-serif;
  --font-body:'DM Sans','Helvetica Neue',system-ui,sans-serif;
  --font-mono:'JetBrains Mono','SF Mono',monospace;
  --bd:2.5px solid var(--charcoal); --shadow:5px 5px 0 0 var(--charcoal);
}
*{margin:0;padding:0;box-sizing:border-box;}
@page{ size:A4; margin:0; }
html,body{ background:#d9d4cc; font-family:var(--font-body); color:var(--charcoal);
  -webkit-font-smoothing:antialiased; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
.page{ width:210mm; height:297mm; margin:0 auto; padding:14mm 15mm 12mm;
  background:var(--cream-light); position:relative; display:flex; flex-direction:column; overflow:hidden; }
@media screen{ body{ padding:24px 0; } .page{ box-shadow:0 8px 40px rgba(0,0,0,.28); } }
.head{ display:flex; justify-content:space-between; align-items:flex-start; padding-bottom:4mm; border-bottom:var(--bd); }
.brand{ display:flex; align-items:center; gap:3.5mm; }
.brand img{ width:13mm; height:13mm; display:block; }
.brand .wm{ font-family:var(--font-display); font-weight:800; font-size:15pt; letter-spacing:-0.01em; text-transform:uppercase; line-height:1; }
.brand .tag{ font-family:var(--font-mono); font-weight:500; font-size:6.5pt; letter-spacing:1.5px; text-transform:uppercase; color:var(--terracotta); margin-top:1.5mm; }
.sender{ text-align:right; font-size:8pt; line-height:1.45; color:var(--charcoal-soft); }
.sender strong{ color:var(--charcoal); font-size:8.5pt; }
.meta{ display:flex; justify-content:space-between; align-items:flex-start; margin-top:7mm; }
.recipient{ font-size:10.5pt; line-height:1.5; }
.recipient .name{ font-weight:700; }
.date{ font-family:var(--font-mono); font-size:8.5pt; letter-spacing:0.5px; color:var(--charcoal-soft); white-space:nowrap; padding-top:1mm; }
.salute{ font-size:11pt; font-weight:500; margin-top:6mm; }
.lead{ font-size:10.5pt; line-height:1.5; margin-top:3mm; max-width:150mm; }
.hero{ display:flex; align-items:stretch; margin-top:6mm; border:var(--bd); box-shadow:var(--shadow); }
.hero-score{ flex:0 0 46mm; background:var(--charcoal); color:var(--cream-light); padding:6mm 5mm;
  display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; border-right:var(--bd); }
.hero-score .k{ font-family:var(--font-mono); font-size:6.5pt; letter-spacing:2px; text-transform:uppercase; color:var(--terracotta); margin-bottom:2mm; }
.hero-score .num{ font-family:var(--font-display); font-weight:800; font-size:54pt; line-height:0.85; color:var(--terracotta); }
.hero-score .num small{ font-size:16pt; color:var(--cream-light); font-weight:700; }
.hero-body{ flex:1; background:var(--cream-mid); padding:6mm 6mm; display:flex; flex-direction:column; justify-content:center; }
.hero-body .headline{ font-family:var(--font-display); font-weight:700; font-size:13pt; line-height:1.22; text-transform:uppercase; letter-spacing:-0.01em; }
.hero-body .headline b{ color:var(--terracotta); }
.hero-body .verdict{ font-size:9.5pt; line-height:1.4; margin-top:3mm; color:var(--charcoal-soft); }
.sec-label{ font-family:var(--font-mono); font-weight:700; font-size:7.5pt; letter-spacing:2px; text-transform:uppercase; color:var(--terracotta); margin:7mm 0 3.5mm; display:flex; align-items:center; gap:3mm; }
.sec-label::after{ content:""; flex:1; height:2px; background:var(--charcoal); }
.checks{ display:flex; gap:4mm; }
.check{ flex:1; border:var(--bd); background:var(--white); padding:4mm 4mm 4.5mm; }
.check .n{ font-family:var(--font-display); font-weight:800; font-size:11pt; width:7mm; height:7mm; background:var(--terracotta); color:var(--white); border:2px solid var(--charcoal); display:flex; align-items:center; justify-content:center; margin-bottom:3mm; }
.check .t{ font-size:9.5pt; font-weight:700; line-height:1.2; margin-bottom:2mm; }
.check .d{ font-size:8.5pt; line-height:1.4; color:var(--charcoal-soft); }
.check .d b{ color:var(--charcoal); font-weight:700; }
.cta{ display:flex; align-items:center; gap:6mm; margin-top:7mm; border:var(--bd); box-shadow:var(--shadow); background:var(--peach); padding:5mm 6mm; }
.cta .qr{ width:28mm; height:28mm; flex:0 0 28mm; border:2px solid var(--charcoal); background:var(--white); display:block; }
.cta .qr-fallback{ width:28mm; flex:0 0 28mm; font-family:var(--font-mono); font-size:7pt; word-break:break-all; }
.cta-t{ font-family:var(--font-display); font-weight:800; font-size:12.5pt; text-transform:uppercase; line-height:1.1; letter-spacing:-0.01em; }
.cta-d{ font-size:9pt; line-height:1.45; margin-top:2.5mm; max-width:105mm; }
.signoff{ font-size:10pt; line-height:1.5; margin-top:auto; padding-top:6mm; }
.signoff .rk{ color:var(--charcoal-soft); }
.signoff .nm{ font-family:var(--font-display); font-weight:800; font-size:12pt; text-transform:uppercase; letter-spacing:-0.01em; margin-top:1mm; }
.signoff .rl{ font-size:8.5pt; color:var(--charcoal-soft); }
.foot{ display:flex; justify-content:space-between; align-items:center; margin-top:5mm; padding-top:2.5mm; border-top:var(--bd); font-family:var(--font-mono); font-size:7pt; letter-spacing:0.5px; text-transform:uppercase; color:var(--charcoal-soft); }
.foot .r{ color:var(--terracotta); font-weight:700; }
"""


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


def build_html(d: dict, salute_name: str, recipient: list[str], qr_uri: str, qr_url: str,
               sender: dict, sign_name: str) -> str:
    brand = escape(d.get("brand_name", "your firm"))
    noun = escape(prospect_config.noun_phrase(d.get("industry") or ""))
    score = int(d.get("geo_score", 0))
    band = score_band(score)
    headline = escape(d.get("headline", ""))
    problems = d.get("top_problems", [])[:3]
    date = datetime.now().strftime("%-d %B %Y")
    dom = domain_of(d.get("url", ""))
    web = escape(sender.get("web", "antekautomation.com"))

    # Data-driven checks: the prospect's real findings, not the template's fixed
    # ChatGPT/Claude/rival wording. Numbered 1..3.
    checks_html = "".join(
        f'<div class="check"><div class="n">{i}</div>'
        f'<div class="t">{escape(p.get("title",""))}</div>'
        f'<div class="d">{escape(p.get("body",""))}</div></div>'
        for i, p in enumerate(problems, 1))

    lines = [escape(x) for x in recipient if x]
    name = lines[0] if lines else "the partners"
    rest = "".join(f"<br>{x}" for x in lines[1:])
    fonts = _asset("letter_fonts.css")
    logo = _asset("antek_logo.b64").strip()
    logo_img = f'<img src="{logo}" alt="Antek Automation">' if logo else ""
    qr_block = (f'<img class="qr" src="{qr_uri}" alt="Booking QR code">' if qr_uri
                else f'<div class="qr-fallback">{escape(qr_url)}</div>')

    return f"""<!DOCTYPE html><html lang="en-GB"><head><meta charset="utf-8">
<style>{fonts}</style>
<style>{_LETTER_CSS}</style></head><body>
<section class="page">
  <header class="head">
    <div class="brand">{logo_img}
      <div><div class="wm">Antek Automation</div>
      <div class="tag">AI Automation Agency &middot; UK</div></div>
    </div>
    <div class="sender"><strong>Antek Automation</strong><br>
      Chantry House, 38 Chantry Way<br>Andover SP10 1LZ<br>{web}</div>
  </header>
  <div class="meta">
    <div class="recipient"><span class="name">{name}</span>{rest}</div>
    <div class="date">{date}</div>
  </div>
  <div class="salute">Dear {escape(salute_name) if salute_name else "the partners"},</div>
  <p class="lead">We ran {brand} through the same checks the AI search engines now use when someone asks them to recommend {noun}. Here is what they found.</p>
  <div class="hero">
    <div class="hero-score"><div class="k">AI Visibility</div>
      <div class="num">{score}<small>/100</small></div></div>
    <div class="hero-body">
      <div class="headline">{headline}</div>
      <div class="verdict">{escape(band['verdict'])}</div>
    </div>
  </div>
  <div class="sec-label">What the checks found</div>
  <div class="checks">{checks_html}</div>
  <div class="cta">
    {qr_block}
    <div><div class="cta-t">Scan to book a free 15-minute walkthrough</div>
    <div class="cta-d">No slides, no pitch. I show you your score across all six visibility areas, which of the nine AI engines you are missing from, and the three fixes worth doing first.</div></div>
  </div>
  <div class="signoff"><div class="rk">Kind regards,</div>
    <div class="nm">{escape(sign_name)}</div>
    <div class="rl">Antek Automation</div></div>
  <div class="foot"><span>AI search visibility report &middot; {escape(dom)}</span>
    <span class="r">GEO SLAB by Antek Automation</span></div>
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
    ap.add_argument("--sender-details", default="Chantry House, 38 Chantry Way\nAndover SP10 1LZ")
    ap.add_argument("--phone", default="")
    ap.add_argument("--web", default="antekautomation.com")
    ap.add_argument("--sign-name", default="Andrew Norman")
    ap.add_argument("--pdf", action="store_true")
    a = ap.parse_args()

    d = json.load(open(a.data, encoding="utf-8"))
    qr_url = a.qr_url or d.get("cta_url", "https://antekautomation.com/contact")
    recipient = [x.strip() for x in a.recipient.split("|")] if a.recipient else []
    sender = {"name": a.sender_name, "details": a.sender_details.replace("\\n", "\n"),
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
