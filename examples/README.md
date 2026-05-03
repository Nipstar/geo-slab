# Examples

Sample artifacts produced by GEO SLAB. Useful for testing report renderers, the web dashboard, and showing prospects what a finished deliverable looks like.

## Files

| File | What it is |
|------|------------|
| [`antekautomation.com-audit.json`](antekautomation.com-audit.json) | Real `audit-data.json` from a `/geo audit antekautomation.com` run (April 2026). Canonical input for all renderers. |
| [`antekautomation.com-GEO-report.html`](antekautomation.com-GEO-report.html) | Self-contained neo brutalist HTML report rendered from the audit JSON. Open in a browser. |
| [`antekautomation.com-GEO-report.pdf`](antekautomation.com-GEO-report.pdf) | Playwright-printed PDF of the HTML report. Client-ready deliverable format. |
| [`antekautomation.com-proposal.md`](antekautomation.com-proposal.md) | Sample tiered service proposal — GEO Growth tier at £2,400 / month for the score-62 case. |
| [`prospects-demo.json`](prospects-demo.json) | Two-row demo of the dashboard data model. Drop into `~/.geo-slab/prospects.json` to seed the webapp. |

## How to use

### Test the webapp locally

```bash
mkdir -p ~/.geo-slab
cp examples/prospects-demo.json ~/.geo-slab/prospects.json
cd webapp && python app.py
# Open http://localhost:5050 — should show 2 prospects
```

### Test a report renderer change

```bash
python3 scripts/render_geo_report.py \
  examples/antekautomation.com-audit.json \
  /tmp/test-report.html
```

### Pitch deck / sales asset

The `.pdf` is a real deliverable suitable for screenshots in a sales deck or "what you get" section on a pricing page.

## Regenerating

The audit JSON is a snapshot — re-run `/geo audit https://www.antekautomation.com` to refresh. The HTML and PDF are produced from the JSON by `scripts/render_geo_report.py` and `scripts/generate_pdf_report.py` respectively.
