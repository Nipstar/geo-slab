#!/usr/bin/env python3
"""
GEO SLAB — outreach copy generator (spec §5, `/geo outreach`).

Deterministic, template-driven email + LinkedIn-connect copy in the Antek
voice. No LLM call — the personalisation comes from the DB (company, director,
town, trade) and the prospect's latest free AI Visibility Check (how many of
the four engines recommended them, which competitor came up instead). Cheap,
repeatable, and never hallucinates a result the check didn't produce.

Every send path is suppression-checked first (§8/§12): a domain / email /
company on the suppressions list is skipped, no copy generated.

Scope note: this is COLD OUTREACH driving to the free 15-minute walkthrough.
It cites only free-check findings (mention yes/no + competitors). The technical
report and the fixes themselves stay paid — see the walkthrough CTA copy.

    python3 outreach_generator.py --prospect PRO-001
    python3 outreach_generator.py --batch checked --out prospects/outreach/
    python3 outreach_generator.py --self-check

Persists one `outreach` row per channel (status='drafted'). --out also writes a
human-readable .md per prospect so you can copy/paste or review before sending.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402

SENDER_NAME = os.environ.get("OUTREACH_SENDER", "Andrew Norman")
SENDER_WEB = os.environ.get("OUTREACH_WEB", "antekautomation.com")
SENDER_PHONE = os.environ.get("OUTREACH_PHONE", "0333 038 9960")
CTA_URL = os.environ.get("OUTREACH_CTA", "https://antekautomation.com/contact")
LINKEDIN_LIMIT = 300  # LinkedIn connection-note hard cap


def first_name(director: str) -> str:
    """CH stores 'SURNAME, Forename'. Return a usable first name, or ''."""
    if not director:
        return ""
    if "," in director:
        return director.split(",", 1)[1].strip().split()[0]
    parts = director.split()
    return parts[0] if parts else ""


def trade_word(industry: str) -> str:
    """A noun that reads naturally after 'recommend a ...'."""
    ind = (industry or "").strip()
    return ind.rstrip("s") if ind else "business like yours"


def result_sentence(check: dict | None) -> str:
    """One plain sentence describing the free-check outcome."""
    if not check:
        return ("I haven't run your check yet — it takes about a minute and "
                "shows exactly what each engine says when someone asks for a recommendation.")
    tested = check.get("platforms_tested") or 0
    mentioned = check.get("mentioned_count") or 0
    if tested == 0:
        return "The engines didn't return a clean result, which is itself worth a look."
    if mentioned == 0:
        return f"None of the four recommended you — you didn't come up at all."
    if mentioned == tested:
        return (f"You came up on all {tested}, which is rare — the gap is in "
                "how clearly they can describe what you do.")
    return (f"{mentioned} of the {tested} recommended you; the other "
            f"{tested - mentioned} didn't mention you at all.")


def competitor_sentence(check: dict | None) -> str:
    if not check:
        return ""
    try:
        comps = json.loads(check.get("competitors_json") or "[]")
    except (ValueError, TypeError):
        comps = []
    names = [c.get("name") for c in comps if c.get("name")]
    if not names:
        return ""
    top = names[0]
    return f" When you weren't recommended, {top} came up instead."


def build_email(p: dict, check: dict | None) -> tuple[str, str]:
    company = p.get("company") or "your firm"
    town = p.get("postcode_town") or p.get("address_town") or _town(p)
    trade = trade_word(p.get("industry", ""))
    fname = first_name(p.get("director_name", ""))
    greeting = f"Hi {fname}," if fname else "Hello,"
    where = f" in {town}" if town else ""

    subject = f"Is {company} showing up when people ask AI for a {trade}{where}?"
    body = f"""{greeting}

I run Antek Automation. We look at how local firms show up when someone asks ChatGPT, Gemini, Perplexity or Google's AI to recommend a {trade}{where} — the searches that increasingly happen instead of a Google search.

I ran {company} through those four engines. {result_sentence(check)}{competitor_sentence(check)}

None of this is a hard fix, and most of the value sits in a couple of changes.

Worth a free 15-minute walkthrough? I'll show you what each engine actually says about you and the two or three things that would help most. No slides, no pitch.

{CTA_URL}

Kind regards,
{SENDER_NAME}
Antek Automation
{SENDER_WEB} · {SENDER_PHONE}"""
    return subject, body


def build_linkedin(p: dict, check: dict | None) -> str:
    company = p.get("company") or "your firm"
    trade = trade_word(p.get("industry", ""))
    fname = first_name(p.get("director_name", ""))
    hi = f"Hi {fname} — " if fname else "Hi — "
    note = (f"{hi}I checked how {company} shows up when people ask AI (ChatGPT, "
            f"Gemini, Perplexity) to recommend a {trade}. Happy to share the "
            f"2-minute summary if it's useful.")
    if len(note) > LINKEDIN_LIMIT:
        # ponytail: drop the company clause first — it's the longest optional bit
        note = (f"{hi}I checked how you show up when people ask AI to recommend "
                f"a {trade}. Happy to share the 2-minute summary if useful.")
    return note[:LINKEDIN_LIMIT]


def _town(p: dict) -> str:
    """Best-effort town from the formatted address (segment before postcode)."""
    addr = p.get("address") or ""
    parts = [s.strip() for s in addr.split(",") if s.strip()]
    # drop a trailing country token
    if parts and parts[-1].lower() in ("uk", "united kingdom"):
        parts = parts[:-1]
    if not parts:
        return ""
    last = parts[-1]
    # "Basingstoke RG21 7QW" -> "Basingstoke"
    toks = last.split()
    town_toks = [t for t in toks if not any(ch.isdigit() for ch in t)]
    return " ".join(town_toks).strip() or (parts[-2] if len(parts) > 1 else "")


def generate_for(ref: str, out_dir: Path | None, dry_run: bool = False) -> dict | None:
    p = db.get_prospect(ref)
    if not p:
        print(f"  {ref}: not found", file=sys.stderr)
        return None
    if db.is_suppressed(domain=p.get("domain") or "", email=p.get("email") or "",
                        company=p.get("company") or ""):
        print(f"  {ref} ({p.get('company')}): SUPPRESSED — skipped")
        return None

    check = db.latest_check(p["pk"])
    subject, email_body = build_email(p, check)
    li_note = build_linkedin(p, check)

    if not dry_run:
        db.insert_outreach({"prospect_id": p["pk"], "channel": "email",
                            "subject": subject, "body": email_body})
        db.insert_outreach({"prospect_id": p["pk"], "channel": "linkedin",
                            "subject": "", "body": li_note})

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        md = (f"# Outreach — {p.get('company')} ({ref})\n\n"
              f"## Email\n\n**Subject:** {subject}\n\n{email_body}\n\n"
              f"## LinkedIn connect note ({len(li_note)}/{LINKEDIN_LIMIT})\n\n{li_note}\n")
        (out_dir / f"OUTREACH-{ref}.md").write_text(md, encoding="utf-8")

    return {"ref": ref, "company": p.get("company"), "subject": subject,
            "linkedin_len": len(li_note)}


def run(refs: list[str], out_dir: Path | None, dry_run: bool) -> list[dict]:
    results = []
    for ref in refs:
        r = generate_for(ref, out_dir, dry_run)
        if r:
            results.append(r)
            print(f"  {ref} {r['company']}: email + linkedin ({r['linkedin_len']} chars)")
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate cold outreach copy (email + LinkedIn)")
    ap.add_argument("--prospect", help="Single prospect ref (PRO-001)")
    ap.add_argument("--batch", help="Status to generate for (e.g. checked)")
    ap.add_argument("--out", help="Directory to write per-prospect .md drafts")
    ap.add_argument("--dry-run", action="store_true", help="Don't persist outreach rows")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        _demo()
        return

    db.init_db()
    if args.prospect:
        refs = [args.prospect]
    elif args.batch:
        refs = [p["id"] for p in db.all_prospects() if p.get("status") == args.batch]
    else:
        ap.error("pass --prospect PRO-001 or --batch <status>")

    if not refs:
        print("No matching prospects.")
        return
    out_dir = Path(args.out) if args.out else None
    results = run(refs, out_dir, args.dry_run)
    print(f"\nGenerated outreach for {len(results)} prospect(s)"
          + (f" → {out_dir}" if out_dir else "")
          + (" (dry run, nothing persisted)" if args.dry_run else ""))


def _demo() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["GEO_SLAB_DB"] = str(Path(tmp) / "t.db")
        db.init_db()

        # name + trade + town helpers
        assert first_name("SMITH, Jane Anne") == "Jane"
        assert first_name("Bob Jones") == "Bob"
        assert first_name("") == ""
        assert trade_word("plumbers") == "plumber"
        assert trade_word("") == "business like yours"

        p = db.insert_prospect({"company": "Acme Plumbing Ltd", "domain": "acme.co.uk",
                                "industry": "plumbers", "director_name": "BARCOCK, Kevin",
                                "address": "5 High St, Basingstoke RG21 7QW, UK",
                                "status": "checked"})
        db.insert_check({"prospect_id": p["pk"], "platforms_tested": 4,
                         "mentioned_count": 1, "visibility_score": 25,
                         "competitors_json": json.dumps([{"name": "PlumbCo", "mentions": 3}])})

        subj, body = build_email(db.get_prospect(p["id"]), db.latest_check(p["pk"]))
        assert "Kevin" in body and "Basingstoke" in subj and "plumber" in subj
        assert "PlumbCo came up instead" in body
        assert "3 of the 4 recommended you" not in body  # 1 mentioned -> other 3
        assert "the other 3 didn't mention you" in body

        li = build_linkedin(db.get_prospect(p["id"]), db.latest_check(p["pk"]))
        assert len(li) <= LINKEDIN_LIMIT and "Kevin" in li

        # no-check prospect -> soft copy, no fabricated result
        p2 = db.insert_prospect({"company": "Beta Ltd", "industry": "electricians"})
        _, body2 = build_email(db.get_prospect(p2["id"]), None)
        assert "haven't run your check yet" in body2

        # suppression is enforced
        db.add_suppression(company="Acme Plumbing Ltd", reason="opted_out")
        assert generate_for(p["id"], None) is None

        # banned-word + US-spelling guard on generated copy
        import style
        low = (subj + body + li + body2).lower()
        for w in style.BANNED_WORDS:
            assert w not in low, f"banned word in copy: {w}"
        for us in style.US_TO_UK_SPELLINGS:
            assert us not in low, f"US spelling in copy: {us}"

    print("outreach_generator self-check passed")


if __name__ == "__main__":
    main()
