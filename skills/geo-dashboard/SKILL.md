---
name: geo-dashboard
description: Launch the GEO SLAB web dashboard — a Flask + HTMX browser CRM for prospect management, notes, and audit artifact viewing. Use when the user asks to open the dashboard, manage prospects in the UI, review audits in the browser, or invokes /geo dashboard.
allowed-tools: Bash, Read
---

# GEO SLAB Dashboard

Browser CRM for prospect management. Persists to `~/.geo-slab/prospects.json`. Auto-discovers audit artifacts under `reports/<domain>/`.

## When invoked

The user typed `/geo dashboard` or asked to open the GEO SLAB dashboard / CRM / web UI.

## Action

1. Tell the user how to start the dashboard:

   ```bash
   cd webapp
   pip install -r requirements-webapp.txt   # first run only
   python app.py
   # → http://localhost:5050
   ```

   For auto-reload during development: `FLASK_DEBUG=true python app.py`.

2. If the user has never run the dashboard before, suggest seeding it with the example data:

   ```bash
   mkdir -p ~/.geo-slab
   cp examples/prospects-demo.json ~/.geo-slab/prospects.json
   ```

3. Briefly describe what the dashboard offers:

   - Prospect CRUD with status pipeline (lead → audit → proposal → active → churned/lost)
   - Per-prospect notes with HTMX-powered inline updates
   - Auto-discovered audit JSON / HTML report / PDF / proposal markdown viewers
   - GBP MRR + pipeline KPIs
   - Filter by status, sort by score / company / MRR / updated

## Notes

- The dashboard is a runtime tool — it is not installed by `install.sh` and runs locally.
- Source: `webapp/app.py` and `webapp/templates/`. Vanilla Flask + HTMX + Jinja2.
- Visual language matches the report PDFs: neo brutalist (coral / cream / sage), Barlow Condensed headings.
- See [`webapp/README.md`](../../webapp/README.md) for routes, data model, and env vars.

## Output

Print the launch instructions. Do not attempt to start the server in the background — the user controls the process lifecycle.
