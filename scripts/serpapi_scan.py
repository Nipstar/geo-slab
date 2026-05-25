#!/usr/bin/env python3
"""
GEO SLAB — SerpAPI brand presence scan.

Pulls real SERP data so the platform / brand subagents stop guessing about
external signals. One call per query, cached on disk for 24h.

Default scans (UK locale):
  1.  Brand-name SERP        — knowledge panel? sitelinks? top organic position?
  2.  site:reddit.com brand  — Reddit footprint count + sample threads
  3.  site:youtube.com brand — YouTube video / channel count
  4.  brand + reviews        — Trustpilot/G2/Capterra/Clutch surface positions
  5.  "<brand>" news         — News mentions (last 30 days proxy via tbs)
  6.  site:wikipedia.org brand — quick sanity check (Wikidata lookup is primary)
  7.  Optional: "best <service> in <town>" — local pack presence

Output:
    {
      "brand": "Antek Automation",
      "domain": "antekautomation.com",
      "queries": {
        "brand_serp": { "knowledge_panel": {...}, "top_results": [...], "site_in_top_10": true },
        "reddit":     { "count": 0, "samples": [] },
        ...
      },
      "summary": {
        "knowledge_panel_present": true,
        "wikipedia_in_results":    false,
        "reddit_footprint":        0,
        "youtube_results":         12,
        "review_directories":      ["clutch.co", "g.co/maps", "..."]
      }
    }

Usage:
    python serpapi_scan.py --brand "Antek Automation" --domain antekautomation.com \\
                           --output reports/<domain>/serpapi.json
    python serpapi_scan.py --brand "Wards Solicitors" --domain wards.uk.com \\
                           --service "family law" --location "Bristol"

Requires SERPAPI_API_KEY in env or .env.local.
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


SERPAPI_URL = "https://serpapi.com/search.json"
CACHE_DIR = Path.home() / ".geo-slab" / "cache" / "serpapi"
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24h


def _load_dotenv():
    for p in [
        Path(__file__).resolve().parent.parent / ".env.local",
        Path.cwd() / ".env.local",
        Path.home() / ".env.local",
    ]:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))
            break


def _key():
    _load_dotenv()
    k = os.environ.get("SERPAPI_API_KEY", "").strip()
    if not k:
        print("ERROR: SERPAPI_API_KEY not set in env or .env.local", file=sys.stderr)
        sys.exit(2)
    return k


def _cache_path(params):
    """Stable cache filename keyed on the API params (minus the key)."""
    clean = {k: v for k, v in params.items() if k != "api_key"}
    h = hashlib.sha256(json.dumps(clean, sort_keys=True).encode()).hexdigest()[:16]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{h}.json"


def _serpapi(params):
    """Single SerpAPI call with 24h disk cache."""
    cache = _cache_path(params)
    if cache.exists() and (time.time() - cache.stat().st_mtime) < CACHE_TTL_SECONDS:
        return json.loads(cache.read_text(encoding="utf-8"))
    params = dict(params)
    params["api_key"] = _key()
    url = f"{SERPAPI_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "geo-slab-serpapi/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8")
    cache.write_text(body, encoding="utf-8")
    return json.loads(body)


# ── Scan helpers ────────────────────────────────────────────────────────────

UK = {"engine": "google", "gl": "uk", "hl": "en", "google_domain": "google.co.uk", "num": "10"}


def scan_brand_serp(brand, domain):
    """Knowledge panel + top organic + sitelinks for the brand query itself."""
    data = _serpapi({**UK, "q": brand})
    kp = data.get("knowledge_graph") or {}
    organic = data.get("organic_results") or []
    domain_in_top = any(domain and domain in (r.get("link") or "") for r in organic[:10])
    return {
        "knowledge_panel": {
            "present": bool(kp),
            "title": kp.get("title"),
            "type": kp.get("type"),
            "description": kp.get("description"),
            "website": kp.get("website"),
            "kgmid": kp.get("kgmid"),
            "rating": kp.get("rating"),
            "review_count": kp.get("review_count") or kp.get("reviews"),
            "social_profiles": kp.get("profiles") or [],
        } if kp else {"present": False},
        "site_in_top_10": domain_in_top,
        "top_results": [
            {"position": r.get("position"), "title": r.get("title"),
             "link": r.get("link"), "displayed_link": r.get("displayed_link")}
            for r in organic[:5]
        ],
        "answer_box":   data.get("answer_box"),
        "related_questions": [q.get("question") for q in (data.get("related_questions") or [])][:5],
    }


def scan_count(brand, modifier, label):
    """Count organic results for `site:X brand` and surface the top 3."""
    data = _serpapi({**UK, "q": f"{modifier} {brand}"})
    organic = data.get("organic_results") or []
    return {
        "label": label,
        "query": f"{modifier} {brand}",
        "count": len(organic),
        "total_estimate": (data.get("search_information") or {}).get("total_results"),
        "samples": [
            {"title": r.get("title"), "link": r.get("link"), "snippet": r.get("snippet")}
            for r in organic[:3]
        ],
    }


def scan_review_directories(brand):
    """Which review directories return a hit for the brand."""
    data = _serpapi({**UK, "q": f"{brand} reviews"})
    organic = data.get("organic_results") or []
    review_hosts = {"trustpilot.com", "uk.trustpilot.com", "g2.com", "capterra.com",
                    "capterra.co.uk", "clutch.co", "yelp.com", "yelp.co.uk", "yell.com",
                    "google.com/maps", "g.page"}
    found = []
    for r in organic[:10]:
        link = (r.get("link") or "").lower()
        for h in review_hosts:
            if h in link:
                found.append({"host": h, "title": r.get("title"), "link": r.get("link"), "position": r.get("position")})
                break
    return {
        "query": f"{brand} reviews",
        "hits": found,
        "directories_found": sorted({f["host"] for f in found}),
    }


def scan_local_pack(brand, service, location):
    """For local businesses — does 'best <service> in <town>' include the brand?"""
    if not (service and location):
        return None
    q = f"best {service} in {location}"
    data = _serpapi({**UK, "q": q})
    organic = data.get("organic_results") or []
    local = data.get("local_results") or {}
    if isinstance(local, dict):
        local_places = local.get("places") or []
    else:
        local_places = local
    brand_lower = brand.lower()
    cited_in_local = [p for p in local_places if brand_lower in (p.get("title") or "").lower()]
    cited_in_organic = [r for r in organic[:10] if brand_lower in (r.get("title") or "").lower()
                        or brand_lower in (r.get("snippet") or "").lower()]
    return {
        "query": q,
        "brand_in_local_pack": len(cited_in_local) > 0,
        "local_pack_titles": [p.get("title") for p in local_places[:5]],
        "brand_in_organic_top_10": len(cited_in_organic) > 0,
        "organic_top_5": [r.get("title") for r in organic[:5]],
    }


# ── Top-level scan ──────────────────────────────────────────────────────────

def full_scan(brand, domain=None, service=None, location=None):
    queries = {
        "brand_serp":       scan_brand_serp(brand, domain or ""),
        "reddit":           scan_count(brand, "site:reddit.com", "Reddit footprint"),
        "youtube":          scan_count(brand, "site:youtube.com", "YouTube footprint"),
        "wikipedia":        scan_count(brand, "site:wikipedia.org", "Wikipedia mentions"),
        "linkedin":         scan_count(brand, "site:linkedin.com", "LinkedIn footprint"),
        "review_directories": scan_review_directories(brand),
    }
    if service and location:
        queries["local_pack"] = scan_local_pack(brand, service, location)

    bs = queries["brand_serp"]
    kp = bs.get("knowledge_panel") or {}
    summary = {
        "knowledge_panel_present": bool(kp.get("present")),
        "knowledge_panel_kgmid":   kp.get("kgmid"),
        "wikipedia_in_results":    queries["wikipedia"]["count"] > 0,
        "reddit_footprint":        queries["reddit"]["count"],
        "youtube_results":         queries["youtube"]["count"],
        "linkedin_results":        queries["linkedin"]["count"],
        "review_directories":      queries["review_directories"]["directories_found"],
        "site_in_top_10":          bs.get("site_in_top_10"),
    }
    return {"brand": brand, "domain": domain, "queries": queries, "summary": summary}


def main():
    p = argparse.ArgumentParser(description="SerpAPI brand presence scan — real SERP data, no guessing")
    p.add_argument("--brand", required=True, help="Brand name (exact, as you'd search)")
    p.add_argument("--domain", help="Domain for 'in top 10' check (e.g. antekautomation.com)")
    p.add_argument("--service", help="Service for local-pack test (e.g. 'family law solicitor')")
    p.add_argument("--location", help="Location for local-pack test (e.g. 'Bristol')")
    p.add_argument("--output", type=Path, help="Write JSON output (default: stdout)")
    args = p.parse_args()

    out = full_scan(args.brand, args.domain, args.service, args.location)
    txt = json.dumps(out, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(txt, encoding="utf-8")
        s = out["summary"]
        print(
            f"serpapi_scan: wrote {args.output} — KP={s['knowledge_panel_present']}, "
            f"Wikipedia={s['wikipedia_in_results']}, Reddit={s['reddit_footprint']}, "
            f"YouTube={s['youtube_results']}, dirs={len(s['review_directories'])}",
            file=sys.stderr,
        )
    else:
        print(txt)


if __name__ == "__main__":
    main()
