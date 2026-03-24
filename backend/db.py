"""
Database layer for Prism.

Split storage pattern:
  scans.json       — scan metadata (fast reads, used for history listing)
  screenshots.json — screenshot blobs (large, loaded on demand only)
  prospects.json   — discover prospects
"""

import os
from datetime import datetime, timezone

from tinydb import TinyDB, Query

os.makedirs("/app/data", exist_ok=True)

scans_db = TinyDB("/app/data/scans.json", indent=2, ensure_ascii=False)
screenshots_db = TinyDB("/app/data/screenshots.json", indent=2, ensure_ascii=False)
prospects_db = TinyDB("/app/data/prospects.json", indent=2, ensure_ascii=False)
ScanRecord = Query()
ProspectRecord = Query()


def migrate_legacy_db() -> None:
    """One-time migration: split legacy db.json → scans.json + screenshots.json.
    Runs on startup only if db.json exists and hasn't been migrated yet.
    """
    legacy_path = "/app/data/db.json"
    bak_path = "/app/data/db.json.bak"
    if not os.path.exists(legacy_path):
        return
    print("[db] legacy db.json found — migrating to scans.json + screenshots.json...")
    try:
        legacy = TinyDB(legacy_path, indent=2, ensure_ascii=False)
        records = legacy.all()
        migrated = 0
        for r in records:
            url = r.get("url", "")
            if not url:
                continue
            screenshot = r.pop("screenshot_b64", "") or ""
            scans_db.upsert(r, ScanRecord.url == url)
            if screenshot:
                screenshots_db.upsert(
                    {"url": url, "screenshot_b64": screenshot},
                    ScanRecord.url == url,
                )
            migrated += 1
        legacy.close()
        os.rename(legacy_path, bak_path)
        print(f"[db] ✓ migrated {migrated} records — db.json → db.json.bak")
    except Exception as e:
        print(f"[db] ⚠ migration failed: {e}")


def upsert_scan(data: dict) -> None:
    """Upsert scan metadata to scans.json, screenshot blob to screenshots.json."""
    url = data.get("url", "")
    if not url:
        return
    existing = scans_db.get(ScanRecord.url == url)
    email_block = existing.get("email") if existing else None
    record = {
        "emails_found": data.get("emails_found", []),
        "url": url,
        "scan_mode": data.get("scan_mode", "shallow"),
        "score": data.get("score", 0),
        "title": data.get("title", ""),
        "summary": data.get("summary", ""),
        "total_issues": data.get("totalIssues", 0),
        "issue_counts": data.get("issueCounts", {}),
        "issues": data.get("issues", []),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }
    if email_block:
        record["email"] = email_block
    scans_db.upsert(record, ScanRecord.url == url)
    screenshot = data.get("screenshot", "")
    if screenshot:
        screenshots_db.upsert(
            {"url": url, "screenshot_b64": screenshot},
            ScanRecord.url == url,
        )
    print(f"[db] upserted scan for {url}")


def update_email(url: str, recipient: str, subject: str, html: str) -> None:
    """Update the email block for a scan record after sending."""
    existing = scans_db.get(ScanRecord.url == url)
    if not existing:
        print(f"[db] ⚠ no scan record for {url} — email block not saved")
        return
    email_block = {
        "recipient": recipient,
        "subject": subject,
        "html": html,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "got_response": existing.get("email", {}).get("got_response", False),
    }
    scans_db.update({"email": email_block}, ScanRecord.url == url)
    print(f"[db] email record saved for {url} → {recipient}")


def schedule_email(url: str, recipient: str, subject: str, html: str, scheduled_at: str, settings: dict) -> None:
    """Save an email with a scheduled_at time and the sending settings."""
    existing = scans_db.get(ScanRecord.url == url)
    if not existing:
        print(f"[db] ⚠ no scan record for {url} — cannot schedule email")
        return
    email_block = {
        "recipient": recipient,
        "subject": subject,
        "html": html,
        "scheduled_at": scheduled_at,
        "status": "scheduled",
        "settings": settings,
        "got_response": existing.get("email", {}).get("got_response", False),
    }
    scans_db.update({"email": email_block}, ScanRecord.url == url)
    print(f"[db] email scheduled for {url} → {recipient} at {scheduled_at}")


def cancel_scheduled_email(url: str) -> None:
    """Cancel a scheduled email by reverting to a draft state."""
    existing = scans_db.get(ScanRecord.url == url)
    if not existing or not existing.get("email"):
        return
    email_block = existing["email"]
    if "scheduled_at" in email_block:
        del email_block["scheduled_at"]
    if "settings" in email_block:
        del email_block["settings"]
    if email_block.get("status") == "scheduled":
        email_block["status"] = "draft"
    scans_db.update({"email": email_block}, ScanRecord.url == url)
    print(f"[db] email schedule canceled for {url}")


def get_scheduled_emails() -> list:
    """Return a list of records that currently have a scheduled email."""
    return [r for r in scans_db.all() if r.get("email", {}).get("status") == "scheduled"]


def get_full_scan(url: str) -> dict | None:
    """Return full scan record with screenshot joined from screenshots.json."""
    record = scans_db.get(ScanRecord.url == url)
    if not record:
        return None
    shot = screenshots_db.get(ScanRecord.url == url)
    if shot:
        record = {**record, "screenshot_b64": shot.get("screenshot_b64", "")}
    return record


# Run migration on import (safe — no-op if already done)
migrate_legacy_db()
