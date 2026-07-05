#!/usr/bin/env python3
"""
GEO SLAB — postal letter batch builder (spec §5, `/geo mail`).

Stannp API is deferred, so this produces a folder you import into Stannp by
hand: one personalised A4 letter PDF per prospect + a `stannp_recipients.csv`
addressed to Stannp's standard import columns (firstname, lastname, address1,
address2, city, postcode, country). Drop the folder into a Stannp "letters"
mailing, map the CSV, done.

Each letter is the 2-page mailer (render_prospect_mailer) driven by the
prospect's latest free AI Visibility Check — the "problems" ARE the check
findings (which engines don't recommend them, which competitor does), not an
audit. Scope stays free-tier; the technical report + fixes remain paid (see the
mailer's CTA copy).

Channel + suppression aware: by default only prospects with
outreach_channel='letter' are mailed (that's the §8 PECR routing companies_house
set), and anything on the suppressions list is skipped.

    python3 mail_batch.py --batch enriched --out prospects/mail-2026-07/
    python3 mail_batch.py --prospect PRO-002 PRO-005 --out prospects/mail/
    python3 mail_batch.py --self-check

ponytail: PDFs render via the same headless-Chrome call the mailer uses. No
Stannp HTTP — that lands when the key does; the CSV is the handoff.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402
import render_prospect_mailer as mailer  # noqa: E402

UK_POSTCODE = re.compile(r"([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})", re.I)

STANNP_COLS = ["firstname", "lastname", "company", "address1", "address2",
               "city", "postcode", "country", "ref", "file"]


def reformat_director(director: str) -> str:
    """CH 'SURNAME, Forename' -> 'Forename Surname' for a natural salutation."""
    if not director:
        return ""
    if "," in director:
        surname, first = [x.strip() for x in director.split(",", 1)]
        return f"{first} {surname}".strip()
    return director.strip()


def split_name(director: str) -> tuple[str, str]:
    """Return (firstname, lastname) for the CSV."""
    if not director:
        return "", ""
    if "," in director:
        surname, first = [x.strip() for x in director.split(",", 1)]
        return first, surname
    parts = director.split()
    return (parts[0], " ".join(parts[1:])) if len(parts) > 1 else (director, "")


def parse_address(address: str, postcode: str) -> dict:
    """Best-effort split of a Google formatted address into Stannp fields.

    ponytail: comma-split heuristic — good enough for UK GBP addresses like
    '5 High St, Basingstoke RG21 7QW, UK'. Verify/clean in the CSV before a
    paid send; addresses without commas fall back to address1=whole string.
    """
    pc = (postcode or "").strip()
    parts = [s.strip() for s in (address or "").split(",") if s.strip()]
    if parts and parts[-1].lower() in ("uk", "united kingdom", "gb"):
        parts = parts[:-1]
    # pull postcode out of whichever segment carries it
    if not pc:
        for seg in parts:
            m = UK_POSTCODE.search(seg)
            if m:
                pc = m.group(1).upper()
                break
    city = ""
    if parts:
        last = UK_POSTCODE.sub("", parts[-1]).strip(" ,")
        city = last
    addr1 = parts[0] if parts else (address or "")
    addr2 = ", ".join(parts[1:-1]) if len(parts) > 2 else ""
    return {"address1": addr1, "address2": addr2, "city": city,
            "postcode": pc.upper(), "country": "United Kingdom"}


def synth_data(p: dict, check: dict | None) -> dict:
    """Build the mailer's prospect-data.json from the free-check result."""
    import json
    platforms = []
    competitors = []
    if check:
        try:
            platforms = json.loads(check.get("results_json") or "[]")
        except (ValueError, TypeError):
            platforms = []
        try:
            competitors = json.loads(check.get("competitors_json") or "[]")
        except (ValueError, TypeError):
            competitors = []

    missing = [pl["platform"] for pl in platforms if pl.get("tested") and not pl.get("mentioned")]
    present = [pl["platform"] for pl in platforms if pl.get("mentioned")]

    problems = []
    for plat in missing[:2]:
        problems.append({
            "title": f"Invisible on {plat}",
            "body": f"Ask {plat} to recommend a firm like yours and you don't come up. "
                    "The enquiry goes to whoever it names instead.",
        })
    if competitors:
        top = competitors[0].get("name", "a competitor")
        problems.append({
            "title": "Competitors are being recommended in your place",
            "body": f"When the engines answered, {top} came up instead of you — "
                    "repeatedly, across different questions.",
        })
    if not problems:
        problems.append({
            "title": "How you're described is thin",
            "body": "The engines can find you but can't confidently say what you do "
                    "or who you serve, so they hedge or skip you.",
        })

    working = [f"{plat} does mention you by name" for plat in present[:3]]
    if not working:
        working = ["You have a live website the engines can reach",
                   "Your business details are consistent enough to match"]

    return {
        "brand_name": p.get("company", "your firm"),
        "url": p.get("website") or p.get("domain") or "",
        "industry": p.get("industry", ""),
        "geo_score": int(check.get("visibility_score", 0)) if check else 0,
        "top_problems": problems,
        "working": working,
        "cta_url": os.environ.get("OUTREACH_CTA", "https://antekautomation.com/contact"),
    }


def render_letter(data: dict, director: str, recipient: list[str], out_dir: Path,
                  qr_url: str) -> Path:
    sender = {"name": "Antek Automation", "details": "Antek Automation, Hampshire, UK",
              "phone": os.environ.get("OUTREACH_PHONE", "0333 038 9960"),
              "web": os.environ.get("OUTREACH_WEB", "antekautomation.com")}
    qr_uri = mailer.qr_data_uri(qr_url)
    html = mailer.build_html(data, director, recipient, qr_uri, qr_url, sender, "Andrew Norman")
    dom = mailer.domain_of(data.get("url", "letter")) or "letter"
    html_path = out_dir / f"LETTER-{dom}.html"
    html_path.write_text(html, encoding="utf-8")
    pdf_path = out_dir / f"LETTER-{dom}.pdf"
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    chrome = chrome if os.path.exists(chrome) else "google-chrome"
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", f"file://{html_path.resolve()}"],
                   check=True, capture_output=True)
    return pdf_path


def build_row(p: dict, pdf_file: str) -> dict:
    first, last = split_name(p.get("director_name", ""))
    addr = parse_address(p.get("address", ""), p.get("postcode", ""))
    return {"firstname": first, "lastname": last, "company": p.get("company", ""),
            "address1": addr["address1"], "address2": addr["address2"],
            "city": addr["city"], "postcode": addr["postcode"],
            "country": addr["country"], "ref": p.get("id", ""), "file": pdf_file}


def run(refs: list[str], out_dir: Path, force_channel: bool, no_pdf: bool) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    qr_url = os.environ.get("OUTREACH_CTA", "https://antekautomation.com/contact")
    rows = []
    for ref in refs:
        p = db.get_prospect(ref)
        if not p:
            print(f"  {ref}: not found", file=sys.stderr)
            continue
        if not force_channel and (p.get("outreach_channel") or "letter") != "letter":
            print(f"  {ref} {p.get('company')}: channel={p.get('outreach_channel')} — skipped (use --force)")
            continue
        if db.is_suppressed(domain=p.get("domain") or "", company=p.get("company") or ""):
            print(f"  {ref} {p.get('company')}: SUPPRESSED — skipped")
            continue

        check = db.latest_check(p["pk"])
        data = synth_data(p, check)
        director = reformat_director(p.get("director_name", ""))
        addr = parse_address(p.get("address", ""), p.get("postcode", ""))
        recipient = [x for x in [p.get("company", ""), addr["address1"], addr["address2"],
                                 f"{addr['city']} {addr['postcode']}".strip()] if x]
        pdf_file = f"LETTER-{mailer.domain_of(data.get('url','letter')) or ref}.pdf"
        if not no_pdf:
            pdf_path = render_letter(data, director, recipient, out_dir, qr_url)
            pdf_file = pdf_path.name

        db.insert_outreach({"prospect_id": p["pk"], "channel": "letter",
                            "subject": "Postal AI visibility letter",
                            "body": pdf_file, "status": "queued"})
        rows.append(build_row(p, pdf_file))
        print(f"  {ref} {p.get('company')}: letter → {pdf_file}")

    if rows:
        csv_path = out_dir / "stannp_recipients.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=STANNP_COLS)
            w.writeheader()
            w.writerows(rows)
        print(f"\n{len(rows)} letter(s) + {csv_path}")
    else:
        print("\nNo letters produced.")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a Stannp-ready postal letter batch")
    ap.add_argument("--prospect", nargs="+", help="One or more refs (PRO-001 ...)")
    ap.add_argument("--batch", help="Status to mail (e.g. enriched, checked)")
    ap.add_argument("--out", default="prospects/mail", help="Output folder")
    ap.add_argument("--force", action="store_true",
                    help="Mail regardless of outreach_channel")
    ap.add_argument("--no-pdf", action="store_true", help="CSV only, skip PDF render")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        _demo()
        return

    db.init_db()
    if args.prospect:
        refs = args.prospect
    elif args.batch:
        refs = [p["id"] for p in db.all_prospects() if p.get("status") == args.batch]
    else:
        ap.error("pass --prospect PRO-001 ... or --batch <status>")
    if not refs:
        print("No matching prospects.")
        return
    run(refs, Path(args.out), args.force, args.no_pdf)


def _demo() -> None:
    import tempfile, json
    # name splitting / salutation
    assert reformat_director("BARCOCK, Kevin") == "Kevin BARCOCK"
    assert split_name("BARCOCK, Kevin") == ("Kevin", "BARCOCK")
    assert split_name("Bob Jones") == ("Bob", "Jones")
    assert split_name("") == ("", "")

    # address parsing
    a = parse_address("5 High St, Basingstoke RG21 7QW, UK", "")
    assert a["address1"] == "5 High St", a
    assert a["city"] == "Basingstoke", a
    assert a["postcode"] == "RG21 7QW", a
    assert a["country"] == "United Kingdom"
    # postcode column wins if address lacks one
    b = parse_address("Unit 2, Some Park", "SO23 9AB")
    assert b["postcode"] == "SO23 9AB", b

    # synth data maps check findings to problems/working
    p = {"company": "Acme Plumbing Ltd", "website": "https://acme.co.uk", "industry": "plumbers"}
    check = {"visibility_score": 25,
             "results_json": json.dumps([
                 {"platform": "ChatGPT", "tested": True, "mentioned": False},
                 {"platform": "Gemini", "tested": True, "mentioned": False},
                 {"platform": "Perplexity", "tested": True, "mentioned": True},
             ]),
             "competitors_json": json.dumps([{"name": "PlumbCo", "mentions": 3}])}
    data = synth_data(p, check)
    assert data["geo_score"] == 25
    titles = [x["title"] for x in data["top_problems"]]
    assert any("Invisible on ChatGPT" in t for t in titles), titles
    assert any("Competitors" in t for t in titles), titles
    assert any("Perplexity" in w for w in data["working"]), data["working"]

    # no check -> still safe defaults, score 0
    d0 = synth_data(p, None)
    assert d0["geo_score"] == 0 and d0["top_problems"] and d0["working"]

    # end-to-end CSV row build + suppression skip (no PDF render)
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["GEO_SLAB_DB"] = str(Path(tmp) / "t.db")
        db.init_db()
        pr = db.insert_prospect({"company": "Acme Plumbing Ltd", "domain": "acme.co.uk",
                                 "director_name": "BARCOCK, Kevin", "industry": "plumbers",
                                 "address": "5 High St, Basingstoke RG21 7QW, UK",
                                 "outreach_channel": "letter", "status": "enriched"})
        db.insert_check({"prospect_id": pr["pk"], "platforms_tested": 3,
                         "mentioned_count": 1, "visibility_score": 25,
                         "results_json": check["results_json"],
                         "competitors_json": check["competitors_json"]})
        rows = run([pr["id"]], Path(tmp) / "out", force_channel=False, no_pdf=True)
        assert len(rows) == 1 and rows[0]["city"] == "Basingstoke", rows
        assert (Path(tmp) / "out" / "stannp_recipients.csv").exists()

        db.add_suppression(company="Acme Plumbing Ltd", reason="opted_out")
        assert run([pr["id"]], Path(tmp) / "out2", force_channel=False, no_pdf=True) == []

    print("mail_batch self-check passed")


if __name__ == "__main__":
    main()
