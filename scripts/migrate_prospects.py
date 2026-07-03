#!/usr/bin/env python3
"""
One-shot migration: ~/.geo-slab/prospects.json → SQLite (geo-slab.db).

Idempotent. Preserves existing PRO-xxx refs. Skips any ref already in the DB,
so re-running is safe. If prospects.json does not exist, reports nothing to do.

    python3 scripts/migrate_prospects.py
"""

from __future__ import annotations

import json
from pathlib import Path

import db

JSON_PATH = Path.home() / ".geo-slab" / "prospects.json"


def main() -> None:
    db.init_db()

    if not JSON_PATH.exists():
        print(f"No {JSON_PATH} — nothing to migrate. DB initialised at {db.db_path()}")
        return

    records = json.loads(JSON_PATH.read_text())
    conn = db.connect()
    existing = {r["ref"] for r in conn.execute("SELECT ref FROM prospects WHERE ref IS NOT NULL")}

    imported = skipped = 0
    for rec in records:
        ref = rec.get("id")  # old flat file used `id` = PRO-xxx
        if ref and ref in existing:
            skipped += 1
            continue
        data = dict(rec)
        data["ref"] = ref  # keep continuity
        data.pop("id", None)
        db.insert_prospect(data, conn)
        imported += 1

    conn.close()
    print(f"Migrated {imported} prospect(s), skipped {skipped} already present → {db.db_path()}")


if __name__ == "__main__":
    main()
