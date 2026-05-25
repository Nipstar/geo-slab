"""
bootstrap_keywords.py — Generate seed keywords for prospecting.

Given a vertical + location, produces a keyword file ready for
discover_prospects.py. Uses Anthropic (preferred) or OpenAI.

Usage:
    python bootstrap_keywords.py \\
        --vertical "personal injury law" \\
        --location "Dallas, Texas, United States" \\
        --count 8 \\
        --output prospects/keywords/legal_dallas.txt

Region (us/uk) auto-detected from location. Keywords use the local
phrasing (e.g. "lawyer" for US, "solicitor" for UK).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


def _has_anthropic():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _has_openai():
    return bool(os.environ.get("OPENAI_API_KEY"))


def _has_openrouter():
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def _has_llm():
    return _has_anthropic() or _has_openai() or _has_openrouter()


def _infer_region(location: str) -> str:
    loc = (location or "").lower()
    uk_signals = ("united kingdom", "england", "scotland", "wales",
                  "northern ireland", " uk", ", uk")
    return "uk" if any(s in loc for s in uk_signals) else "us"


def _system_prompt():
    return (
        "You generate cold-search SEO keywords for B2B prospecting. "
        "You return only valid JSON. No commentary."
    )


def _user_prompt(vertical, location, region, count):
    locale_hint = (
        "UK English. Use UK terminology (solicitor, plumber, joiner, "
        "lift, lorry, town/city names familiar to UK searchers)."
        if region == "uk" else
        "US English. Use US terminology (lawyer, attorney, plumber, "
        "city/state names familiar to US searchers)."
    )
    return f"""Generate {count} Google search keywords likely used by people in or near "{location}" looking for: {vertical}.

Rules:
- Mix of head terms and longer-tail variations
- Include geographic modifiers (city, region, "near me")
- Mix service-led and intent-led phrasing
- {locale_hint}
- No exclamation marks
- No quotation marks in the keywords themselves

Return JSON: {{"keywords": ["kw1", "kw2", ...]}}"""


def _strip_to_json(s):
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    first = s.find("{")
    last = s.rfind("}")
    if first >= 0 and last > first:
        s = s[first:last + 1]
    return s


def _call_anthropic(prompt, model="claude-sonnet-4-6"):
    from anthropic import Anthropic  # type: ignore
    client = Anthropic()
    msg = client.messages.create(
        model=model,
        max_tokens=512,
        system=_system_prompt(),
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in msg.content if hasattr(b, "text"))
    return json.loads(_strip_to_json(text))


def _call_openai(prompt, model="gpt-4o-mini"):
    from openai import OpenAI  # type: ignore
    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        max_tokens=512,
    )
    return json.loads(_strip_to_json(resp.choices[0].message.content or ""))


def _call_openrouter(prompt, model=None):
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
            {"role": "user", "content": prompt},
        ],
        max_tokens=512,
        extra_headers={
            "HTTP-Referer": "https://antekautomation.com",
            "X-Title": "GEO SLAB Keywords",
        },
    )
    return json.loads(_strip_to_json(resp.choices[0].message.content or ""))


def generate_keywords(vertical, location, count, region=None):
    region = region or _infer_region(location)
    prompt = _user_prompt(vertical, location, region, count)
    if _has_anthropic():
        payload = _call_anthropic(prompt)
    elif _has_openai():
        payload = _call_openai(prompt)
    elif _has_openrouter():
        payload = _call_openrouter(prompt)
    else:
        raise RuntimeError("Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY.")
    kws = payload.get("keywords") or []
    cleaned = []
    for k in kws:
        k = str(k).strip().strip('"').strip("'").replace("!", "")
        if k and k not in cleaned:
            cleaned.append(k)
    return cleaned[:count]


def _slugify(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "untitled"


PRESETS_PATH = Path(__file__).resolve().parent.parent / "prospects" / "icps" / "icp_presets.json"


def _load_presets():
    if not PRESETS_PATH.exists():
        return None
    try:
        return json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _find_preset(preset_id):
    data = _load_presets()
    if not data:
        return None
    for p in data.get("presets", []):
        if p.get("id") == preset_id:
            return p
    return None


def list_presets():
    data = _load_presets()
    if not data:
        print("No preset catalogue at prospects/icps/icp_presets.json", file=sys.stderr)
        return
    print(f"{'ID':<28} {'TIER':<6} {'REGION':<8} {'RETAINER':<15} NAME", file=sys.stderr)
    print("-" * 100, file=sys.stderr)
    for p in data.get("presets", []):
        retainer = f"{p.get('retainer_min','?')}-{p.get('retainer_max','?')} {p.get('currency','')}"
        print(f"{p.get('id',''):<28} T{p.get('tier','?'):<5} {p.get('region',''):<8} {retainer:<15} {p.get('name','')}", file=sys.stderr)


def expand_preset_keywords(preset, city):
    """Fill [city] in each template. If preset is 'national', city can be empty."""
    out = []
    is_national = preset.get("national", False)
    for tpl in preset.get("keyword_templates", []):
        if "[city]" in tpl:
            if is_national:
                # Drop the [city] modifier for national-scope presets
                kw = tpl.replace(" [city]", "").replace("[city]", "").strip()
            else:
                kw = tpl.replace("[city]", city).strip()
        else:
            kw = tpl.strip()
        if kw and kw not in out:
            out.append(kw)
    return out


def main():
    parser = argparse.ArgumentParser(description="Generate seed keywords for prospecting")
    parser.add_argument("--preset", default=None,
                        help="ICP preset id (e.g. family_law_uk). See --list-presets.")
    parser.add_argument("--list-presets", action="store_true",
                        help="List available presets and exit")
    parser.add_argument("--city", default=None,
                        help="City to fill [city] placeholder when using --preset")
    parser.add_argument("--vertical", default=None)
    parser.add_argument("--location", default=None)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--region", choices=["us", "uk"], default=None,
                        help="Override region detection")
    parser.add_argument("--no-llm", action="store_true",
                        help="Use preset templates only — skip LLM expansion. Requires --preset.")
    parser.add_argument("--output", default=None,
                        help="Output path. Default: prospects/keywords/{vertical}_{location}.txt")
    args = parser.parse_args()

    if args.list_presets:
        list_presets()
        return 0

    # Preset path
    if args.preset:
        preset = _find_preset(args.preset)
        if not preset:
            print(f"Preset '{args.preset}' not found. Run --list-presets to see options.", file=sys.stderr)
            return 5
        # Pull defaults from preset if operator didn't supply
        if not args.vertical:
            args.vertical = preset.get("vertical")
        if not args.region:
            preg = preset.get("region")
            args.region = preg if preg in ("us", "uk") else None
        if not args.location:
            if preset.get("national"):
                args.location = "United States" if args.region == "us" else "United Kingdom"
            else:
                if not args.city:
                    print("Preset is city-scoped — pass --city '<city>' (e.g. 'London' or 'Dallas, Texas, United States')", file=sys.stderr)
                    return 6
                # Build SerpAPI-style location from city for convenience
                args.location = args.city if "," in args.city else (
                    f"{args.city}, England, United Kingdom" if args.region == "uk"
                    else f"{args.city}, United States"
                )

        preset_keywords = expand_preset_keywords(preset, args.city or "")

        # No-LLM path: just write preset templates
        if args.no_llm or not _has_llm():
            keywords = preset_keywords[:args.count]
            output = args.output or f"prospects/keywords/{_slugify(args.preset)}_{_slugify(args.city or 'national')}.txt"
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            header = f"# Preset '{args.preset}' — {preset.get('name')}\n# Location: {args.location}\n"
            out_path.write_text(header + "\n".join(keywords) + "\n", encoding="utf-8")
            print(f"Wrote {len(keywords)} preset keywords to {out_path}", file=sys.stderr)
            for k in keywords:
                print(f"  - {k}", file=sys.stderr)
            return 0

        # LLM-augmented path: seed with preset templates, ask for expansion
        print(f"Using preset '{args.preset}' as seed. Augmenting with LLM for {args.count} keywords...", file=sys.stderr)
        seed_text = "\n".join(f"- {k}" for k in preset_keywords)
        try:
            extra_count = max(0, args.count - len(preset_keywords))
            if extra_count == 0:
                keywords = preset_keywords[:args.count]
            else:
                # Build augmentation prompt
                aug_prompt = f"""Here are existing seed keywords for {preset.get('vertical')} in {args.location}:
{seed_text}

Generate exactly {extra_count} ADDITIONAL keywords (do not repeat the seeds). Same vertical, same location intent, complementary terms (longer-tail variants, intent-led phrasing, related sub-services).

Region: {args.region.upper()}.
{"UK English." if args.region == "uk" else "US English."}
No exclamation marks. No quotes inside keywords.

Return JSON: {{"keywords": [...]}}"""
                if _has_anthropic():
                    payload = _call_anthropic(aug_prompt)
                elif _has_openai():
                    payload = _call_openai(aug_prompt)
                else:
                    payload = _call_openrouter(aug_prompt)
                extra = [str(k).strip().strip('"').strip("'").replace("!", "") for k in (payload.get("keywords") or [])]
                keywords = preset_keywords + [k for k in extra if k and k not in preset_keywords]
                keywords = keywords[:args.count]
        except Exception as e:
            print(f"LLM augmentation failed ({e}); using preset templates only.", file=sys.stderr)
            keywords = preset_keywords[:args.count]

        output = args.output or f"prospects/keywords/{_slugify(args.preset)}_{_slugify(args.city or 'national')}.txt"
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        header = f"# Preset '{args.preset}' — {preset.get('name')}\n# Location: {args.location}\n"
        out_path.write_text(header + "\n".join(keywords) + "\n", encoding="utf-8")
        print(f"Wrote {len(keywords)} keywords to {out_path}", file=sys.stderr)
        for k in keywords:
            print(f"  - {k}", file=sys.stderr)
        return 0

    # Non-preset path requires --vertical and --location
    if not args.vertical or not args.location:
        print("Either pass --preset <id>, or supply both --vertical and --location.", file=sys.stderr)
        return 7

    if not _has_llm():
        print("Fatal: set ANTHROPIC_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY.", file=sys.stderr)
        return 2

    output = args.output
    if not output:
        slug = f"{_slugify(args.vertical)}_{_slugify(args.location)}"
        output = f"prospects/keywords/{slug}.txt"

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.count} keywords for '{args.vertical}' in '{args.location}'", file=sys.stderr)
    try:
        keywords = generate_keywords(args.vertical, args.location, args.count, args.region)
    except Exception as e:
        print(f"Fatal: {type(e).__name__}: {e}", file=sys.stderr)
        return 3

    if not keywords:
        print("No keywords generated.", file=sys.stderr)
        return 4

    header = f"# Auto-generated keywords for '{args.vertical}' in '{args.location}'\n"
    out_path.write_text(header + "\n".join(keywords) + "\n", encoding="utf-8")
    print(f"Wrote {len(keywords)} keywords to {out_path}", file=sys.stderr)
    for k in keywords:
        print(f"  - {k}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
