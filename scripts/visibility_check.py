#!/usr/bin/env python3
"""
GEO SLAB — Free AI Visibility Check (the lead magnet).

Runs a business through ChatGPT, Claude, Gemini and Perplexity (all via one
OpenRouter key) and reports whether AI recommends them or their competitors.

SCOPE IS FROZEN (spec §7): mention yes/no per platform, how described, up to 5
competitors AI named instead, one blunt 0-100 score. NO citability, technical,
schema, priorities or action plan — those are the PAID Quick Check / Full Audit.

Pure Python, zero LLM orchestration — safe to run from cron / n8n / a Flask
endpoint with no Claude Code session.

    python3 visibility_check.py --company "Dave Plumbing" --domain daveplumbing.co.uk \
        --industry plumber --location Basingstoke [--county Hampshire]
    python3 visibility_check.py --prospect PRO-001        # pull details from DB
    python3 visibility_check.py --prospect PRO-001 --no-report   # skip HTML/PDF
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402
from lib.ai_query_core import (  # noqa: E402
    CHECK_MODELS,
    detect_brand_mention,
    extract_competitors,
    load_env,
    query_openrouter_full,
)

PLATFORMS = list(CHECK_MODELS.keys())  # ChatGPT, Claude, Gemini, Perplexity


def _art(word: str) -> str:
    """a / an by leading vowel. ponytail: vowel heuristic — 'hour'/'MOT' edge
    cases rare for trade nouns; fix with a word list only if one bites."""
    return "an" if word[:1].lower() in "aeiou" else "a"


# Raw category strings (landing form, Google Places, Companies House SIC
# descriptions) mapped to what a real person actually types into ChatGPT.
# Key = lowercased raw term. Value = (singular, plural). Keep UK vocabulary.
TERM_MAP: dict[str, tuple[str, str]] = {
    # professional services
    "legal services": ("solicitor", "solicitors"),
    "law firm": ("solicitor", "solicitors"),
    "lawyer": ("solicitor", "solicitors"),
    "solicitor": ("solicitor", "solicitors"),
    "accounting": ("accountant", "accountants"),
    "accountancy": ("accountant", "accountants"),
    "accounting services": ("accountant", "accountants"),
    "bookkeeping": ("bookkeeper", "bookkeepers"),
    "financial services": ("financial adviser", "financial advisers"),
    "financial advice": ("financial adviser", "financial advisers"),
    "insurance": ("insurance broker", "insurance brokers"),
    "insurance agency": ("insurance broker", "insurance brokers"),
    "marketing": ("marketing agency", "marketing agencies"),
    "marketing services": ("marketing agency", "marketing agencies"),
    "recruitment": ("recruitment agency", "recruitment agencies"),
    "it services": ("IT support company", "IT support companies"),
    "it support": ("IT support company", "IT support companies"),
    "architecture": ("architect", "architects"),
    "surveying": ("surveyor", "surveyors"),
    # property
    "real estate": ("estate agent", "estate agents"),
    "real estate agency": ("estate agent", "estate agents"),
    "estate agency": ("estate agent", "estate agents"),
    "letting agency": ("letting agent", "letting agents"),
    "property management": ("property management company",
                            "property management companies"),
    # health
    "dental": ("dentist", "dentists"),
    "dental practice": ("dentist", "dentists"),
    "dentistry": ("dentist", "dentists"),
    "veterinary": ("vet", "vets"),
    "veterinary practice": ("vet", "vets"),
    "veterinary services": ("vet", "vets"),
    "physiotherapy": ("physiotherapist", "physiotherapists"),
    "optician": ("optician", "opticians"),
    "chiropractic": ("chiropractor", "chiropractors"),
    # trades
    "plumbing": ("plumber", "plumbers"),
    "plumbing services": ("plumber", "plumbers"),
    "electrical": ("electrician", "electricians"),
    "electrical services": ("electrician", "electricians"),
    "roofing": ("roofer", "roofers"),
    "building": ("builder", "builders"),
    "construction": ("builder", "builders"),
    "heating": ("heating engineer", "heating engineers"),
    "heating services": ("heating engineer", "heating engineers"),
    "landscaping": ("landscaper", "landscapers"),
    "gardening": ("gardener", "gardeners"),
    "cleaning": ("cleaning company", "cleaning companies"),
    "cleaning services": ("cleaning company", "cleaning companies"),
    "pest control": ("pest control company", "pest control companies"),
    "locksmith": ("locksmith", "locksmiths"),
    "removals": ("removals company", "removals companies"),
    # automotive
    "car repair": ("garage", "garages"),
    "auto repair": ("garage", "garages"),
    "vehicle repair": ("garage", "garages"),
    "mot": ("MOT garage", "MOT garages"),
    "car dealership": ("car dealer", "car dealers"),
    # print / office (Antek verticals)
    "managed print services": ("managed print provider",
                               "managed print providers"),
    "printing services": ("printer", "printing companies"),
}


def _clean_town(town: str) -> str:
    """Strip trailing country suffixes people paste in — 'Southampton, UK'
    reads robotic inside a prompt."""
    t = town.strip()
    for suffix in (", uk", ", united kingdom", ", england", ", scotland",
                   ", wales", ", gb"):
        if t.lower().endswith(suffix):
            t = t[: -len(suffix)].rstrip(" ,")
    return t


def _plural(word: str) -> str:
    """Grammar-safe pluralisation. Never produces 'servicess'."""
    w = word.strip()
    lower = w.lower()
    if lower.endswith("s") or lower.endswith("services"):
        return w
    if lower.endswith("y") and lower[-2:-1] not in "aeiou":
        return w[:-1] + "ies"
    if lower.endswith(("ch", "sh", "x", "z")):
        return w + "es"
    return w + "s"


def normalise_term(industry: str) -> tuple[str, str, bool]:
    """Return (singular, plural, countable) for the search noun a real person
    would use. countable=False means the term is a service phrase ('legal
    services') that never got mapped — templates must avoid 'a X' grammar."""
    raw = industry.strip().lower()
    if raw in TERM_MAP:
        s, p = TERM_MAP[raw]
        return s, p, True
    # try stripping a trailing 'services' -> map again ('roofing services')
    if raw.endswith(" services"):
        base = raw[: -len(" services")].strip()
        if base in TERM_MAP:
            s, p = TERM_MAP[base]
            return s, p, True
    # unmapped: keep the term, decide countability by shape
    countable = not (raw.endswith("s") or " services" in raw
                     or raw.endswith("ing"))
    term = industry.strip()
    if not countable and term.lower().endswith(" services"):
        term = term[: -len(" services")].rstrip()
    return term, _plural(term), countable


# Free check runs the top FREE_PROMPTS buyer intents (best / recommend /
# reviews). The full 5-prompt sweep (adds who-to-call + compare) is a paid
# Quick Check / Full Audit feature. Override with env FREE_PROMPTS.
FREE_PROMPTS = int(os.environ.get("FREE_PROMPTS", "3"))


def build_prompts(industry: str, town: str, county: str = "",
                  limit: int | None = None) -> list[str]:
    """Discovery prompts (spec §7 intents), phrased the way a real person
    types them, ordered by conversion signal. Default returns the free-tier
    subset; pass limit=5 for the paid full sweep."""
    town = _clean_town(town)
    county = _clean_town(county) or town
    sing, plur, countable = normalise_term(industry)
    if countable:
        prompts = [
            f"Who's the best {sing} in {town}?",
            f"Can you recommend a good {sing} near {town}?",
            f"Which {plur} in {town} have the best reviews?",
            f"I need {_art(sing)} {sing} in {county}, who should I call?",
            f"Compare {plur} in {town}",
        ]
    else:
        # service-phrase fallback — grammar-safe, no articles, no blind plurals
        prompts = [
            f"Who's the best for {sing} in {town}?",
            f"Can you recommend somewhere for {sing} near {town}?",
            f"Which {sing} companies in {town} have the best reviews?",
            f"I need {sing} in {county}, who should I call?",
            f"Compare {sing} companies in {town}",
        ]
    n = limit if limit is not None else FREE_PROMPTS
    return prompts[:max(1, min(n, len(prompts)))]


def run_check(company: str, domain: str, industry: str, town: str,
              county: str = "") -> dict:
    """Query 4 platforms × 5 prompts via OpenRouter. Returns the full result
    dict. Pure — no DB writes, no file output."""
    load_env()
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("ERROR: OPENROUTER_API_KEY not set (env or .env.local)")

    prompts = build_prompts(industry, town, county)
    jobs = [(plat, CHECK_MODELS[plat], prompt) for plat in PLATFORMS for prompt in prompts]

    def _one(job):
        plat, model, prompt = job
        time.sleep(0.2)  # gentle rate limit
        res = query_openrouter_full(prompt, api_key, model)
        return plat, prompt, res

    raw: list[tuple] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for fut in concurrent.futures.as_completed([ex.submit(_one, j) for j in jobs]):
            raw.append(fut.result())

    # Aggregate per platform
    platforms_out = []
    competitor_counts: dict[str, dict] = {}
    total_cost = 0.0
    prompts_total = prompts_mentioned = 0

    for plat in PLATFORMS:
        entries = [(prompt, res) for (p, prompt, res) in raw if p == plat]
        responses, mentioned_here, best_snippet, sentiment = [], 0, "", "neutral"
        answered = 0
        for prompt, res in entries:
            if not res:
                responses.append({"prompt": prompt, "answered": False, "mentioned": False,
                                  "snippet": "", "response": ""})
                continue
            answered += 1
            total_cost += res.get("cost_usd", 0.0)
            det = detect_brand_mention(res["text"], company, domain)
            for comp in extract_competitors(res["text"], company):
                c = competitor_counts.setdefault(comp.lower(), {"name": comp, "mentions": 0})
                c["mentions"] += 1
            snippet = det["positions"][0] if det["positions"] else ""
            if det["mentioned"]:
                mentioned_here += 1
                if not best_snippet:
                    best_snippet = snippet
                    sentiment = det["sentiment"]
            # Store the verbatim answer — this is the proof shown in the report
            # ("we asked X, here is exactly what ChatGPT replied").
            responses.append({"prompt": prompt, "answered": True,
                              "mentioned": det["mentioned"], "snippet": snippet,
                              "response": res["text"]})
        prompts_total += answered
        prompts_mentioned += mentioned_here
        platforms_out.append({
            "platform": plat,
            "model": CHECK_MODELS[plat],
            "tested": answered > 0,
            "mentioned": mentioned_here > 0,
            "prompts_answered": answered,
            "prompts_mentioned": mentioned_here,
            "snippet": best_snippet,
            "sentiment": sentiment,
            "responses": responses,
        })

    platforms_tested = sum(1 for p in platforms_out if p["tested"])
    platforms_mentioned = sum(1 for p in platforms_out if p["mentioned"])

    # Blunt 0-100 score (spec §7). Guard div-by-zero if every platform errored.
    score = 0.0
    if platforms_tested:
        score += (platforms_mentioned / platforms_tested) * 70
    if prompts_total:
        score += (prompts_mentioned / prompts_total) * 30
    score = round(score)

    competitors = sorted(competitor_counts.values(), key=lambda c: c["mentions"], reverse=True)[:5]

    return {
        "company": company, "domain": domain, "industry": industry,
        "town": town, "county": county or town,
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prompts": prompts,
        "platforms": platforms_out,
        "platforms_tested": platforms_tested,
        "platforms_mentioned": platforms_mentioned,
        "prompts_total": prompts_total,
        "prompts_mentioned": prompts_mentioned,
        "competitors": competitors,
        "visibility_score": score,
        "cost_usd": round(total_cost, 5),
    }


def save_to_db(result: dict, prospect_ref: str | None,
               html_path: str = "", pdf_path: str = "") -> int | None:
    """Insert the check row and (if a prospect ref given) advance status→checked."""
    prospect_pk = None
    if prospect_ref:
        p = db.get_prospect(prospect_ref)
        prospect_pk = p["pk"] if p else None
    cid = db.insert_check({
        "prospect_id": prospect_pk,
        "run_at": result["run_at"],
        "prompts_json": json.dumps(result["prompts"]),
        "results_json": json.dumps(result["platforms"]),
        "mentioned_count": result["platforms_mentioned"],
        "platforms_tested": result["platforms_tested"],
        "competitors_json": json.dumps(result["competitors"]),
        "visibility_score": result["visibility_score"],
        "report_html_path": html_path,
        "report_pdf_path": pdf_path,
        "cost_usd": result["cost_usd"],
    })
    if prospect_pk and (p := db.get_prospect(prospect_ref)) and p["status"] in ("found", "enriched"):
        db.update_prospect(prospect_ref, {"status": "checked"})
    return cid


def main() -> None:
    ap = argparse.ArgumentParser(description="Free AI Visibility Check (lead magnet)")
    ap.add_argument("--prospect", help="Prospect ref (PRO-001) — pulls company/domain/industry from DB")
    ap.add_argument("--company")
    ap.add_argument("--domain")
    ap.add_argument("--industry")
    ap.add_argument("--location", help="Town")
    ap.add_argument("--county", default="")
    ap.add_argument("--no-report", action="store_true", help="Skip HTML/PDF render")
    ap.add_argument("--output-json", help="Also write raw result JSON here")
    args = ap.parse_args()

    ref = args.prospect
    if ref:
        db.init_db()
        p = db.get_prospect(ref)
        if not p:
            raise SystemExit(f"ERROR: prospect {ref} not found")
        company = args.company or p["company"]
        domain = args.domain or p["domain"]
        industry = args.industry or p.get("industry") or ""
        town = args.location or (p.get("postcode") or "").split()[0] or (p.get("address") or "")
    else:
        if not (args.company and args.domain and args.industry and args.location):
            raise SystemExit("ERROR: pass --prospect OR --company --domain --industry --location")
        company, domain, industry, town = args.company, args.domain, args.industry, args.location

    print(f"[check] {company} ({domain}) — {industry} in {town} ...", file=sys.stderr)
    result = run_check(company, domain, industry, town, args.county)

    # Never ship a report built on nothing. If every engine errored (bad key,
    # no credits, network) platforms_tested is 0 — that is an API failure, NOT a
    # genuine "invisible" result, and a rendered 0/100 report would be a lie.
    # Abort loudly so no fabricated-looking deliverable is produced.
    if result["platforms_tested"] == 0:
        raise SystemExit(
            "ERROR: no live AI responses captured (every engine errored — check "
            "OPENROUTER_API_KEY / credits / network). No report generated. The "
            "check reports only genuine AI answers; it does not fabricate a result.")

    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(json.dumps(result, indent=2), encoding="utf-8")

    html_path = pdf_path = ""
    if not args.no_report:
        import render_check_report
        out_dir = Path(__file__).resolve().parent.parent / "reports" / domain
        paths = render_check_report.render(result, out_dir, pdf=True)
        html_path, pdf_path = paths.get("html", ""), paths.get("pdf", "")

    cid = save_to_db(result, ref, html_path, pdf_path)

    print(f"\nAI Visibility Check — {company}")
    print(f"  Score: {result['visibility_score']}/100")
    print(f"  Mentioned on {result['platforms_mentioned']} of {result['platforms_tested']} platforms")
    for p in result["platforms"]:
        mark = "✓" if p["mentioned"] else "✗"
        print(f"    {mark} {p['platform']}: {p['prompts_mentioned']}/{p['prompts_answered']} prompts")
    if result["competitors"]:
        print("  AI recommended instead: " + ", ".join(f"{c['name']} ({c['mentions']})" for c in result["competitors"]))
    print(f"  Cost: ${result['cost_usd']}   check id: {cid}")
    if html_path:
        print(f"  Report: {html_path}")


# ── Self-check (offline — monkeypatches the network call) ──────────────────

def _demo() -> None:
    import lib.ai_query_core as core
    fake = {
        "Who is the best plumber in Testville?": "The best is **Beta Plumbing** and **Gamma Heating**.",
        "_mention": "Dave Plumbing is a great, trusted local plumber. Also try Beta Plumbing.",
    }

    def fake_full(prompt, api_key, model):
        # ChatGPT model mentions the brand; others recommend competitors only.
        if model == core.CHECK_MODELS["ChatGPT"]:
            return {"text": fake["_mention"], "cost_usd": 0.001, "tokens": 50}
        return {"text": fake["Who is the best plumber in Testville?"], "cost_usd": 0.001, "tokens": 50}

    orig = core.query_openrouter_full
    core.query_openrouter_full = fake_full
    # visibility_check imported the symbol directly — patch there too.
    globals()["query_openrouter_full"] = fake_full
    os.environ["OPENROUTER_API_KEY"] = "test"
    try:
        r = run_check("Dave Plumbing", "daveplumbing.co.uk", "plumber", "Testville")
    finally:
        core.query_openrouter_full = orig
        globals()["query_openrouter_full"] = orig

    assert r["platforms_tested"] == 4, r["platforms_tested"]
    assert r["platforms_mentioned"] == 1, r["platforms_mentioned"]   # only ChatGPT
    # score = (1/4)*70 + (5/20)*30 = 17.5 + 7.5 = 25
    assert r["visibility_score"] == 25, r["visibility_score"]
    names = {c["name"] for c in r["competitors"]}
    assert "Beta Plumbing" in names and "Dave Plumbing" not in names, names
    chatgpt = next(p for p in r["platforms"] if p["platform"] == "ChatGPT")
    assert chatgpt["mentioned"] and chatgpt["snippet"]
    print("visibility_check self-check passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        _demo()
    else:
        main()
