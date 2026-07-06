#!/usr/bin/env python3
"""
GEO SLAB — Prospect discovery via Google Places API (New) Text Search.

Query pattern "<trade> in <town>" → prospects table in SQLite (db.py).
Dedupes on place_id then on normalised domain. Skips prospects with no
website (nothing to check) and, unless --allow-chains, obvious chains.

Uses Places API (NEW) — POST places:searchText with a tight field mask, so
website + phone + rating come back in ONE billed request (the legacy API
needs a separate Place Details call per result). Field mask is the cost lever
the spec (§5) calls out.

    python3 places_prospector.py --trade plumber --location "Basingstoke, UK"
    python3 places_prospector.py --query "electricians in Andover" --limit 40
    python3 places_prospector.py --trade roofer --location "Winchester, UK" --dry-run

Requires GOOGLE_PLACES_API_KEY (env or .env.local) with "Places API (New)"
enabled on the GCP project.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402


# ── Env ──────────────────────────────────────────────────────────────────

def _load_dotenv() -> None:
    for p in (
        Path(__file__).resolve().parent.parent / ".env.local",
        Path.cwd() / ".env.local",
        Path.home() / ".env.local",
    ):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))
        break


def _key() -> str:
    _load_dotenv()
    key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    if not key:
        print("ERROR: GOOGLE_PLACES_API_KEY not set in env or .env.local", file=sys.stderr)
        sys.exit(2)
    return key


# ── Places API (New) ───────────────────────────────────────────────────────

SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress",
    "places.location", "places.websiteUri", "places.nationalPhoneNumber",
    "places.rating", "places.userRatingCount", "places.types",
    "nextPageToken",
])
# ponytail: Text Search (New) with contact/atmosphere fields bills ~ the "Pro"
# SKU. Verify current pricing before big batches — override via env if it drifts.
USD_PER_REQUEST = float(os.environ.get("PLACES_USD_PER_REQUEST", "0.035"))
PAGE_SIZE = 20  # Places API (New) hard max


def _search_page(query: str, key: str, page_token: str | None) -> dict:
    body: dict = {"textQuery": query, "regionCode": "GB", "pageSize": PAGE_SIZE}
    if page_token:
        body["pageToken"] = page_token
    req = urllib.request.Request(
        SEARCH_TEXT_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": FIELD_MASK,
            "User-Agent": "geo-slab-prospector/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        if e.code in (403, 401) and ("SERVICE_DISABLED" in detail or "PERMISSION_DENIED" in detail):
            print(
                "ERROR: Places API (New) rejected the request. Enable it at\n"
                "  https://console.cloud.google.com/apis/library/places.googleapis.com\n"
                f"API said: {detail[:400]}",
                file=sys.stderr,
            )
            sys.exit(3)
        print(f"ERROR: Places API HTTP {e.code}: {detail[:400]}", file=sys.stderr)
        sys.exit(3)


def search_text(query: str, limit: int) -> list[dict]:
    """Page through Places (New) Text Search up to `limit` results."""
    key = _key()
    results: list[dict] = []
    token: str | None = None
    while len(results) < limit:
        data = _search_page(query, key, token)
        results.extend(data.get("places", []))
        token = data.get("nextPageToken")
        if not token:
            break
    return results[:limit]


# ── Parsing helpers ──────────────────────────────────────────────────────

_UK_POSTCODE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})\b", re.I)

# Minimal chain/franchise skip list. Extend as needed; --allow-chains bypasses.
CHAIN_KEYWORDS = {
    "pimlico", "dyno", "british gas", "checkatrade", "rated people",
    "homeserve", "247", "24/7", "mears", "npower",
}


def normalise_domain(website: str | None) -> str:
    if not website:
        return ""
    d = website.strip().lower().rstrip("/")
    for pre in ("https://", "http://"):
        if d.startswith(pre):
            d = d[len(pre):]
    if d.startswith("www."):
        d = d[4:]
    return d.split("/")[0]


def extract_postcode(address: str | None) -> str:
    if not address:
        return ""
    m = _UK_POSTCODE.search(address)
    return f"{m.group(1).upper()} {m.group(2).upper()}" if m else ""


def is_chain(name: str) -> bool:
    low = (name or "").lower()
    return any(kw in low for kw in CHAIN_KEYWORDS)


def to_prospect(place: dict, industry: str, campaign: str) -> dict | None:
    website = place.get("websiteUri")
    domain = normalise_domain(website)
    if not domain:
        return None  # no website = nothing to check
    loc = place.get("location") or {}
    # Google display names sometimes carry emoji/badges (e.g. "⭐Chartered…") —
    # strip non-ASCII so a mail-merge salutation/letterhead stays clean.
    raw_name = (place.get("displayName") or {}).get("text") or ""
    company = re.sub(r"[^\x00-\x7f]", "", raw_name).strip(" \t-•*·")
    return {
        "company": company,
        "domain": domain,
        "website": website,
        "place_id": place.get("id"),
        "phone": place.get("nationalPhoneNumber"),
        "address": place.get("formattedAddress"),
        "postcode": extract_postcode(place.get("formattedAddress")),
        "lat": loc.get("latitude"),
        "lng": loc.get("longitude"),
        "rating": place.get("rating"),
        "review_count": place.get("userRatingCount"),
        "industry": industry,
        "source": "places",
        "campaign": campaign,
        "status": "found",
    }


def slug_campaign(trade: str, location: str) -> str:
    town = (location or "").split(",")[0]
    stamp = datetime.now().strftime("%b%y").lower()
    base = f"{trade}-{town}-{stamp}"
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")


# ── Run ──────────────────────────────────────────────────────────────────

def run(query: str, industry: str, campaign: str, limit: int,
        allow_chains: bool, dry_run: bool, max_spend: float | None) -> dict:
    # Budget guard (§5): estimate worst-case request count before spending.
    est_requests = -(-limit // PAGE_SIZE)  # ceil
    est_cost = est_requests * USD_PER_REQUEST
    if max_spend is not None and est_cost > max_spend:
        print(
            f"ABORT: estimated ${est_cost:.2f} ({est_requests} requests) exceeds "
            f"--max-spend ${max_spend:.2f}. Lower --limit or raise the cap.",
            file=sys.stderr,
        )
        sys.exit(4)

    places = search_text(query, limit)

    conn = db.connect()
    existing_pids = {r[0] for r in conn.execute("SELECT place_id FROM prospects WHERE place_id IS NOT NULL")}
    existing_domains = {r[0] for r in conn.execute("SELECT domain FROM prospects WHERE domain IS NOT NULL")}

    inserted, skipped_dupe, skipped_noweb, skipped_chain = 0, 0, 0, 0
    seen_domains: set[str] = set()
    new_refs: list[str] = []

    for place in places:
        p = to_prospect(place, industry, campaign)
        if p is None:
            skipped_noweb += 1
            continue
        if not allow_chains and is_chain(p["company"]):
            skipped_chain += 1
            continue
        if p["place_id"] in existing_pids:
            skipped_dupe += 1
            continue
        if p["domain"] in existing_domains or p["domain"] in seen_domains:
            skipped_dupe += 1
            continue
        seen_domains.add(p["domain"])
        if dry_run:
            inserted += 1
            new_refs.append(f"(dry) {p['company']} — {p['domain']}")
            continue
        created = db.insert_prospect(p, conn)
        inserted += 1
        new_refs.append(f"{created['id']} {p['company']} — {p['domain']}")

    conn.close()
    return {
        "query": query, "campaign": campaign, "found_raw": len(places),
        "inserted": inserted, "skipped_dupe": skipped_dupe,
        "skipped_nowebsite": skipped_noweb, "skipped_chain": skipped_chain,
        "est_cost_usd": round(est_cost, 3), "refs": new_refs, "dry_run": dry_run,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Discover prospects via Google Places (New) → SQLite")
    ap.add_argument("--query", help='Full query, e.g. "plumbers in Basingstoke"')
    ap.add_argument("--trade", help='Trade term, e.g. "plumber" (combined with --location)')
    ap.add_argument("--location", help='Town, e.g. "Basingstoke, UK"')
    ap.add_argument("--limit", type=int, default=20, help="Max results to consider (default 20)")
    ap.add_argument("--campaign", help="Campaign tag (auto-derived from trade+location if omitted)")
    ap.add_argument("--allow-chains", action="store_true", help="Keep chains/franchises")
    ap.add_argument("--max-spend", type=float, help="Abort if estimated USD cost exceeds this")
    ap.add_argument("--dry-run", action="store_true", help="Search + report, do not insert")
    args = ap.parse_args()

    query = args.query or (f"{args.trade} in {args.location}" if args.trade and args.location else None)
    if not query:
        print("ERROR: pass --query OR --trade + --location", file=sys.stderr)
        sys.exit(2)

    industry = args.trade or query.split(" in ")[0]
    campaign = args.campaign or slug_campaign(industry, args.location or query)

    db.init_db()
    out = run(query, industry, campaign, args.limit,
              args.allow_chains, args.dry_run, args.max_spend)

    verb = "would insert" if out["dry_run"] else "inserted"
    print(f"\nPlaces discovery — query: {query!r}  campaign: {campaign}")
    print(f"  raw results: {out['found_raw']}   {verb}: {out['inserted']}")
    print(f"  skipped — dupe: {out['skipped_dupe']}, no-website: {out['skipped_nowebsite']}, chain: {out['skipped_chain']}")
    print(f"  est. cost: ${out['est_cost_usd']}")
    for r in out["refs"]:
        print(f"    + {r}")


# ── Self-check ─────────────────────────────────────────────────────────────

def _demo() -> None:
    assert normalise_domain("https://www.Acme-Plumbing.co.uk/contact/") == "acme-plumbing.co.uk"
    assert normalise_domain("http://foo.com") == "foo.com"
    assert normalise_domain(None) == ""
    assert extract_postcode("12 High St, Basingstoke RG21 7QW, UK") == "RG21 7QW"
    assert extract_postcode("London SW1A 1AA") == "SW1A 1AA"
    assert extract_postcode("no postcode here") == ""
    assert is_chain("Pimlico Plumbers")
    assert not is_chain("Dave's Local Plumbing")
    p = to_prospect(
        {"id": "X1", "displayName": {"text": "Dave Plumbing"},
         "websiteUri": "https://daveplumbing.co.uk", "formattedAddress": "1 A St, Andover SP10 1AA",
         "location": {"latitude": 51.2, "longitude": -1.4}, "rating": 4.8, "userRatingCount": 30,
         "nationalPhoneNumber": "01264 123456"},
        "plumber", "test-campaign",
    )
    assert p["company"] == "Dave Plumbing" and p["domain"] == "daveplumbing.co.uk"
    assert p["postcode"] == "SP10 1AA" and p["review_count"] == 30 and p["status"] == "found"
    assert to_prospect({"id": "X2", "displayName": {"text": "No Web Co"}}, "x", "c") is None
    assert slug_campaign("plumber", "Basingstoke, UK").startswith("plumber-basingstoke-")
    print("places_prospector.py self-check passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        _demo()
    else:
        main()
