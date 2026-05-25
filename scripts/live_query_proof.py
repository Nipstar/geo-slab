"""
Live AI proof for the prospect lite report.

Runs ONE live query against Perplexity (cheapest provider with real web
search) for a sector+location combination, captures which firms get
cited, and returns a structured result for embedding in the report.

If PERPLEXITY_API_KEY is not set, returns None — the report falls
back to the "we'll run these live on the call" framing only. We do
NOT use OpenAI / Anthropic without web search because they hallucinate
firm names from training data and would damage credibility.

Results cache to ~/.geo-slab/cache/live_queries/ keyed by a hash of
(sector, location, query). 30-day TTL keeps repeated reports for the
same sector+location free.

Usage:
    from live_query_proof import (
        build_primary_query, build_followup_queries, run_primary_query,
    )

    q = build_primary_query("family_law", "Bristol")
    result = run_primary_query(q, "wards.uk.com", "Wards Solicitors")
    followups = build_followup_queries("family_law", "Bristol")
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CACHE_DIR = Path.home() / ".geo-slab" / "cache" / "live_queries"
CACHE_TTL_DAYS = 30
QUERY_TIMEOUT_S = 20

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from style import sector_display
except ImportError:
    def sector_display(slug: str) -> str:
        return (slug or "").replace("_", " ").lower()


# ── Query construction ─────────────────────────────────────────────────────

_QUERY_TEMPLATES = {
    "family_law": [
        "best family law solicitor in {location}",
        "fixed fee divorce solicitor {location}",
        "how much does a family law solicitor cost in {location}",
        "best family law firm for high net worth divorce {location}",
        "child custody solicitor {location} reviews",
    ],
    "criminal_defence": [
        "best criminal defence solicitor in {location}",
        "24 hour criminal solicitor {location}",
        "magistrates court solicitor {location} legal aid",
        "drug offence solicitor {location}",
    ],
    "conveyancing": [
        "best conveyancing solicitor {location}",
        "fixed fee conveyancing {location} quote",
        "fastest conveyancer {location}",
        "leasehold conveyancing specialist {location}",
    ],
    "personal_injury": [
        "no win no fee solicitor {location}",
        "personal injury solicitor {location} reviews",
        "best road traffic accident solicitor {location}",
        "workplace injury claim solicitor {location}",
    ],
    "immigration": [
        "immigration solicitor {location}",
        "spouse visa solicitor {location}",
        "indefinite leave to remain solicitor {location}",
        "asylum solicitor {location} legal aid",
    ],
    "commercial_law": [
        "best commercial solicitor {location}",
        "business contract lawyer {location}",
        "shareholder dispute solicitor {location}",
        "commercial property solicitor {location}",
    ],
    "private_client": [
        "wills and probate solicitor {location}",
        "estate planning solicitor {location}",
        "trust solicitor {location}",
        "lasting power of attorney solicitor {location}",
    ],
    "dentist": [
        "best dentist in {location}",
        "private dentist {location} reviews",
        "Invisalign dentist {location} cost",
        "emergency dentist {location}",
    ],
    "plastic_surgery": [
        "best plastic surgeon {location}",
        "rhinoplasty surgeon {location} reviews",
        "breast surgery clinic {location}",
        "facelift specialist {location} cost",
    ],
    "fertility": [
        "best IVF clinic {location}",
        "fertility clinic {location} success rates",
        "egg freezing clinic {location} cost",
        "IUI clinic {location} reviews",
    ],
    "rehab": [
        "best rehab clinic {location}",
        "private alcohol rehab {location}",
        "drug detox clinic {location} cost",
        "residential addiction treatment {location}",
    ],
    "tradespeople": [
        "best {trade_label} {location}",
        "{trade_label} {location} reviews",
        "emergency {trade_label} {location}",
    ],
    "saas_b2b": [
        "best {sector_label} software for UK businesses",
        "{sector_label} platform reviews 2026",
        "{sector_label} pricing comparison UK",
    ],
}

_GENERIC_FALLBACK = [
    "best {sector_label} in {location}",
    "top {sector_label} {location} reviews",
    "{sector_label} {location} pricing",
]


def _templates_for(sector_slug: str) -> list[str]:
    if sector_slug and sector_slug in _QUERY_TEMPLATES:
        return _QUERY_TEMPLATES[sector_slug]
    return _GENERIC_FALLBACK


def build_primary_query(sector_slug: str, location: str) -> Optional[str]:
    """Build the single live query. Returns None if we can't confidently form one."""
    if not sector_slug or not location:
        return None
    location = location.strip()
    if not location:
        return None
    tmpl = _templates_for(sector_slug)[0]
    return tmpl.format(
        location=location,
        sector_label=sector_display(sector_slug),
        trade_label=sector_display(sector_slug),
    ).strip()


def build_followup_queries(sector_slug: str, location: str, count: int = 3) -> list[str]:
    """Return N follow-up queries as 'we'll run these on the call' samples."""
    if not sector_slug or not location:
        return []
    location = location.strip()
    if not location:
        return []
    templates = _templates_for(sector_slug)
    # Skip the first one — that's the primary query, already used.
    pool = templates[1:] if len(templates) > 1 else templates
    out = []
    for t in pool[:count]:
        out.append(t.format(
            location=location,
            sector_label=sector_display(sector_slug),
            trade_label=sector_display(sector_slug),
        ).strip())
    return out


# ── Brand / firm extraction from the model's answer ────────────────────────

def _normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _looks_like_firm_name(cand: str, location: str = "") -> bool:
    """Filter heading-shaped or location-shaped strings out of the firm list."""
    if not cand:
        return False
    # Reject items containing the query location
    if location and location.lower() in cand.lower():
        return False
    # Reject 'City, Country' shapes — Perplexity bolds these as section headings
    if re.match(r"^[A-Z][a-z]+,\s*[A-Z]{2,}$", cand):
        return False
    # Reject obvious non-firm phrases
    rejects = {
        "uk", "england", "united kingdom", "scotland", "wales",
        "best firms", "top firms", "key features", "additional info",
        "main considerations", "what to look for", "things to consider",
    }
    if cand.lower().strip() in rejects:
        return False
    return True


def _extract_firm_names(text: str, location: str = "") -> list[str]:
    """Pull plausible firm/business names out of the Perplexity answer."""
    found: list[str] = []
    seen: set[str] = set()

    # Bold (**Foo Solicitors**) — Perplexity often bolds firm names
    for m in re.finditer(r"\*\*([A-Z][^*\n]{2,60}?)\*\*", text):
        cand = m.group(1).strip().strip(":,.")
        key = _normalise(cand)
        if key and key not in seen and 3 <= len(cand) <= 60 and _looks_like_firm_name(cand, location):
            seen.add(key)
            found.append(cand)

    # Numbered list items
    for m in re.finditer(r"(?:^|\n)\s*\d+[.)]\s*\**([A-Z][^\n*]{2,60}?)(?:\*\*|\s—|\s–|\s-|:|$)", text):
        cand = m.group(1).strip().strip(":,.")
        key = _normalise(cand)
        if key and key not in seen and 3 <= len(cand) <= 60 and _looks_like_firm_name(cand, location):
            seen.add(key)
            found.append(cand)

    # Strip noise like "Best Firms", "Top Picks", "Introduction"
    noise = {
        "introduction", "summary", "conclusion", "overview", "topfirms",
        "topsolicitors", "bestoptions", "keyfeatures", "factorstoconsider",
        "considerations", "additionalinfo",
    }
    return [f for f in found if _normalise(f) not in noise]


_GENERIC_TOKENS = {
    "law", "legal", "solicitor", "solicitors", "lawyer", "lawyers",
    "firm", "firms", "practice", "practices", "chambers", "company",
    "ltd", "limited", "llp", "plc", "limited", "the", "and",
    "uk", "england", "bristol", "london", "manchester", "leeds",
    "birmingham", "liverpool", "glasgow", "edinburgh",
    "family", "criminal", "commercial", "civil", "property",
    "best", "top", "leading", "trusted",
    "info", "site", "page", "home", "contact", "about",
    "solutions", "services", "group", "associates", "partners",
    "dental", "clinic", "medical", "health",
}


def _check_prospect_cited(text: str, prospect_domain: str, prospect_name: str) -> bool:
    """Return True iff the prospect's firm/domain appears in the answer.
    Filters generic legal/business tokens so 'Solicitors' doesn't trigger
    a false positive against any family-law answer.
    """
    text_l = (text or "").lower()
    if prospect_domain:
        bare = re.sub(r"^www\.", "", prospect_domain.lower())
        if bare in text_l:
            return True
        first = bare.split(".")[0]
        if first and len(first) > 3 and first not in _GENERIC_TOKENS and first in text_l:
            return True
    if prospect_name:
        for tok in sorted(prospect_name.split(), key=len, reverse=True):
            tok_clean = re.sub(r"[^a-z]", "", tok.lower())
            if len(tok_clean) < 4 or tok_clean in _GENERIC_TOKENS:
                continue
            # Require a word-boundary match so 'wards' doesn't fire on 'awards'
            if re.search(rf"\b{re.escape(tok_clean)}\b", text_l):
                return True
    return False


# ── Cache ──────────────────────────────────────────────────────────────────

def _cache_key(sector_slug: str, location: str, query: str) -> str:
    blob = f"{sector_slug}|{location.lower().strip()}|{query.lower().strip()}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _read_cache(key: str) -> Optional[dict]:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_at = data.get("cached_at", 0)
        age_days = (time.time() - cached_at) / 86400.0
        if age_days > CACHE_TTL_DAYS:
            return None
        data["cache_hit"] = True
        return data
    except Exception:
        return None


def _write_cache(key: str, result: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = dict(result)
        payload["cached_at"] = time.time()
        (CACHE_DIR / f"{key}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[live_query_proof] cache write failed: {e}", file=sys.stderr)


# ── Provider — Perplexity only ─────────────────────────────────────────────

def _query_perplexity(query: str) -> Optional[dict]:
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        return None
    try:
        import requests
    except ImportError:
        return None
    try:
        r = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": query}],
                "max_tokens": 800,
            },
            timeout=QUERY_TIMEOUT_S,
        )
        r.raise_for_status()
        body = r.json()
    except Exception as e:
        print(f"[live_query_proof] Perplexity error: {e}", file=sys.stderr)
        return None
    try:
        choice = body["choices"][0]
        answer = choice["message"]["content"] or ""
        citations = body.get("citations") or choice.get("citations") or []
        if not isinstance(citations, list):
            citations = []
        return {"answer": answer, "citations": citations[:10]}
    except (KeyError, IndexError, TypeError) as e:
        print(f"[live_query_proof] Perplexity parse error: {e}", file=sys.stderr)
        return None


# ── Public entry ───────────────────────────────────────────────────────────

def run_primary_query(query: str, prospect_domain: str = "", prospect_name: str = "",
                      sector_slug: str = "", location: str = "") -> Optional[dict]:
    """
    Run the primary live query. Returns a dict suitable for embedding in
    the report data, or None if no API key / failure / skipped.

    Shape on success:
        {
            "provider": "Perplexity",
            "query": "best family law solicitor in Bristol",
            "tested_at": "25 May 2026",
            "prospect_cited": False,
            "firms_cited": ["Wards Solicitors", "Henriques Griffiths", ...],
            "citations": ["https://...", ...],
            "cache_hit": True | False,
        }
    """
    if not query:
        return None

    key = _cache_key(sector_slug, location, query)
    cached = _read_cache(key)
    if cached:
        # Re-check prospect citation against the cached answer in case the
        # prospect changed (different firm pulling same sector+location).
        if prospect_domain or prospect_name:
            cached["prospect_cited"] = _check_prospect_cited(
                cached.get("_answer_blob", ""), prospect_domain, prospect_name
            )
        return cached

    raw = _query_perplexity(query)
    if not raw:
        return None

    firms = _extract_firm_names(raw["answer"], location=location)[:5]
    cited = _check_prospect_cited(raw["answer"], prospect_domain, prospect_name)

    result = {
        "provider": "Perplexity",
        "query": query,
        "tested_at": datetime.now(timezone.utc).strftime("%-d %B %Y"),
        "prospect_cited": cited,
        "firms_cited": firms,
        "citations": raw.get("citations", []),
        "cache_hit": False,
        "_answer_blob": raw["answer"],  # kept for re-checking citation on cache hits
    }
    _write_cache(key, result)
    return result


__all__ = [
    "build_primary_query",
    "build_followup_queries",
    "run_primary_query",
]
