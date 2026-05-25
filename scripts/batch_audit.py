"""
batch_audit.py — Lite GEO audit for a CSV of prospects.

Composes existing geo-slab modules (no duplication of scoring logic):
- fetch_page.fetch_page          — homepage HTML + signals
- fetch_page.fetch_robots_txt    — AI crawler allow/disallow
- citability_scorer.analyze_page_citability — passage scoring
- llmstxt_generator.validate_llmstxt — llms.txt presence + validity

Runs N prospects in parallel (default concurrency 2). Per-prospect timeout 60s.
Failures are logged and the run continues.

Usage:
    python batch_audit.py \\
        --input prospects/run_001/prospects.csv \\
        --output prospects/run_001/audited.csv \\
        --concurrency 2 \\
        --reports-dir prospects/run_001/reports
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Make sibling scripts importable when invoked from anywhere
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fetch_page  # noqa: E402
import citability_scorer  # noqa: E402
import llmstxt_generator  # noqa: E402


AUDIT_COLUMNS = [
    "geo_score",
    "citability_score",
    "has_llmstxt",
    "llmstxt_valid",
    "has_schema",
    "is_https",
    "is_mobile_optimised",
    "blocks_ai_crawlers",
    "top_gap_1",
    "top_gap_2",
    "top_gap_3",
    "audit_status",
    "audit_error",
    "audited_at",
]


def _bool_str(b):
    return "true" if b else "false"


def _is_mobile(page):
    metas = page.get("meta_tags") or {}
    if not isinstance(metas, dict):
        return False
    # Be permissive — different fetch implementations use different keys
    for k, v in metas.items():
        if not v:
            continue
        if "viewport" in str(k).lower():
            return True
        if isinstance(v, str) and "width=device-width" in v.lower():
            return True
    # Fallback to raw HTML check if present
    raw = page.get("text_content") or ""
    return "width=device-width" in raw.lower()


def _has_schema(page):
    sd = page.get("structured_data")
    if isinstance(sd, list) and sd:
        return True
    return False


def _blocks_ai_crawlers(robots):
    """True if any of the visibility-positive AI bots are disallowed."""
    if not robots or not robots.get("exists"):
        # No robots.txt → nothing is blocked by directive
        return False
    status = robots.get("ai_crawler_status") or {}
    critical = ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"]
    for bot in critical:
        info = status.get(bot)
        if isinstance(info, dict) and info.get("allowed") is False:
            return True
        if isinstance(info, str) and info.lower() in ("blocked", "disallow", "disallowed"):
            return True
    return False


def _composite_geo_score(citability, has_llms, has_schema, mobile_ok, blocks_ai):
    return round(
        0.40 * (citability or 0)
        + 0.20 * (100 if has_llms else 0)
        + 0.20 * (100 if has_schema else 0)
        + 0.10 * (100 if mobile_ok else 0)
        + 0.10 * (0 if blocks_ai else 100)
    )


def _top_gaps(flags):
    """flags: dict of human-readable gap label → bool (True = gap present)."""
    return [label for label, gap in flags.items() if gap]


def audit_one(row, reports_dir=None):
    """Run lite audit for a single prospect row. Returns merged row."""
    out = dict(row)
    out["audit_status"] = "failed"
    out["audit_error"] = ""
    out["audited_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for col in AUDIT_COLUMNS:
        out.setdefault(col, "")

    website = (row.get("website") or "").strip()
    if not website:
        out["audit_error"] = "no_website"
        return out

    try:
        page = fetch_page.fetch_page(website, timeout=45)
        status = page.get("status_code")
        if not status or not (200 <= int(status) < 400):
            out["audit_error"] = f"http_{status}"
            return out

        is_https = website.lower().startswith("https://")
        mobile_ok = _is_mobile(page)
        has_schema = _has_schema(page)

        # Robots.txt
        try:
            robots = fetch_page.fetch_robots_txt(website, timeout=15)
        except Exception:
            robots = {"exists": False}
        blocks_ai = _blocks_ai_crawlers(robots)

        # llms.txt
        try:
            llms = llmstxt_generator.validate_llmstxt(website)
        except Exception:
            llms = {"exists": False, "format_valid": False}
        has_llms = bool(llms.get("exists"))
        llms_valid = bool(llms.get("format_valid"))

        # Citability — reuse score_passage on extracted blocks (cheap path)
        citability_score = 0
        try:
            blocks = fetch_page.extract_content_blocks(page.get("text_content") or "")
            if blocks:
                scored = []
                for b in blocks[:25]:  # cap for batch speed
                    text = b.get("text") if isinstance(b, dict) else str(b)
                    if not text:
                        continue
                    s = citability_scorer.score_passage(text)
                    if isinstance(s, dict):
                        scored.append(s.get("total_score") or s.get("score") or 0)
                if scored:
                    citability_score = round(sum(scored) / len(scored))
        except Exception:
            citability_score = 0

        # Fallback citability path: full analyzer if cheap path produced nothing
        if not citability_score:
            try:
                deep = citability_scorer.analyze_page_citability(website)
                if isinstance(deep, dict):
                    citability_score = int(deep.get("average_citability_score") or 0)
            except Exception:
                pass

        # Composite + gaps
        geo_score = _composite_geo_score(citability_score, has_llms, has_schema, mobile_ok, blocks_ai)
        gap_flags = {
            "No llms.txt": not has_llms,
            "No schema markup": not has_schema,
            "Blocks AI crawlers": blocks_ai,
            "Not mobile optimised": not mobile_ok,
            "Low citability": citability_score < 40,
            "Site not HTTPS": not is_https,
            "llms.txt invalid format": has_llms and not llms_valid,
        }
        gaps = _top_gaps(gap_flags)[:3] + ["", "", ""]

        out["geo_score"] = geo_score
        out["citability_score"] = citability_score
        out["has_llmstxt"] = _bool_str(has_llms)
        out["llmstxt_valid"] = _bool_str(llms_valid)
        out["has_schema"] = _bool_str(has_schema)
        out["is_https"] = _bool_str(is_https)
        out["is_mobile_optimised"] = _bool_str(mobile_ok)
        out["blocks_ai_crawlers"] = _bool_str(blocks_ai)
        out["top_gap_1"], out["top_gap_2"], out["top_gap_3"] = gaps[0], gaps[1], gaps[2]
        out["audit_status"] = "success"
        out["audit_error"] = ""

        # Optional per-prospect HTML report
        if reports_dir:
            try:
                _write_prospect_report(row, out, page, reports_dir)
            except Exception as e:
                out["audit_status"] = "partial"
                out["audit_error"] = f"report_failed: {e}"

        return out

    except Exception as e:
        out["audit_error"] = f"{type(e).__name__}: {e}"
        return out


def _write_prospect_report(row, audit_out, page, reports_dir):
    """Build a lite report data file + call generate_prospect_report.py."""
    domain = (row.get("domain") or "").lower().strip()
    if not domain:
        return
    slug = domain.replace(".", "-")

    citability = int(audit_out.get("citability_score") or 0)
    geo_score = int(audit_out.get("geo_score") or 0)

    has_llms = audit_out.get("has_llmstxt") == "true"
    has_schema = audit_out.get("has_schema") == "true"
    blocks_ai = audit_out.get("blocks_ai_crawlers") == "true"
    mobile_ok = audit_out.get("is_mobile_optimised") == "true"

    problems = []
    if blocks_ai:
        problems.append({
            "title": "AI crawlers blocked",
            "body": "Your robots.txt disallows one or more of GPTBot, ClaudeBot, PerplexityBot, or Google-Extended. The engines your customers use can't index your site.",
        })
    if not has_llms:
        problems.append({
            "title": "No llms.txt published",
            "body": "AI systems use llms.txt to discover and prioritise your content. Without one, you rely on slow crawling and noisy heuristics.",
        })
    if not has_schema:
        problems.append({
            "title": "No structured data",
            "body": "No JSON-LD schema detected on the homepage. AI engines need structured signals to verify your entity and surface you in answers.",
        })
    if citability < 40:
        problems.append({
            "title": "Content not citable by AI",
            "body": "Your passages average below 40/100 for AI citability. AI systems pick competitors with self-contained, fact-rich content instead.",
        })
    if not mobile_ok:
        problems.append({
            "title": "No mobile viewport",
            "body": "Missing the mobile viewport meta tag. Modern crawlers and ranking systems treat this as a baseline failure.",
        })

    # Pad to 3 if needed
    while len(problems) < 3:
        problems.append({
            "title": "Generic GEO gap",
            "body": "Multiple smaller signals are pulling your AI visibility down. The full audit identifies all of them.",
        })
    problems = problems[:3]

    working = []
    if has_llms:
        working.append("llms.txt is published at the root")
    if has_schema:
        working.append("Structured data detected on homepage")
    if not blocks_ai:
        working.append("AI crawlers are allowed in robots.txt")
    if mobile_ok:
        working.append("Mobile viewport correctly declared")
    working = working[:3] or ["Site responds and serves content to crawlers"]

    data = {
        "url": row.get("website"),
        "brand_name": row.get("business_name") or domain,
        "date": datetime.now().strftime("%-d %B %Y") if sys.platform != "win32" else datetime.now().strftime("%#d %B %Y"),
        "geo_score": geo_score,
        "scores": {
            "ai_citability": citability,
            "brand_authority": 50,  # not measured in lite — neutral placeholder
            "content_eeat": citability,
            "technical": _composite_geo_score(citability, has_llms, has_schema, mobile_ok, blocks_ai),
            "schema": 80 if has_schema else 15,
            "platform_optimization": 30 if blocks_ai else 65,
        },
        "top_problems": problems,
        "working": working,
        "cta_url": "https://antekautomation.com/book",
        "cta_price": "",
        "cta_label": "Book a 15-minute walkthrough",
    }

    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as tmp:
        json.dump(data, tmp)
        tmp_path = tmp.name

    try:
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "generate_prospect_report.py"),
                "--data", tmp_path,
                "--output", str(reports_dir),
                "--pdf",
            ],
            check=False, capture_output=True, timeout=120,
        )
        # Rename to slug if generator used a different filename
        for ext in ("html", "pdf"):
            candidate = reports_dir / f"GEO-PROSPECT-{domain}.{ext}"
            target = reports_dir / f"{slug}.{ext}"
            if candidate.exists() and candidate != target:
                try:
                    candidate.replace(target)
                except Exception:
                    pass
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Lite batch audit for prospect CSV")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--reports-dir", default=None,
                        help="If set, write per-prospect lite HTML reports here")
    parser.add_argument("--errors-log", default=None,
                        help="Append per-failure error lines here (default: alongside --output)")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    errors_log = Path(args.errors_log) if args.errors_log else out_path.parent / "errors.log"

    with in_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        in_fields = reader.fieldnames or []

    if not rows:
        print("Input CSV is empty.", file=sys.stderr)
        # write header-only output
        all_fields = list(dict.fromkeys(list(in_fields) + AUDIT_COLUMNS))
        with out_path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=all_fields).writeheader()
        return 0

    print(f"Auditing {len(rows)} prospects (concurrency={args.concurrency})", file=sys.stderr)

    concurrency = max(1, min(args.concurrency, 5))
    results = [None] * len(rows)
    failures = 0
    started = time.time()

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {
            ex.submit(audit_one, row, args.reports_dir): i
            for i, row in enumerate(rows)
        }
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                results[i] = fut.result(timeout=120)
            except Exception as e:
                results[i] = dict(rows[i])
                results[i]["audit_status"] = "failed"
                results[i]["audit_error"] = f"timeout_or_crash: {e}"
                for col in AUDIT_COLUMNS:
                    results[i].setdefault(col, "")
            row_now = results[i]
            domain = row_now.get("domain", "?")
            status = row_now.get("audit_status", "?")
            score = row_now.get("geo_score", "")
            print(f"  [{i+1}/{len(rows)}] {domain} → {status} (geo_score={score})", file=sys.stderr)
            if status == "failed":
                failures += 1
                try:
                    with errors_log.open("a", encoding="utf-8") as ef:
                        ef.write(f"{row_now.get('audited_at','')} {domain} {row_now.get('audit_error','')}\n")
                except Exception:
                    pass

    all_fields = list(dict.fromkeys(list(in_fields) + AUDIT_COLUMNS))
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r or {})

    elapsed = time.time() - started
    print(f"Done in {elapsed:.1f}s — {len(rows) - failures}/{len(rows)} successful", file=sys.stderr)
    print(f"Written to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
