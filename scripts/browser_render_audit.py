#!/usr/bin/env python3
"""
GEO SLAB — Browser Render Audit (Playwright)

Runs targeted JS-rendered browser checks against a handful of CRITICAL pages
that plain HTTP fetches can't measure. Output is a JSON report consumed by
the geo-technical agent and merged into the master GEO audit.

Checks per URL:
  1. Cookie/consent wall detection + auto-dismiss
  2. Server-HTML vs hydrated-DOM word-count delta (SSR gap)
  3. Schema.org JSON-LD block count + types (pre- and post-hydration)
  4. Core Web Vitals: LCP, CLS, render time, TTFB
  5. Console errors + network request count
  6. UA differential: render as default Mozilla vs GPTBot; compare word counts (cloaking)
  7. Desktop + mobile screenshot capture (PNG)

Usage:
    python3 browser_render_audit.py \\
        --urls https://example.com/ https://example.com/pricing \\
        --domain example.com \\
        --output reports/example.com/browser-render.json \\
        --screenshots reports/example.com/screenshots

Notes:
  - Cap of 5 URLs enforced; pass the most critical pages only.
  - Headless Chromium. ~5-10s per URL.
  - Requires: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
import ssl
from pathlib import Path
from urllib.parse import urlparse

try:
    from playwright.sync_api import sync_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium", file=sys.stderr)
    sys.exit(1)


MAX_URLS = 5
NAV_TIMEOUT_MS = 45000
HYDRATE_WAIT_MS = 2500

DESKTOP_VIEWPORT = {"width": 1440, "height": 900}
MOBILE_VIEWPORT = {"width": 390, "height": 844}
MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
DEFAULT_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
GPTBOT_UA = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.2; +https://openai.com/gptbot"

CONSENT_BUTTON_PATTERNS = [
    "Accept All", "Accept all", "ACCEPT ALL",
    "Allow All", "Allow all",
    "Agree", "I Agree", "I accept",
    "OK", "Got it",
    "Accept Cookies", "Accept cookies",
    "Consent", "Continue",
]


def server_html_word_count(url: str, retries: int = 2):
    """Plain HTTP fetch — what AI crawlers (no JS) see. Returns (word_count, status, error)."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": DEFAULT_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.5",
            })
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
                html = r.read().decode("utf-8", errors="replace")
                status = r.status
            text = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL | re.I)
            text = re.sub(r"<style.*?</style>", "", text, flags=re.DOTALL | re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            return len(text.split()), status, None
        except Exception as e:
            last_err = str(e)
            if attempt < retries:
                time.sleep(2 + attempt * 2)
    return 0, 0, last_err


def extract_schema_blocks(html_or_dom: str) -> list[dict]:
    blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_or_dom, re.DOTALL | re.I,
    )
    parsed = []
    for b in blocks:
        try:
            d = json.loads(b.strip())
            parsed.append(d)
        except Exception:
            pass
    return parsed


def schema_types(blocks: list[dict]) -> list[str]:
    types: list[str] = []
    def walk(node):
        if isinstance(node, dict):
            t = node.get("@type")
            if isinstance(t, str):
                types.append(t)
            elif isinstance(t, list):
                types.extend([str(x) for x in t])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    for b in blocks:
        walk(b)
    return sorted(set(types))


def try_dismiss_cookie_wall(page) -> tuple[bool, str | None]:
    """Attempt to click common consent buttons. Returns (clicked, button_text)."""
    # First try common selectors
    for sel in [
        "#onetrust-accept-btn-handler",
        "button[id*='accept']",
        "button[class*='accept-all']",
        "button[class*='cookie'][class*='accept']",
        "[data-testid*='accept']",
        "[aria-label*='Accept all']",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=500):
                el.click(timeout=1500)
                return True, f"selector:{sel}"
        except Exception:
            continue
    # Then try by visible button text
    for txt in CONSENT_BUTTON_PATTERNS:
        try:
            btn = page.get_by_role("button", name=re.compile(rf"^\s*{re.escape(txt)}\s*$", re.I)).first
            if btn.is_visible(timeout=400):
                btn.click(timeout=1500)
                return True, f"text:{txt}"
        except Exception:
            continue
    return False, None


def detect_cookie_wall(page) -> bool:
    """Heuristic: large overlay containing 'cookie' text covering viewport."""
    try:
        result = page.evaluate("""() => {
            const els = document.querySelectorAll('div,section,aside');
            for (const el of els) {
                const txt = (el.innerText || '').toLowerCase();
                if (txt.length > 80 && txt.length < 4000 && /cookie|consent|privacy/.test(txt)) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 250 && r.height > 100) return true;
                }
            }
            return false;
        }""")
        return bool(result)
    except Exception:
        return False


def capture_cwv(page) -> dict:
    """Capture LCP, CLS, TTFB, DCL, load time via PerformanceObserver / Navigation Timing."""
    try:
        return page.evaluate("""() => {
            return new Promise(resolve => {
                const out = { lcp_ms: null, cls: null, ttfb_ms: null, dcl_ms: null, load_ms: null };
                const nav = performance.getEntriesByType('navigation')[0];
                if (nav) {
                    out.ttfb_ms = Math.round(nav.responseStart - nav.startTime);
                    out.dcl_ms = Math.round(nav.domContentLoadedEventEnd);
                    out.load_ms = Math.round(nav.loadEventEnd);
                }
                let lcp = 0, cls = 0;
                try {
                    new PerformanceObserver(list => {
                        const entries = list.getEntries();
                        if (entries.length) lcp = entries[entries.length - 1].startTime;
                    }).observe({ type: 'largest-contentful-paint', buffered: true });
                    new PerformanceObserver(list => {
                        for (const e of list.getEntries()) if (!e.hadRecentInput) cls += e.value;
                    }).observe({ type: 'layout-shift', buffered: true });
                } catch (e) {}
                setTimeout(() => {
                    out.lcp_ms = lcp ? Math.round(lcp) : null;
                    out.cls = cls ? Math.round(cls * 1000) / 1000 : 0;
                    resolve(out);
                }, 800);
            });
        }""")
    except Exception as e:
        return {"error": str(e)}


def audit_url(browser, url: str, screenshot_dir: Path, slug: str) -> dict:
    result: dict = {"url": url, "checks": {}}

    # 1. Server-HTML word count (no JS)
    srv_words, srv_status, srv_err = server_html_word_count(url)
    result["checks"]["server_html"] = {
        "word_count": srv_words,
        "status": srv_status,
        "error": srv_err,
    }

    # Server-rendered schema (curl-style)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA})
        srv_html = urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()).read().decode("utf-8", errors="replace")
        srv_schema_blocks = extract_schema_blocks(srv_html)
        result["checks"]["server_schema"] = {
            "block_count": len(srv_schema_blocks),
            "types": schema_types(srv_schema_blocks),
        }
    except Exception as e:
        result["checks"]["server_schema"] = {"error": str(e)}

    # 2. Desktop render
    console_msgs: list[str] = []
    network_count = {"n": 0}
    context = browser.new_context(
        viewport=DESKTOP_VIEWPORT,
        user_agent=DEFAULT_UA,
        ignore_https_errors=True,
    )
    page = context.new_page()
    page.on("console", lambda msg: console_msgs.append(f"{msg.type}: {msg.text}"[:300]))
    page.on("request", lambda req: network_count.update(n=network_count["n"] + 1))

    nav_err = None
    nav_status = None
    for attempt in range(2):
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            nav_status = resp.status if resp else None
            page.wait_for_timeout(HYDRATE_WAIT_MS)
            nav_err = None
            break
        except PlaywrightTimeout:
            nav_err = "navigation_timeout"
        except PlaywrightError as e:
            nav_err = str(e)[:200]
        if attempt == 0:
            page.wait_for_timeout(3000)

    # Cookie wall detect + dismiss
    wall_present = detect_cookie_wall(page) if not nav_err else False
    wall_clicked, wall_btn = (False, None)
    if wall_present:
        wall_clicked, wall_btn = try_dismiss_cookie_wall(page)
        if wall_clicked:
            page.wait_for_timeout(1500)
            wall_present_after = detect_cookie_wall(page)
        else:
            wall_present_after = True
    else:
        wall_present_after = False

    result["checks"]["cookie_wall"] = {
        "present_initial": wall_present,
        "dismissed": wall_clicked,
        "button_matched": wall_btn,
        "present_after_attempt": wall_present_after,
    }

    # Hydrated DOM word count + schema
    hyd_words = 0
    hyd_schema_types: list[str] = []
    hyd_schema_count = 0
    if not nav_err:
        try:
            hyd_html = page.content()
            text_only = page.evaluate("() => document.body ? document.body.innerText : ''")
            hyd_words = len((text_only or "").split())
            blocks = extract_schema_blocks(hyd_html)
            hyd_schema_count = len(blocks)
            hyd_schema_types = schema_types(blocks)
        except Exception as e:
            result["checks"]["hydrated_dom_error"] = str(e)

    result["checks"]["hydrated_dom"] = {
        "word_count": hyd_words,
        "nav_status": nav_status,
        "nav_error": nav_err,
    }
    result["checks"]["ssr_gap"] = {
        "server_words": srv_words,
        "hydrated_words": hyd_words,
        "delta": hyd_words - srv_words,
        "delta_pct": round((hyd_words - srv_words) / max(srv_words, 1) * 100, 1) if srv_words else None,
        "interpretation": (
            "ssr_complete" if srv_words and hyd_words and abs(hyd_words - srv_words) / max(srv_words, 1) < 0.15
            else "js_dependent_content" if hyd_words > srv_words * 1.3
            else "minor_diff"
        ),
    }
    result["checks"]["hydrated_schema"] = {
        "block_count": hyd_schema_count,
        "types": hyd_schema_types,
        "added_by_js": sorted(set(hyd_schema_types) - set(result["checks"].get("server_schema", {}).get("types", []))),
    }

    # 3. Core Web Vitals
    if not nav_err:
        result["checks"]["cwv"] = capture_cwv(page)
    result["checks"]["console_errors"] = [m for m in console_msgs if m.startswith("error")][:10]
    result["checks"]["console_error_count"] = sum(1 for m in console_msgs if m.startswith("error"))
    result["checks"]["network_request_count"] = network_count["n"]

    # 4. Desktop screenshot
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    desktop_png = screenshot_dir / f"{slug}-desktop.png"
    try:
        page.screenshot(path=str(desktop_png), full_page=False)
        result["checks"]["screenshot_desktop"] = str(desktop_png)
    except Exception as e:
        result["checks"]["screenshot_desktop_error"] = str(e)

    context.close()

    # 5. Mobile render
    mobile_ctx = browser.new_context(
        viewport=MOBILE_VIEWPORT,
        user_agent=MOBILE_UA,
        is_mobile=True,
        has_touch=True,
        ignore_https_errors=True,
    )
    mobile_page = mobile_ctx.new_page()
    try:
        mobile_page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
        mobile_page.wait_for_timeout(HYDRATE_WAIT_MS)
        try_dismiss_cookie_wall(mobile_page)
        mobile_png = screenshot_dir / f"{slug}-mobile.png"
        mobile_page.screenshot(path=str(mobile_png), full_page=False)
        result["checks"]["screenshot_mobile"] = str(mobile_png)
    except Exception as e:
        result["checks"]["screenshot_mobile_error"] = str(e)
    mobile_ctx.close()

    # 6. UA differential — render as GPTBot, compare visible word count
    gpt_ctx = browser.new_context(
        viewport=DESKTOP_VIEWPORT,
        user_agent=GPTBOT_UA,
        ignore_https_errors=True,
    )
    gpt_page = gpt_ctx.new_page()
    gpt_words = 0
    gpt_err = None
    try:
        gpt_resp = gpt_page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
        gpt_status = gpt_resp.status if gpt_resp else None
        gpt_page.wait_for_timeout(HYDRATE_WAIT_MS)
        gpt_text = gpt_page.evaluate("() => document.body ? document.body.innerText : ''")
        gpt_words = len((gpt_text or "").split())
    except Exception as e:
        gpt_err = str(e)[:200]
        gpt_status = None
    gpt_ctx.close()

    default_words = hyd_words
    cloaking_delta_pct = (
        round((default_words - gpt_words) / max(default_words, 1) * 100, 1)
        if default_words else None
    )
    result["checks"]["ua_differential"] = {
        "default_ua_words": default_words,
        "gptbot_ua_words": gpt_words,
        "gptbot_status": gpt_status,
        "gptbot_error": gpt_err,
        "cloaking_delta_pct": cloaking_delta_pct,
        "cloaking_risk": (
            "high" if cloaking_delta_pct is not None and abs(cloaking_delta_pct) > 25
            else "low" if cloaking_delta_pct is not None
            else "unknown"
        ),
    }

    return result


def derive_slug(url: str) -> str:
    p = urlparse(url)
    path = re.sub(r"[^a-z0-9]+", "-", (p.path or "/").lower()).strip("-")
    return path or "home"


def summarise(per_url: list[dict]) -> dict:
    summary = {
        "pages_audited": len(per_url),
        "cookie_walls_found": sum(1 for p in per_url if p["checks"].get("cookie_wall", {}).get("present_initial")),
        "cookie_walls_dismissable": sum(1 for p in per_url if p["checks"].get("cookie_wall", {}).get("dismissed")),
        "pages_with_ssr_gap": sum(1 for p in per_url if p["checks"].get("ssr_gap", {}).get("interpretation") == "js_dependent_content"),
        "schema_added_by_js": sorted({
            t for p in per_url for t in p["checks"].get("hydrated_schema", {}).get("added_by_js", [])
        }),
        "cloaking_risk_pages": [
            p["url"] for p in per_url
            if p["checks"].get("ua_differential", {}).get("cloaking_risk") == "high"
        ],
        "console_error_pages": [
            p["url"] for p in per_url
            if p["checks"].get("console_error_count", 0) > 0
        ],
        "avg_lcp_ms": None,
        "avg_cls": None,
    }
    lcps = [p["checks"].get("cwv", {}).get("lcp_ms") for p in per_url if isinstance(p["checks"].get("cwv", {}).get("lcp_ms"), (int, float))]
    clss = [p["checks"].get("cwv", {}).get("cls") for p in per_url if isinstance(p["checks"].get("cwv", {}).get("cls"), (int, float))]
    if lcps:
        summary["avg_lcp_ms"] = round(sum(lcps) / len(lcps))
    if clss:
        summary["avg_cls"] = round(sum(clss) / len(clss), 3)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="GEO Browser Render Audit (Playwright)")
    ap.add_argument("--urls", nargs="+", required=True, help=f"Critical page URLs (max {MAX_URLS})")
    ap.add_argument("--domain", required=True, help="Domain label (used in slugs)")
    ap.add_argument("--output", required=True, help="Output JSON file path")
    ap.add_argument("--screenshots", required=True, help="Output screenshots directory")
    args = ap.parse_args()

    urls = args.urls[:MAX_URLS]
    if len(args.urls) > MAX_URLS:
        print(f"WARN: capped {len(args.urls)} URLs to {MAX_URLS}", file=sys.stderr)

    screenshot_dir = Path(args.screenshots)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[browser-render] auditing {len(urls)} URL(s) for {args.domain}", file=sys.stderr)

    per_url: list = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for i, url in enumerate(urls, 1):
            slug = derive_slug(url)
            print(f"  [{i}/{len(urls)}] {url}", file=sys.stderr)
            try:
                per_url.append(audit_url(browser, url, screenshot_dir, slug))
            except Exception as e:
                per_url.append({"url": url, "fatal_error": str(e)})
            # Inter-page delay to avoid tripping rate-limit / anti-bot on smaller sites
            if i < len(urls):
                time.sleep(3)
        browser.close()

    report = {
        "domain": args.domain,
        "summary": summarise(per_url),
        "pages": per_url,
    }
    out_path.write_text(json.dumps(report, indent=2))
    print(f"[browser-render] wrote {out_path}", file=sys.stderr)
    print(f"[browser-render] summary: {json.dumps(report['summary'])}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
