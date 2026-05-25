"""
discover_prospects.py — SERP-based prospect discovery for geo-slab.

Finds businesses ranking in the "almost there" zone (positions 8-15) for
target keywords in a given location. Supports US + UK (and any SerpAPI
location string). Optional Google Places enrichment for business name,
phone, address, rating, review count.

Usage:
    python discover_prospects.py \\
        --keywords prospects/keywords/legal_dallas.txt \\
        --location "Dallas, Texas, United States" \\
        --output prospects/run_001/prospects.csv

    python discover_prospects.py \\
        --keywords prospects/keywords/plumber_southampton.txt \\
        --location "Southampton, England, United Kingdom" \\
        --gl uk --hl en-GB \\
        --enrich \\
        --output prospects/run_002/prospects.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import requests

SERPAPI_URL = "https://serpapi.com/search.json"
PLACES_API_URL = "https://places.googleapis.com/v1/places:searchText"

EXCLUDED_DOMAINS = {
    # Legal directories (US + UK)
    "yelp.com", "yelp.co.uk", "yellowpages.com", "yell.com",
    "findlaw.com", "justia.com", "avvo.com", "lawyers.com",
    "martindale.com", "superlawyers.com", "lawinfo.com", "nolo.com",
    "lawyer.com", "expertise.com", "thumbtack.com",
    "lawsociety.org.uk", "sra.org.uk", "barcouncil.org.uk",
    "thelawsuperstore.co.uk", "solicitors.lawsociety.org.uk",
    "resolution.org.uk", "stepcommunity.com", "step.org",
    "cilex.org.uk", "ilex.org.uk", "ciarb.org",
    # Home / trade services
    "angi.com", "homeadvisor.com", "houzz.com", "houzz.co.uk",
    "checkatrade.com", "trustatrader.com", "mybuilder.com",
    "ratedpeople.com", "bark.com", "yell.co.uk",
    # Social / search / directories
    "google.com", "google.co.uk", "maps.google.com",
    "facebook.com", "linkedin.com", "instagram.com", "twitter.com",
    "x.com", "youtube.com", "pinterest.com", "tiktok.com",
    "bbb.org", "trustpilot.com", "tripadvisor.com", "tripadvisor.co.uk",
    "reddit.com", "quora.com", "wikipedia.org", "wikidata.org",
    # Major publishers
    "forbes.com", "nytimes.com", "wsj.com", "bloomberg.com",
    "theguardian.com", "telegraph.co.uk", "bbc.co.uk", "bbc.com",
    "thetimes.co.uk", "dailymail.co.uk", "independent.co.uk",
    # E-commerce / aggregators
    "amazon.com", "amazon.co.uk", "ebay.com", "ebay.co.uk", "etsy.com",
}


@dataclass
class KeywordRanking:
    keyword: str
    position: int
    url: str
    title: str
    snippet: str


@dataclass
class RankingProspect:
    domain: str
    website: str
    rankings: list = field(default_factory=list)
    business_name: str | None = None
    phone: str | None = None
    address: str | None = None
    rating: float | None = None
    review_count: int | None = None

    @property
    def keyword_count(self) -> int:
        return len(self.rankings)

    @property
    def avg_position(self) -> float:
        if not self.rankings:
            return 0.0
        return sum(r.position for r in self.rankings) / len(self.rankings)

    @property
    def best_position(self) -> int:
        return min((r.position for r in self.rankings), default=0)

    @property
    def worst_position(self) -> int:
        return max((r.position for r in self.rankings), default=0)

    @property
    def opportunity_score(self) -> float:
        if not self.rankings:
            return 0.0
        position_score = max(0.0, (20 - self.avg_position) / 12)
        breadth_score = min(1.0, self.keyword_count / 5)
        return round((position_score * 0.6 + breadth_score * 0.4) * 100, 1)

    def to_csv_row(self) -> dict:
        return {
            "domain": self.domain,
            "website": self.website,
            "business_name": self.business_name or "",
            "phone": self.phone or "",
            "address": self.address or "",
            "rating": self.rating if self.rating is not None else "",
            "review_count": self.review_count if self.review_count is not None else "",
            "keyword_count": self.keyword_count,
            "avg_position": round(self.avg_position, 1),
            "best_position": self.best_position,
            "worst_position": self.worst_position,
            "opportunity_score": self.opportunity_score,
            "keywords": " | ".join(f"{r.keyword} (#{r.position})" for r in self.rankings),
            "top_url": self.rankings[0].url if self.rankings else "",
        }


def _extract_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _is_targetable_domain(domain: str) -> bool:
    if not domain:
        return False
    for blocked in EXCLUDED_DOMAINS:
        if domain == blocked or domain.endswith(f".{blocked}"):
            return False
    return True


def _read_keywords(path: Path) -> list:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [
        line.strip() for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]


def _infer_region(location: str) -> tuple:
    """Return (gl, hl) defaults inferred from location string.

    SerpAPI uses ISO 3166-1 alpha-2 country codes: UK = 'gb', US = 'us'.
    """
    loc = (location or "").lower()
    uk_signals = ("united kingdom", "england", "scotland", "wales",
                  "northern ireland", " uk", ", uk")
    if any(s in loc for s in uk_signals):
        return "gb", "en"
    return "us", "en"


def _query_serpapi(keyword, location, api_key, gl="us", hl="en", num_results=20):
    params = {
        "engine": "google",
        "q": keyword,
        "location": location,
        "num": num_results,
        "api_key": api_key,
        "hl": hl,
        "gl": gl,
    }
    resp = requests.get(SERPAPI_URL, params=params, timeout=30)
    if resp.status_code == 429:
        time.sleep(5)
        resp = requests.get(SERPAPI_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("organic_results", []) or []


def discover(keywords, location, min_position=9, max_position=13,
             max_prospects=15, api_key=None, gl=None, hl=None):
    api_key = api_key or os.environ.get("SERPAPI_KEY") or os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        raise RuntimeError("SERPAPI_KEY not set. https://serpapi.com")

    if gl is None or hl is None:
        inferred_gl, inferred_hl = _infer_region(location)
        gl = gl or inferred_gl
        hl = hl or inferred_hl

    prospects = {}

    for kw in keywords:
        if len(prospects) >= max_prospects:
            break
        print(f"  Querying: {kw} (gl={gl}, hl={hl})", file=sys.stderr)
        try:
            results = _query_serpapi(kw, location, api_key, gl=gl, hl=hl)
        except requests.HTTPError as e:
            print(f"  SerpAPI error for '{kw}': {e}", file=sys.stderr)
            continue
        except requests.RequestException as e:
            print(f"  Request error for '{kw}': {e}", file=sys.stderr)
            continue

        for result in results:
            position = result.get("position")
            if not position or position < min_position or position > max_position:
                continue
            url = result.get("link", "")
            domain = _extract_domain(url)
            if not _is_targetable_domain(domain):
                continue

            ranking = KeywordRanking(
                keyword=kw,
                position=position,
                url=url,
                title=result.get("title", ""),
                snippet=result.get("snippet", ""),
            )
            if domain not in prospects:
                prospects[domain] = RankingProspect(domain=domain, website=f"https://{domain}")
            prospects[domain].rankings.append(ranking)

        time.sleep(0.5)

    return prospects


def enrich_with_places(prospects, location, api_key=None):
    api_key = api_key or os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        print("  Skipping Places enrichment (no GOOGLE_PLACES_API_KEY)", file=sys.stderr)
        return

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join([
            "places.displayName",
            "places.nationalPhoneNumber",
            "places.formattedAddress",
            "places.rating",
            "places.userRatingCount",
            "places.websiteUri",
        ]),
    }

    for domain, prospect in prospects.items():
        title_hint = prospect.rankings[0].title if prospect.rankings else domain
        body = {"textQuery": f"{title_hint} {location}", "pageSize": 1}
        try:
            resp = requests.post(PLACES_API_URL, headers=headers, json=body, timeout=15)
            if resp.status_code != 200:
                continue
            places = resp.json().get("places", []) or []
            if not places:
                continue
            place = places[0]
            places_website = place.get("websiteUri", "")
            if places_website and _extract_domain(places_website) != domain:
                continue
            prospect.business_name = (place.get("displayName") or {}).get("text")
            prospect.phone = place.get("nationalPhoneNumber")
            prospect.address = place.get("formattedAddress")
            prospect.rating = place.get("rating")
            prospect.review_count = place.get("userRatingCount")
        except Exception:
            continue
        time.sleep(0.2)


def write_csv(prospects, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not prospects:
        # write header-only file so downstream tools see schema
        fieldnames = list(RankingProspect(domain="", website="").to_csv_row().keys())
        with output_path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fieldnames).writeheader()
        print("No prospects to write (empty header file written).", file=sys.stderr)
        return
    fieldnames = list(prospects[0].to_csv_row().keys())
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in prospects:
            writer.writerow(p.to_csv_row())


def main():
    parser = argparse.ArgumentParser(description="SERP-based prospect discovery (US + UK)")
    parser.add_argument("--keywords", required=True, help="Path to keyword file (one per line, # comments ok)")
    parser.add_argument("--location", required=True,
                        help='SerpAPI location, e.g. "Dallas, Texas, United States" or "Southampton, England, United Kingdom"')
    parser.add_argument("--gl", default=None,
                        help="Country code (us, uk). Auto-detected from location if omitted.")
    parser.add_argument("--hl", default=None,
                        help="Language (en, en-GB). Auto-detected from location if omitted.")
    parser.add_argument("--min-position", type=int, default=9)
    parser.add_argument("--max-position", type=int, default=13)
    parser.add_argument("--max-prospects", type=int, default=15)
    parser.add_argument("--enrich", action="store_true",
                        help="Enrich with Google Places API (needs GOOGLE_PLACES_API_KEY)")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    keywords = _read_keywords(Path(args.keywords))
    if not keywords:
        print("No keywords found.", file=sys.stderr)
        return 1

    print(f"Searching {len(keywords)} keywords in '{args.location}'", file=sys.stderr)
    print(f"Positions: {args.min_position}-{args.max_position} (max {args.max_prospects})", file=sys.stderr)

    try:
        prospects_dict = discover(
            keywords=keywords,
            location=args.location,
            min_position=args.min_position,
            max_position=args.max_position,
            max_prospects=args.max_prospects,
            gl=args.gl,
            hl=args.hl,
        )
    except RuntimeError as e:
        print(f"Fatal: {e}", file=sys.stderr)
        return 2

    if args.enrich:
        print(f"Enriching {len(prospects_dict)} prospects via Places API", file=sys.stderr)
        enrich_with_places(prospects_dict, args.location)

    prospects = sorted(prospects_dict.values(), key=lambda p: p.opportunity_score, reverse=True)
    write_csv(prospects, Path(args.output))
    print(f"Found {len(prospects)} prospects in target zone", file=sys.stderr)
    print(f"Written to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
