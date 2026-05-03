# GEO SLAB Dashboard

Browser CRM for prospects, notes, and audit artifacts. Vanilla Flask + HTMX. Neo brutalist palette to match the report PDFs.

## Run

```bash
cd webapp
pip install -r requirements-webapp.txt
python app.py
# → http://localhost:5050
```

Set `FLASK_DEBUG=true` for auto-reload.

## Data model

Single JSON file at `~/.geo-slab/prospects.json`. Stdlib `json` only — no SQLite, no migrations.

```jsonc
[
  {
    "id": "PRO-001",
    "company": "Antek Automation",
    "domain": "antekautomation.com",
    "contact_name": "...",
    "contact_email": "...",
    "industry": "...",
    "country": "UK",
    "status": "lead | audit | proposal | active | churned | lost",
    "geo_score": 62,
    "audit_date": "YYYY-MM-DD",
    "monthly_value": 2400,
    "contract_start": null,
    "contract_months": 3,
    "notes": [{"date": "ISO8601", "text": "..."}],
    "created_at": "...",
    "updated_at": "..."
  }
]
```

To seed locally:

```bash
mkdir -p ~/.geo-slab
cp ../examples/prospects-demo.json ~/.geo-slab/prospects.json
```

## Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Dashboard with KPI row, status filter, sort |
| `/prospect/new` | GET, POST | Create prospect |
| `/prospect/<pid>` | GET | Detail view |
| `/prospect/<pid>/edit` | GET, POST | Edit prospect |
| `/prospect/<pid>/delete` | POST | Delete |
| `/prospect/<pid>/note` | POST | HTMX add-note (returns notes fragment) |
| `/prospect/<pid>/status` | POST | HTMX status change (returns badge) |
| `/prospect/<pid>/audit` | GET | Render audit JSON viewer |
| `/prospect/<pid>/report` | GET | Serve `GEO-REPORT-<domain>.html` |
| `/prospect/<pid>/pdf` | GET | Download `GEO-REPORT-<domain>.pdf` |
| `/prospect/<pid>/proposal` | GET | Render proposal markdown |

## Artifact discovery

`find_artefacts(domain)` scans `<repo>/reports/<domain>/` for:

- `audit-data.json`
- `GEO-REPORT-*.html` / `.pdf`
- `GEO-PROPOSAL-*.md`
- `live-visibility.json`
- `GEO-AUDIT-REPORT.md`

The dashboard never writes into `reports/` — that directory is owned by the audit pipeline.

## Stack

- Flask 3.x — routes + Jinja2 templating
- HTMX 1.9 (CDN) — partial swaps for notes + status without a JS build
- `markdown` — proposal rendering
- Vanilla CSS in [`static/css/slab.css`](static/css/slab.css)

## Env

| Var | Default | Use |
|-----|---------|-----|
| `GEO_SLAB_SECRET` | `geo-slab-dev-secret` | Flash-message signing key |
| `FLASK_DEBUG` | `false` | Auto-reload |

## Notes

- Webapp is intentionally not installed by `install.sh` — it's a runtime tool, not a Claude Code skill.
- For the slash-command surface inside Claude Code, see [`skills/geo-dashboard/`](../skills/geo-dashboard/).
