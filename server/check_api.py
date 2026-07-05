#!/usr/bin/env python3
"""
GEO SLAB — inbound free-check API (spec §6).

Thin Flask wrapper around visibility_check.run_check so a landing-page form (via
n8n or a direct POST) can trigger the free AI Visibility Check, get a score +
report back, persist the lead, and hand it to Brevo for the follow-up sequence.

Endpoints:
  GET  /health   -> {"ok": true}
  POST /check    -> run a check (Bearer token required)

Auth: `Authorization: Bearer <CHECK_API_TOKEN>`. If CHECK_API_TOKEN is unset the
API fails CLOSED (503) — it never runs open, since each check costs OpenRouter
credits. Compared with hmac.compare_digest (constant time).

POST /check body (JSON):
  { "company": "...", "domain": "...", "industry": "...", "town": "...",
    "county": "?", "email": "?", "name": "?", "campaign": "?" }
company, domain, industry, town required. email (if given) enrols the lead in
Brevo — unless suppressed.

Scope is the same FROZEN free check (mention detection + competitors + score).
No citability/technical/schema — those stay paid.

Run locally:  CHECK_API_TOKEN=dev python3 server/check_api.py
Production:   gunicorn -w 2 -b 0.0.0.0:8000 check_api:app   (see Dockerfile)
"""
from __future__ import annotations

import hmac
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request

# scripts/ holds the check engine + db layer; server/ imports from it
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # local brevo

import db  # noqa: E402
import render_check_report  # noqa: E402
import visibility_check  # noqa: E402
from lib.ai_query_core import load_env  # noqa: E402
import brevo  # noqa: E402

load_env()
app = Flask(__name__)

REQUIRED = ("company", "domain", "industry", "town")


def _normalise_domain(raw: str) -> str:
    d = (raw or "").strip().lower()
    d = d.replace("https://", "").replace("http://", "").replace("www.", "")
    return d.rstrip("/").split("/")[0]


def _report_url(domain: str, html_path: str) -> str:
    """Public URL for the report if REPORT_BASE is set, else the local path.
    REPORT_BASE should serve the repo `reports/` dir (e.g. via nginx/CDN)."""
    base = os.environ.get("REPORT_BASE", "").rstrip("/")
    if base and html_path:
        return f"{base}/{domain}/{Path(html_path).name}"
    return html_path


def _authorised(req) -> bool:
    token = os.environ.get("CHECK_API_TOKEN")
    if not token:
        return False  # fail closed
    header = req.headers.get("Authorization", "")
    prefix = "Bearer "
    if not header.startswith(prefix):
        return False
    return hmac.compare_digest(header[len(prefix):], token)


def _upsert_prospect(company: str, domain: str, industry: str, campaign: str) -> dict:
    """Find an existing prospect by domain or create one (source=inbound)."""
    for p in db.all_prospects():
        if _normalise_domain(p.get("domain") or "") == domain and domain:
            return p
    return db.insert_prospect({
        "company": company, "domain": domain, "industry": industry,
        "source": "inbound", "campaign": campaign or "inbound-check",
        "status": "found",
    })


@app.get("/health")
def health():
    return jsonify(ok=True)


@app.post("/check")
def check():
    if not os.environ.get("CHECK_API_TOKEN"):
        return jsonify(error="CHECK_API_TOKEN not configured"), 503
    if not _authorised(request):
        return jsonify(error="unauthorised"), 401
    if not os.environ.get("OPENROUTER_API_KEY"):
        return jsonify(error="OPENROUTER_API_KEY not configured"), 503

    data = request.get_json(silent=True) or {}
    missing = [k for k in REQUIRED if not data.get(k)]
    if missing:
        return jsonify(error=f"missing fields: {', '.join(missing)}"), 400

    company = data["company"].strip()
    domain = _normalise_domain(data["domain"])
    industry = data["industry"].strip()
    town = data["town"].strip()
    county = (data.get("county") or "").strip()

    result = visibility_check.run_check(company, domain, industry, town, county)

    # HTML only — no headless Chrome in the API container. PDF is generated
    # later by the sales flow (`/geo check`) if the lead converts.
    out_dir = REPO / "reports" / domain
    paths = render_check_report.render(result, out_dir, pdf=False)
    report_url = _report_url(domain, paths.get("html", ""))
    prospect = _upsert_prospect(company, domain, industry, data.get("campaign", ""))
    visibility_check.save_to_db(result, prospect["id"], paths.get("html", ""), "")

    # enrol the lead unless suppressed (they asked, but respect opt-outs)
    email = (data.get("email") or "").strip()
    enrolled = False
    if email and not db.is_suppressed(domain=domain, email=email, company=company):
        enrolled = brevo.enrol_lead(email, data.get("name", ""),
                                    result["visibility_score"], report_url,
                                    company=company)

    return jsonify(
        ok=True,
        ref=prospect["id"],
        company=company,
        score=result["visibility_score"],
        platforms_tested=result["platforms_tested"],
        platforms_mentioned=result["platforms_mentioned"],
        competitors=[c["name"] for c in result["competitors"]],
        report_url=report_url,
        enrolled=enrolled,
    )


if __name__ == "__main__":
    db.init_db()
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
