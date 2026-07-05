#!/usr/bin/env python3
"""
GEO SLAB — funnel report (spec §7, `/geo funnel`).

Reads the SQLite pipeline and prints where prospects sit, stage-to-stage
conversion, check economics (spend, avg score, mention rate), and outreach
volume by channel. One glance at whether the machine is actually converting.

    python3 funnel_report.py                # table to stdout
    python3 funnel_report.py --json         # machine-readable
    python3 funnel_report.py --campaign X   # filter to one campaign
    python3 funnel_report.py --self-check

ponytail: status is a single current-state string, so "reached stage N" = count
of prospects whose status sits at or beyond N in STAGE_ORDER. That's the honest
read of a funnel from a state column without an event log — if per-event
timing ever matters, add an events table then; not before.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402

# Pipeline order. Anything past 'checked' is a warm/converting lead; the paid
# tiers are quick_check (£247) and full_audit (£497). do_not_contact is off-funnel.
STAGE_ORDER = [
    "found", "enriched", "checked", "contacted", "replied",
    "walkthrough_booked", "quick_check", "full_audit", "audit_fix", "retainer",
]
STAGE_LABELS = {
    "found": "Discovered", "enriched": "Enriched (CH)", "checked": "Free check run",
    "contacted": "Contacted", "replied": "Replied", "walkthrough_booked": "Walkthrough booked",
    "quick_check": "Quick Check (£247)", "full_audit": "Full Audit (£497)",
    "audit_fix": "Fixes engaged", "retainer": "Retainer",
}
OFF_FUNNEL = {"do_not_contact", "lost", "churned"}


def compute(prospects: list[dict], checks: list[dict], outreach: list[dict]) -> dict:
    rank = {s: i for i, s in enumerate(STAGE_ORDER)}
    total = len(prospects)

    # cumulative "reached at least this stage"
    reached = {s: 0 for s in STAGE_ORDER}
    for p in prospects:
        r = rank.get(p.get("status"))
        if r is None:
            continue  # off-funnel / legacy status
        for s in STAGE_ORDER[: r + 1]:
            reached[s] += 1

    stages = []
    prev = None
    for s in STAGE_ORDER:
        n = reached[s]
        # conversion vs previous stage; first stage is vs total discovered
        base = prev if prev is not None else (reached["found"] or total)
        pct = round(100 * n / base, 1) if base else 0.0
        stages.append({"stage": s, "label": STAGE_LABELS[s], "count": n,
                       "conv_from_prev_pct": pct})
        prev = n

    scores = [c["visibility_score"] for c in checks if c.get("visibility_score") is not None]
    mentioned = [c for c in checks if (c.get("mentioned_count") or 0) > 0]
    check_stats = {
        "runs": len(checks),
        "total_cost_usd": round(sum(c.get("cost_usd") or 0 for c in checks), 4),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "mention_rate_pct": round(100 * len(mentioned) / len(checks), 1) if checks else None,
    }

    by_channel: dict[str, int] = {}
    for o in outreach:
        by_channel[o.get("channel") or "?"] = by_channel.get(o.get("channel") or "?", 0) + 1

    by_source: dict[str, int] = {}
    for p in prospects:
        by_source[p.get("source") or "unknown"] = by_source.get(p.get("source") or "unknown", 0) + 1

    off = sum(1 for p in prospects if p.get("status") in OFF_FUNNEL)

    return {"total_prospects": total, "off_funnel": off, "stages": stages,
            "checks": check_stats, "outreach_by_channel": by_channel,
            "by_source": by_source}


def _load(campaign: str | None) -> dict:
    conn = db.connect()
    try:
        prospects = db.all_prospects(conn)
        if campaign:
            prospects = [p for p in prospects if p.get("campaign") == campaign]
        pks = {p["pk"] for p in prospects}
        checks = [dict(r) for r in conn.execute("SELECT * FROM checks").fetchall()
                  if r["prospect_id"] in pks or not campaign]
        outreach = [dict(r) for r in conn.execute("SELECT * FROM outreach").fetchall()
                    if r["prospect_id"] in pks or not campaign]
    finally:
        conn.close()
    return compute(prospects, checks, outreach)


def render_table(rep: dict) -> str:
    L = []
    L.append(f"FUNNEL — {rep['total_prospects']} prospects"
             + (f"  ({rep['off_funnel']} off-funnel)" if rep["off_funnel"] else ""))
    L.append("-" * 52)
    for s in rep["stages"]:
        bar = "█" * min(30, s["count"])
        L.append(f"{s['label']:<22} {s['count']:>4}  {s['conv_from_prev_pct']:>5}%  {bar}")
    c = rep["checks"]
    L.append("-" * 52)
    L.append(f"Checks: {c['runs']} runs  ·  ${c['total_cost_usd']} spent  "
             f"·  avg {c['avg_score']}/100  ·  mention rate {c['mention_rate_pct']}%")
    if rep["outreach_by_channel"]:
        L.append("Outreach: " + ", ".join(f"{k} {v}" for k, v in rep["outreach_by_channel"].items()))
    if rep["by_source"]:
        L.append("Source: " + ", ".join(f"{k} {v}" for k, v in rep["by_source"].items()))
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description="Prospecting funnel report")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--campaign")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        _demo()
        return
    db.init_db()
    rep = _load(args.campaign)
    print(json.dumps(rep, indent=2) if args.json else render_table(rep))


def _demo() -> None:
    prospects = [
        {"pk": 1, "status": "retainer", "source": "inbound", "campaign": "a"},
        {"pk": 2, "status": "checked", "source": "places", "campaign": "a"},
        {"pk": 3, "status": "checked", "source": "places", "campaign": "a"},
        {"pk": 4, "status": "found", "source": "places", "campaign": "a"},
        {"pk": 5, "status": "do_not_contact", "source": "places", "campaign": "a"},
    ]
    checks = [
        {"prospect_id": 2, "visibility_score": 20, "mentioned_count": 0, "cost_usd": 0.04},
        {"prospect_id": 3, "visibility_score": 60, "mentioned_count": 2, "cost_usd": 0.05},
    ]
    outreach = [{"prospect_id": 1, "channel": "email"}, {"prospect_id": 1, "channel": "letter"}]
    r = compute(prospects, checks, outreach)

    st = {s["stage"]: s for s in r["stages"]}
    # retainer prospect counts toward every earlier stage; 2 checked + 1 retainer = 3 reached 'checked'
    assert st["found"]["count"] == 4, st["found"]        # all funnel prospects (excl do_not_contact)
    assert st["checked"]["count"] == 3, st["checked"]    # 2 checked + 1 retainer
    assert st["retainer"]["count"] == 1, st["retainer"]
    assert r["off_funnel"] == 1                          # do_not_contact
    assert r["checks"]["runs"] == 2
    assert r["checks"]["total_cost_usd"] == 0.09
    assert r["checks"]["avg_score"] == 40.0
    assert r["checks"]["mention_rate_pct"] == 50.0       # 1 of 2 mentioned
    assert r["outreach_by_channel"] == {"email": 1, "letter": 1}
    assert r["by_source"]["places"] == 4
    # conversion: checked(3) from enriched(1)? enriched only counts those at>=enriched:
    # found=4, enriched=1 (only retainer passed through enriched rank), checked=3 ...
    # first stage conv vs discovered(4) -> 100%
    assert st["found"]["conv_from_prev_pct"] == 100.0
    assert render_table(r).startswith("FUNNEL — 5 prospects")
    print("funnel_report self-check passed")


if __name__ == "__main__":
    main()
