---
name: geo-browser-render
description: Headless-Chromium browser audit for CRITICAL pages only — cookie-wall dismissal, SSR vs hydrated-DOM word-count gap, schema injected by JS, Core Web Vitals, UA-differential cloaking detection, desktop+mobile screenshots
version: 1.0.0
author: antek-automation
tags: [geo, playwright, cwv, ssr, cloaking, browser, screenshots]
allowed-tools: Bash, Read, Write
---

# GEO Browser Render Audit

## Purpose

Plain HTTP fetches (curl, WebFetch, Firecrawl scrape mode) can't measure several things that decide whether AI crawlers see your content. This sub-skill runs a **headless Chromium** browser audit against a tiny set of CRITICAL pages and produces a JSON report that the `geo-technical` agent merges into the master GEO audit.

Run ONLY on critical pages. Browser rendering is ~5-10× slower than plain fetches — never use it for full site crawls.

## When to Use

- Always: as part of `/geo audit` against the 3-5 most important pages
- On demand: when investigating an SSR-suspect page (`/properties`, `/dashboard`, anything behind a SPA router)
- When a site shows `Vary: User-Agent` and cloaking is suspected
- When client asks for visual screenshots in the PDF deliverable

## Critical-Page Selection (max 5)

1. **Homepage** (always)
2. **Primary inventory / listings page** (e.g. `/properties`, `/products`, `/shop`)
3. **Pricing / packages page**
4. **Highest-value service or category page** (from sitemap signal)
5. **Any page flagged in Phase 1 as JS-heavy, login-walled, or low SSR word count** (under 200 words server-rendered while visually content-rich)

If fewer than 5 critical pages exist, fall back to: homepage, blog index, contact-us. Cap at 5 — the script enforces this.

## How to Run

```bash
python3 ~/.claude/skills/geo/scripts/browser_render_audit.py \
  --urls https://example.com/ \
         https://example.com/pricing \
         https://example.com/properties \
  --domain example.com \
  --output reports/example.com/browser-render.json \
  --screenshots reports/example.com/screenshots
```

Inside this repo (pre-install), call from project root:
```bash
python3 scripts/browser_render_audit.py --urls ... --domain ... --output ... --screenshots ...
```

Requirements: `pip install playwright && python3 -m playwright install chromium` (already in `requirements.txt`).

## Checks Per URL

| Check | What it measures | Why it matters for GEO |
|---|---|---|
| `server_html` | Plain HTTP fetch word count + status | Baseline — what AI crawlers without JS see |
| `cookie_wall` | Overlay heuristic + auto-click "Accept All" patterns | Detects if content is hidden behind consent; whether the wall is dismissable |
| `ssr_gap` | Server word count vs hydrated DOM word count + delta | `js_dependent_content` = AI crawlers miss the bulk of the page |
| `hydrated_schema.added_by_js` | Schema types only present after JS executes | Yoast/RankMath inject post-hydration; invisible to GPTBot |
| `cwv` | LCP, CLS, TTFB, DCL, load time (Performance Observer) | Core Web Vitals feed Technical GEO score |
| `console_errors` | JS errors during load | Errors break crawler rendering |
| `network_request_count` | Total requests | Heavy 3rd-party load slows AI fetchers |
| `ua_differential` | Word count rendered as default Chrome vs GPTBot UA | `cloaking_risk: high` if delta > 25% — major penalty signal |
| `screenshot_desktop` / `screenshot_mobile` | PNG at 1440×900 and 390×844 | Visual evidence for client deliverable + mobile parity check |

## Output Schema

```json
{
  "domain": "example.com",
  "summary": {
    "pages_audited": 5,
    "cookie_walls_found": 2,
    "cookie_walls_dismissable": 2,
    "pages_with_ssr_gap": 1,
    "schema_added_by_js": ["Article", "BreadcrumbList"],
    "cloaking_risk_pages": [],
    "console_error_pages": ["https://example.com/properties"],
    "avg_lcp_ms": 1850,
    "avg_cls": 0.04
  },
  "pages": [
    {
      "url": "https://example.com/",
      "checks": {
        "server_html": {"word_count": 980, "status": 200, "error": null},
        "cookie_wall": {"present_initial": true, "dismissed": true, "button_matched": "text:Accept All", "present_after_attempt": false},
        "ssr_gap": {"server_words": 980, "hydrated_words": 1020, "delta": 40, "delta_pct": 4.1, "interpretation": "ssr_complete"},
        "hydrated_schema": {"block_count": 2, "types": ["Organisation","WebSite","WebPage","Article"], "added_by_js": ["Article"]},
        "cwv": {"lcp_ms": 1850, "cls": 0.04, "ttfb_ms": 220, "dcl_ms": 1450, "load_ms": 2200},
        "console_errors": [],
        "console_error_count": 0,
        "network_request_count": 38,
        "ua_differential": {"default_ua_words": 1020, "gptbot_ua_words": 1010, "cloaking_delta_pct": 1.0, "cloaking_risk": "low"},
        "screenshot_desktop": "reports/example.com/screenshots/home-desktop.png",
        "screenshot_mobile": "reports/example.com/screenshots/home-mobile.png"
      }
    }
  ]
}
```

## How `geo-technical` Agent Should Consume This

1. After the standard plain-fetch technical audit, identify the critical-page list (homepage + up to 4 from the rules above).
2. Run the script; read `browser-render.json`.
3. Use signals to adjust the Technical GEO score:
   - **CWV penalties:** LCP > 2500ms = −5, LCP > 4000ms = −10. CLS > 0.1 = −5, CLS > 0.25 = −10.
   - **SSR gap critical:** any page with `interpretation: js_dependent_content` AND `delta_pct > 50` → Critical finding ("AI crawlers see <X% of content on /page").
   - **Cloaking risk high:** `cloaking_risk: high` on any page → Critical finding (could trigger search penalty).
   - **Cookie wall non-dismissable:** `present_after_attempt: true` after auto-click attempt → High finding ("Content blocked by cookie wall even after auto-accept; AI crawlers see nothing").
   - **Schema-by-JS:** flag `schema_added_by_js` types as "invisible to AI crawlers" — they're not in the server HTML.
4. Embed the screenshot paths into the client PDF report via the existing PDF generator (pass into the JSON data file's `evidence` field).

## Performance

- ~5-10s per URL (desktop render + cookie dismissal + CWV + mobile render + GPTBot render = 3 navigations)
- 5 URLs ≈ 30-60s total
- Headless mode; no display required
- Cap of 5 URLs enforced in the script — do not bypass

## Scoring Impact

The browser-render output should adjust the existing **Technical GEO** category score by ±10 points based on the signals above. It does NOT introduce a new top-level category — it sharpens the existing Technical category with measured evidence.

## Failure Modes

- **Playwright not installed:** script exits with install instruction.
- **Page timeout:** that page logs `nav_error: navigation_timeout`; audit continues with remaining URLs.
- **Cookie wall not dismissable:** flagged in `present_after_attempt: true`; hydrated_words may be 0.
- **Site blocks Playwright UA:** rare; if `nav_status >= 400`, fall back to plain-fetch findings only.
