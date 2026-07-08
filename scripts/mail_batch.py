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
import prospect_config  # noqa: E402

# Score-0-with-positive-signals flags collected during a run, written to
# REVIEW.md so a probable scorer artefact never ships silently (spec fix 4).
REVIEW_FLAGS: list[str] = []

UK_POSTCODE = re.compile(r"([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})", re.I)

STANNP_COLS = ["firstname", "lastname", "company", "address1", "address2",
               "city", "postcode", "country", "ref", "file"]


def reformat_director(director: str) -> str:
    """CH 'SURNAME, Forename Middle' -> 'Forename Surname' for a salutation.

    Title-cases (CH stores surnames upper-case) and drops middle names so the
    letter reads 'Dear Jonathan Brothers', not 'Dear Jonathan Peter BROTHERS'.
    ponytail: .title() mangles Mc/Mac/O' (McDonald->Mcdonald) — rare, fix with a
    name-casing lib only if it becomes a real complaint.
    """
    if not director:
        return ""
    if "," in director:
        surname, first = [x.strip() for x in director.split(",", 1)]
        first = first.split()[0] if first.split() else ""  # drop middle names
        return f"{first} {surname}".strip().title()
    return director.strip().title()


def split_name(director: str) -> tuple[str, str]:
    """Return (firstname, lastname) for the CSV — first forename only, title-cased."""
    if not director:
        return "", ""
    if "," in director:
        surname, first = [x.strip() for x in director.split(",", 1)]
        first = first.split()[0] if first.split() else ""  # drop middle names
        return first.title(), surname.title()
    parts = director.split()
    return (parts[0].title(), " ".join(parts[1:]).title()) if len(parts) > 1 else (director.title(), "")


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


def _review_flag(p: dict, msg: str) -> None:
    line = f"{p.get('id') or p.get('ref') or '?'} {p.get('company', '?')}: {msg}"
    REVIEW_FLAGS.append(line)
    print(f"  REVIEW: {line}", file=sys.stderr)


def _headline(noun: str, top: str | None, missing: list, present: list) -> str:
    """The outcome-led opening finding: where the enquiry goes, not a metric.
    Kept short to sit in the hero headline box."""
    if top:
        return f"Ask AI to recommend {noun} and it names {top}, not you."
    if missing:
        return f"Ask AI to recommend {noun} and you are not the answer it gives."
    return f"When people ask AI to recommend {noun}, you are hard to find."


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
    noun = prospect_config.noun_phrase(p.get("industry", ""))

    problems = []
    for plat in missing[:2]:
        problems.append({
            "title": f"Invisible on {plat}",
            "body": f"Ask {plat} to recommend {noun} and you do not come up. "
                    "The enquiry goes to whoever it names instead.",
        })

    # Competitor gate: only a validated real firm reaches the letter. Junk the
    # extractor sometimes stores (directories, page headings) is suppressed. If
    # candidates existed but none survive, say what actually happened instead of
    # fabricating a rival (spec fix 1).
    raw_comps = [c.get("name", "") for c in competitors if c.get("name")]
    top = prospect_config.first_valid_competitor(raw_comps, brand=p.get("company", ""))
    if top:
        problems.append({
            "title": "Competitors are being recommended in your place",
            "body": f"When the engines answered, {top} came up instead of you, "
                    "across several different questions.",
        })
    elif raw_comps:
        problems.append({
            "title": "The engines point to directories, not firms",
            "body": f"Asked to recommend {noun}, the engines returned review sites "
                    "and general advice rather than a named firm like yours.",
        })

    if not problems:
        problems.append({
            "title": "How you are described is thin",
            "body": "The engines can find you but cannot confidently say what you do "
                    "or who you serve, so they hedge or skip you.",
        })

    # Positives derived from real signals, so they can never invert against the
    # score (spec fix 4): only claim a live site if we hold a URL, only claim
    # consistent details if we hold address/postcode or a phone.
    working = [f"{plat} does mention you by name" for plat in present[:3]]
    if not working:
        working = []
        if p.get("website"):
            working.append("You have a live website the engines can reach")
        if (p.get("address") and p.get("postcode")) or p.get("phone"):
            working.append("Your business details are consistent enough for the engines to match")
        if not working:
            working.append("Your listing is active and can be built on")

    score = int(check.get("visibility_score", 0)) if check else 0
    if score == 0 and (p.get("website") or present):
        _review_flag(p, "score is 0 but positive signals exist (live site / platform "
                        "mention) — verify the scorer or relabel before sending")

    town = parse_address(p.get("address", ""), p.get("postcode", ""))["city"]
    return {
        "brand_name": prospect_config.clean_company_name(p.get("company", "") or "your firm", town),
        "url": p.get("website") or p.get("domain") or "",
        "industry": p.get("industry", ""),
        "geo_score": score,
        "score_label": "AI visibility score",
        "headline": _headline(noun, top, missing, present),
        "top_problems": problems,
        "working": working,
        "cta_url": os.environ.get("OUTREACH_CTA", "https://antekautomation.com/contact"),
    }


def render_letter(data: dict, salute: str, recipient: list[str], out_dir: Path,
                  qr_url: str) -> Path:
    sender = {"name": "Antek Automation",
              "details": "Chantry House, 38 Chantry Way\nAndover SP10 1LZ",
              "phone": os.environ.get("OUTREACH_PHONE", "0333 038 9960"),
              "web": os.environ.get("OUTREACH_WEB", "antekautomation.com")}
    qr_uri = mailer.qr_data_uri(qr_url)
    html = mailer.build_html(data, salute, recipient, qr_uri, qr_url, sender, "Andrew Norman")
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
    company = prospect_config.clean_company_name(p.get("company", ""), addr["city"])
    return {"firstname": first, "lastname": last, "company": company,
            "address1": addr["address1"], "address2": addr["address2"],
            "city": addr["city"], "postcode": addr["postcode"],
            "country": addr["country"], "ref": p.get("id", ""), "file": pdf_file}


def run(refs: list[str], out_dir: Path, force_channel: bool, no_pdf: bool) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    REVIEW_FLAGS.clear()
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
        # Envelope shows the proper full name ("Craig Fisher"); the salutation
        # uses the first name only ("Dear Craig,") — spec fix 3.
        full_name = reformat_director(p.get("director_name", ""))
        salute = split_name(p.get("director_name", ""))[0]
        addr = parse_address(p.get("address", ""), p.get("postcode", ""))
        company_clean = prospect_config.clean_company_name(p.get("company", ""), addr["city"])
        recipient = [x for x in [full_name, company_clean, addr["address1"], addr["address2"],
                                 f"{addr['city']} {addr['postcode']}".strip()] if x]
        pdf_file = f"LETTER-{mailer.domain_of(data.get('url','letter')) or ref}.pdf"
        if not no_pdf:
            pdf_path = render_letter(data, salute, recipient, out_dir, qr_url)
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

    if REVIEW_FLAGS:
        review_path = out_dir / "REVIEW.md"
        review_path.write_text(
            "# Review before sending\n\n"
            "These prospects scored 0 but show positive signals, which usually "
            "means the score is mislabelled or the scorer undercounted. Check each "
            "before a paid send.\n\n"
            + "".join(f"- {f}\n" for f in REVIEW_FLAGS), encoding="utf-8")
        print(f"{len(REVIEW_FLAGS)} prospect(s) flagged for review → {review_path}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a Stannp-ready postal letter batch")
    ap.add_argument("--prospect", nargs="+", help="One or more refs (PRO-001 ...)")
    ap.add_argument("--batch", help="Status to mail (e.g. enriched, checked)")
    ap.add_argument("--campaign", help="Restrict --batch to this campaign tag")
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
        refs = [p["id"] for p in db.all_prospects()
                if p.get("status") == args.batch
                and (not args.campaign or p.get("campaign") == args.campaign)]
    else:
        ap.error("pass --prospect PRO-001 ... or --batch <status>")
    if not refs:
        print("No matching prospects.")
        return
    run(refs, Path(args.out), args.force, args.no_pdf)


def _demo() -> None:
    import tempfile, json
    # name splitting / salutation
    assert reformat_director("BARCOCK, Kevin") == "Kevin Barcock"
    assert reformat_director("MACRAE, Gladys Pek Yue") == "Gladys Macrae"  # drops middle names
    assert split_name("BARCOCK, Kevin") == ("Kevin", "Barcock")
    assert split_name("MACRAE, Gladys Pek Yue") == ("Gladys", "Macrae")
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
             "competitors_json": json.dumps([{"name": "Rival Plumbing Ltd", "mentions": 3}])}
    data = synth_data(p, check)
    assert data["geo_score"] == 25
    assert data["score_label"] == "AI visibility score"
    assert "a firm like yours" in data["headline"], data["headline"]  # plumbers noun phrase
    titles = [x["title"] for x in data["top_problems"]]
    assert any("Invisible on ChatGPT" in t for t in titles), titles
    assert any("Competitors" in t for t in titles), titles
    assert any("Perplexity" in w for w in data["working"]), data["working"]

    # competitor gate: junk-only competitor list -> truthful line, never a fake firm
    junk = dict(check, competitors_json=json.dumps([{"name": "Hourly Rates"},
                                                    {"name": "Google Maps Search"}]))
    jtitles = [x["title"] for x in synth_data(p, junk)["top_problems"]]
    assert any("directories" in t for t in jtitles), jtitles
    assert not any("Competitors are being recommended" in t for t in jtitles), jtitles

    # no check -> still safe defaults, score 0
    d0 = synth_data(p, None)
    assert d0["geo_score"] == 0 and d0["top_problems"] and d0["working"]

    # positives never invert against a 0 score: a live-site signal is required
    # to claim a live site, not hardcoded.
    d_site = synth_data({"company": "X Ltd", "website": "https://x.co.uk", "industry": "plumbers"}, None)
    assert any("live website" in w for w in d_site["working"]), d_site["working"]
    d_bare = synth_data({"company": "Y Ltd", "industry": "plumbers"}, None)
    assert not any("live website" in w for w in d_bare["working"]), d_bare["working"]

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
