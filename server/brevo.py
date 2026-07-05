#!/usr/bin/env python3
"""
Thin Brevo client for the inbound free-check funnel (spec §6).

Just enough to drop a lead into Brevo after they run a check: upsert the
contact with the check result as attributes and (optionally) add them to a
list, which is where a Brevo automation / n8n sequence picks them up. No SDK —
stdlib urllib, so `server/` stays dependency-light.

Reads BREVO_API_KEY from the environment. Every call is a no-op returning False
when the key is absent, so the API and self-checks run fine without it.

    from brevo import upsert_contact
    upsert_contact("a@b.com", {"FIRSTNAME": "Sam", "GEO_SCORE": 25}, list_ids=[7])
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional

BREVO_BASE = "https://api.brevo.com/v3"


def _key() -> Optional[str]:
    return os.environ.get("BREVO_API_KEY")


def _post(path: str, payload: dict) -> tuple[int, str]:
    key = _key()
    if not key:
        return 0, "no BREVO_API_KEY"
    req = urllib.request.Request(
        BREVO_BASE + path,
        data=json.dumps(payload).encode(),
        headers={"api-key": key, "content-type": "application/json",
                 "accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        # 204 "contact updated" comes back as HTTPError in some urllib versions
        return e.code, e.read().decode(errors="replace")
    except Exception as e:  # noqa: BLE001 — network path, never crash the request
        return -1, str(e)


def upsert_contact(email: str, attributes: Optional[dict] = None,
                   list_ids: Optional[list[int]] = None) -> bool:
    """Create-or-update a Brevo contact. Returns True on 2xx (or 204 update)."""
    if not email:
        return False
    payload: dict = {"email": email, "updateEnabled": True}
    if attributes:
        # Brevo attribute names are upper-cased by convention
        payload["attributes"] = {k.upper(): v for k, v in attributes.items()}
    if list_ids:
        payload["listIds"] = list_ids
    code, _ = _post("/contacts", payload)
    return code in (200, 201, 204)


def enrol_lead(email: str, name: str, score: int, report_url: str,
               company: str = "", list_id: Optional[int] = None) -> bool:
    """Enrol a free-check lead: contact + attributes, added to the funnel list.

    list_id defaults to BREVO_CHECK_LIST_ID (env). Without it the contact is
    still upserted, just not listed — the sequence won't fire, which is the
    correct fail-open for a missing config value.
    """
    lid = list_id or os.environ.get("BREVO_CHECK_LIST_ID")
    list_ids = [int(lid)] if lid else None
    attrs = {"FIRSTNAME": name, "GEO_SCORE": score, "REPORT_URL": report_url}
    if company:
        attrs["COMPANY"] = company
    return upsert_contact(email, attrs, list_ids)


def _demo() -> None:
    # No key -> every call is a safe no-op (never raises, returns False)
    os.environ.pop("BREVO_API_KEY", None)
    assert upsert_contact("a@b.com", {"GEO_SCORE": 1}) is False
    assert enrol_lead("a@b.com", "Sam", 25, "http://x") is False
    assert upsert_contact("", {}) is False

    # Payload shaping is correct without hitting the network
    captured = {}

    def fake_post(path, payload):
        captured["path"] = path
        captured["payload"] = payload
        return 201, "{}"

    global _post
    real = _post
    _post = fake_post
    try:
        os.environ["BREVO_API_KEY"] = "x"  # key present so we reach _post
        assert enrol_lead("a@b.com", "Sam", 25, "http://x", company="Acme", list_id=7)
        p = captured["payload"]
        assert p["email"] == "a@b.com" and p["updateEnabled"] is True
        assert p["attributes"]["GEO_SCORE"] == 25 and p["attributes"]["COMPANY"] == "Acme"
        assert p["listIds"] == [7]
    finally:
        _post = real
        os.environ.pop("BREVO_API_KEY", None)
    print("brevo self-check passed")


if __name__ == "__main__":
    _demo()
