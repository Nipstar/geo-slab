#!/usr/bin/env python3
"""
GEO SLAB — SQLite persistence layer.

Single DB file at ~/.geo-slab/geo-slab.db (override with $GEO_SLAB_DB).
Replaces the old ~/.geo-slab/prospects.json flat file.

Schema follows the prospecting-engine spec (§4): prospects / checks /
outreach / suppressions. The `prospects` table is a SUPERSET — it carries
the spec's discovery + enrichment + pipeline columns AND the columns the
Flask dashboard already relies on (geo_score, monthly_value, contract_months,
contact_name/email, notes, audit/report/proposal file pointers), so the
webapp keeps working with no template changes.

ponytail: stdlib sqlite3 only, no ORM. If query volume ever gets hairy,
swap the raw SQL for SQLModel/SQLAlchemy — not before.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ── Location ─────────────────────────────────────────────────────────────

def db_path() -> Path:
    override = os.environ.get("GEO_SLAB_DB")
    if override:
        return Path(override)
    return Path.home() / ".geo-slab" / "geo-slab.db"


# ── Schema ───────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects (
    id INTEGER PRIMARY KEY,
    ref TEXT UNIQUE,                  -- PRO-001 style, URL + continuity key
    company TEXT NOT NULL,
    domain TEXT,
    place_id TEXT UNIQUE,             -- Google Places dedupe key
    phone TEXT,
    email TEXT,
    website TEXT,
    address TEXT,
    postcode TEXT,
    lat REAL, lng REAL,
    industry TEXT,
    rating REAL, review_count INTEGER,
    -- Companies House
    ch_number TEXT,
    ch_name TEXT,
    ch_status TEXT,
    ch_type TEXT,
    ch_registered_address TEXT,
    ch_incorporated TEXT,
    ch_sic TEXT,
    ch_match_confidence REAL,
    director_name TEXT,
    -- LinkedIn (Apify)
    li_company_url TEXT,
    li_person_url TEXT,
    li_person_title TEXT,
    li_headcount TEXT,
    -- Pipeline
    status TEXT DEFAULT 'found',
    outreach_channel TEXT,
    source TEXT,
    campaign TEXT,
    monthly_value REAL,
    notes TEXT,                       -- JSON array of {date,text}
    -- Dashboard-era columns (kept so the webapp/templates are untouched)
    contact_name TEXT,
    contact_email TEXT,
    country TEXT,
    geo_score INTEGER,
    contract_months INTEGER,
    audit_date TEXT,
    contract_start TEXT,
    audit_file TEXT,
    report_html TEXT,
    proposal_file TEXT,
    created_at TEXT, updated_at TEXT
);

CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    run_at TEXT,
    prompts_json TEXT,
    results_json TEXT,
    mentioned_count INTEGER,
    platforms_tested INTEGER,
    competitors_json TEXT,
    visibility_score INTEGER,
    report_html_path TEXT,
    report_pdf_path TEXT,
    cost_usd REAL
);

CREATE TABLE IF NOT EXISTS outreach (
    id INTEGER PRIMARY KEY,
    prospect_id INTEGER REFERENCES prospects(id),
    channel TEXT,
    subject TEXT,
    body TEXT,
    status TEXT,
    stannp_id TEXT,
    sent_at TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS suppressions (
    id INTEGER PRIMARY KEY,
    domain TEXT, email TEXT, company TEXT,
    reason TEXT,
    added_at TEXT
);
"""

# Columns the dashboard read/writes. Used to build INSERT/UPDATE dynamically
# so callers can pass partial dicts.
_PROSPECT_COLS = [
    "ref", "company", "domain", "place_id", "phone", "email", "website",
    "address", "postcode", "lat", "lng", "industry", "rating", "review_count",
    "ch_number", "ch_name", "ch_status", "ch_type", "ch_registered_address",
    "ch_incorporated", "ch_sic", "ch_match_confidence", "director_name",
    "li_company_url", "li_person_url", "li_person_title", "li_headcount",
    "status", "outreach_channel", "source", "campaign", "monthly_value",
    "notes", "contact_name", "contact_email", "country", "geo_score",
    "contract_months", "audit_date", "contract_start", "audit_file",
    "report_html", "proposal_file", "created_at", "updated_at",
]


# ── Connection ───────────────────────────────────────────────────────────

def connect() -> sqlite3.Connection:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    close = conn is None
    conn = conn or connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        if close:
            conn.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Row <-> dict ─────────────────────────────────────────────────────────

def _row_to_prospect(row: sqlite3.Row) -> dict:
    """Return a dict the webapp/templates expect: `id` is the PRO-xxx ref,
    integer PK preserved as `pk`, notes parsed to a list."""
    d = dict(row)
    d["pk"] = d["id"]
    d["id"] = d.get("ref") or d["id"]
    raw_notes = d.get("notes")
    if raw_notes:
        try:
            d["notes"] = json.loads(raw_notes)
        except (ValueError, TypeError):
            d["notes"] = []
    else:
        d["notes"] = []
    return d


def _prep_writes(data: dict) -> dict:
    """Filter to known columns and JSON-encode notes if a list was passed."""
    out = {k: v for k, v in data.items() if k in _PROSPECT_COLS}
    if isinstance(out.get("notes"), (list, dict)):
        out["notes"] = json.dumps(out["notes"], ensure_ascii=False)
    return out


# ── Prospect CRUD ────────────────────────────────────────────────────────

def all_prospects(conn: Optional[sqlite3.Connection] = None) -> list[dict]:
    close = conn is None
    conn = conn or connect()
    try:
        rows = conn.execute("SELECT * FROM prospects").fetchall()
        return [_row_to_prospect(r) for r in rows]
    finally:
        if close:
            conn.close()


def get_prospect(ref: str, conn: Optional[sqlite3.Connection] = None) -> Optional[dict]:
    close = conn is None
    conn = conn or connect()
    try:
        row = conn.execute("SELECT * FROM prospects WHERE ref = ?", (ref,)).fetchone()
        return _row_to_prospect(row) if row else None
    finally:
        if close:
            conn.close()


def next_ref(conn: sqlite3.Connection) -> str:
    nums = []
    for (ref,) in conn.execute("SELECT ref FROM prospects WHERE ref IS NOT NULL"):
        m = re.match(r"PRO-(\d+)$", ref or "")
        if m:
            nums.append(int(m.group(1)))
    return f"PRO-{(max(nums) + 1) if nums else 1:03d}"


def insert_prospect(data: dict, conn: Optional[sqlite3.Connection] = None) -> dict:
    close = conn is None
    conn = conn or connect()
    try:
        row = _prep_writes(data)
        row.setdefault("ref", next_ref(conn))
        row.setdefault("created_at", now_iso())
        row["updated_at"] = now_iso()
        cols = list(row.keys())
        placeholders = ", ".join("?" for _ in cols)
        conn.execute(
            f"INSERT INTO prospects ({', '.join(cols)}) VALUES ({placeholders})",
            [row[c] for c in cols],
        )
        conn.commit()
        return get_prospect(row["ref"], conn)  # type: ignore[return-value]
    finally:
        if close:
            conn.close()


def update_prospect(ref: str, data: dict, conn: Optional[sqlite3.Connection] = None) -> Optional[dict]:
    close = conn is None
    conn = conn or connect()
    try:
        row = _prep_writes(data)
        row.pop("ref", None)  # ref is immutable
        row["updated_at"] = now_iso()
        if not row:
            return get_prospect(ref, conn)
        assignments = ", ".join(f"{c} = ?" for c in row)
        conn.execute(
            f"UPDATE prospects SET {assignments} WHERE ref = ?",
            [*row.values(), ref],
        )
        conn.commit()
        return get_prospect(ref, conn)
    finally:
        if close:
            conn.close()


def delete_prospect(ref: str, conn: Optional[sqlite3.Connection] = None) -> None:
    close = conn is None
    conn = conn or connect()
    try:
        conn.execute("DELETE FROM prospects WHERE ref = ?", (ref,))
        conn.commit()
    finally:
        if close:
            conn.close()


def add_note(ref: str, text: str, conn: Optional[sqlite3.Connection] = None) -> Optional[dict]:
    close = conn is None
    conn = conn or connect()
    try:
        p = get_prospect(ref, conn)
        if not p:
            return None
        notes = p.get("notes") or []
        notes.append({"date": now_iso(), "text": text})
        return update_prospect(ref, {"notes": notes}, conn)
    finally:
        if close:
            conn.close()


# ── Checks (free visibility check, §7) ─────────────────────────────────────

_CHECK_COLS = [
    "prospect_id", "run_at", "prompts_json", "results_json", "mentioned_count",
    "platforms_tested", "competitors_json", "visibility_score",
    "report_html_path", "report_pdf_path", "cost_usd",
]


def insert_check(data: dict, conn: Optional[sqlite3.Connection] = None) -> int:
    """Insert a checks row. `data` keys match _CHECK_COLS (prospect_id is the
    integer PK, nullable for ad-hoc/inbound checks). Returns the new check id."""
    close = conn is None
    conn = conn or connect()
    try:
        row = {k: v for k, v in data.items() if k in _CHECK_COLS}
        row.setdefault("run_at", now_iso())
        cols = list(row.keys())
        placeholders = ", ".join("?" for _ in cols)
        cur = conn.execute(
            f"INSERT INTO checks ({', '.join(cols)}) VALUES ({placeholders})",
            [row[c] for c in cols],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        if close:
            conn.close()


# ── Suppression check (used by every outreach path, §8/§12) ───────────────

def is_suppressed(domain: str = "", email: str = "", company: str = "",
                  conn: Optional[sqlite3.Connection] = None) -> bool:
    close = conn is None
    conn = conn or connect()
    try:
        for field, val in (("domain", domain), ("email", email), ("company", company)):
            if val and conn.execute(
                f"SELECT 1 FROM suppressions WHERE {field} = ? LIMIT 1", (val,)
            ).fetchone():
                return True
        return False
    finally:
        if close:
            conn.close()


# ── Self-check ───────────────────────────────────────────────────────────

def _demo() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["GEO_SLAB_DB"] = str(Path(tmp) / "test.db")
        init_db()
        assert all_prospects() == []

        p1 = insert_prospect({"company": "Acme Ltd", "domain": "acme.com", "geo_score": 42})
        assert p1["id"] == "PRO-001", p1["id"]
        assert p1["pk"] == 1
        assert p1["geo_score"] == 42
        assert p1["notes"] == []

        p2 = insert_prospect({"company": "Beta LLP"})
        assert p2["id"] == "PRO-002", p2["id"]

        upd = update_prospect("PRO-001", {"status": "checked", "monthly_value": 497})
        assert upd["status"] == "checked"
        assert upd["monthly_value"] == 497
        assert upd["company"] == "Acme Ltd"  # untouched fields preserved

        withnote = add_note("PRO-001", "Called, no answer")
        assert len(withnote["notes"]) == 1
        assert withnote["notes"][0]["text"] == "Called, no answer"

        assert len(all_prospects()) == 2
        assert get_prospect("PRO-002")["company"] == "Beta LLP"

        delete_prospect("PRO-002")
        assert get_prospect("PRO-002") is None
        assert len(all_prospects()) == 1

        # ref generation skips gaps correctly (max+1, not count+1)
        p3 = insert_prospect({"company": "Gamma"})
        assert p3["id"] == "PRO-002", p3["id"]  # 002 freed, max was 001

        # suppressions
        conn = connect()
        conn.execute("INSERT INTO suppressions (domain, reason, added_at) VALUES (?,?,?)",
                     ("acme.com", "opted_out", now_iso()))
        conn.commit()
        conn.close()
        assert is_suppressed(domain="acme.com")
        assert not is_suppressed(domain="clean.com")

        # checks
        cid = insert_check({"prospect_id": p1["pk"], "visibility_score": 0,
                            "platforms_tested": 4, "mentioned_count": 0, "cost_usd": 0.012})
        assert isinstance(cid, int) and cid >= 1

    print("db.py self-check passed")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--init":
        init_db()
        print(f"Initialised {db_path()}")
    else:
        _demo()
