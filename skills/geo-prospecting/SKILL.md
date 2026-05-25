---
name: geo-prospecting
description: SERP-driven prospecting. Find businesses ranking in positions 9–13 for target keywords in the UK or US, run lite GEO audits in parallel, score by pitchability, draft outreach copy (email + LinkedIn + voice). Trigger when the operator wants to BUILD an outbound list rather than audit a known URL. Phrases like "find me prospects", "prospect for X in Y", "/geo prospecting".
allowed-tools: Bash, Read, Write
---

# geo-prospecting

> **⚠️ EXPERIMENTAL — not fully working yet.**
> Discovery + lite audit + scoring are stable. Outreach copy generation is workable but unrefined. Decision-maker scraping (`find_decision_makers.py`) works for standard team-page layouts but yields zero results on JS-only or non-standard structures (e.g. Duncan Lewis category cards, Walker Family Law spans without card classes). Email pattern detection rarely finds a published email to seed from, so most contact rows have a Google-search fallback for LinkedIn and no email. Treat this pipeline as a first-pass list builder that still needs manual cleanup.

End-to-end prospecting pipeline. Distinct from the existing `geo-prospect` skill (which renders a lite report from an already-run audit). This skill **discovers** prospects from SERPs, audits them, scores them, and drafts outreach copy.

## How invocation works

`/geo prospecting` is **wizard-driven by default**. The `geo-prospecting` subagent asks setup questions via `AskUserQuestion` before running anything. First question is the **starting point**:

- **Pick an ICP preset** (recommended) — 24 high-ticket verticals catalogued at `prospects/icps/icp_presets.json` (UK + US legal sub-verticals, fertility, hair restoration, plastic surgery, rehab, dentists, MBA admissions, etc.). Each preset pre-fills vertical, region, keyword templates, retainer band, upsell ladder, and pitch hook.
- **Custom vertical** — free-text vertical + location.

If preset path: only city, depth, and operator name need to be asked.
If custom path: vertical, region, location, keyword source, depth.

After discovery + audit + scoring, the agent **pauses and shows top 5** before spending LLM tokens on outreach copy.

Operator can also pass everything inline: `/geo prospecting <keywords_file> <location>` — wizard skips questions whose answers are already supplied.

## When to use

The operator wants to **find prospects**, not audit a known URL. Triggers:
- "Find me prospects in {location} for {vertical}"
- "Run prospecting on {keyword set}"
- "/geo prospecting ..."

## Inputs

**Required:**
- **vertical** — e.g. "personal injury lawyer", "Hampshire plumbers", "Reading SEO agencies"
- **location** — SerpAPI location string. US: `"Dallas, Texas, United States"`. UK: `"Southampton, England, United Kingdom"`
- **keyword file** — path to a `.txt` with one keyword per line (`#` comments allowed)

**Optional:**
- **gl / hl** — country code + language. Auto-detected from location (UK / US). Override only when SerpAPI returns the wrong locale.
- **min-position** (default 9), **max-position** (default 13)
- **max-prospects** (default 15)
- **min-pitchability** (default 50) — outreach cutoff
- **target-region** (default = inferred from location: `us` or `uk`) — controls outreach copy English register
- **enrich** flag — Google Places enrichment for business name / phone / address / rating

## Region behaviour

The pipeline supports **UK and US prospects**. Region propagates through:
- `discover_prospects.py` — `--gl us|uk`, `--hl en|en-GB` (auto-detected from location)
- `generate_outreach.py` — `--target-region us|uk` (auto-detected from location; operator can override)
- Internal logs and the `summary.md` always use UK English (operator preference)
- Outreach copy uses the target region's English register

## Flow

Generate `run_id = {vertical_slug}_{location_slug}_{YYYYMMDD_HHMMSS}`. Create `prospects/{run_id}/`.

0. **Wizard** — agent asks setup questions via `AskUserQuestion` (vertical, region, location, keyword source, depth, enrich, operator name). Defaults applied where sensible.

1. **Keyword bootstrap** (only if operator chose auto-generate)
   ```bash
   python scripts/bootstrap_keywords.py \
       --vertical "<vertical>" --location "<location>" \
       --count <N> --region <us|uk> \
       --output prospects/keywords/<slug>.txt
   ```
   Show generated keywords + confirm before continuing.

2. **Discovery**
   ```bash
   python scripts/discover_prospects.py \
       --keywords <kw_file> \
       --location <location> \
       --min-position 9 --max-position 13 \
       --max-prospects 15 \
       --enrich \
       --output prospects/<run_id>/prospects.csv
   ```
   Stream stderr to the operator. Report count when done.

2. **Audit**
   ```bash
   python scripts/batch_audit.py \
       --input prospects/<run_id>/prospects.csv \
       --output prospects/<run_id>/audited.csv \
       --concurrency 2 \
       --reports-dir prospects/<run_id>/reports
   ```
   Default concurrency 2. Per-prospect HTML lite reports land in `reports/{domain-with-dashes}.html`.

3. **Score**
   ```bash
   python scripts/score_prospects.py \
       --input prospects/<run_id>/audited.csv \
       --output prospects/<run_id>/scored.csv
   ```
   Show the operator the **top 5 by pitchability**: domain · business name · pitchability · geo_score · top_gap_1 · best_position.

4. **Pause for confirmation** — ask: *"Found {N} prospects above pitchability threshold. Generate outreach copy for all? (y/n)"*

5. **Outreach** (only if confirmed):
   ```bash
   python scripts/generate_outreach.py \
       --input prospects/<run_id>/scored.csv \
       --output prospects/<run_id>/outreach.csv \
       --min-pitchability 50 \
       --my-name "<operator name>" \
       --my-company "Antek Automation" \
       --vertical "<vertical>" \
       --target-region <us|uk>
   ```

6. **Decision-maker discovery** (optional, free — no API cost):
   ```bash
   python scripts/find_decision_makers.py \
       --input prospects/<run_id>/scored.csv \
       --output prospects/<run_id>/contacts.csv \
       --top 6 --limit-pages 5
   ```
   Scrapes public team pages (static fetch + Playwright fallback) for partners, directors, heads of department. Extracts JSON-LD `Person` schema when present, decodes Cloudflare-obfuscated emails, builds Google search URLs as LinkedIn fallback. **Known limitations:** misses non-standard team-page structures (JS-only sites, category-card layouts mistaken for people, sites without team links in main nav). Manual cleanup expected. Output columns: `domain,name,title,email,linkedin_url,phone,source_page,extraction_method,confidence`.

7. **Summary** — write `prospects/<run_id>/summary.md` with:
   - Run stats (keywords searched, prospects found, audited OK, above threshold)
   - Top 5 prospects table with links to their HTML reports
   - Path to `outreach.csv`
   - Errors-log path if any failures recorded

## Outputs

- `prospects/<run_id>/prospects.csv` — discovery
- `prospects/<run_id>/audited.csv` — audit results
- `prospects/<run_id>/scored.csv` — pitchability ranked
- `prospects/<run_id>/outreach.csv` — Brevo/CRM-ready outbound list
- `prospects/<run_id>/contacts.csv` — decision-makers scraped from team pages (optional, experimental)
- `prospects/<run_id>/reports/<slug>.html` — per-prospect lite reports
- `prospects/<run_id>/summary.md` — human-readable run overview
- `prospects/<run_id>/errors.log` — per-failure entries (only if failures)

## Required env

- `SERPAPI_KEY` (or `SERPAPI_API_KEY`) — fatal if missing
- `GOOGLE_PLACES_API_KEY` — optional, only when `--enrich`
- LLM API keys (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OPENROUTER_API_KEY`) — **optional**. The default outreach path is agent-generated inside Claude Code under your Max plan (zero external cost). Script-driven outreach (`generate_outreach.py`) only needs one of these keys as a fallback for large batches.

## Error handling

| Failure | Action |
|---|---|
| `SERPAPI_KEY` missing | Stop. Tell operator to export it. |
| Discovery returns 0 prospects | Tell operator. Suggest widening `--min-position` / `--max-position` or adding keywords. |
| All audits fail | Stop, suggest checking connectivity / Firecrawl. |
| Some audits fail | Continue. Log to `errors.log`. Set `audit_status: failed` in CSV. |
| No LLM key for step 5 | Stop *before* invoking, tell operator. |

## Notes

- Default position range 9–13 is intentionally tight for pitch-validation mode. Widen to 8–15 + `--max-prospects 50` for scale-up.
- Keyword files live in `prospects/keywords/{vertical}_{location}.txt` — reusable across runs.
- All Python scripts log to stderr. Show progress inline.
- No exclamation marks anywhere — code, logs, summaries, generated copy.
- This pipeline does **not** call brand_scanner (too slow for batch). Reserve full audits for top-N prospects via `/geo audit <url>`.
