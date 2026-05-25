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
import shutil
import subprocess
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
    "/contact", "/contact/", "/contact-us", "/contact-us/",
    "/offices", "/offices/", "/our-offices", "/our-offices/",
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

CLAUDE_CLI = "claude"
CLAUDE_CLI_TIMEOUT = 90
TEXT_BUDGET = 18_000
PER_PAGE_TEXT_CAP = 8_000

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

LLM_PROMPT = """You are extracting law-firm decision-maker intelligence from raw web page text.

Goal: identify the firm's MANAGING PARTNER / SENIOR PARTNER / HEAD OF FAMILY LAW / FOUNDER plus other PARTNERS, DIRECTORS, and HEADS OF DEPARTMENT. Capture direct emails, direct phone numbers, and LinkedIn profile URLs where present in the page text.

Return STRICT JSON with this shape:
{
  "firm_name": "The Firm's Proper Display Name (e.g. 'Wards Solicitors', 'The Family Law Practice')" or null,
  "firm_address": "Head office postal address, single line: Building, Street, City, Postcode, Country" or null,
  "office_addresses": ["additional office 1", "additional office 2", ...],
  "managing_partner": "First Last" or null,
  "managing_partner_title": "string" or null,
  "managing_partner_email": "name@firm.com" or null,
  "managing_partner_linkedin": "https://linkedin.com/in/..." or null,
  "partners": [
    {"name": "First Last", "title": "Partner", "email": "name@firm.com" or null, "phone": "+44..." or null, "linkedin": "https://linkedin.com/in/..." or null}
  ],
  "all_emails": ["any@email.com", ...]
}

Rules:
- For firm_address: return the head office or first-listed postal address. Format as a single line including building/street, town, postcode, country. UK postcodes look like "BS1 4NH", "SW1A 1AA".
- For office_addresses: any additional branch office addresses, each as a single line.
- Prefer titles: Managing Partner, Senior Partner, Partner, Head of Family Law, Head of [Department], Director, Managing Director, Founder, Principal.
- Include only people who appear to work at THIS firm. Skip paralegals, trainees, support staff, and clients unless they have a senior title.
- Return real emails only — never guess email patterns.
- Return real LinkedIn URLs only if they appear in the page text.
- If nothing can be extracted, return all fields as null / empty arrays.
- JSON only, no commentary, no code fences.

PAGE TEXT (truncated):
{page_text}"""

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
    business_name: str = ""
    title: str = ""
    email: str = ""
    linkedin_url: str = ""
    phone: str = ""
    firm_address: str = ""
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


def claude_cli_available() -> bool:
    return shutil.which(CLAUDE_CLI) is not None


def fetch_text_playwright(domain: str, paths: list[str]) -> tuple[list[str], str]:
    """Visit homepage + team paths via Playwright. Return (visited_urls, combined_text)."""
    if not PLAYWRIGHT_AVAILABLE:
        return [], ""
    base = base_url(domain)
    urls = [base] + [urljoin(base, p) for p in paths]
    visited = []
    chunks = []
    seen = set()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 900},
                locale="en-GB",
            )
            page = ctx.new_page()
            for url in urls:
                if url in seen:
                    continue
                seen.add(url)
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=15000)
                except Exception:
                    continue
                if not resp or resp.status >= 400:
                    continue
                # Dismiss cookies
                for sel in COOKIE_BUTTON_SELECTORS:
                    try:
                        page.locator(sel).first.click(timeout=1000)
                        break
                    except Exception:
                        continue
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except PWTimeout:
                    pass
                try:
                    html = page.content()
                except Exception:
                    continue
                soup = BeautifulSoup(html, "html.parser")
                for bad in soup(["script", "style", "noscript", "svg"]):
                    bad.decompose()
                # Preserve linkedin URLs inline before stripping
                li_links = []
                for a in soup.find_all("a", href=re.compile(r"linkedin\.com/in/", re.I)):
                    li_links.append(a["href"].split("?")[0])
                text = soup.get_text(separator=" ", strip=True)
                text = re.sub(r"\s+", " ", text)[:PER_PAGE_TEXT_CAP]
                if li_links:
                    text += " LINKEDIN_URLS: " + " ".join(li_links)
                visited.append(url)
                chunks.append(f"=== {url} ===\n{text}")
                if sum(len(c) for c in chunks) >= TEXT_BUDGET:
                    break
            browser.close()
    except Exception as e:
        print(f"  playwright fetch error: {e}", file=sys.stderr)

    combined = "\n\n".join(chunks)[:TEXT_BUDGET]
    return visited, combined


def llm_extract(page_text: str, firm_name: str, domain: str) -> dict:
    """Pipe text to `claude -p`, parse JSON response."""
    prompt = LLM_PROMPT.replace("{page_text}", page_text)
    full_input = f"Firm: {firm_name or domain}\n\n{prompt}"
    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p"],
            input=full_input,
            capture_output=True,
            text=True,
            timeout=CLAUDE_CLI_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        print("  claude CLI timeout", file=sys.stderr)
        return {}
    except FileNotFoundError:
        print("  claude CLI not found", file=sys.stderr)
        return {}
    if result.returncode != 0:
        print(f"  claude CLI exit {result.returncode}: {result.stderr[:200]}", file=sys.stderr)
        return {}
    raw = (result.stdout or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"  LLM non-JSON, snippet: {raw[:200]}", file=sys.stderr)
        return {}


def llm_to_contacts(extracted: dict, domain: str, firm_name: str, source: str, fallback_address: str = "") -> list[Contact]:
    contacts = []
    firm_addr = (extracted.get("firm_address") or "").strip() or fallback_address
    biz_name = (extracted.get("firm_name") or "").strip() or firm_name
    mp = extracted.get("managing_partner")
    if mp:
        contacts.append(Contact(
            domain=domain,
            name=mp,
            business_name=biz_name,
            title=extracted.get("managing_partner_title") or "Managing Partner",
            email=extracted.get("managing_partner_email") or "",
            linkedin_url=extracted.get("managing_partner_linkedin") or "",
            firm_address=firm_addr,
            source_page=source,
            extraction_method="claude-cli",
            confidence="high",
        ))
    for p in extracted.get("partners", []) or []:
        name = p.get("name") if isinstance(p, dict) else None
        if not name:
            continue
        if mp and name.strip().lower() == mp.strip().lower():
            continue
        contacts.append(Contact(
            domain=domain,
            name=name,
            business_name=biz_name,
            title=p.get("title", "") if isinstance(p, dict) else "",
            email=(p.get("email") or "") if isinstance(p, dict) else "",
            linkedin_url=(p.get("linkedin") or "") if isinstance(p, dict) else "",
            phone=(p.get("phone") or "") if isinstance(p, dict) else "",
            firm_address=firm_addr,
            source_page=source,
            extraction_method="claude-cli",
            confidence="high",
        ))
    return contacts


def enrich_with_llm(domain: str, firm_name: str, fallback_address: str = "") -> list[Contact]:
    visited, text = fetch_text_playwright(domain, TEAM_PATHS)
    if not text:
        return []
    raw_emails = sorted({
        m.group(0).lower() for m in EMAIL_REGEX.finditer(text)
        if not m.group(0).lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
    })
    extracted = llm_extract(text, firm_name, domain)
    if not extracted:
        return []
    llm_emails = extracted.get("all_emails") or []
    extracted["all_emails"] = sorted(set(llm_emails + raw_emails))
    source = "; ".join(visited[:3])
    return llm_to_contacts(extracted, domain, firm_name, source, fallback_address)


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


def load_top_prospects(csv_path: Path, top: int) -> list[tuple[str, str, str]]:
    rows = []
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                score = float(row.get("pitchability_score") or 0)
            except ValueError:
                score = 0
            rows.append((score, row.get("domain", ""), row.get("business_name", ""), row.get("address", "")))
    rows.sort(reverse=True, key=lambda r: r[0])
    return [(d, n, a) for _, d, n, a in rows[:top] if d]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="scored.csv path")
    ap.add_argument("--output", required=True, help="contacts.csv output")
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--limit-pages", type=int, default=3)
    ap.add_argument("--llm", dest="llm", action="store_true", default=None,
                    help="Use Playwright + claude CLI for extraction (default ON when claude CLI available)")
    ap.add_argument("--no-llm", dest="llm", action="store_false",
                    help="Disable LLM extraction, use heuristic-only")
    args = ap.parse_args()

    if not PLAYWRIGHT_AVAILABLE:
        print("WARN: playwright not installed — JS sites may yield nothing", file=sys.stderr)

    use_llm = args.llm
    if use_llm is None:
        use_llm = claude_cli_available() and PLAYWRIGHT_AVAILABLE
    if use_llm and not claude_cli_available():
        print("WARN: claude CLI not in PATH — falling back to heuristic", file=sys.stderr)
        use_llm = False
    if use_llm and not PLAYWRIGHT_AVAILABLE:
        print("WARN: playwright unavailable — falling back to heuristic", file=sys.stderr)
        use_llm = False

    print(f"Mode: {'LLM (Playwright + claude -p)' if use_llm else 'heuristic-only'}", file=sys.stderr)

    prospects = load_top_prospects(Path(args.input), args.top)
    print(f"Scraping {len(prospects)} firms…", file=sys.stderr)

    all_contacts = []
    for domain, firm, addr in prospects:
        print(f"\n=== {domain} ({firm or '-'}) ===", file=sys.stderr)
        contacts = []
        try:
            if use_llm:
                contacts = enrich_with_llm(domain, firm, fallback_address=addr)
                print(f"  LLM → {len(contacts)} contacts", file=sys.stderr)
            if not contacts:
                if use_llm:
                    print("  LLM yielded zero — falling back to heuristic", file=sys.stderr)
                contacts = scrape_firm(domain, firm, args.limit_pages)
                contacts = [c for c in contacts if is_decision_title(c.title) or not c.title]
                for c in contacts:
                    if not c.firm_address and addr:
                        c.firm_address = addr
                    if not c.business_name and firm:
                        c.business_name = firm
            for c in contacts:
                if not c.linkedin_url:
                    c.linkedin_url = linkedin_search_url(c.name, firm or domain)
            all_contacts.extend(contacts)
        except Exception as e:
            print(f"  ERROR {domain}: {e}", file=sys.stderr)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        fieldnames = ["domain", "business_name", "name", "title", "email", "linkedin_url",
                      "phone", "firm_address", "source_page", "extraction_method", "confidence"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for c in all_contacts:
            w.writerow(asdict(c))

    print(f"\n✓ wrote {len(all_contacts)} contacts → {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
