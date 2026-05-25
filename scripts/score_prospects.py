"""
score_prospects.py — Pitchability scoring for audited prospects.

Reads audited.csv (output of batch_audit.py), adds pitchability columns,
writes scored.csv sorted by pitchability descending.

Formula:
    pitchability = 0.40 * geo_gap
                 + 0.25 * opportunity_score   (carried from discovery)
                 + 0.20 * business_signal
                 + 0.15 * contactability

    geo_gap         = min(100 - geo_score, 80)
    business_signal = bucket(review_count) * rating_factor
    contactability  = phone(50) + website-200(50)

Optional --vertical-fit-config <yaml> overrides weights and thresholds.

Usage:
    python score_prospects.py \\
        --input prospects/run_001/audited.csv \\
        --output prospects/run_001/scored.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

DEFAULTS = {
    "weights": {
        "geo_gap": 0.40,
        "opportunity_score": 0.25,
        "business_signal": 0.20,
        "contactability": 0.15,
    },
    "review_buckets": [
        (200, 100),
        (50, 70),
        (10, 40),
        (0, 20),
    ],
    "review_missing_default": 30,
    "geo_gap_cap": 80,
}

PITCH_COLUMNS = [
    "geo_gap",
    "business_signal",
    "contactability",
    "pitchability_score",
    "recommended_tier",
]


def _safe_int(v, default=0):
    try:
        if v is None or v == "":
            return default
        return int(float(v))
    except (ValueError, TypeError):
        return default


def _safe_float(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (ValueError, TypeError):
        return default


def _bool(v):
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("true", "1", "yes", "y")


def _review_bucket(review_count, buckets, missing_default):
    if review_count is None or review_count == "":
        return missing_default
    n = _safe_int(review_count, 0)
    for threshold, score in buckets:
        if n >= threshold:
            return score
    return missing_default


def _rating_factor(rating):
    r = _safe_float(rating, 0.0)
    if r <= 0:
        return 0.8
    return max(0.0, min(1.0, r / 5.0))


def _load_config(path):
    if not path:
        return DEFAULTS
    try:
        import yaml  # type: ignore
    except ImportError:
        print("PyYAML not installed — using defaults.", file=sys.stderr)
        return DEFAULTS
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cfg = {**DEFAULTS, **{k: v for k, v in raw.items() if v is not None}}
    cfg["weights"] = {**DEFAULTS["weights"], **(raw.get("weights") or {})}
    return cfg


def score_row(row, cfg):
    audit_status = (row.get("audit_status") or "").lower()
    if audit_status != "success":
        return {
            "geo_gap": 0,
            "business_signal": 0,
            "contactability": 0,
            "pitchability_score": 0,
            "recommended_tier": "skip",
        }

    geo_score = _safe_int(row.get("geo_score"), 0)
    geo_gap = min(100 - geo_score, cfg["geo_gap_cap"])
    geo_gap = max(0, geo_gap)

    opportunity = _safe_float(row.get("opportunity_score"), 0.0)

    bucket = _review_bucket(row.get("review_count"), cfg["review_buckets"], cfg["review_missing_default"])
    business_signal = round(bucket * _rating_factor(row.get("rating")), 1)

    has_phone = bool((row.get("phone") or "").strip())
    website_ok = True  # audit_status success implies website responded
    contactability = (50 if has_phone else 0) + (50 if website_ok else 0)

    w = cfg["weights"]
    pitchability = round(
        w["geo_gap"] * geo_gap
        + w["opportunity_score"] * opportunity
        + w["business_signal"] * business_signal
        + w["contactability"] * contactability,
        1,
    )

    if pitchability >= 70:
        tier = "premium"
    elif pitchability >= 50:
        tier = "standard"
    else:
        tier = "skip"

    return {
        "geo_gap": geo_gap,
        "business_signal": business_signal,
        "contactability": contactability,
        "pitchability_score": pitchability,
        "recommended_tier": tier,
    }


def main():
    parser = argparse.ArgumentParser(description="Pitchability scoring for audited prospects")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--vertical-fit-config", default=None,
                        help="Optional YAML overriding weights / review buckets")
    args = parser.parse_args()

    cfg = _load_config(args.vertical_fit_config)

    in_path = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with in_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        in_fields = reader.fieldnames or []

    if not rows:
        print("Input CSV empty.", file=sys.stderr)
        all_fields = list(dict.fromkeys(list(in_fields) + PITCH_COLUMNS))
        with out_path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=all_fields).writeheader()
        return 0

    scored = []
    for row in rows:
        scores = score_row(row, cfg)
        merged = dict(row)
        merged.update(scores)
        scored.append(merged)

    scored.sort(key=lambda r: _safe_float(r.get("pitchability_score"), 0.0), reverse=True)

    all_fields = list(dict.fromkeys(list(in_fields) + PITCH_COLUMNS))
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        for r in scored:
            writer.writerow(r)

    above_50 = sum(1 for r in scored if _safe_float(r.get("pitchability_score"), 0.0) >= 50)
    print(f"Scored {len(scored)} prospects — {above_50} above pitchability 50", file=sys.stderr)
    print(f"Written to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
