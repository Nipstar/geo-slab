#!/usr/bin/env python3
"""
Find decision-makers at prospect law firms by scraping public team/people pages.

Strategy:
1. Try static fetch (requests + BeautifulSoup) on common team-page paths.
2. Fallback to Playwright if: <3 names found, cookie wall detected, JS-only DOM.
3. Extract Person JSON-LD if present (most reliable).
4. Heuristic extract: name+title near photos, mailto: links, LinkedIn icons.
5. Build LinkedIn search URL for any contact missing a profile link.
6. Guess email from confirmed pattern on the site (no guessing if no sample).

Usage:
    python3 find_decision_makers.py --input scored.csv --output contacts.csv [--top 6] [--limit-pages 3]

Output columns:
    domain,name,title,email,linkedin_url,phone,source_page,extraction_method,confidence
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: pip install requests beautifulsoup4", file=sys.stderr)
    sys.exit(1)

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

TEAM_PATHS = [
    "/meet-the-team/", "/meet-the-team", "/meet-our-team/", "/meet-our-team",
    "/our-people/", "/our-people", "/people/", "/people",
    "/our-team/", "/our-team", "/team/", "/team",
    "/our-lawyers", "/lawyers", "/solicitors", "/our-solicitors",
    "/staff", "/our-staff", "/site/our-people/", "/site/people/", "/site/team/",
    "/about/our-people", "/about/team", "/about-us/our-team", "/about-us/people",
    "/who-we-are", "/about", "/about-us", "/family-law-team",
]

NAME_NOISE_WORDS = {
    "director", "partner", "solicitor", "manager", "associate", "consultant",
    "principal", "founder", "team", "law", "authority", "regulation", "chambers",
    "office", "department", "head", "legal", "marketing", "business",
    "counsellor", "paralegal", "executive", "fellow", "clerk", "trainee",
    "visa", "benefits", "disputes", "workers", "negligence", "abduction",
    "defence", "hearing", "social", "claims", "abuse", "litigation",
    "settlement", "custody", "rights", "compensation", "welfare", "asylum",
    "immigration", "criminal", "civil", "tribunal", "tribunals", "review",
    "appeals", "appeal", "system", "based",
}

# Common UI/service phrases that pass NAME_REGEX but aren't people
NAME_BLACKLIST = {
    "latest news", "read more", "our people", "our team", "search search",
    "meet team", "contact us", "our services", "social network", "child abduction",
    "fraud defence", "inquest hearing", "property disputes", "negligence claims",
    "court protection", "mental capacity", "civil litigation", "criminal defence",
    "employment law", "family law", "wills probate", "powers attorney",
    "personal injury", "clinical negligence", "medical negligence", "estate planning",
    "trust planning", "divorce settlement", "child custody", "domestic abuse",
    "high net", "net worth", "private client", "commercial property", "residential property",
    "dispute resolution", "alternative dispute", "first meeting", "meet our",
    "view profile", "find out", "learn more", "click here", "get touch",
    "book consultation", "privacy policy", "cookie policy", "terms conditions",
}

DECISION_TITLES = [
    "managing partner", "senior partner", "partner",
    "head of family", "head of family law", "head of department",
    "director", "managing director", "principal", "founder",
    "marketing director", "marketing manager", "business development",
    "practice manager",
]

TITLE_REGEX = re.compile(
    r"\b("
    r"managing\s+partner|senior\s+partner|partner|"
    r"head\s+of\s+[a-z\s&]+|"
    r"managing\s+director|director|principal|founder|co-founder|"
    r"marketing\s+(?:director|manager|lead)|"
    r"business\s+development\s+(?:director|manager|lead)|"
    r"practice\s+manager|"
    r"solicitor|associate|consultant"
    r")\b",
    re.IGNORECASE,
)

NAME_REGEX = re.compile(r"^[A-Z][a-z'\-]+(?:\s+[A-Z][a-z'\-]+){1,3}$")


def is_real_name(text: str) -> bool:
    if not NAME_REGEX.match(text):
        return False
    low = text.lower().strip()
    if low in NAME_BLACKLIST:
        return False
    parts = low.split()
    if any(p in NAME_NOISE_WORDS for p in parts):
        return False
    # 2-word phrases — require at least one common name signal (vowel pattern)
    return True


def decode_cf_email(cfemail: str) -> str:
    try:
        r = int(cfemail[:2], 16)
        return "".join(chr(int(cfemail[i:i+2], 16) ^ r) for i in range(2, len(cfemail), 2))
    except Exception:
        return ""

COOKIE_BUTTON_SELECTORS = [
    'button:has-text("Accept all")', 'button:has-text("Accept All")',
    'button:has-text("Accept")', 'button:has-text("I agree")',
    'button:has-text("Allow all")', 'button:has-text("OK")',
    '#onetrust-accept-btn-handler', '.cc-allow', '#cookie-accept',
]


@dataclass
class Contact:
    domain: str
    name: str
    title: str = ""
    email: str = ""
    linkedin_url: str = ""
    phone: str = ""
    source_page: str = ""
    extraction_method: str = ""
    confidence: str = "low"


def normalize_domain(d: str) -> str:
    d = d.strip().lower()
    if d.startswith("www."):
        d = d[4:]
    return d


def base_url(domain: str) -> str:
    return f"https://{domain}"


def is_decision_title(title: str) -> bool:
    t = title.lower()
    return any(dt in t for dt in DECISION_TITLES)


def fetch_static(url: str, timeout: int = 15) -> Optional[str]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code == 200 and len(r.text) > 500:
            return r.text
    except Exception:
        pass
    return None


def fetch_playwright(url: str, timeout_ms: int = 20000) -> Optional[str]:
    if not PLAYWRIGHT_AVAILABLE:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1366, "height": 900},
                locale="en-GB",
            )
            page = ctx.new_page()
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            for sel in COOKIE_BUTTON_SELECTORS:
                try:
                    page.locator(sel).first.click(timeout=1500)
                    break
                except Exception:
                    continue
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except PWTimeout:
                pass
            for _ in range(4):
                page.mouse.wheel(0, 3000)
                time.sleep(0.4)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        print(f"  playwright error: {e}", file=sys.stderr)
        return None


def find_team_pages(domain: str) -> list[str]:
    base = base_url(domain)
    home = fetch_static(base)
    pages = []
    if home:
        soup = BeautifulSoup(home, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            text = (a.get_text() or "").lower()
            if any(k in href or k in text for k in ["team", "people", "lawyer", "solicitor", "staff", "about-us", "meet"]):
                full = urljoin(base, a["href"])
                if normalize_domain(urlparse(full).netloc) == domain:
                    pages.append(full.split("#")[0])
    for path in TEAM_PATHS:
        pages.append(base + path)
    seen = set()
    out = []
    for p in pages:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def extract_jsonld_persons(soup: BeautifulSoup, domain: str, source: str) -> list[Contact]:
    contacts = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            graph = item.get("@graph", [item]) if isinstance(item, dict) else [item]
            for node in graph:
                if not isinstance(node, dict):
                    continue
                if node.get("@type") in ("Person", ["Person"]):
                    name = node.get("name", "").strip()
                    title = node.get("jobTitle", "")
                    email = node.get("email", "").replace("mailto:", "")
                    same_as = node.get("sameAs", [])
                    if isinstance(same_as, str):
                        same_as = [same_as]
                    li = next((s for s in same_as if "linkedin.com" in s), "")
                    if name and NAME_REGEX.match(name):
                        contacts.append(Contact(
                            domain=domain, name=name, title=title,
                            email=email, linkedin_url=li,
                            source_page=source,
                            extraction_method="jsonld-person",
                            confidence="high",
                        ))
    return contacts


def extract_emails_from_html(html: str) -> list[str]:
    found = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", html)
    cf = re.findall(r'data-cfemail="([a-f0-9]+)"', html, re.I)
    for token in cf:
        decoded = decode_cf_email(token)
        if decoded and "@" in decoded:
            found.append(decoded)
    return list({e.lower() for e in found if "example" not in e.lower() and "sentry" not in e.lower()})


def detect_email_pattern(emails: list[str], domain: str) -> Optional[str]:
    """Return pattern token: 'first.last', 'f.last', 'first', 'firstlast' or None."""
    candidates = [e for e in emails if e.endswith("@" + domain) or e.endswith("." + domain)]
    for e in candidates:
        local = e.split("@")[0]
        if re.match(r"^[a-z]+\.[a-z]+$", local):
            return "first.last"
        if re.match(r"^[a-z]\.[a-z]+$", local):
            return "f.last"
        if re.match(r"^[a-z]+[a-z]+$", local) and len(local) > 4:
            return "firstlast"
    return None


def guess_email(name: str, domain: str, pattern: Optional[str]) -> str:
    if not pattern:
        return ""
    parts = name.lower().split()
    if len(parts) < 2:
        return ""
    first, last = parts[0], parts[-1]
    first = re.sub(r"[^a-z]", "", first)
    last = re.sub(r"[^a-z]", "", last)
    if pattern == "first.last":
        return f"{first}.{last}@{domain}"
    if pattern == "f.last":
        return f"{first[0]}.{last}@{domain}"
    if pattern == "firstlast":
        return f"{first}{last}@{domain}"
    return ""


def extract_heuristic(html: str, domain: str, source: str) -> list[Contact]:
    soup = BeautifulSoup(html, "html.parser")
    contacts: dict[str, Contact] = {}
    page_emails = extract_emails_from_html(html)
    pattern = detect_email_pattern(page_emails, domain)

    # Strategy: only headings + anchor children — these wrap real people-card titles
    candidates = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
        text = tag.get_text(" ", strip=True)
        if not text or len(text) > 60:
            continue
        if is_real_name(text.strip()):
            candidates.append((tag, text.strip()))
    # Also anchors that wrap a person name (common pattern: <a><h3>Name</h3></a> or <a>Name</a>)
    for a in soup.find_all("a"):
        if a.find(["h1", "h2", "h3", "h4", "h5"]):
            continue  # heading inside already captured
        text = a.get_text(" ", strip=True)
        if not text or len(text) > 60:
            continue
        if is_real_name(text.strip()):
            candidates.append((a, text.strip()))
    # span/div names — only when inside person-card containers
    card_class_pattern = re.compile(r"(card|member|staff|person|profile|team-|people-|lawyer|solicitor|bio|portrait)", re.I)
    for tag in soup.find_all(["span", "div", "p"]):
        text = tag.get_text(" ", strip=True)
        if not text or len(text) > 50:
            continue
        if not is_real_name(text.strip()):
            continue
        # require ancestor with card-ish class
        anc = tag.parent
        for _ in range(4):
            if anc is None:
                break
            classes = " ".join(anc.get("class", []) if hasattr(anc, "get") else [])
            if card_class_pattern.search(classes):
                candidates.append((tag, text.strip()))
                break
            anc = anc.parent

    for tag, name in candidates:
        # Tight scope: same parent only, max 2 levels up
        parent = tag.parent
        scope_text = ""
        for _ in range(2):
            if parent is None:
                break
            scope_text = parent.get_text(" ", strip=True)[:300]
            if len(scope_text) > 30:
                break
            parent = parent.parent
        m = TITLE_REGEX.search(scope_text)
        if not m:
            continue
        title = m.group(0).strip().title()
        if not is_decision_title(title):
            continue

        # Find email near the name
        email = ""
        anchor = tag.parent
        for _ in range(4):
            if anchor is None:
                break
            mail = anchor.find("a", href=re.compile(r"^mailto:", re.I))
            if mail:
                email = mail["href"].replace("mailto:", "").split("?")[0].lower()
                break
            anchor = anchor.parent

        # LinkedIn
        linkedin = ""
        anchor = tag.parent
        for _ in range(4):
            if anchor is None:
                break
            li = anchor.find("a", href=re.compile(r"linkedin\.com/in/", re.I))
            if li:
                linkedin = li["href"].split("?")[0]
                break
            anchor = anchor.parent

        if not email and pattern:
            email = guess_email(name, domain, pattern)

        key = name.lower()
        if key not in contacts:
            contacts[key] = Contact(
                domain=domain, name=name, title=title,
                email=email, linkedin_url=linkedin,
                source_page=source,
                extraction_method="heuristic",
                confidence="high" if email and not pattern else ("medium" if email else "low"),
            )
        else:
            existing = contacts[key]
            if email and not existing.email:
                existing.email = email
            if linkedin and not existing.linkedin_url:
                existing.linkedin_url = linkedin

    return list(contacts.values())


def linkedin_search_url(name: str, firm: str) -> str:
    from urllib.parse import quote_plus
    q = quote_plus(f'site:linkedin.com/in/ "{name}" "{firm}"')
    return f"https://www.google.com/search?q={q}"


def looks_thin(contacts: list[Contact], html: str) -> bool:
    if len(contacts) >= 3:
        return False
    if html and any(kw in html.lower() for kw in ["please enable javascript", "cookie", "consent"]):
        return True
    return True


def scrape_firm(domain: str, firm_name: str, page_limit: int = 3) -> list[Contact]:
    print(f"\n=== {domain} ({firm_name or '-'}) ===", file=sys.stderr)
    pages = find_team_pages(domain)[:page_limit + 4]
    all_contacts: dict[str, Contact] = {}

    for url in pages:
        if len(all_contacts) >= 12:
            break
        print(f"  fetch: {url}", file=sys.stderr)
        html = fetch_static(url)
        method_used = "static"

        if html:
            soup = BeautifulSoup(html, "html.parser")
            j = extract_jsonld_persons(soup, domain, url)
            h = extract_heuristic(html, domain, url)
            page_contacts = j + h
            if looks_thin(page_contacts, html) and PLAYWRIGHT_AVAILABLE:
                print(f"  thin result ({len(page_contacts)}), retry playwright", file=sys.stderr)
                html2 = fetch_playwright(url)
                if html2:
                    soup2 = BeautifulSoup(html2, "html.parser")
                    j2 = extract_jsonld_persons(soup2, domain, url)
                    h2 = extract_heuristic(html2, domain, url)
                    page_contacts = j2 + h2
                    method_used = "playwright"
        else:
            if not PLAYWRIGHT_AVAILABLE:
                continue
            html2 = fetch_playwright(url)
            if not html2:
                continue
            soup2 = BeautifulSoup(html2, "html.parser")
            j2 = extract_jsonld_persons(soup2, domain, url)
            h2 = extract_heuristic(html2, domain, url)
            page_contacts = j2 + h2
            method_used = "playwright"

        for c in page_contacts:
            if c.extraction_method == "heuristic":
                c.extraction_method = f"heuristic-{method_used}"
            key = c.name.lower()
            if key not in all_contacts:
                all_contacts[key] = c
            else:
                existing = all_contacts[key]
                if c.email and not existing.email:
                    existing.email = c.email
                if c.linkedin_url and not existing.linkedin_url:
                    existing.linkedin_url = c.linkedin_url
                if c.title and not existing.title:
                    existing.title = c.title

        print(f"  → +{len(page_contacts)} (total {len(all_contacts)})", file=sys.stderr)

    # Backfill LinkedIn search URLs
    for c in all_contacts.values():
        if not c.linkedin_url:
            c.linkedin_url = linkedin_search_url(c.name, firm_name or domain)

    return list(all_contacts.values())


def load_top_prospects(csv_path: Path, top: int) -> list[tuple[str, str]]:
    rows = []
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                score = float(row.get("pitchability_score") or 0)
            except ValueError:
                score = 0
            rows.append((score, row.get("domain", ""), row.get("business_name", "")))
    rows.sort(reverse=True)
    return [(d, n) for _, d, n in rows[:top] if d]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="scored.csv path")
    ap.add_argument("--output", required=True, help="contacts.csv output")
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--limit-pages", type=int, default=3)
    args = ap.parse_args()

    if not PLAYWRIGHT_AVAILABLE:
        print("WARN: playwright not installed — JS sites may yield nothing", file=sys.stderr)

    prospects = load_top_prospects(Path(args.input), args.top)
    print(f"Scraping {len(prospects)} firms…", file=sys.stderr)

    all_contacts = []
    for domain, firm in prospects:
        try:
            contacts = scrape_firm(domain, firm, args.limit_pages)
            decision_only = [c for c in contacts if is_decision_title(c.title) or not c.title]
            all_contacts.extend(decision_only)
        except Exception as e:
            print(f"  ERROR {domain}: {e}", file=sys.stderr)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        fieldnames = ["domain", "name", "title", "email", "linkedin_url", "phone",
                      "source_page", "extraction_method", "confidence"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for c in all_contacts:
            w.writerow(asdict(c))

    print(f"\n✓ wrote {len(all_contacts)} contacts → {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
