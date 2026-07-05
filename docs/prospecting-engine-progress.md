# Prospecting Engine — Build Progress

Expanding GEO SLAB from an audit toolkit into a prospecting + lead-magnet
system, per the July 2026 build spec. This tracks what's built vs pending.

**Core principle (do not blur):** the free AI Visibility Check is a *sales tool*,
not a mini-audit — mention detection + competitors + CTA only. Citability,
technical, schema, priorities stay in the PAID Quick Check (£247) / Full Audit
(£497). Don't let the free tier eat the paid tiers.

## Phase status

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | `db.py` (SQLite), schema, `migrate_prospects.py`, webapp on SQLite | ✅ Done |
| 2 | `places_prospector.py`, `/geo find`, campaign tagging | ✅ Done |
| 3 | `companies_house.py`, fuzzy match, `/geo enrich`, review queue | ✅ Done |
| 4 | `lib/ai_query_core.py`, `visibility_check.py`, `render_check_report.py`, `/geo check` | ✅ Done |
| 5 | `outreach_generator.py`, `mail_batch.py` (Stannp-file path), suppression enforcement, `/geo outreach`, `/geo mail` | ✅ Done (Stannp *API* deferred — outputs files) |
| 6 | `server/check_api.py` + `brevo.py`, Dockerfile, n8n workflow, deploy docs | ✅ Done (code+config; needs `CHECK_API_TOKEN` + deploy) |
| 7 | `landing/index.html` (+ JSON-LD), `funnel_report.py`/`/geo funnel`, `docs/ads-playbook.md` | ✅ Done (ads = copy/config to launch) |
| 8 | `apify_linkedin.py`, LinkedIn enrichment layer | ✅ Done |

## What works today (end-to-end, tested live)

```
/geo find plumber "Basingstoke, UK"     # Places (New) → SQLite (status=found)
/geo enrich --batch found               # Companies House → director + channel (→enriched)
/geo check PRO-001 --location Basingstoke  # 4 AI engines → 1-page report (→checked)
/geo linkedin PRO-003                   # Apify LinkedIn (shortlist only, gated)
/geo outreach --batch checked --out prospects/outreach/   # email + LinkedIn copy (deterministic)
/geo mail --batch enriched --out prospects/mail/          # A4 letter PDFs + Stannp import CSV
```

Storage: `~/.geo-slab/geo-slab.db` (SQLite, outside repo). Dashboard reads it
at `http://localhost:5050` (`/geo dashboard`).

## New files

| File | Role |
|------|------|
| `scripts/db.py` | SQLite layer — prospects/checks/outreach/suppressions. `prospects` is a superset (spec cols + legacy dashboard cols). `ref` (PRO-001) is the URL key; integer `id` is the internal PK. |
| `scripts/migrate_prospects.py` | One-shot prospects.json → SQLite (idempotent; no-op if no JSON). |
| `scripts/places_prospector.py` | Google Places API **(New)** searchText → prospects. Field-mask cost control; dedupe on place_id + domain; skips no-website + chains. |
| `scripts/companies_house.py` | CH enrichment. Fuzzy match (difflib token-sort + postcode-district signal). Sets `ch_match_confidence` + `outreach_channel` (§8 PECR). `--review` lists 0.5–0.8 band. `--linkedin` chains P8. |
| `scripts/lib/ai_query_core.py` | Shared brand-detection + OpenRouter calls. `live_ai_query.py` now imports from here (no divergence). |
| `scripts/visibility_check.py` | Free check — 5 prompts × 4 engines via OpenRouter. Pure/headless (P6 check_api will import `run_check`). Blunt 0–100 score. |
| `scripts/render_check_report.py` | 1-page neo brutalist HTML+PDF (`reports/<domain>/AI-CHECK-<domain>.{html,pdf}`). |
| `scripts/apify_linkedin.py` | LinkedIn enrichment via Apify harvestapi actors. Name-match + verified-company gates. |
| `scripts/outreach_generator.py` | Cold email + LinkedIn-connect copy. Deterministic Antek-voice templates (no LLM), personalised from latest check. Suppression-enforced. Writes `outreach` rows + optional `.md` drafts. |
| `scripts/mail_batch.py` | Stannp-ready postal batch: A4 letter PDF per prospect (reuses `render_prospect_mailer`, driven by free-check findings) + `stannp_recipients.csv`. Channel + suppression aware. Stannp *API* deferred — this is the file handoff. |
| `server/check_api.py` + `brevo.py` | Inbound free-check API (Flask, Bearer-auth, fails closed) + Brevo enrolment. Dockerfile, n8n workflow, README alongside. |
| `scripts/funnel_report.py` | Funnel report from SQLite — stage conversion, check spend/score/mention rate, outreach + source split. `/geo funnel`, `--campaign`, `--json`. |
| `landing/geo-audit-embed.html` | Drop-in snippet for the EXISTING page antekautomation.com/services/geo-audit — JSON-LD (Organization/Service/FAQ) for `<head>` + a script that wires the on-page form to the n8n webhook and renders the score inline (UTM capture, guarded gtag/fbq). No page rebuild. |
| `docs/ads-playbook.md` | Google + Meta ad copy, UTM taxonomy (ties to DB `campaign`), budgets, weekly review via `funnel_report`. |

Modified: `webapp/app.py` (JSON store → SQLite), `scripts/live_ai_query.py`
(refactored onto `ai_query_core`), `geo/SKILL.md` (new command rows).

## Key decisions & gotchas (read before resuming)

- **Superset schema** keeps the dashboard working with zero template churn.
- **OpenRouter model slugs drift and 404 silently.** Verified in `CHECK_MODELS`
  2026-07-03: `openai/gpt-4o-mini`, `anthropic/claude-haiku-4.5`,
  `google/gemini-2.5-flash`, `perplexity/sonar`. Re-verify via
  `GET /api/v1/models` if a platform drops out.
- **CH matching: name is primary, postcode is confirmation, not a gate.** Small
  firms register at the director's home/accountant, so trading-pc ≠ registered-pc
  is normal. District match = +0.10 boost, mismatch = ×0.85 mild penalty,
  inactive = ×0.3. ≥0.8 auto, 0.5–0.8 review, <0.5 = probable sole trader.
- **LinkedIn is a fragile multiplier — two safety gates.** (1) Reject a company
  result whose name doesn't token-match the prospect (caught "Options Plumbing"
  → "Options Bath & Tile Studio"). (2) Person lookup only runs with a *verified*
  company URL (name-only search returns namesakes). For local SMBs this often
  returns nothing — correct, not a bug.
- Every self-contained script has a `--self-check` / `_demo()` offline assertion.

## Env keys (`.env.local`, gitignored)

Present: Places, SerpAPI, Firecrawl, Perplexity, OpenRouter, PSI,
Companies House, Brevo, Apify (`APIFY_API_TOKEN`).
Missing / deferred: `STANNP_API_KEY`, `STANNP_TEMPLATE_ID` (postal — deferred),
`CHECK_API_TOKEN` (P6 endpoint auth).

## Next up

- **P5 Stannp API** — `mail_batch.py` currently outputs files (PDFs + CSV) for
  manual Stannp import. When `STANNP_API_KEY` lands, add a `--send` path that
  POSTs each letter. Address parse is heuristic — verify the CSV before sending.
- **P6 deploy** — code + Dockerfile + n8n workflow done and self-checked.
  Remaining is ops: generate `CHECK_API_TOKEN`, deploy the container on Coolify
  with a persistent volume for `GEO_SLAB_DB`, set `BREVO_CHECK_LIST_ID`, import
  `n8n-workflow.json`, wire the landing form. See `server/README.md`.
- **P7 launch** — funnel report done; landing page already exists at
  antekautomation.com/services/geo-audit. Remaining is ops: paste
  `landing/geo-audit-embed.html` block A (schema) + block B (form wiring) into
  that page — set `CHECK_WEBHOOK`, `FORM_SELECTOR`, `FIELD_MAP` to the real form;
  paste gtag/fbq pixels; launch the campaigns in `docs/ads-playbook.md`.

**All 8 phases built.** What's left across P5–P7 is external ops, not code:
Stannp key + `--send`, deploy the API container (Coolify) + n8n wiring, host the
landing page + launch ads.
