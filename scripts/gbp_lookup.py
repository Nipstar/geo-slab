#!/usr/bin/env python3
"""
GEO SLAB — Google Business Profile lookup.

Queries the Google Places API (Text Search + Place Details) for a firm's
listing(s) so the platform / brand agents don't have to guess at GBP presence.

Designed to drop into Phase 1 of /geo audit, immediately after the social
harvest step. Reads GOOGLE_PLACES_API_KEY from the environment (and falls back
to a .env.local lookup so it works in this repo without extra config).

Output:
    {
      "query": "Antek Automation Andover SP10",
      "found": true,
      "place_count": 1,
      "places": [
        {
          "name": "Antek Automation",
          "place_id": "...",
          "formatted_address": "Chantry House, 38 Chantry Way, Andover SP10 1LZ, UK",
          "rating": 4.9,
          "user_ratings_total": 23,
          "international_phone_number": "+44 333 038 9960",
          "website": "https://www.antekautomation.com/",
          "opening_hours": [...],
          "types": ["..."],
          "photo_count": 6,
          "url": "https://maps.google.com/?cid=..."
        }
      ],
      "completeness_score": 0..100,
      "issues": ["No photos", "Website mismatch", ...]
    }

Usage:
    python gbp_lookup.py --query "Antek Automation Andover"
    python gbp_lookup.py --name "Antek Automation" --location "Andover SP10"
    python gbp_lookup.py --name "..." --postcode "SP10 1LZ" --output reports/<domain>/gbp.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def _load_dotenv() -> None:
    """Load .env.local from repo root so GOOGLE_PLACES_API_KEY is available."""
    candidates = [
        Path(__file__).resolve().parent.parent / ".env.local",
        Path.cwd() / ".env.local",
        Path.home() / ".env.local",
    ]
    for p in candidates:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            v = v.strip().strip("'").strip('"')
            os.environ.setdefault(k.strip(), v)
        break


def _key() -> str:
    _load_dotenv()
    key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    if not key:
        print("ERROR: GOOGLE_PLACES_API_KEY not set in env or .env.local", file=sys.stderr)
        sys.exit(2)
    return key


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "geo-slab-gbp/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


# ── Text Search ─────────────────────────────────────────────────────────────

PLACES_TEXT_SEARCH = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS = "https://maps.googleapis.com/maps/api/place/details/json"


def text_search(query: str) -> list[dict]:
    key = _key()
    params = {"query": query, "key": key}
    url = f"{PLACES_TEXT_SEARCH}?{urllib.parse.urlencode(params)}"
    data = _http_get_json(url)
    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        print(f"WARN: Places API status={data.get('status')} error={data.get('error_message','')}", file=sys.stderr)
    return data.get("results", [])


def place_details(place_id: str) -> dict:
    key = _key()
    fields = ",".join([
        "name", "formatted_address", "international_phone_number", "website",
        "rating", "user_ratings_total", "opening_hours", "types", "photos",
        "url", "business_status", "place_id",
    ])
    params = {"place_id": place_id, "fields": fields, "key": key}
    url = f"{PLACES_DETAILS}?{urllib.parse.urlencode(params)}"
    return _http_get_json(url).get("result", {})


# ── Scoring ─────────────────────────────────────────────────────────────────

def completeness(place: dict, expected_domain: str | None) -> tuple[int, list[str]]:
    """Score the GBP listing 0-100 + return human-readable issue strings."""
    score = 100
    issues: list[str] = []

    if not place.get("user_ratings_total"):
        score -= 25; issues.append("No reviews on the profile")
    elif place["user_ratings_total"] < 5:
        score -= 15; issues.append(f"Only {place['user_ratings_total']} review(s) — under the 5-review threshold AI engines look for")

    if not place.get("photo_count"):
        score -= 15; issues.append("No photos on the profile")
    elif place["photo_count"] < 5:
        score -= 5; issues.append(f"Only {place['photo_count']} photo(s) — aim for 10+")

    if not place.get("opening_hours"):
        score -= 10; issues.append("Opening hours not set")

    if not place.get("international_phone_number"):
        score -= 10; issues.append("Phone number missing")

    if not place.get("website"):
        score -= 10; issues.append("Website link missing")
    elif expected_domain and expected_domain not in place["website"]:
        score -= 5; issues.append(f"Website on profile ({place['website']}) doesn't match expected domain ({expected_domain})")

    if place.get("business_status") and place["business_status"] != "OPERATIONAL":
        score -= 30; issues.append(f"Business status: {place['business_status']}")

    return max(0, score), issues


def normalise(place: dict) -> dict:
    """Flatten Place Details into the shape we want to ship to agents."""
    photo_count = len(place.get("photos", []) or [])
    hours = []
    if place.get("opening_hours"):
        hours = place["opening_hours"].get("weekday_text") or []
    return {
        "name": place.get("name"),
        "place_id": place.get("place_id"),
        "formatted_address": place.get("formatted_address"),
        "international_phone_number": place.get("international_phone_number"),
        "website": place.get("website"),
        "rating": place.get("rating"),
        "user_ratings_total": place.get("user_ratings_total", 0),
        "business_status": place.get("business_status"),
        "opening_hours": hours,
        "types": place.get("types", []),
        "photo_count": photo_count,
        "url": place.get("url"),
    }


def lookup(query: str, expected_domain: str | None = None, top_n: int = 3) -> dict:
    """End-to-end: text search → details for top_n → completeness scores."""
    results = text_search(query)
    if not results:
        return {
            "query": query, "found": False, "place_count": 0, "places": [],
            "completeness_score": 0, "issues": ["No matching GBP found via text search — listing likely doesn't exist or NAP is too inconsistent for Google to match"],
        }
    places, scores, all_issues = [], [], []
    for r in results[:top_n]:
        pid = r.get("place_id")
        if not pid:
            continue
        detail = place_details(pid)
        flat = normalise(detail)
        s, issues = completeness(flat, expected_domain)
        flat["completeness_score"] = s
        flat["issues"] = issues
        places.append(flat)
        scores.append(s)
        all_issues.append((flat["name"], s, issues))

    best = max(scores) if scores else 0
    return {
        "query": query, "found": True, "place_count": len(places), "places": places,
        "completeness_score": best,
        "issues": [f"{n} ({s}/100): {', '.join(i) or 'no issues'}" for n, s, i in all_issues],
    }


def main():
    p = argparse.ArgumentParser(description="Look up Google Business Profile presence + completeness")
    p.add_argument("--query", help="Free-text search (e.g. 'Wards Solicitors Bristol')")
    p.add_argument("--name", help="Business name")
    p.add_argument("--location", help="City / area / postcode (combined with name)")
    p.add_argument("--postcode", help="UK postcode (combined with name)")
    p.add_argument("--domain", help="Expected website domain for NAP-website cross-check")
    p.add_argument("--output", type=Path, help="Write JSON to file (default: stdout)")
    args = p.parse_args()

    query = args.query or " ".join(x for x in [args.name, args.location, args.postcode] if x)
    if not query:
        print("ERROR: pass --query OR --name + (--location | --postcode)", file=sys.stderr)
        sys.exit(2)

    out = lookup(query, expected_domain=args.domain)
    txt = json.dumps(out, indent=2)
    if args.output:
        args.output.write_text(txt, encoding="utf-8")
        print(f"gbp_lookup: wrote {args.output} — found={out['found']}, completeness={out.get('completeness_score')}", file=sys.stderr)
    else:
        print(txt)


if __name__ == "__main__":
    main()
