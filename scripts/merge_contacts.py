#!/usr/bin/env python3
"""
Merge per-contact contacts.csv with per-firm scored.csv (audit signals) and
outreach.csv (drafted email/LinkedIn/voice copy). Produces enriched_contacts.csv
with one row per decision-maker, carrying the firm's audit + outreach context.

Used by the linkedin-toolkit chrome extension to show scan results and
copy-to-clipboard outreach copy per prospect card.

Usage:
    python3 merge_contacts.py \
        --contacts prospects/<run>/contacts.csv \
        --scored   prospects/<run>/scored.csv \
        --outreach prospects/<run>/outreach.csv \
        --output   prospects/<run>/enriched_contacts.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


SCORED_PASSTHROUGH = [
    "business_name", "geo_score", "citability_score",
    "has_llmstxt", "has_schema", "is_https", "blocks_ai_crawlers",
    "best_position", "avg_position", "keywords",
    "top_gap_1", "top_gap_2", "top_gap_3",
    "pitchability_score", "recommended_tier",
]

OUTREACH_PASSTHROUGH = [
    "email_subject", "email_body", "linkedin_dm", "voice_opener",
    "top_gap",
]


def index_by_domain(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open() as f:
        return {r["domain"]: r for r in csv.DictReader(f) if r.get("domain")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--contacts", required=True)
    ap.add_argument("--scored", required=True)
    ap.add_argument("--outreach", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    contacts_path = Path(args.contacts)
    scored = index_by_domain(Path(args.scored))
    outreach = index_by_domain(Path(args.outreach))

    if not contacts_path.exists():
        print(f"ERROR: contacts file not found: {contacts_path}", file=sys.stderr)
        sys.exit(1)

    with contacts_path.open() as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("no rows in contacts.csv", file=sys.stderr)
        sys.exit(0)

    contact_cols = list(rows[0].keys())
    add_scored = [c for c in SCORED_PASSTHROUGH if c not in contact_cols]
    add_outreach = [c for c in OUTREACH_PASSTHROUGH if c not in contact_cols and c not in add_scored]
    fieldnames = contact_cols + add_scored + add_outreach

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            d = row.get("domain", "")
            sc = scored.get(d, {})
            ot = outreach.get(d, {})
            for col in add_scored:
                row[col] = sc.get(col, "")
            for col in add_outreach:
                row[col] = ot.get(col, "")
            # Fill business_name from scored.csv if blank in contacts
            if not row.get("business_name"):
                row["business_name"] = sc.get("business_name") or ot.get("business_name") or ""
            w.writerow(row)

    print(f"✓ wrote {len(rows)} enriched rows → {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
