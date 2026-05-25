#!/usr/bin/env python3
"""
PageSpeed Insights (PSI) client for GEO SLAB.

Runs mobile + desktop Lighthouse audits via Google's PSI API, parses scores +
Core Web Vitals (CrUX field data preferred, lab fallback), and extracts top
optimization opportunities. Output feeds into geo-technical audit category 6
(Core Web Vitals) and category 8 (Page Speed).

CLI:
    python3 pagespeed.py <url>
    python3 pagespeed.py <url> --strategy mobile
    python3 pagespeed.py <url> --no-cache
    python3 pagespeed.py --self-test  # parser test against fixture

Library:
    from pagespeed import run_pagespeed_audit
    result = run_pagespeed_audit("https://example.com")

Env:
    PSI_API_KEY  — Google API key with PageSpeed Insights API enabled.
                   Free tier: 25,000 req/day, 240/min.

Cache: 24h on-disk JSON at ~/.geo-slab/cache/psi/<sha1>.json
Concurrency: mobile + desktop run in parallel (2 workers).
Timeout: 60s per request. Retries: 3 with exponential backoff (2/4/8s).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
CACHE_DIR = Path.home() / ".geo-slab" / "cache" / "psi"
CACHE_TTL_SECONDS = 24 * 60 * 60
DEFAULT_TIMEOUT = 60
DEFAULT_RETRIES = 3
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
CATEGORIES = ("performance", "accessibility", "best-practices", "seo")


# ────────────────────────────────────────────────────────────
# Result types
# ────────────────────────────────────────────────────────────


@dataclass
class StrategyScores:
    performance: Optional[float] = None
    accessibility: Optional[float] = None
    best_practices: Optional[float] = None
    seo: Optional[float] = None


@dataclass
class StrategyMetrics:
    lcp_ms: Optional[float] = None
    cls: Optional[float] = None
    tbt_ms: Optional[float] = None
    speed_index_ms: Optional[float] = None
    fcp_ms: Optional[float] = None


@dataclass
class StrategyResult:
    strategy: str
    scores: StrategyScores
    metrics: StrategyMetrics
    error: Optional[str] = None


@dataclass
class Opportunity:
    id: str
    title: str
    description: str
    savings_ms: float


@dataclass
class CoreWebVitals:
    lcp_ms: Optional[float] = None
    inp_ms: Optional[float] = None
    cls: Optional[float] = None
    category: Optional[str] = None  # FAST | AVERAGE | SLOW
    source: Optional[str] = None  # field | lab


@dataclass
class PageSpeedResult:
    url: str
    fetched_at: str
    status: str  # success | partial | failed
    mobile: Optional[StrategyResult] = None
    desktop: Optional[StrategyResult] = None
    core_web_vitals: CoreWebVitals = field(default_factory=CoreWebVitals)
    top_opportunities: list[Opportunity] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


# ────────────────────────────────────────────────────────────
# Cache
# ────────────────────────────────────────────────────────────


def _cache_key(url: str, strategy: str) -> Path:
    h = hashlib.sha1(f"{strategy}:{url}".encode()).hexdigest()
    return CACHE_DIR / f"{h}.json"


def _cache_get(url: str, strategy: str) -> Optional[dict[str, Any]]:
    path = _cache_key(url, strategy)
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > CACHE_TTL_SECONDS:
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _cache_put(url: str, strategy: str, raw: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_key(url, strategy)
    try:
        path.write_text(json.dumps(raw))
    except OSError as e:
        print(f"[psi] cache write failed: {e}", file=sys.stderr)


# ────────────────────────────────────────────────────────────
# API client
# ────────────────────────────────────────────────────────────


def _fetch_psi(
    url: str,
    strategy: str,
    api_key: str,
    locale: str = "en_GB",
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> dict[str, Any]:
    """Fetch raw PSI response. Raises on permanent failure after retries."""
    params: list[tuple[str, str]] = [
        ("url", url),
        ("strategy", strategy),
        ("locale", locale),
        ("key", api_key),
    ]
    for cat in CATEGORIES:
        params.append(("category", cat))

    last_err: Optional[str] = None
    for attempt in range(retries):
        try:
            resp = requests.get(PSI_ENDPOINT, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (400, 403):
                # Permanent: bad URL, quota exceeded, key invalid
                raise RuntimeError(f"PSI {resp.status_code}: {resp.text[:200]}")
            if resp.status_code in RETRYABLE_STATUS:
                last_err = f"HTTP {resp.status_code}"
            else:
                raise RuntimeError(f"PSI unexpected {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as e:
            last_err = str(e)
        if attempt < retries - 1:
            backoff = 2 ** (attempt + 1)
            time.sleep(backoff)
    raise RuntimeError(f"PSI failed after {retries} attempts: {last_err}")


# ────────────────────────────────────────────────────────────
# Parser
# ────────────────────────────────────────────────────────────


def _safe_score(categories: dict[str, Any], key: str) -> Optional[float]:
    cat = categories.get(key)
    if not isinstance(cat, dict):
        return None
    score = cat.get("score")
    return float(score) if isinstance(score, (int, float)) else None


def _safe_audit_numeric(audits: dict[str, Any], key: str) -> Optional[float]:
    audit = audits.get(key)
    if not isinstance(audit, dict):
        return None
    val = audit.get("numericValue")
    return float(val) if isinstance(val, (int, float)) else None


def parse_strategy(raw: dict[str, Any], strategy: str) -> StrategyResult:
    """Extract scores + lab metrics for a single strategy response."""
    lh = raw.get("lighthouseResult", {})
    categories = lh.get("categories", {}) or {}
    audits = lh.get("audits", {}) or {}

    scores = StrategyScores(
        performance=_safe_score(categories, "performance"),
        accessibility=_safe_score(categories, "accessibility"),
        best_practices=_safe_score(categories, "best-practices"),
        seo=_safe_score(categories, "seo"),
    )
    metrics = StrategyMetrics(
        lcp_ms=_safe_audit_numeric(audits, "largest-contentful-paint"),
        cls=_safe_audit_numeric(audits, "cumulative-layout-shift"),
        tbt_ms=_safe_audit_numeric(audits, "total-blocking-time"),
        speed_index_ms=_safe_audit_numeric(audits, "speed-index"),
        fcp_ms=_safe_audit_numeric(audits, "first-contentful-paint"),
    )
    return StrategyResult(strategy=strategy, scores=scores, metrics=metrics)


def parse_field_cwv(raw: dict[str, Any]) -> Optional[CoreWebVitals]:
    """Extract CrUX field data when present. Returns None if absent."""
    le = raw.get("loadingExperience") or {}
    metrics = le.get("metrics") or {}
    if not metrics:
        return None
    lcp = metrics.get("LARGEST_CONTENTFUL_PAINT_MS", {}).get("percentile")
    inp = metrics.get("INTERACTION_TO_NEXT_PAINT", {}).get("percentile")
    cls_raw = metrics.get("CUMULATIVE_LAYOUT_SHIFT_SCORE", {}).get("percentile")
    # CrUX returns CLS percentile * 100 (integer). Normalise back to float ≤ ~0.3 range.
    cls = cls_raw / 100.0 if isinstance(cls_raw, (int, float)) else None
    return CoreWebVitals(
        lcp_ms=float(lcp) if isinstance(lcp, (int, float)) else None,
        inp_ms=float(inp) if isinstance(inp, (int, float)) else None,
        cls=cls,
        category=le.get("overall_category"),
        source="field",
    )


def parse_lab_cwv(strategy_result: StrategyResult) -> CoreWebVitals:
    """Fallback CWV from lab data. INP unavailable in lab — leaves None."""
    return CoreWebVitals(
        lcp_ms=strategy_result.metrics.lcp_ms,
        inp_ms=None,
        cls=strategy_result.metrics.cls,
        category=None,
        source="lab",
    )


def parse_opportunities(raw: dict[str, Any], top_n: int = 5) -> list[Opportunity]:
    audits = (raw.get("lighthouseResult") or {}).get("audits") or {}
    found: list[Opportunity] = []
    for audit_id, audit in audits.items():
        if not isinstance(audit, dict):
            continue
        details = audit.get("details") or {}
        if details.get("type") != "opportunity":
            continue
        savings = audit.get("numericValue")
        if not isinstance(savings, (int, float)) or savings <= 0:
            continue
        found.append(
            Opportunity(
                id=audit_id,
                title=str(audit.get("title", audit_id)),
                description=str(audit.get("description", "")),
                savings_ms=float(savings),
            )
        )
    found.sort(key=lambda o: o.savings_ms, reverse=True)
    return found[:top_n]


# ────────────────────────────────────────────────────────────
# Runner
# ────────────────────────────────────────────────────────────


def _run_one(
    url: str,
    strategy: str,
    api_key: str,
    use_cache: bool,
) -> tuple[str, Optional[dict[str, Any]], Optional[str]]:
    """Fetch (with cache) + return (strategy, raw_json_or_None, error_or_None)."""
    if use_cache:
        cached = _cache_get(url, strategy)
        if cached is not None:
            return strategy, cached, None
    try:
        raw = _fetch_psi(url, strategy, api_key)
        if use_cache:
            _cache_put(url, strategy, raw)
        return strategy, raw, None
    except Exception as e:
        return strategy, None, str(e)


def run_pagespeed_audit(
    url: str,
    api_key: Optional[str] = None,
    strategies: tuple[str, ...] = ("mobile", "desktop"),
    use_cache: bool = True,
) -> PageSpeedResult:
    """
    Public entry point. Runs mobile + desktop in parallel and returns a
    normalised PageSpeedResult. Never raises — returns status='failed' instead.
    """
    api_key = api_key or os.environ.get("PSI_API_KEY")
    fetched_at = datetime.now(timezone.utc).isoformat()

    if not api_key:
        return PageSpeedResult(
            url=url,
            fetched_at=fetched_at,
            status="failed",
            error="PSI_API_KEY not set. Skipping PageSpeed Insights audit.",
        )

    if not _looks_like_url(url):
        return PageSpeedResult(
            url=url,
            fetched_at=fetched_at,
            status="failed",
            error=f"Invalid URL: {url!r}",
        )

    raw_by_strategy: dict[str, Optional[dict[str, Any]]] = {}
    errors_by_strategy: dict[str, Optional[str]] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(_run_one, url, s, api_key, use_cache): s for s in strategies
        }
        for fut in concurrent.futures.as_completed(futures):
            strategy, raw, err = fut.result()
            raw_by_strategy[strategy] = raw
            errors_by_strategy[strategy] = err

    mobile_raw = raw_by_strategy.get("mobile")
    desktop_raw = raw_by_strategy.get("desktop")

    mobile_result = parse_strategy(mobile_raw, "mobile") if mobile_raw else None
    desktop_result = parse_strategy(desktop_raw, "desktop") if desktop_raw else None
    if mobile_result and errors_by_strategy.get("mobile"):
        mobile_result.error = errors_by_strategy["mobile"]
    if desktop_result and errors_by_strategy.get("desktop"):
        desktop_result.error = errors_by_strategy["desktop"]

    # Prefer mobile field CWV (Google ranks on mobile). Fall back to desktop, then lab.
    cwv: Optional[CoreWebVitals] = None
    for raw in (mobile_raw, desktop_raw):
        if raw:
            field_cwv = parse_field_cwv(raw)
            if field_cwv and (field_cwv.lcp_ms or field_cwv.inp_ms or field_cwv.cls):
                cwv = field_cwv
                break
    if cwv is None:
        fallback = mobile_result or desktop_result
        cwv = parse_lab_cwv(fallback) if fallback else CoreWebVitals()

    # Opportunities — pull from mobile if available, else desktop.
    opps: list[Opportunity] = []
    if mobile_raw:
        opps = parse_opportunities(mobile_raw)
    elif desktop_raw:
        opps = parse_opportunities(desktop_raw)

    # Status calculation
    succeeded = sum(1 for r in (mobile_raw, desktop_raw) if r is not None)
    if succeeded == len(strategies):
        status = "success"
    elif succeeded > 0:
        status = "partial"
    else:
        status = "failed"

    combined_error = " | ".join(
        f"{s}: {e}" for s, e in errors_by_strategy.items() if e
    ) or None

    return PageSpeedResult(
        url=url,
        fetched_at=fetched_at,
        status=status,
        mobile=mobile_result,
        desktop=desktop_result,
        core_web_vitals=cwv,
        top_opportunities=opps,
        error=combined_error,
    )


def _looks_like_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


# ────────────────────────────────────────────────────────────
# CLI + self-test
# ────────────────────────────────────────────────────────────


def _self_test() -> int:
    """Parse a fixture without hitting the network. Used by tests."""
    fixture_path = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "psi-response.json"
    if not fixture_path.exists():
        print(f"FIXTURE MISSING: {fixture_path}", file=sys.stderr)
        return 1
    raw = json.loads(fixture_path.read_text())
    strat = parse_strategy(raw, "mobile")
    field_cwv = parse_field_cwv(raw)
    opps = parse_opportunities(raw)

    print(f"perf={strat.scores.performance} seo={strat.scores.seo} "
          f"lcp_lab={strat.metrics.lcp_ms} cls_lab={strat.metrics.cls}")
    if field_cwv:
        print(f"field: lcp={field_cwv.lcp_ms} inp={field_cwv.inp_ms} "
              f"cls={field_cwv.cls} cat={field_cwv.category}")
    else:
        print("field: none")
    print(f"opportunities: {len(opps)}")
    for o in opps:
        print(f"  - {o.id}: {o.savings_ms:.0f}ms savings")

    # Minimal assertions
    assert strat.scores.performance is not None, "performance score missing"
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="PageSpeed Insights audit (PSI v5)")
    ap.add_argument("url", nargs="?", help="URL to audit")
    ap.add_argument("--strategy", choices=("mobile", "desktop", "both"), default="both")
    ap.add_argument("--no-cache", action="store_true", help="Bypass 24h on-disk cache")
    ap.add_argument("--self-test", action="store_true", help="Parse fixture, no network")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = ap.parse_args(argv)

    if args.self_test:
        return _self_test()

    if not args.url:
        ap.error("url required (or pass --self-test)")

    strategies: tuple[str, ...]
    if args.strategy == "both":
        strategies = ("mobile", "desktop")
    else:
        strategies = (args.strategy,)

    result = run_pagespeed_audit(args.url, strategies=strategies, use_cache=not args.no_cache)
    indent = 2 if args.pretty else None
    print(json.dumps(result.to_dict(), indent=indent, default=str))
    return 0 if result.status != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
