#!/usr/bin/env python3
"""
migrate_tinydb_to_mongo.py
──────────────────────────
One-shot migration: reads TinyDB JSON files from ./data/ and imports
everything into MongoDB.

Usage
-----
Windows (cmd):
  set DRY_RUN=1 && python migrate_tinydb_to_mongo.py
  python migrate_tinydb_to_mongo.py

Windows (PowerShell):
  $env:DRY_RUN="1"; python migrate_tinydb_to_mongo.py
  python migrate_tinydb_to_mongo.py

Mac / Linux:
  DRY_RUN=1 python3 migrate_tinydb_to_mongo.py
  python3 migrate_tinydb_to_mongo.py

Or pass --dry-run as a command-line flag (works everywhere):
  python migrate_tinydb_to_mongo.py --dry-run
  python migrate_tinydb_to_mongo.py

Environment variables (all optional):
  MONGO_URL   MongoDB connection string   (default: mongodb://localhost:27017)
  DATA_DIR    folder containing *.json    (default: ./data)
  DRY_RUN     set to "1" to preview       (default: 0)
"""

import json
import os
import sys

# ── Config — env vars OR command-line flag ────────────────────────────────────

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DATA_DIR  = os.environ.get("DATA_DIR",  "./data")
DRY_RUN   = os.environ.get("DRY_RUN", "0") == "1" or "--dry-run" in sys.argv


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_tinydb(path: str) -> list[dict]:
    """Read a TinyDB JSON file and return all records as a plain list."""
    if not os.path.exists(path):
        print(f"  (file not found: {path} — skipping)")
        return []
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    # TinyDB stores records under a "_default" table key, values are dicts
    # keyed by string integer IDs: {"_default": {"1": {...}, "2": {...}}}
    table = raw.get("_default", raw)
    records = list(table.values()) if isinstance(table, dict) else []
    return records


def strip_tinydb_internals(rec: dict) -> dict:
    """Remove TinyDB internal keys that shouldn't go into Mongo."""
    return {k: v for k, v in rec.items() if not k.startswith("_")}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    try:
        from pymongo import MongoClient, UpdateOne
        from pymongo.errors import BulkWriteError
    except ImportError:
        print("ERROR: pymongo not installed.")
        print("  Run:  pip install pymongo")
        sys.exit(1)

    mode = "[DRY RUN] " if DRY_RUN else ""
    print(f"{mode}Connecting to {MONGO_URL} ...")
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        print("✓ MongoDB connection OK")
    except Exception as e:
        print(f"✗ Cannot connect to MongoDB: {e}")
        print("  Make sure MongoDB / Docker is running.")
        print("  Tip:  docker compose up mongo -d")
        sys.exit(1)

    db = client["prism"]

    # ── 1. Scans ──────────────────────────────────────────────────────────────
    scans_path = os.path.join(DATA_DIR, "scans.json")
    scans = load_tinydb(scans_path)
    print(f"\nScans: found {len(scans)} records in {scans_path}")

    if scans and not DRY_RUN:
        ops, skipped = [], 0
        for rec in scans:
            rec = strip_tinydb_internals(rec)
            url = rec.get("url", "")
            if not url:
                skipped += 1
                continue
            ops.append(UpdateOne({"url": url}, {"$set": rec}, upsert=True))
        if ops:
            try:
                r = db["scans"].bulk_write(ops, ordered=False)
                print(f"  ✓ Upserted {r.upserted_count} new | modified {r.modified_count} | skipped {skipped} (no URL)")
            except BulkWriteError as e:
                print(f"  ⚠ Partial write: {e.details}")
    elif DRY_RUN and scans:
        for rec in scans[:3]:
            print(f"  preview: url={rec.get('url','?')}  score={rec.get('score','?')}  scanned_at={rec.get('scanned_at','?')}")
        if len(scans) > 3:
            print(f"  ... and {len(scans)-3} more")

    # ── 2. Screenshots ────────────────────────────────────────────────────────
    shots_path = os.path.join(DATA_DIR, "screenshots.json")
    shots = load_tinydb(shots_path)
    print(f"\nScreenshots: found {len(shots)} records in {shots_path}")

    if shots and not DRY_RUN:
        ops, skipped = [], 0
        for rec in shots:
            rec = strip_tinydb_internals(rec)
            url = rec.get("url", "")
            if not url:
                skipped += 1
                continue
            ops.append(UpdateOne({"url": url}, {"$set": rec}, upsert=True))
        if ops:
            try:
                r = db["screenshots"].bulk_write(ops, ordered=False)
                total_kb = sum(len(rec.get("screenshot_b64", "")) // 1024 for rec in shots)
                print(f"  ✓ Upserted {r.upserted_count} new | modified {r.modified_count} | ~{total_kb} KB total | skipped {skipped}")
            except BulkWriteError as e:
                print(f"  ⚠ Partial write: {e.details}")
    elif DRY_RUN and shots:
        for rec in shots[:3]:
            size_kb = len(rec.get("screenshot_b64", "")) // 1024
            print(f"  preview: url={rec.get('url','?')}  screenshot={size_kb} KB")
        if len(shots) > 3:
            print(f"  ... and {len(shots)-3} more")

    # ── 3. Prospects ──────────────────────────────────────────────────────────
    prospects_path = os.path.join(DATA_DIR, "prospects.json")
    prospects = load_tinydb(prospects_path)
    print(f"\nProspects: found {len(prospects)} records in {prospects_path}")

    if prospects and not DRY_RUN:
        ops, skipped = [], 0
        for rec in prospects:
            rec = strip_tinydb_internals(rec)
            website = rec.get("website", "")
            if not website:
                skipped += 1
                continue
            ops.append(UpdateOne({"website": website}, {"$set": rec}, upsert=True))
        if ops:
            try:
                r = db["prospects"].bulk_write(ops, ordered=False)
                print(f"  ✓ Upserted {r.upserted_count} new | modified {r.modified_count} | skipped {skipped} (no website)")
            except BulkWriteError as e:
                print(f"  ⚠ Partial write: {e.details}")
    elif DRY_RUN and prospects:
        for rec in prospects[:3]:
            print(f"  preview: name={rec.get('name','?')}  website={rec.get('website','?')}  status={rec.get('status','?')}")
        if len(prospects) > 3:
            print(f"  ... and {len(prospects)-3} more")

    # ── 4. Indexes ────────────────────────────────────────────────────────────
    if not DRY_RUN:
        print("\nEnsuring indexes...")
        db["scans"].create_index("url", unique=True)
        db["screenshots"].create_index("url", unique=True)
        db["prospects"].create_index("website", unique=True)
        print("  ✓ Indexes OK")

    # ── Summary ───────────────────────────────────────────────────────────────
    if not DRY_RUN:
        print("\n── Final counts in MongoDB ──")
        print(f"  scans:       {db['scans'].count_documents({})}")
        print(f"  screenshots: {db['screenshots'].count_documents({})}")
        print(f"  prospects:   {db['prospects'].count_documents({})}")
        print("\n✓ Migration complete.")
        print("\nYou can now archive the old JSON files:")
        print("  Windows:  rename data\\scans.json scans.json.bak")
        print("  Mac/Linux: mv data/scans.json data/scans.json.bak")
    else:
        print("\n[DRY RUN complete — nothing was written]")
        print("Run without --dry-run to actually migrate.")


if __name__ == "__main__":
    main()
