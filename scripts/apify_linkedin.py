#!/usr/bin/env python3
"""
GEO SLAB — LinkedIn enrichment via Apify (spec §6 / Phase 8).

A personalisation MULTIPLIER, not a dependency. Run it ONLY on shortlisted
prospects — after the free visibility check shows a story worth telling
(prospect invisible, competitors cited). Never batch the whole `found` pool:
LinkedIn actors cost real money per result.

Inputs come from earlier phases: company name (Places) + primary director
(Companies House). Outputs → li_company_url, li_person_url, li_person_title,
li_headcount on the prospect row. Used for email personalisation and the
LinkedIn connect campaign layer.

Actor slugs are env-overridable because Apify LinkedIn actors drift / get
delisted — defaults are verified current but check APIFY_* env if a run 404s.

    python3 apify_linkedin.py --prospect PRO-003
    python3 apify_linkedin.py --batch checked --max-profiles 10
    python3 apify_linkedin.py --prospect PRO-003 --dry-run

Auth: APIFY_API_TOKEN.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402
from lib.ai_query_core import load_env  # noqa: E402
from companies_house import token_sort_ratio  # noqa: E402  (name-match sanity gate)

# LinkedIn company search matches on a bare name and readily returns the WRONG
# firm (e.g. "Options" → "Options Bath & Tile Studio"). Reject a company result
# whose returned name doesn't reasonably match the prospect — a wrong company
# URL poisons personalised outreach, so no data beats bad data.
COMPANY_NAME_MATCH_MIN = 0.5

APIFY_BASE = "https://api.apify.com/v2"

# ── Actor config (env-overridable — see module docstring) ──────────────────
# Defaults verified live against Apify Store (2026-07-03): both harvestapi
# actors are cookieless, pay-per-result, ~99-100% success. Prices are BRONZE
# tier per-result (GOLD+ ~25% cheaper). Slugs drift — override via env if a
# run 404s.

COMPANY_ACTOR = os.environ.get("APIFY_LINKEDIN_COMPANY_ACTOR", "harvestapi/linkedin-company")
PERSON_ACTOR = os.environ.get("APIFY_LINKEDIN_PERSON_ACTOR", "harvestapi/linkedin-profile-search-by-name")
COMPANY_PRICE = float(os.environ.get("APIFY_LINKEDIN_COMPANY_PRICE", "0.004"))
PERSON_PRICE = float(os.environ.get("APIFY_LINKEDIN_PERSON_PRICE", "0.002"))


# ── Apify REST ──────────────────────────────────────────────────────────────

def _token() -> str:
    load_env()
    tok = os.environ.get("APIFY_API_TOKEN", "").strip()
    if not tok:
        print("ERROR: APIFY_API_TOKEN not set (env or .env.local)", file=sys.stderr)
        sys.exit(2)
    return tok


def run_sync(actor_slug: str, run_input: dict, timeout: int = 180) -> list[dict]:
    """Run an actor synchronously and return its dataset items.
    Actor slug 'user/name' -> path 'user~name'."""
    actor_path = actor_slug.replace("/", "~")
    url = (f"{APIFY_BASE}/acts/{actor_path}/run-sync-get-dataset-items"
           f"?token={urllib.parse.quote(_token())}")
    req = urllib.request.Request(
        url, data=json.dumps(run_input).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "geo-slab-apify/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"WARN: Apify actor {actor_slug} HTTP {e.code}: "
              f"{e.read().decode('utf-8','replace')[:300]}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"WARN: Apify actor {actor_slug} error: {e}", file=sys.stderr)
        return []


# ── Actor adapters (harvestapi input/output shapes) ────────────────────────

def build_company_input(company: str, website: str | None = None) -> dict:
    return {"searches": [company]}


def parse_company_output(items: list[dict]) -> dict:
    if not items:
        return {}
    it = items[0]
    headcount = it.get("employeeCountRange") or {}
    if isinstance(headcount, dict) and headcount.get("start"):
        end = headcount.get("end")
        hc = f"{headcount['start']}-{end}" if end else f"{headcount['start']}+"
    else:
        hc = str(it.get("employeeCount")) if it.get("employeeCount") else ""
    return {"li_company_url": it.get("linkedinUrl") or "", "li_headcount": hc,
            "name": it.get("name") or ""}


def split_director_name(name: str) -> tuple[str, str]:
    """CH gives 'SURNAME, Firstname Middle'. Return (first, last), title-cased."""
    name = (name or "").strip()
    if "," in name:
        surname, _, given = name.partition(",")
        first = given.strip().split()[0] if given.strip().split() else ""
        return first.title(), surname.strip().title()
    parts = name.split()
    if len(parts) >= 2:
        return parts[0].title(), parts[-1].title()
    return name.title(), ""


def build_person_input(director_name: str, company: str, company_url: str = "") -> dict:
    first, last = split_director_name(director_name)
    inp = {"profileScraperMode": "Short", "firstName": first, "lastName": last,
           "strictSearch": True, "maxItems": 1, "maxPages": 1}
    if company_url:
        inp["currentCompanies"] = [company_url]  # disambiguate by employer (chained from Job A)
    return inp


def parse_person_output(items: list[dict]) -> dict:
    if not items:
        return {}
    it = items[0]
    return {"li_person_url": it.get("linkedinUrl") or "",
            "li_person_title": it.get("position") or it.get("headline") or ""}


def enrich_linkedin(ref: str, dry_run: bool = False, conn=None) -> dict:
    close = conn is None
    conn = conn or db.connect()
    try:
        p = db.get_prospect(ref, conn)
        if not p:
            return {"ref": ref, "error": "not found"}
        if not p.get("director_name") and not p.get("company"):
            return {"ref": ref, "error": "no company/director to look up"}

        update: dict = {}
        cost = 0.0
        company_url = ""
        summary = {"ref": ref, "company": p["company"]}

        # Company page + headcount — gated on a name-match sanity check
        if COMPANY_ACTOR:
            items = run_sync(COMPANY_ACTOR, build_company_input(p["company"], p.get("website")))
            comp = parse_company_output(items)
            ratio = token_sort_ratio(p["company"], comp.get("name", "")) if comp else 0.0
            if comp.get("li_company_url") and ratio >= COMPANY_NAME_MATCH_MIN:
                company_url = comp["li_company_url"]
                update["li_company_url"] = company_url
                if comp.get("li_headcount"):
                    update["li_headcount"] = comp["li_headcount"]
            elif comp.get("name"):
                summary["company_rejected"] = f"{comp['name']!r} (match {ratio:.2f})"
            cost += (len(items) or 0) * COMPANY_PRICE

        # Person profile + title — ONLY when we have a verified company URL to
        # disambiguate. Name-only search finds namesakes (a different "Rory
        # Hodder" at Expedia), which is worse than no data for outreach.
        if PERSON_ACTOR and p.get("director_name") and company_url:
            items = run_sync(PERSON_ACTOR, build_person_input(p["director_name"], p["company"], company_url))
            person = parse_person_output(items)
            if person.get("li_person_url"):
                update["li_person_url"] = person["li_person_url"]
            if person.get("li_person_title"):
                update["li_person_title"] = person["li_person_title"]
            cost += (len(items) or 0) * PERSON_PRICE

        summary.update({k: update.get(k) for k in
                        ("li_company_url", "li_person_url", "li_person_title", "li_headcount")})
        summary["cost_usd"] = round(cost, 4)

        if update and not dry_run:
            db.update_prospect(ref, update, conn)
            db.add_note(ref, f"LinkedIn enriched via Apify (~${round(cost,4)})", conn)
        return summary
    finally:
        if close:
            conn.close()


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="LinkedIn enrichment via Apify → SQLite")
    ap.add_argument("--prospect", help="Single prospect ref (PRO-003)")
    ap.add_argument("--batch", help="Status to enrich (default checked) — shortlist only",
                    nargs="?", const="checked")
    ap.add_argument("--max-profiles", type=int, default=10,
                    help="Hard cap on prospects enriched this run (cost guard)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not COMPANY_ACTOR and not PERSON_ACTOR:
        print("ERROR: no Apify LinkedIn actor configured. Set APIFY_LINKEDIN_COMPANY_ACTOR "
              "and/or APIFY_LINKEDIN_PERSON_ACTOR (see module docstring).", file=sys.stderr)
        sys.exit(2)

    db.init_db()
    refs: list[str] = []
    if args.prospect:
        refs = [args.prospect]
    elif args.batch:
        conn = db.connect()
        # Shortlist guard: only prospects with a director (a person to find) at
        # the given status. Never the whole `found` pool.
        refs = [r[0] for r in conn.execute(
            "SELECT ref FROM prospects WHERE status = ? AND director_name IS NOT NULL "
            "AND director_name != '' ORDER BY ref LIMIT ?",
            (args.batch, args.max_profiles))]
        conn.close()
        if not refs:
            print(f"No shortlisted prospects (status={args.batch}, with a director). "
                  "Run /geo check + /geo enrich first.", file=sys.stderr)
            return
    else:
        print("ERROR: pass --prospect PRO-003 OR --batch [status]", file=sys.stderr)
        sys.exit(2)

    if len(refs) > args.max_profiles:
        refs = refs[:args.max_profiles]

    conn = db.connect()
    total_cost = 0.0
    for ref in refs:
        s = enrich_linkedin(ref, dry_run=args.dry_run, conn=conn)
        if s.get("error"):
            print(f"  {ref}: {s['error']}"); continue
        total_cost += s.get("cost_usd", 0.0)
        line = (f"  {ref} {s['company']!r} → company={s.get('li_company_url')} "
                f"person={s.get('li_person_url')} title={s.get('li_person_title')!r} "
                f"headcount={s.get('li_headcount')} (~${s.get('cost_usd')})")
        if s.get("company_rejected"):
            line += f"  [company rejected: {s['company_rejected']}]"
        print(line)
    conn.close()
    print(f"\nLinkedIn enriched {len(refs)} prospect(s), est. total ~${round(total_cost,4)}")


# ── Self-check (offline) ───────────────────────────────────────────────────

def _demo() -> None:
    assert split_director_name("HODDER, Rory Philip") == ("Rory", "Hodder")
    assert split_director_name("LE ROUX, Jacques") == ("Jacques", "Le Roux") or \
        split_director_name("LE ROUX, Jacques") == ("Jacques", "Le roux")  # title() quirk ok
    assert split_director_name("Jane Smith") == ("Jane", "Smith")
    assert build_company_input("Options Plumbing Ltd") == {"searches": ["Options Plumbing Ltd"]}

    comp = parse_company_output([{"linkedinUrl": "https://linkedin.com/company/options",
                                  "employeeCountRange": {"start": 11, "end": 50}}])
    assert comp["li_company_url"].endswith("/options") and comp["li_headcount"] == "11-50", comp
    assert parse_company_output([{"linkedinUrl": "x", "employeeCount": 7}])["li_headcount"] == "7"
    assert parse_company_output([]) == {}

    pin = build_person_input("HODDER, Rory Philip", "Options", "https://linkedin.com/company/options")
    assert pin["firstName"] == "Rory" and pin["lastName"] == "Hodder"
    assert pin["currentCompanies"] == ["https://linkedin.com/company/options"]
    assert pin["profileScraperMode"] == "Short"
    # no company URL → no currentCompanies key
    assert "currentCompanies" not in build_person_input("HODDER, Rory", "Options")

    person = parse_person_output([{"linkedinUrl": "https://linkedin.com/in/rory", "position": "Director"}])
    assert person["li_person_url"].endswith("/rory") and person["li_person_title"] == "Director"

    # name-match gate: a real match passes, a wrong-firm match is rejected
    assert token_sort_ratio("Options Plumbing and Heating Ltd", "Options Plumbing & Heating") >= COMPANY_NAME_MATCH_MIN
    assert token_sort_ratio("Options Plumbing and Heating Ltd", "Options Bath & Tile Studio") < COMPANY_NAME_MATCH_MIN
    print("apify_linkedin self-check passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        _demo()
    else:
        main()

