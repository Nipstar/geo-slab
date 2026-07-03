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


def build_prompts(industry: str, town: str, county: str = "") -> list[str]:
    """The 5 frozen discovery prompts (spec §7)."""
    county = county or town
    return [
        f"Who is the best {industry} in {town}?",
        f"Recommend a {industry} near {town}",
        f"I need a {industry} in {county}, who should I call?",
        f"{industry} {town} reviews — who do you recommend?",
        f"Compare {industry}s in {town}",
    ]


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
                responses.append({"prompt": prompt, "answered": False, "mentioned": False, "snippet": ""})
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
            responses.append({"prompt": prompt, "answered": True,
                              "mentioned": det["mentioned"], "snippet": snippet})
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
