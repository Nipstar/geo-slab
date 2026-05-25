"""
generate_outreach.py — Draft outreach copy per prospect.

Reads scored.csv. For each prospect with pitchability_score >= --min-pitchability,
calls Anthropic (preferred) or OpenAI to generate:
  - email_subject (under 60 chars)
  - email_body    (80-100 words)
  - linkedin_dm   (40-50 words)
  - voice_opener  (30-second cold-call opener)

Region-aware: --target-region us|uk controls whether the copy uses US or UK English.
Internal logs/summaries always use UK English (operator preference).
No exclamation marks anywhere. Direct tone.

Usage:
    python generate_outreach.py \\
        --input prospects/run_001/scored.csv \\
        --output prospects/run_001/outreach.csv \\
        --min-pitchability 50 \\
        --my-name "Andy Norman" \\
        --my-company "Antek Automation" \\
        --vertical "personal injury law" \\
        --target-region us
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

OUTREACH_COLUMNS = [
    "email_subject",
    "email_body",
    "linkedin_dm",
    "voice_opener",
    "outreach_status",
    "outreach_error",
]

OUTPUT_FIELDS = [
    "domain", "business_name", "website", "phone",
    "pitchability_score", "geo_score", "top_gap_1",
    "email_subject", "email_body", "linkedin_dm", "voice_opener",
    "outreach_status", "outreach_error",
]


def _safe_float(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (ValueError, TypeError):
        return default


def _top_gap(row):
    for k in ("top_gap_1", "top_gap_2", "top_gap_3"):
        v = (row.get(k) or "").strip()
        if v:
            return v
    return "general GEO gaps"


def _has_anthropic():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _has_openai():
    return bool(os.environ.get("OPENAI_API_KEY"))


def _has_openrouter():
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def _build_user_prompt(row, vertical, target_region, my_name, my_company):
    region_english = "UK English (e.g. optimise, organisation, behaviour)" if target_region == "uk" else "US English (e.g. optimise, organisation, behavior)"
    return f"""Prospect: {row.get('business_name') or row.get('domain')} ({row.get('website')})
Vertical: {vertical}
Target region: {target_region.upper()}
Current rankings: {row.get('keywords') or 'unknown'}
GEO score: {row.get('geo_score') or 'unknown'}/100
Top gaps: {row.get('top_gap_1') or ''}; {row.get('top_gap_2') or ''}; {row.get('top_gap_3') or ''}
Sender: {my_name} from {my_company}

Generate cold outreach that:
- Opens with their specific ranking position for their most important keyword
- Names ONE specific GEO gap (the most severe)
- Connects ranking weakness to the AI search shift
- Offers a 15-minute call (no pitch, no demo)
- Signs off as {my_name} from {my_company}
- Tone: direct, no corporate filler. {region_english} throughout the copy.
- No exclamation marks. Short sentences.

Return strictly JSON with exactly these keys: email_subject, email_body, linkedin_dm, voice_opener.
email_subject: under 60 chars.
email_body: 80 to 100 words.
linkedin_dm: 40 to 50 words.
voice_opener: ~30 seconds of speech (about 70 to 90 words), readable as a cold-call opener."""


def _system_prompt():
    return (
        "You write cold B2B outreach for a UK AI automation agency selling "
        "Generative Engine Optimisation (GEO) services to UK and US businesses. "
        "You are direct, specific, and never use corporate filler. You never use "
        "exclamation marks. You always return strictly valid JSON when asked."
    )


def _strip_to_json(s):
    s = s.strip()
    # Remove markdown fences if present
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    # Find first { and last }
    first = s.find("{")
    last = s.rfind("}")
    if first >= 0 and last > first:
        s = s[first:last + 1]
    return s


def _call_anthropic(user_prompt, model="claude-sonnet-4-6"):
    from anthropic import Anthropic  # type: ignore
    client = Anthropic()
    msg = client.messages.create(
        model=model,
        max_tokens=1024,
        system=_system_prompt(),
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(b.text for b in msg.content if hasattr(b, "text"))
    return json.loads(_strip_to_json(text))


def _call_openai(user_prompt, model="gpt-4o-mini"):
    from openai import OpenAI  # type: ignore
    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        max_tokens=1024,
    )
    text = resp.choices[0].message.content or ""
    return json.loads(_strip_to_json(text))


def _call_openrouter(user_prompt, model=None):
    from openai import OpenAI  # type: ignore
    model = model or os.environ.get("OPENROUTER_MODEL") or "anthropic/claude-3.5-haiku"
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1024,
        extra_headers={
            "HTTP-Referer": "https://antekautomation.com",
            "X-Title": "GEO SLAB Outreach",
        },
    )
    text = resp.choices[0].message.content or ""
    return json.loads(_strip_to_json(text))


def generate_for_row(row, vertical, target_region, my_name, my_company):
    user_prompt = _build_user_prompt(row, vertical, target_region, my_name, my_company)
    if _has_anthropic():
        return _call_anthropic(user_prompt)
    if _has_openai():
        return _call_openai(user_prompt)
    if _has_openrouter():
        return _call_openrouter(user_prompt)
    raise RuntimeError("Neither ANTHROPIC_API_KEY, OPENAI_API_KEY, nor OPENROUTER_API_KEY set.")


def main():
    parser = argparse.ArgumentParser(description="Outreach copy generation")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-pitchability", type=float, default=50.0)
    parser.add_argument("--my-name", required=True)
    parser.add_argument("--my-company", required=True)
    parser.add_argument("--vertical", required=True,
                        help='e.g. "personal injury law" or "Hampshire plumbers"')
    parser.add_argument("--target-region", choices=["us", "uk"], default="us",
                        help="us → US English copy; uk → UK English copy")
    parser.add_argument("--sleep", type=float, default=0.5,
                        help="Seconds between LLM calls")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not (_has_anthropic() or _has_openai() or _has_openrouter()):
        print("Fatal: set ANTHROPIC_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY.", file=sys.stderr)
        return 2

    with in_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("Input CSV empty.", file=sys.stderr)
        with out_path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=OUTPUT_FIELDS).writeheader()
        return 0

    eligible = [r for r in rows if _safe_float(r.get("pitchability_score"), 0.0) >= args.min_pitchability]
    skipped = len(rows) - len(eligible)
    print(f"Generating for {len(eligible)} prospects (skipping {skipped} below threshold {args.min_pitchability})", file=sys.stderr)

    out_rows = []
    for i, row in enumerate(eligible, 1):
        domain = row.get("domain", "?")
        print(f"  [{i}/{len(eligible)}] {domain}", file=sys.stderr)
        record = {k: (row.get(k) or "") for k in OUTPUT_FIELDS}
        record["outreach_status"] = "failed"
        record["outreach_error"] = ""

        try:
            payload = generate_for_row(row, args.vertical, args.target_region, args.my_name, args.my_company)
            for k in ("email_subject", "email_body", "linkedin_dm", "voice_opener"):
                v = (payload.get(k) or "").strip()
                # Strip any exclamation marks defensively
                v = v.replace("!", ".")
                record[k] = v
            record["outreach_status"] = "success"
        except Exception as e:
            record["outreach_error"] = f"{type(e).__name__}: {e}"

        out_rows.append(record)
        time.sleep(args.sleep)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in out_rows:
            writer.writerow(r)

    ok = sum(1 for r in out_rows if r["outreach_status"] == "success")
    print(f"Done — {ok}/{len(out_rows)} successful", file=sys.stderr)
    print(f"Written to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
