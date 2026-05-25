#!/usr/bin/env python3
"""
GEO SLAB — Social / identity URL harvester.

Greps a set of fetched pages (rendered HTML + server-rendered JSON-LD) for
canonical social and identity URLs. The output prevents the platform / brand
agents from claiming "no X account" or "no LinkedIn" when those links are
actually wired into the site.

Two input modes:

1.  --pages <html_file> [html_file ...]
    One or more locally-saved HTML files (e.g. from browser_render_audit.py
    or fetch_page.py output).

2.  --browser-render <browser-render.json>
    Pull server_html + hydrated_schema directly from a browser-render audit.

Output:
    {
      "by_platform": {
        "x":        ["https://x.com/AntekAutomation"],
        "linkedin": ["https://www.linkedin.com/company/antekautomation"],
        ...
      },
      "all_urls": [...],
      "sameAs":   [...],          # URLs found inside JSON-LD sameAs arrays
      "count":    N
    }

Usage:
    python social_harvest.py --browser-render reports/<domain>/browser-render.json \\
                             --output reports/<domain>/identity-urls.json

The orchestrator passes the resulting JSON into the platform + brand + schema
agents as `verified_identity_urls` so they never deny a presence that exists.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


# Pattern table: each platform → compiled regex that captures a profile URL.
# Match canonical patterns only; quietly skip share/intent URLs.
PLATFORM_PATTERNS = {
    "x":          r"https?://(?:www\.)?(?:twitter|x)\.com/(?!intent|share|home|search|hashtag|i/)([A-Za-z0-9_]{1,15})\b",
    "linkedin":   r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:company|in|school)/([A-Za-z0-9\-._~%]+)/?",
    "facebook":   r"https?://(?:www\.)?facebook\.com/(?!sharer|share|dialog|tr|plugins|pages/category|pg/help)([A-Za-z0-9.\-]{3,})/?",
    "instagram":  r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?",
    "youtube":    r"https?://(?:www\.)?youtube\.com/(?:c|channel|user|@)([A-Za-z0-9_\-]+)",
    "tiktok":     r"https?://(?:www\.)?tiktok\.com/@([A-Za-z0-9._]+)",
    "github":     r"https?://(?:www\.)?github\.com/([A-Za-z0-9\-_.]+)/?",
    "crunchbase": r"https?://(?:www\.)?crunchbase\.com/organization/([A-Za-z0-9\-]+)",
    "wikipedia":  r"https?://(?:[a-z]{2,3}\.)?wikipedia\.org/wiki/([A-Za-z0-9_%()\-]+)",
    "wikidata":   r"https?://(?:www\.)?wikidata\.org/(?:wiki|entity)/(Q\d+)",
    "trustpilot": r"https?://(?:[a-z]{2,3}\.)?trustpilot\.com/review/([A-Za-z0-9.\-]+)",
    "g2":         r"https?://(?:www\.)?g2\.com/products/([A-Za-z0-9\-]+)",
    "capterra":   r"https?://(?:www\.)?capterra\.[a-z.]+/p/(\d+)/[A-Za-z0-9\-]+",
    "clutch":     r"https?://(?:www\.)?clutch\.co/profile/([A-Za-z0-9\-]+)",
    "youtube_at": r"https?://(?:www\.)?youtube\.com/(@[A-Za-z0-9_\-]+)",
    "gbp_short":  r"https?://(?:www\.)?g\.page/([A-Za-z0-9\-]+)",
    "gmaps":      r"https?://(?:www\.)?(?:maps\.google\.[a-z.]+|maps\.app\.goo\.gl)/[^\"'\s>]+",
    "fsb":        r"https?://(?:www\.)?fsb\.org\.uk/[^\"'\s>]+",
    "retell":     r"https?://(?:www\.)?retellai\.com/[^\"'\s>]*partner[^\"'\s>]*",
    "about_me":   r"https?://(?:www\.)?about\.me/([A-Za-z0-9_\-]+)",
    "upwork":     r"https?://(?:www\.)?upwork\.com/(?:agencies|freelancers)/[^\"'\s>]+",
    "companieshouse": r"https?://(?:www\.)?find-and-update\.company-information\.service\.gov\.uk/company/(\d+)",
    "sra":        r"https?://(?:www\.)?(?:solicitors|sra)\.(?:org\.uk|lawsociety\.org\.uk)/[^\"'\s>]+",
}


def harvest_text(text: str):
    """Return {platform: [unique_urls]} discovered in arbitrary text."""
    out = defaultdict(set)
    for platform, pattern in PLATFORM_PATTERNS.items():
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            url = m.group(0).rstrip(").,;:>\"'")
            out[platform].add(url)
    return {k: sorted(v) for k, v in out.items() if v}


def harvest_jsonld_sameas(html: str):
    """Pull every URL inside any sameAs array from any JSON-LD script block."""
    urls = set()
    # Find every JSON-LD block
    for block in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, flags=re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(block.strip())
        except Exception:
            # Strict JSON might fail on multi-graph blocks; soft-grep instead.
            for u in re.findall(r'"(https?://[^"]+)"', block):
                urls.add(u)
            continue
        _walk_sameas(data, urls)
    return sorted(urls)


def _walk_sameas(node, urls):
    if isinstance(node, dict):
        if "sameAs" in node:
            sa = node["sameAs"]
            if isinstance(sa, str):
                urls.add(sa)
            elif isinstance(sa, list):
                for v in sa:
                    if isinstance(v, str):
                        urls.add(v)
        for v in node.values():
            _walk_sameas(v, urls)
    elif isinstance(node, list):
        for v in node:
            _walk_sameas(v, urls)


def from_browser_render(path):
    """Aggregate identity URLs from a browser-render audit JSON file.

    Falls back to fetching the URLs directly when browser-render.json doesn't
    persist server_html (current schema only stores word_count/status).
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    text_parts, sameas = [], set()
    urls_to_fetch = []
    for page in data.get("pages", []):
        c = page.get("checks", {})
        server_html = c.get("server_html")
        if isinstance(server_html, str) and server_html.strip():
            text_parts.append(server_html)
            for s in harvest_jsonld_sameas(server_html):
                sameas.add(s)
        elif page.get("url"):
            urls_to_fetch.append(page["url"])
    if urls_to_fetch:
        fetched = from_urls(urls_to_fetch)
        # Merge fetched result into our text-based aggregation
        for u in fetched["sameAs"]:
            sameas.add(u)
        # Re-aggregate everything
        agg = _aggregate(text_parts, sameas)
        # Overlay platform finds from the fetched aggregate
        for k, vs in fetched["by_platform"].items():
            merged = set(agg["by_platform"].get(k, []))
            merged.update(vs)
            agg["by_platform"][k] = sorted(merged)
        all_set = set(agg["all_urls"]) | set(fetched["all_urls"])
        agg["all_urls"] = sorted(all_set)
        agg["count"] = len(all_set)
        return agg
    return _aggregate(text_parts, sameas)


def from_html_files(paths):
    text_parts, sameas = [], set()
    for p in paths:
        txt = p.read_text(encoding="utf-8", errors="replace")
        text_parts.append(txt)
        for u in harvest_jsonld_sameas(txt):
            sameas.add(u)
    return _aggregate(text_parts, sameas)


def from_urls(urls):
    """Fetch each URL with requests + parse. Sandbox-safe (no curl needed)."""
    import urllib.request
    text_parts, sameas = [], set()
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "geo-slab-harvest/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                html = r.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"WARN: fetch failed for {u}: {e}", file=sys.stderr)
            continue
        text_parts.append(html)
        for s in harvest_jsonld_sameas(html):
            sameas.add(s)
    return _aggregate(text_parts, sameas)


def _aggregate(text_parts, sameas):
    merged = "\n".join(text_parts)
    by_platform = harvest_text(merged)
    by_sa = harvest_text("\n".join(sameas))
    for k, vs in by_sa.items():
        merged_set = set(by_platform.get(k, []))
        merged_set.update(vs)
        by_platform[k] = sorted(merged_set)
    all_urls = sorted({u for vs in by_platform.values() for u in vs} | set(sameas))
    return {
        "by_platform": by_platform,
        "all_urls": all_urls,
        "sameAs": sorted(sameas),
        "count": len(all_urls),
    }


def main():
    p = argparse.ArgumentParser(description="Harvest social / identity URLs from rendered pages + JSON-LD sameAs")
    p.add_argument("--browser-render", type=Path, help="Path to browser-render.json (only if it persists server_html)")
    p.add_argument("--pages", nargs="+", type=Path, help="One or more local HTML files")
    p.add_argument("--urls", nargs="+", help="One or more URLs to fetch + parse directly")
    p.add_argument("--output", type=Path, help="Where to write JSON output (default: stdout)")
    args = p.parse_args()

    if args.urls:
        result = from_urls(args.urls)
    elif args.browser_render:
        result = from_browser_render(args.browser_render)
    elif args.pages:
        result = from_html_files(args.pages)
    else:
        print("ERROR: pass --urls, --browser-render, or --pages", file=sys.stderr)
        sys.exit(2)

    payload = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
        print(f"social_harvest: wrote {args.output} — {result['count']} URLs across {len(result['by_platform'])} platforms", file=sys.stderr)
    else:
        print(payload)


if __name__ == "__main__":
    main()
