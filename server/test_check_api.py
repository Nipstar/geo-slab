#!/usr/bin/env python3
"""Offline self-check for the inbound free-check API.

Monkeypatches run_check / render / brevo so nothing hits the network or spends
OpenRouter credits. Exercises auth (fail-closed + wrong token), validation, and
the happy path (persist + suppression-aware Brevo enrol).

    python3 server/test_check_api.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["GEO_SLAB_DB"] = str(Path(tempfile.mkdtemp()) / "t.db")
os.environ["OPENROUTER_API_KEY"] = "x"        # presence check only (run_check is stubbed)
os.environ.pop("CHECK_API_TOKEN", None)       # start unconfigured to test fail-closed

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_api  # noqa: E402
import db  # noqa: E402

FAKE_RESULT = {
    "visibility_score": 25, "platforms_tested": 4, "platforms_mentioned": 1,
    "platforms": [], "competitors": [{"name": "PlumbCo", "mentions": 3}],
    "run_at": "2026-07-05T00:00:00Z", "prompts": [],
}

check_api.visibility_check.run_check = lambda *a, **k: FAKE_RESULT
check_api.render_check_report.render = lambda result, out_dir, pdf=True: {
    "html": str(Path(out_dir) / "AI-CHECK.html")}
check_api.visibility_check.save_to_db = lambda *a, **k: 1
_enrols: list = []
check_api.brevo.enrol_lead = lambda *a, **k: (_enrols.append(a) or True)

db.init_db()
c = check_api.app.test_client()

VALID = {"company": "Acme Plumbing", "domain": "https://www.acme.co.uk/",
         "industry": "plumbers", "town": "Basingstoke", "email": "sam@acme.co.uk",
         "name": "Sam"}


def _demo() -> None:
    # health is open
    assert c.get("/health").get_json()["ok"] is True

    # no token configured -> fail closed 503
    assert c.post("/check", json=VALID).status_code == 503

    os.environ["CHECK_API_TOKEN"] = "secret"

    # missing / wrong bearer -> 401
    assert c.post("/check", json=VALID).status_code == 401
    assert c.post("/check", json=VALID,
                  headers={"Authorization": "Bearer nope"}).status_code == 401

    auth = {"Authorization": "Bearer secret"}

    # missing required field -> 400
    r = c.post("/check", json={"company": "x"}, headers=auth)
    assert r.status_code == 400 and "missing" in r.get_json()["error"]

    # happy path -> 200, domain normalised, prospect persisted, lead enrolled
    r = c.post("/check", json=VALID, headers=auth)
    body = r.get_json()
    assert r.status_code == 200, body
    assert body["score"] == 25 and body["competitors"] == ["PlumbCo"]
    ref = body["ref"]
    p = db.get_prospect(ref)
    assert p and p["domain"] == "acme.co.uk" and p["source"] == "inbound"
    assert len(_enrols) == 1 and body["enrolled"] is True

    # second submit for same domain reuses the prospect (no duplicate)
    before = len(db.all_prospects())
    c.post("/check", json=VALID, headers=auth)
    assert len(db.all_prospects()) == before

    # suppressed email -> check still runs, but no Brevo enrol
    db.add_suppression(email="blocked@x.com", reason="opted_out")
    _enrols.clear()
    r = c.post("/check", json={**VALID, "domain": "other.co.uk",
                               "email": "blocked@x.com"}, headers=auth)
    assert r.get_json()["enrolled"] is False and not _enrols

    print("check_api self-check passed")


if __name__ == "__main__":
    _demo()
