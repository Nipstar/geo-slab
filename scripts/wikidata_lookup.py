#!/usr/bin/env python3
"""
GEO SLAB — Wikidata + Wikipedia entity lookup.

Confirms whether a brand has a Wikidata item and/or Wikipedia article and
returns the structured identifiers AI engines actually look at.

This is a CHECKER not a builder — the wikipedia-generator project at
~/Library/Mobile Documents/com~apple~CloudDocs/GEO/wikipedia-generator handles
creation. The audit just needs to know what's already public.

Output:
    {
      "query": "Antek Automation",
      "wikidata": {
        "found": true,
        "qid": "Q12345678",
        "label": "Antek Automation",
        "description": "...",
        "wikidata_url": "https://www.wikidata.org/wiki/Q12345678",
        "instance_of": ["Q4830453 (business)"],
        "external_ids": {"P1316": "12345678", "P2088": "antek-automation", ...},
        "official_website": "https://www.antekautomation.com/"
      },
      "wikipedia": {
        "found": false,
        "sitelinks": {}                   # {lang: {"title": "...", "url": "..."}}
      },
      "search_results": [...]             # raw wbsearchentities results when no exact match
    }

Usage:
    python wikidata_lookup.py --name "Antek Automation"
    python wikidata_lookup.py --name "Wards Solicitors" --domain wards.uk.com
    python wikidata_lookup.py --name "..." --output reports/<domain>/wikidata.json

No auth required — Wikidata's wbsearchentities + wbgetentities APIs are open.
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path


WIKIDATA_API = "https://www.wikidata.org/w/api.php"


# Property labels for the IDs we care about. Mirrors wikipedia-generator's
# config/wikidata_properties.json keys we'll surface in the report.
PROPERTY_LABELS = {
    "P31":   "instance of",
    "P17":   "country",
    "P159":  "headquarters location",
    "P571":  "inception",
    "P856":  "official website",
    "P452":  "industry",
    "P112":  "founded by",
    "P1454": "legal form",
    "P749":  "parent organisation",
    "P1316": "Companies House ID",
    "P1320": "OpenCorporates ID",
    "P771":  "DUNS number",
    "P1278": "LEI",
    "P213":  "ISNI",
    "P4264": "LinkedIn org ID",
    "P2088": "Crunchbase organisation",
    "P2002": "X (Twitter) username",
    "P2003": "Instagram username",
    "P2013": "Facebook username",
    "P2397": "YouTube channel ID",
}


def _http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "geo-slab-wikidata/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def search_entities(query, language="en", limit=5):
    """wbsearchentities — returns top matches for a free-text query."""
    params = {
        "action": "wbsearchentities", "search": query,
        "language": language, "limit": str(limit),
        "format": "json", "type": "item",
    }
    url = f"{WIKIDATA_API}?{urllib.parse.urlencode(params)}"
    data = _http_get_json(url)
    return data.get("search", [])


def get_entity(qid, languages="en"):
    """wbgetentities — full payload for a single QID."""
    params = {
        "action": "wbgetentities", "ids": qid,
        "languages": languages, "format": "json",
        "props": "labels|descriptions|claims|sitelinks|aliases",
    }
    url = f"{WIKIDATA_API}?{urllib.parse.urlencode(params)}"
    data = _http_get_json(url)
    return data.get("entities", {}).get(qid)


def _claim_value(claim):
    """Pull a friendly value out of a claims entry (best-effort)."""
    dv = (claim.get("mainsnak") or {}).get("datavalue") or {}
    v = dv.get("value")
    if isinstance(v, dict):
        if "id" in v:
            return v["id"]
        if "time" in v:
            return v["time"]
        if "amount" in v:
            return v.get("amount")
        return v
    return v


def summarise_entity(entity, expected_domain=None):
    """Reduce a wbgetentities response to the audit-relevant fields."""
    if not entity:
        return {"found": False}
    qid = entity.get("id")
    label = (entity.get("labels", {}).get("en") or {}).get("value")
    desc = (entity.get("descriptions", {}).get("en") or {}).get("value")
    claims = entity.get("claims", {})

    # External identifier round-up
    external_ids = {}
    for p, plabel in PROPERTY_LABELS.items():
        if p in claims:
            vals = [_claim_value(c) for c in claims[p]]
            external_ids[p] = {"label": plabel, "values": vals}

    # Official website (P856) is a useful entity-match sanity check
    official_site = None
    if "P856" in claims:
        site_claims = [_claim_value(c) for c in claims["P856"]]
        if site_claims:
            official_site = site_claims[0]

    # Sitelinks — which Wikipedias does this entity exist on?
    sitelinks = {}
    for site, payload in (entity.get("sitelinks") or {}).items():
        if site.endswith("wiki") and not site.endswith("wikiquote") and not site.endswith("wikinews"):
            lang = site[:-4]
            title = payload.get("title")
            sitelinks[lang] = {
                "title": title,
                "url": f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
            }

    # Domain-match confidence — does the entity's P856 actually match what we expected?
    domain_match = None
    if expected_domain and official_site:
        domain_match = expected_domain.lower() in official_site.lower()

    return {
        "found": True,
        "qid": qid,
        "label": label,
        "description": desc,
        "wikidata_url": f"https://www.wikidata.org/wiki/{qid}",
        "official_website": official_site,
        "domain_match": domain_match,
        "external_ids": external_ids,
        "sitelinks": sitelinks,
        "claim_count": sum(len(v) for v in claims.values()),
    }


def lookup(name, expected_domain=None):
    """End-to-end: search → pick best candidate (or none) → fetch + summarise."""
    candidates = search_entities(name, limit=5)
    if not candidates:
        return {
            "query": name,
            "wikidata": {"found": False},
            "wikipedia": {"found": False, "sitelinks": {}},
            "search_results": [],
        }

    # Try each candidate; prefer the first one whose entity returns a domain match.
    # Fall back to the top result.
    chosen_summary = None
    summaries = []
    for c in candidates:
        qid = c.get("id")
        if not qid:
            continue
        entity = get_entity(qid)
        summary = summarise_entity(entity, expected_domain=expected_domain)
        summary["match_label"] = c.get("label")
        summary["match_description"] = c.get("description")
        summaries.append(summary)
        if summary.get("domain_match"):
            chosen_summary = summary
            break

    chosen_summary = chosen_summary or summaries[0]
    return {
        "query": name,
        "wikidata": chosen_summary if chosen_summary.get("found") else {"found": False},
        "wikipedia": {
            "found": bool(chosen_summary.get("sitelinks")),
            "sitelinks": chosen_summary.get("sitelinks", {}),
        },
        "search_results": [
            {
                "qid": c.get("id"),
                "label": c.get("label"),
                "description": c.get("description"),
            }
            for c in candidates
        ],
    }


def main():
    p = argparse.ArgumentParser(description="Look up brand entity on Wikidata + Wikipedia (read-only)")
    p.add_argument("--name", required=True, help="Brand or person name to search")
    p.add_argument("--domain", help="Expected domain for P856 cross-check (e.g. wards.uk.com)")
    p.add_argument("--output", type=Path, help="Write JSON output to file (default: stdout)")
    args = p.parse_args()

    out = lookup(args.name, expected_domain=args.domain)
    txt = json.dumps(out, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(txt, encoding="utf-8")
        wd = out["wikidata"]; wp = out["wikipedia"]
        wdmsg = f"QID={wd.get('qid')} domain_match={wd.get('domain_match')}" if wd.get("found") else "NO MATCH"
        print(
            f"wikidata_lookup: wrote {args.output} — wikidata={wdmsg}, wikipedia={wp['found']} ({len(wp['sitelinks'])} langs)",
            file=sys.stderr,
        )
    else:
        print(txt)


if __name__ == "__main__":
    main()
