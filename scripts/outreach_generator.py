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
import prospect_config  # noqa: E402

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
        return ("I haven't run your check yet. It takes about a minute and "
                "shows exactly what each engine says when someone asks for a recommendation.")
    tested = check.get("platforms_tested") or 0
    mentioned = check.get("mentioned_count") or 0
    if tested == 0:
        return "The engines didn't return a clean result, which is itself worth a look."
    if mentioned == 0:
        return "None of the four recommended you. You did not come up at all."
    if mentioned == tested:
        return (f"You came up on all {tested}, which is rare. The gap is in "
                "how clearly they can describe what you do.")
    return (f"{mentioned} of the {tested} recommended you; the other "
            f"{tested - mentioned} didn't mention you at all.")


def competitor_sentence(check: dict | None) -> str:
    """Only name a validated real firm, never a directory or page heading."""
    if not check:
        return ""
    try:
        comps = json.loads(check.get("competitors_json") or "[]")
    except (ValueError, TypeError):
        comps = []
    names = [c.get("name") for c in comps if c.get("name")]
    top = prospect_config.first_valid_competitor(names)
    if not top:
        return ""
    return f" When you were not recommended, {top} came up instead."


def score_line(check: dict | None) -> str:
    """One short figure with its honest label (AI visibility, not overall)."""
    if not check:
        return ""
    s = check.get("visibility_score")
    if s is None:
        return ""
    return f" Your AI visibility score came out at {int(s)} out of 100."


def build_email(p: dict, check: dict | None) -> tuple[str, str]:
    company = p.get("company") or "your firm"
    town = p.get("postcode_town") or p.get("address_town") or _town(p)
    noun = prospect_config.noun_phrase(p.get("industry", ""))
    fname = first_name(p.get("director_name", ""))
    greeting = f"Hi {fname}," if fname else "Hello,"
    where = f" in {town}" if town else ""

    subject = f"{company} isn't coming up when AI recommends {noun}"
    body = f"""{greeting}

I run Antek Automation. I checked how {company} shows up when someone asks ChatGPT, Gemini or Perplexity to recommend {noun}{where}, the searches that increasingly happen instead of a Google search.

{result_sentence(check)}{competitor_sentence(check)}{score_line(check)}

Worth a free 15-minute walkthrough? I will show you what each engine actually says about you and the two or three changes that would help most. No slides, no pitch.

{CTA_URL}

Kind regards,
{SENDER_NAME}
Antek Automation
{SENDER_WEB} · {SENDER_PHONE}"""
    return subject, body


def build_linkedin(p: dict, check: dict | None) -> str:
    company = p.get("company") or "your firm"
    noun = prospect_config.noun_phrase(p.get("industry", ""))
    fname = first_name(p.get("director_name", ""))
    hi = f"Hi {fname}, " if fname else "Hi, "
    note = (f"{hi}I checked how {company} shows up when people ask AI (ChatGPT, "
            f"Gemini, Perplexity) to recommend {noun}. Happy to share the "
            f"short summary if it is useful.")
    if len(note) > LINKEDIN_LIMIT:
        # ponytail: drop the company clause first — it's the longest optional bit
        note = (f"{hi}I checked how you show up when people ask AI to recommend "
                f"{noun}. Happy to share the short summary if useful.")
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
    # PECR routing: email only fires for the email-eligible segment (corporate,
    # channel set to 'email' by companies_house.channel_for). Sole traders /
    # letter-routed prospects get LinkedIn only, never a cold email.
    email_eligible = (p.get("outreach_channel") or "letter") == "email"
    subject, email_body = build_email(p, check)
    li_note = build_linkedin(p, check)

    if not dry_run:
        if email_eligible:
            db.insert_outreach({"prospect_id": p["pk"], "channel": "email",
                                "subject": subject, "body": email_body})
        db.insert_outreach({"prospect_id": p["pk"], "channel": "linkedin",
                            "subject": "", "body": li_note})

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        email_md = (f"## Email\n\n**Subject:** {subject}\n\n{email_body}\n\n"
                    if email_eligible
                    else "## Email\n\n_Skipped: prospect is letter-routed (PECR), not email-eligible._\n\n")
        md = (f"# Outreach — {p.get('company')} ({ref})\n\n"
              f"{email_md}"
              f"## LinkedIn connect note ({len(li_note)}/{LINKEDIN_LIMIT})\n\n{li_note}\n")
        (out_dir / f"OUTREACH-{ref}.md").write_text(md, encoding="utf-8")

    return {"ref": ref, "company": p.get("company"), "subject": subject,
            "email_eligible": email_eligible, "linkedin_len": len(li_note)}


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
                                "outreach_channel": "email", "status": "checked"})
        db.insert_check({"prospect_id": p["pk"], "platforms_tested": 4,
                         "mentioned_count": 1, "visibility_score": 25,
                         "competitors_json": json.dumps([{"name": "Google Maps Search"},
                                                         {"name": "Rival Plumbing Ltd"}])})

        subj, body = build_email(db.get_prospect(p["id"]), db.latest_check(p["pk"]))
        assert "Kevin" in body and "Acme Plumbing Ltd" in subj
        assert "a firm like yours" in subj  # plumbers noun phrase, not "a plumber"
        assert "Basingstoke" in body
        # competitor gate: skips the directory, names the real firm
        assert "Rival Plumbing Ltd came up instead" in body
        assert "Google Maps Search" not in body
        assert "25 out of 100" in body  # honest AI-visibility label
        assert "the other 3 didn't mention you" in body

        li = build_linkedin(db.get_prospect(p["id"]), db.latest_check(p["pk"]))
        assert len(li) <= LINKEDIN_LIMIT and "Kevin" in li

        # letter-routed prospect -> no email row, LinkedIn only (PECR)
        pl = db.insert_prospect({"company": "Sole Trader Plumbing", "industry": "plumbers",
                                 "outreach_channel": "letter", "status": "checked"})
        r = generate_for(pl["id"], None)
        assert r and r["email_eligible"] is False

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
