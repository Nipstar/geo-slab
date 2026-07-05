# GEO SLAB — Inbound Free-Check API (spec §6)

Thin Flask service that lets a landing page (via n8n or a direct POST) run the
**free AI Visibility Check**, return a score + report, persist the lead to the
SQLite DB, and enrol it in Brevo for follow-up. Same frozen free-check scope as
`/geo check` — mention detection + competitors + score, nothing paid.

## Files

| File | Role |
|------|------|
| `check_api.py` | Flask app. `GET /health`, `POST /check` (Bearer token). |
| `brevo.py` | Stdlib Brevo client — upsert contact + enrol in funnel list. No-op without `BREVO_API_KEY`. |
| `Dockerfile` | Slim Python image, gunicorn. Build context = **repo root**. |
| `requirements-server.txt` | flask, gunicorn, requests, dotenv. No playwright — API renders HTML only. |
| `n8n-workflow.json` | Importable workflow: form webhook → API → response. |
| `test_check_api.py` | Offline self-check (monkeypatched, no network/credits). |

## Environment

| Var | Required | Purpose |
|-----|----------|---------|
| `CHECK_API_TOKEN` | **yes** | Bearer token. Unset → API fails **closed** (503). |
| `OPENROUTER_API_KEY` | **yes** | Powers the 4-engine check. |
| `GEO_SLAB_DB` | prod | Point at a mounted volume so leads persist across deploys. |
| `BREVO_API_KEY` | optional | Enables lead enrolment. |
| `BREVO_CHECK_LIST_ID` | optional | List the sequence watches. Without it the contact is upserted but not listed. |
| `REPORT_BASE` | optional | Public base URL serving `reports/`; used to build the report link. |

## POST /check

```
POST /check
Authorization: Bearer <CHECK_API_TOKEN>
Content-Type: application/json

{ "company": "...", "domain": "...", "industry": "...", "town": "...",
  "county": "?", "email": "?", "name": "?", "campaign": "?" }
```

`company`, `domain`, `industry`, `town` required. Returns:

```json
{ "ok": true, "ref": "PRO-011", "score": 25, "platforms_tested": 4,
  "platforms_mentioned": 1, "competitors": ["PlumbCo"],
  "report_url": "...", "enrolled": true }
```

`email` enrols the lead in Brevo **unless suppressed** (opt-outs are respected
even though the lead asked). Duplicate domains reuse the existing prospect.

## Run

```bash
# local
CHECK_API_TOKEN=dev OPENROUTER_API_KEY=sk-or-... python3 check_api.py

# offline test (no credits)
python3 test_check_api.py

# container (from repo root)
docker build -f server/Dockerfile -t geo-check-api .
docker run -p 8000:8000 -v geo-slab-data:/data \
  -e CHECK_API_TOKEN=... -e OPENROUTER_API_KEY=... \
  -e GEO_SLAB_DB=/data/geo-slab.db -e BREVO_API_KEY=... geo-check-api
```

## Coolify

1. New resource → **Dockerfile**, repo = this repo, Dockerfile path `server/Dockerfile`, build context `/` (repo root).
2. Set the env vars above (Coolify → Environment). Generate `CHECK_API_TOKEN` with `openssl rand -hex 24`.
3. Add a **persistent volume** mounted at `/data`; set `GEO_SLAB_DB=/data/geo-slab.db`.
4. Port `8000`. Health check path `/health`.
5. Point n8n's `CHECK_API_URL` at the deployed domain, import `n8n-workflow.json`, set `CHECK_API_TOKEN` in n8n env.

**PDF note:** the API renders HTML only (no Chromium in the container). The PDF
is generated later by the sales-side `/geo check` if the lead converts.
