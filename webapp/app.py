#!/usr/bin/env python3
"""
GEO SLAB Dashboard — Flask + HTMX prospect CRM.

Run:
    pip install -r requirements-webapp.txt
    python app.py
    # → http://localhost:5050

Persistence:    ~/.geo-slab/prospects.json
Artifact root:  <repo>/reports/<domain>/   (auto-discovered, read-only)

Ported and extended from https://github.com/Nipstar/geo-seo-claude
under the GEO SLAB by Antek Automation rebrand.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import markdown as md_lib
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

# ── Paths ──────────────────────────────────────────────────────────────

WEBAPP_DIR = Path(__file__).resolve().parent
REPO_ROOT = WEBAPP_DIR.parent
REPORTS_ROOT = REPO_ROOT / "reports"

DATA_DIR = Path.home() / ".geo-slab"
CRM_PATH = DATA_DIR / "prospects.json"


# ── App init ───────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get("GEO_SLAB_SECRET", "geo-slab-dev-secret")


@app.context_processor
def inject_globals():
    return {
        "now": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "brand_name": "GEO SLAB",
        "brand_owner": "Antek Automation",
        "brand_owner_url": "https://antekautomation.com",
    }


# ── Status meta ────────────────────────────────────────────────────────

STATUS_META: dict[str, dict[str, str]] = {
    "lead":     {"icon": "○", "label": "Lead",     "tier": "moderate"},
    "audit":    {"icon": "◔", "label": "Audit",    "tier": "moderate"},
    "proposal": {"icon": "◑", "label": "Proposal", "tier": "good"},
    "active":   {"icon": "●", "label": "Active",   "tier": "good"},
    "churned":  {"icon": "✕", "label": "Churned",  "tier": "critical"},
    "lost":     {"icon": "—", "label": "Lost",     "tier": "poor"},
}


# ── Helpers ────────────────────────────────────────────────────────────

def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_prospects() -> list[dict]:
    if not CRM_PATH.exists():
        return []
    with open(CRM_PATH) as f:
        return json.load(f)


def save_prospects(prospects: list[dict]) -> None:
    ensure_data_dir()
    with open(CRM_PATH, "w") as f:
        json.dump(prospects, f, indent=2, ensure_ascii=False)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def next_prospect_id(prospects: list[dict]) -> str:
    nums: list[int] = []
    for p in prospects:
        m = re.match(r"PRO-(\d+)$", p.get("id", ""))
        if m:
            nums.append(int(m.group(1)))
    return f"PRO-{(max(nums) + 1) if nums else 1:03d}"


def find_prospect(prospects: list[dict], pid: str) -> Optional[dict]:
    return next((p for p in prospects if p.get("id") == pid), None)


def score_tier(score) -> str:
    try:
        s = int(score or 0)
    except (TypeError, ValueError):
        s = 0
    if s >= 80:
        return "good"
    if s >= 60:
        return "moderate"
    if s >= 40:
        return "poor"
    return "critical"


def score_label(score) -> str:
    return {"good": "Good", "moderate": "Moderate", "poor": "Poor", "critical": "Critical"}[score_tier(score)]


def format_gbp(value) -> str:
    if not value:
        return "—"
    try:
        return f"£{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def crm_stats(prospects: list[dict]) -> dict:
    total = len(prospects)
    active = [p for p in prospects if p.get("status") == "active"]
    proposals = [p for p in prospects if p.get("status") == "proposal"]
    mrr = sum(p.get("monthly_value") or 0 for p in active)
    pipeline = sum(p.get("monthly_value") or 0 for p in proposals)
    avg_score = round(sum(p.get("geo_score") or 0 for p in prospects) / total) if total else 0
    return {
        "total": total,
        "active": len(active),
        "mrr": format_gbp(mrr),
        "pipeline": format_gbp(pipeline),
        "avg_score": avg_score,
        "avg_tier": score_tier(avg_score),
    }


def find_artefacts(domain: str) -> dict:
    """Auto-discover artifacts in reports/<domain>/. Returns absolute paths or None."""
    out: dict[str, Optional[Path]] = {
        "audit_json": None,
        "report_html": None,
        "report_pdf": None,
        "proposal_md": None,
        "audit_md": None,
        "live_visibility_json": None,
    }
    if not domain:
        return out
    domain_dir = REPORTS_ROOT / domain
    if not domain_dir.is_dir():
        return out

    audit_json = domain_dir / "audit-data.json"
    if audit_json.exists():
        out["audit_json"] = audit_json

    audit_md = domain_dir / "GEO-AUDIT-REPORT.md"
    if audit_md.exists():
        out["audit_md"] = audit_md

    live = domain_dir / "live-visibility.json"
    if live.exists():
        out["live_visibility_json"] = live

    html_match = sorted(domain_dir.glob("GEO-REPORT-*.html"), reverse=True)
    if html_match:
        out["report_html"] = html_match[0]

    pdf_match = sorted(domain_dir.glob("GEO-REPORT-*.pdf"), reverse=True)
    if pdf_match:
        out["report_pdf"] = pdf_match[0]

    proposal_match = sorted(domain_dir.glob("GEO-PROPOSAL-*.md"), reverse=True)
    if proposal_match:
        out["proposal_md"] = proposal_match[0]

    return out


# ── Jinja filters ──────────────────────────────────────────────────────

app.jinja_env.filters["score_tier"] = score_tier
app.jinja_env.filters["score_label"] = score_label
app.jinja_env.filters["format_gbp"] = format_gbp


@app.template_filter("status_meta")
def status_meta_filter(status: str) -> dict:
    return STATUS_META.get(status, {"icon": "?", "label": status or "Unknown", "tier": "poor"})


# ── Form helpers ───────────────────────────────────────────────────────

def _read_form(p: Optional[dict] = None) -> dict:
    """Build a prospect dict from POST form data, preserving existing fields."""
    p = dict(p or {})

    def field(name: str, default: str = "") -> str:
        return request.form.get(name, default).strip()

    p["company"] = field("company")
    raw_domain = field("domain").lower().rstrip("/")
    for prefix in ("https://", "http://"):
        if raw_domain.startswith(prefix):
            raw_domain = raw_domain[len(prefix):]
    if raw_domain.startswith("www."):
        raw_domain = raw_domain[4:]
    p["domain"] = raw_domain
    p["contact_name"] = field("contact_name")
    p["contact_email"] = field("contact_email")
    p["industry"] = field("industry")
    p["country"] = field("country")
    p["status"] = field("status", "lead")

    score_raw = field("geo_score", "0")
    try:
        p["geo_score"] = max(0, min(100, int(score_raw)))
    except ValueError:
        p["geo_score"] = 0

    mrr_raw = field("monthly_value", "0")
    try:
        p["monthly_value"] = max(0, int(mrr_raw))
    except ValueError:
        p["monthly_value"] = 0

    months_raw = field("contract_months", "12")
    try:
        p["contract_months"] = max(1, int(months_raw))
    except ValueError:
        p["contract_months"] = 12

    p["audit_date"] = field("audit_date") or None
    p["contract_start"] = field("contract_start") or None
    p["audit_file"] = field("audit_file")
    p["report_html"] = field("report_html")
    p["proposal_file"] = field("proposal_file")
    p.setdefault("notes", [])
    return p


# ── Routes: dashboard & CRUD ───────────────────────────────────────────

@app.route("/")
def dashboard():
    prospects = load_prospects()
    status_filter = request.args.get("status", "")
    sort = request.args.get("sort", "score")

    filtered = [p for p in prospects if not status_filter or p.get("status") == status_filter]

    if sort == "score":
        filtered.sort(key=lambda x: x.get("geo_score") or 0)
    elif sort == "company":
        filtered.sort(key=lambda x: (x.get("company") or "").lower())
    elif sort == "mrr":
        filtered.sort(key=lambda x: x.get("monthly_value") or 0, reverse=True)
    elif sort == "updated":
        filtered.sort(key=lambda x: x.get("updated_at") or "", reverse=True)

    return render_template(
        "dashboard.html",
        prospects=filtered,
        stats=crm_stats(prospects),
        status_filter=status_filter,
        sort=sort,
        statuses=list(STATUS_META.keys()),
        STATUS_META=STATUS_META,
    )


@app.route("/prospect/new", methods=["GET", "POST"])
def prospect_new():
    if request.method == "POST":
        prospects = load_prospects()
        new = _read_form()
        new["id"] = next_prospect_id(prospects)
        new["created_at"] = now_iso()
        new["updated_at"] = now_iso()
        if not new["company"] or not new["domain"]:
            flash("Company and domain are required.", "error")
            return render_template("prospect_form.html", p=new, statuses=list(STATUS_META.keys()), mode="new")
        prospects.append(new)
        save_prospects(prospects)
        return redirect(url_for("prospect_detail", pid=new["id"]))
    return render_template("prospect_form.html", p={"status": "lead", "contract_months": 12}, statuses=list(STATUS_META.keys()), mode="new")


@app.route("/prospect/<pid>")
def prospect_detail(pid: str):
    prospects = load_prospects()
    p = find_prospect(prospects, pid)
    if not p:
        abort(404)
    artefacts = find_artefacts(p.get("domain", ""))
    return render_template(
        "prospect.html",
        p=p,
        artefacts=artefacts,
        statuses=list(STATUS_META.keys()),
        STATUS_META=STATUS_META,
    )


@app.route("/prospect/<pid>/edit", methods=["GET", "POST"])
def prospect_edit(pid: str):
    prospects = load_prospects()
    p = find_prospect(prospects, pid)
    if not p:
        abort(404)
    if request.method == "POST":
        updated = _read_form(p)
        updated["id"] = p["id"]
        updated["created_at"] = p.get("created_at") or now_iso()
        updated["notes"] = p.get("notes", [])
        updated["updated_at"] = now_iso()
        idx = prospects.index(p)
        prospects[idx] = updated
        save_prospects(prospects)
        return redirect(url_for("prospect_detail", pid=pid))
    return render_template("prospect_form.html", p=p, statuses=list(STATUS_META.keys()), mode="edit")


@app.route("/prospect/<pid>/delete", methods=["POST"])
def prospect_delete(pid: str):
    prospects = load_prospects()
    p = find_prospect(prospects, pid)
    if not p:
        abort(404)
    prospects = [x for x in prospects if x.get("id") != pid]
    save_prospects(prospects)
    return redirect(url_for("dashboard"))


# ── Routes: HTMX fragments ─────────────────────────────────────────────

@app.route("/prospect/<pid>/note", methods=["POST"])
def add_note(pid: str):
    prospects = load_prospects()
    p = find_prospect(prospects, pid)
    if not p:
        abort(404)
    text = request.form.get("text", "").strip()
    if text:
        p.setdefault("notes", []).append({"date": now_iso(), "text": text})
        p["updated_at"] = now_iso()
        save_prospects(prospects)
    return render_template("_notes.html", p=p)


@app.route("/prospect/<pid>/status", methods=["POST"])
def update_status(pid: str):
    prospects = load_prospects()
    p = find_prospect(prospects, pid)
    if not p:
        abort(404)
    new_status = request.form.get("status", "").strip()
    if new_status in STATUS_META:
        p["status"] = new_status
        p["updated_at"] = now_iso()
        save_prospects(prospects)
    meta = STATUS_META.get(p["status"], {})
    return f'<span class="badge badge-status tier-{meta.get("tier","poor")}">{meta.get("icon","?")} {meta.get("label","")}</span>'


# ── Routes: artifact viewers ───────────────────────────────────────────

@app.route("/prospect/<pid>/audit")
def view_audit(pid: str):
    prospects = load_prospects()
    p = find_prospect(prospects, pid)
    if not p:
        abort(404)
    artefacts = find_artefacts(p.get("domain", ""))
    audit_path = artefacts.get("audit_json")
    if not audit_path:
        flash("No audit-data.json found for this domain in reports/.", "error")
        return redirect(url_for("prospect_detail", pid=pid))
    with open(audit_path) as f:
        audit = json.load(f)
    return render_template("audit_viewer.html", p=p, audit=audit, audit_path=str(audit_path))


@app.route("/prospect/<pid>/report")
def view_report(pid: str):
    prospects = load_prospects()
    p = find_prospect(prospects, pid)
    if not p:
        abort(404)
    artefacts = find_artefacts(p.get("domain", ""))
    html_path = artefacts.get("report_html")
    if not html_path:
        flash("No GEO-REPORT-<domain>.html found in reports/.", "error")
        return redirect(url_for("prospect_detail", pid=pid))
    return send_file(html_path, mimetype="text/html")


@app.route("/prospect/<pid>/pdf")
def download_pdf(pid: str):
    prospects = load_prospects()
    p = find_prospect(prospects, pid)
    if not p:
        abort(404)
    artefacts = find_artefacts(p.get("domain", ""))
    pdf_path = artefacts.get("report_pdf")
    if not pdf_path:
        abort(404)
    return send_file(pdf_path, as_attachment=True, download_name=pdf_path.name, mimetype="application/pdf")


@app.route("/prospect/<pid>/proposal")
def view_proposal(pid: str):
    prospects = load_prospects()
    p = find_prospect(prospects, pid)
    if not p:
        abort(404)
    artefacts = find_artefacts(p.get("domain", ""))
    proposal_path = artefacts.get("proposal_md")
    if not proposal_path:
        flash("No GEO-PROPOSAL-<domain>.md found in reports/.", "error")
        return redirect(url_for("prospect_detail", pid=pid))
    raw = proposal_path.read_text(encoding="utf-8")
    body = md_lib.markdown(raw, extensions=["tables", "fenced_code"])
    return render_template("proposal_viewer.html", p=p, body=body, proposal_path=str(proposal_path))


# ── Run ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host="127.0.0.1", port=5050)
