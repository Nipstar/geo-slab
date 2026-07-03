#!/usr/bin/env python3
"""
GEO SLAB — Companies House enrichment (spec §6).

For each prospect: search CH by trading name, fuzzy-match against registered
companies (token-sort name ratio + postcode-district signal + active status),
and on a confident match pull type / status / registered address / SIC /
incorporation date + the primary active (natural-person) director.

A no-match is a SIGNAL, not a failure: an unregistered business is a probable
sole trader / partnership, which drives the outreach channel (§8, PECR).

Also writes `outreach_channel` at enrich time:
    matched active company + email on file  → email
    matched active company, no email        → letter
    no confident match (sole trader)        → letter        (PECR: individual)

Confidence tiers (spec §6): >=0.8 auto-accept, 0.5-0.8 review queue, <0.5 leave
unmatched. `companies_house.py --review` lists the 0.5-0.8 band.

    python3 companies_house.py --prospect PRO-001
    python3 companies_house.py --batch found --limit 25
    python3 companies_house.py --review

Auth: COMPANIES_HOUSE_API_KEY (HTTP basic — key as username, blank password).
Rate limit: 600 requests / 5 min. ~3 calls per prospect; a small sleep keeps
batches well under.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402
from lib.ai_query_core import load_env  # noqa: E402

CH_BASE = "https://api.company-information.service.gov.uk"
_LEGAL_SUFFIXES = {"ltd", "limited", "llp", "plc", "lp", "co", "company", "cic"}
CORPORATE_TYPES = ("ltd", "plc", "llp", "limited", "public")  # substrings in CH `type`


# ── Auth + HTTP ────────────────────────────────────────────────────────────

def _auth_header() -> str:
    load_env()
    key = os.environ.get("COMPANIES_HOUSE_API_KEY", "").strip()
    if not key:
        print("ERROR: COMPANIES_HOUSE_API_KEY not set (env or .env.local)", file=sys.stderr)
        sys.exit(2)
    token = base64.b64encode(f"{key}:".encode()).decode()
    return f"Basic {token}"


def _get(path: str, params: dict | None = None) -> dict | None:
    url = f"{CH_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": _auth_header(),
                                               "User-Agent": "geo-slab-ch/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        if e.code == 429:
            print("WARN: CH rate limit (429) — backing off 20s", file=sys.stderr)
            time.sleep(20)
            return _get(path, params)
        print(f"WARN: CH HTTP {e.code} on {path}: {e.read().decode('utf-8','replace')[:200]}", file=sys.stderr)
        return None


# ── Matching ────────────────────────────────────────────────────────────────

def normalise_name(name: str) -> str:
    n = re.sub(r"[^a-z0-9\s]", " ", (name or "").lower())
    tokens = [t for t in n.split() if t not in _LEGAL_SUFFIXES]
    return " ".join(tokens)


def token_sort_ratio(a: str, b: str) -> float:
    a2 = " ".join(sorted(normalise_name(a).split()))
    b2 = " ".join(sorted(normalise_name(b).split()))
    if not a2 or not b2:
        return 0.0
    return SequenceMatcher(None, a2, b2).ratio()


def postcode_district(pc: str) -> str:
    """Outward code, e.g. 'RG21 7QW' -> 'RG21'."""
    if not pc:
        return ""
    m = re.match(r"\s*([A-Z]{1,2}\d[A-Z\d]?)", pc.upper())
    return m.group(1) if m else ""


def match_confidence(trading_name: str, trading_pc: str, candidate: dict) -> float:
    """Score a CH search candidate 0-1 against the prospect."""
    name_ratio = token_sort_ratio(trading_name, candidate.get("title", ""))

    cand_pc = ""
    addr = candidate.get("address") or {}
    cand_pc = addr.get("postal_code") or ""
    if not cand_pc:
        # search results sometimes only carry address_snippet
        m = re.search(r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}", (candidate.get("address_snippet") or "").upper())
        cand_pc = m.group(0) if m else ""

    # Name is the primary signal. Postcode is confirmation, not a gate: small
    # firms register at the director's home / accountant, so a district mismatch
    # is common for a genuine match — mild penalty, not a veto. A district match
    # is a positive boost. Ambiguous cases (good-but-not-exact name + mismatch)
    # fall into the 0.5-0.8 review band for a human to eyeball.
    score = name_ratio
    d1, d2 = postcode_district(trading_pc), postcode_district(cand_pc)
    if d1 and d2:
        score = min(1.0, score + 0.10) if d1 == d2 else score * 0.85
    if candidate.get("company_status") != "active":
        score *= 0.3   # spec: a confident match must be active
    return round(min(1.0, score), 3)


def best_candidate(trading_name: str, trading_pc: str, candidates: list[dict]) -> tuple[dict | None, float]:
    best, best_score = None, 0.0
    for c in candidates[:5]:
        s = match_confidence(trading_name, trading_pc, c)
        if s > best_score:
            best, best_score = c, s
    return best, best_score


def primary_director(officers: list[dict]) -> str:
    """First active, natural-person director."""
    for o in officers:
        role = (o.get("officer_role") or "").lower()
        if "director" not in role:
            continue
        if o.get("resigned_on"):
            continue
        if (o.get("officer_role") and o.get("identification")):  # corporate officer marker
            # corporate officers carry an `identification` block; skip them
            if o.get("identification", {}).get("identification_type"):
                continue
        return o.get("name", "")
    return ""


def channel_for(matched: bool, ch_type: str, email: str) -> str:
    """§8 PECR channel routing, decided at enrich time."""
    is_corporate = matched and any(t in (ch_type or "").lower() for t in CORPORATE_TYPES)
    if is_corporate:
        return "email" if email else "letter"
    return "letter"  # sole trader / unmatched → individual under PECR → letter only


# ── Enrichment ──────────────────────────────────────────────────────────────

def enrich_prospect(ref: str, dry_run: bool = False, conn=None) -> dict:
    close = conn is None
    conn = conn or db.connect()
    try:
        p = db.get_prospect(ref, conn)
        if not p:
            return {"ref": ref, "error": "not found"}

        search = _get("/search/companies", {"q": p["company"], "items_per_page": 5}) or {}
        candidates = search.get("items", [])
        cand, confidence = best_candidate(p["company"], p.get("postcode") or "", candidates)

        update: dict = {"ch_match_confidence": confidence}
        summary = {"ref": ref, "company": p["company"], "confidence": confidence, "matched": False}

        if cand and confidence >= 0.5:
            number = cand.get("company_number")
            detail = _get(f"/company/{number}") or {}
            officers = (_get(f"/company/{number}/officers", {"register_type": "directors"}) or {}).get("items", [])
            reg = detail.get("registered_office_address") or {}
            reg_str = ", ".join(x for x in [
                reg.get("address_line_1"), reg.get("address_line_2"),
                reg.get("locality"), reg.get("postal_code"),
            ] if x)
            director = primary_director(officers)
            update.update({
                "ch_number": number,
                "ch_name": detail.get("company_name") or cand.get("title"),
                "ch_status": detail.get("company_status") or cand.get("company_status"),
                "ch_type": detail.get("type") or cand.get("company_type"),
                "ch_registered_address": reg_str,
                "ch_incorporated": detail.get("date_of_creation"),
                "ch_sic": ", ".join(detail.get("sic_codes") or []),
                "director_name": director,
            })
            summary.update({"matched": confidence >= 0.8, "review": 0.5 <= confidence < 0.8,
                            "ch_name": update["ch_name"], "ch_number": number,
                            "director": director, "ch_type": update["ch_type"]})

        matched_confident = confidence >= 0.8
        update["outreach_channel"] = channel_for(
            matched_confident, update.get("ch_type", ""), p.get("email") or "")
        summary["outreach_channel"] = update["outreach_channel"]

        # advance status found→enriched (never downgrade checked/later)
        if p["status"] == "found":
            update["status"] = "enriched"

        if not dry_run:
            db.update_prospect(ref, update, conn)
        return summary
    finally:
        if close:
            conn.close()


def review_queue(conn=None) -> list[dict]:
    close = conn is None
    conn = conn or db.connect()
    try:
        rows = conn.execute(
            "SELECT ref, company, ch_name, ch_match_confidence FROM prospects "
            "WHERE ch_match_confidence >= 0.5 AND ch_match_confidence < 0.8 "
            "ORDER BY ch_match_confidence DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if close:
            conn.close()


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Companies House enrichment → SQLite")
    ap.add_argument("--prospect", help="Single prospect ref (PRO-001)")
    ap.add_argument("--batch", help="Enrich all prospects with this status (e.g. found)")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--review", action="store_true", help="List 0.5-0.8 confidence matches needing review")
    ap.add_argument("--linkedin", action="store_true",
                    help="After CH match, also run Apify LinkedIn enrichment (costed — Phase 8)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db.init_db()

    if args.review:
        rows = review_queue()
        print(f"CH review queue — {len(rows)} match(es) at 0.5-0.8 confidence:")
        for r in rows:
            print(f"  {r['ref']}  {r['company']!r}  ~  CH: {r['ch_name']!r}  ({r['ch_match_confidence']})")
        return

    refs: list[str] = []
    if args.prospect:
        refs = [args.prospect]
    elif args.batch:
        conn = db.connect()
        refs = [r[0] for r in conn.execute(
            "SELECT ref FROM prospects WHERE status = ? ORDER BY ref LIMIT ?",
            (args.batch, args.limit))]
        conn.close()
    else:
        print("ERROR: pass --prospect PRO-001 OR --batch <status> OR --review", file=sys.stderr)
        sys.exit(2)

    conn = db.connect()
    n_match = n_review = n_none = 0
    for ref in refs:
        s = enrich_prospect(ref, dry_run=args.dry_run, conn=conn)
        if s.get("error"):
            print(f"  {ref}: {s['error']}"); continue
        if s.get("matched"):
            n_match += 1
            tag = "MATCH"
        elif s.get("review"):
            n_review += 1
            tag = "REVIEW"
        else:
            n_none += 1
            tag = "no-match"
        print(f"  [{tag:8}] {ref} {s['company']!r} conf={s['confidence']} "
              f"director={s.get('director','')!r} channel={s['outreach_channel']}")
        if args.linkedin and s.get("director"):
            import apify_linkedin  # lazy — avoids the companies_house<->apify_linkedin cycle
            li = apify_linkedin.enrich_linkedin(ref, dry_run=args.dry_run, conn=conn)
            print(f"           └─ LinkedIn: company={li.get('li_company_url')} "
                  f"person={li.get('li_person_url')} (~${li.get('cost_usd')})")
        time.sleep(0.4)  # stay under 600/5min
    conn.close()
    print(f"\nEnriched {len(refs)}: {n_match} matched, {n_review} need review, {n_none} unmatched (likely sole traders)")


# ── Self-check (offline) ───────────────────────────────────────────────────

def _demo() -> None:
    assert normalise_name("K B Plumbing & Heating Ltd") == "k b plumbing heating"
    assert token_sort_ratio("Options Plumbing Ltd", "OPTIONS PLUMBING LIMITED") > 0.95
    assert token_sort_ratio("Heating Plumbing Options", "Options Plumbing Heating") > 0.95  # order-insensitive
    assert postcode_district("RG21 7QW") == "RG21"
    assert postcode_district("sp10 1lz") == "SP10"

    active_same_pc = {"title": "OPTIONS PLUMBING AND HEATING LTD", "company_status": "active",
                      "company_type": "ltd", "address_snippet": "1 St, Basingstoke RG23 8PX"}
    hi = match_confidence("Options Plumbing and Heating Ltd", "RG23 8PX", active_same_pc)
    assert hi >= 0.8, hi

    dissolved = {**active_same_pc, "company_status": "dissolved"}
    assert match_confidence("Options Plumbing and Heating Ltd", "RG23 8PX", dissolved) < 0.5

    # District mismatch penalises but does not veto a strong name match; it must
    # still score strictly below the same-district case.
    wrong_pc = {**active_same_pc, "address_snippet": "1 St, Leeds LS1 1AA"}
    assert match_confidence("Options Plumbing and Heating Ltd", "RG23 8PX", wrong_pc) \
        < match_confidence("Options Plumbing and Heating Ltd", "RG23 8PX", active_same_pc)

    # channel routing (§8)
    assert channel_for(True, "ltd", "a@b.com") == "email"
    assert channel_for(True, "ltd", "") == "letter"
    assert channel_for(False, "", "a@b.com") == "letter"   # sole trader → letter even with email
    assert channel_for(True, "llp", "") == "letter"

    # director selection: skip resigned + corporate officers
    officers = [
        {"name": "OLD, Bob", "officer_role": "director", "resigned_on": "2020-01-01"},
        {"name": "ACME NOMINEES LTD", "officer_role": "corporate-director",
         "identification": {"identification_type": "non-eea"}},
        {"name": "SMITH, Jane", "officer_role": "director"},
    ]
    assert primary_director(officers) == "SMITH, Jane", primary_director(officers)
    print("companies_house self-check passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        _demo()
    else:
        main()
