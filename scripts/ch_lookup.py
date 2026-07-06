#!/usr/bin/env python3
"""
Companies House lookup — company + active officers for prospect personalisation.

Uses the official API when COMPANIES_HOUSE_API_KEY is set (basic auth, key as
username, blank password). Falls back to scraping the public register website
(find-and-update.company-information.service.gov.uk) when no key is present, so
it still works before the key is wired up.

    python3 ch_lookup.py --name "Clifford Fry & Co"
    python3 ch_lookup.py --number OC312394 --output ch.json

Returns JSON: {query, source, company:{number,name,type,address}, officers:[{name,role,status,salutation}]}
ponytail: public scrape is a best-effort fallback; the API path is the real one.
"""
from __future__ import annotations
import argparse, base64, json, os, re, sys, urllib.request, urllib.parse
from html import unescape

API = "https://api.company-information.service.gov.uk"
WEB = "https://find-and-update.company-information.service.gov.uk"
UA = {"User-Agent": "Mozilla/5.0 (GEO-SLAB ch_lookup)"}


def _get(url: str, key: str | None) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=dict(UA))
    if key:
        tok = base64.b64encode(f"{key}:".encode()).decode()
        req.add_header("Authorization", f"Basic {tok}")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def _salutation(name: str) -> str:
    """CH gives 'SURNAME, Forename Middle, Title'. Make 'Mr Forename Surname'."""
    parts = [p.strip() for p in name.split(",")]
    title = ""
    if len(parts) >= 3 and parts[-1] in ("Mr", "Mrs", "Ms", "Miss", "Dr", "Sir"):
        title = parts[-1]
    surname = parts[0].title() if parts else name
    forename = parts[1].split()[0].title() if len(parts) > 1 and parts[1] else ""
    core = f"{forename} {surname}".strip()
    return f"{title} {core}".strip() if title else core


# ── API path ──────────────────────────────────────────────────────────────
def via_api(name: str | None, number: str | None, key: str) -> dict | None:
    if not number:
        st, body = _get(f"{API}/search/companies?q={urllib.parse.quote(name)}&items_per_page=5", key)
        if st != 200 or not body:
            return None
        items = json.loads(body).get("items", [])
        # prefer an active LLP/LTD whose title starts with the query
        items.sort(key=lambda i: (i.get("company_status") != "active", "llp" not in (i.get("company_type") or "")))
        if not items:
            return None
        number = items[0]["company_number"]
    st, body = _get(f"{API}/company/{number}", key)
    if st != 200:
        return None
    c = json.loads(body)
    ro = c.get("registered_office_address", {})
    addr = ", ".join(filter(None, [ro.get("address_line_1"), ro.get("address_line_2"),
                                    ro.get("locality"), ro.get("postal_code")]))
    st, body = _get(f"{API}/company/{number}/officers?register_view=false&items_per_page=35", key)
    officers = []
    if st == 200:
        for o in json.loads(body).get("items", []):
            if o.get("resigned_on"):
                continue
            nm = o.get("name", "")
            if not re.search(r"[a-z]", nm.replace(nm.upper(), "")) and "," not in nm:
                pass  # corporate member with all-caps name — keep, filtered below
            if o.get("officer_role", "").startswith("corporate"):
                continue
            officers.append({"name": nm, "role": o.get("officer_role", ""),
                             "status": "active", "salutation": _salutation(nm)})
    return {"source": "api", "company": {"number": number, "name": c.get("company_name"),
            "type": c.get("type"), "address": addr}, "officers": officers}


# ── Public-register scrape fallback ────────────────────────────────────────
def via_scrape(name: str | None, number: str | None) -> dict | None:
    if not number:
        _, body = _get(f"{WEB}/search/companies?q={urllib.parse.quote(name)}", None)
        m = re.findall(r'/company/([0-9A-Z]+)"[^>]*>\s*([^<]+)', body)
        if not m:
            return None
        # prefer an LLP (chartered practices usually are)
        m.sort(key=lambda x: "LLP" not in x[1].upper())
        number = m[0][0]
    _, ch = _get(f"{WEB}/company/{number}", None)
    cname = unescape(re.findall(r"<title>\s*([^<|]+)", ch)[0].strip()) if "<title>" in ch else number
    addr_m = re.search(r'Registered office address[\s\S]{0,400}?<dd[^>]*>\s*([^<]+)', ch)
    addr = unescape(addr_m.group(1).strip()) if addr_m else ""
    _, off = _get(f"{WEB}/company/{number}/officers", None)
    officers = []
    for a in re.finditer(r'/officers/[A-Za-z0-9_-]+/appointments"[^>]*>\s*([^<]+)</a>', off):
        nm = unescape(a.group(1).strip())
        if nm.isupper() and "," not in nm:      # corporate member
            continue
        tail = off[a.end():a.end() + 900]
        status = "resigned" if re.search(r"\bResigned\b", tail[:400]) else "active"
        if status == "resigned":
            continue
        role_m = re.search(r"(Designated LLP Member|LLP Member|Director|Member|Secretary)", tail)
        officers.append({"name": nm, "role": role_m.group(1) if role_m else "",
                         "status": status, "salutation": _salutation(nm)})
    # de-dupe by name preserving order
    seen, uniq = set(), []
    for o in officers:
        if o["name"] not in seen:
            seen.add(o["name"]); uniq.append(o)
    return {"source": "scrape", "company": {"number": number, "name": cname,
            "type": "", "address": addr}, "officers": uniq}


def main():
    ap = argparse.ArgumentParser(description="Companies House company + active officers")
    ap.add_argument("--name")
    ap.add_argument("--number")
    ap.add_argument("--output")
    a = ap.parse_args()
    if not (a.name or a.number):
        ap.error("provide --name or --number")
    key = os.environ.get("COMPANIES_HOUSE_API_KEY")
    res = (via_api(a.name, a.number, key) if key else None) or via_scrape(a.name, a.number)
    if not res:
        print("ch_lookup: nothing found", file=sys.stderr); sys.exit(1)
    res["query"] = a.name or a.number
    out = json.dumps(res, indent=2)
    if a.output:
        with open(a.output, "w") as f:
            f.write(out)
        act = [o["salutation"] for o in res["officers"]]
        print(f"ch_lookup: {res['company']['name']} ({res['company']['number']}) via {res['source']} — "
              f"{len(act)} active: {', '.join(act[:6])}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
