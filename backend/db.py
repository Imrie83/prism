"""
Database layer for Prism — Motor (async MongoDB).

Collections:
  scans       — scan metadata + email block
  screenshots — screenshot blobs (large, loaded on demand only)
  prospects   — discover prospects
"""

import os
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://mongo:27017")
_client: AsyncIOMotorClient | None = None


def _get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URL)
    return _client


def get_db():
    return _get_client()["prism"]


def scans_col():
    return get_db()["scans"]


def screenshots_col():
    return get_db()["screenshots"]


def prospects_col():
    return get_db()["prospects"]


async def ensure_indexes() -> None:
    """Create indexes on startup (idempotent)."""
    await scans_col().create_index("url", unique=True)
    await screenshots_col().create_index("url", unique=True)
    await prospects_col().create_index("website", unique=True)
    print("[db] ✓ MongoDB indexes ensured")


# ── Scans ─────────────────────────────────────────────────────────────────────


async def upsert_scan(data: dict) -> None:
    """Upsert scan metadata to scans collection, screenshot blob separately."""
    url = data.get("url", "")
    if not url:
        return
    existing = await scans_col().find_one({"url": url})
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
        "_tokens": data.get("_tokens"),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }
    if email_block:
        record["email"] = email_block
    await scans_col().update_one({"url": url}, {"$set": record}, upsert=True)
    screenshot = data.get("screenshot", "")
    if screenshot:
        await screenshots_col().update_one(
            {"url": url},
            {"$set": {"url": url, "screenshot_b64": screenshot}},
            upsert=True,
        )
    print(f"[db] upserted scan for {url}")


async def update_email(url: str, recipient: str, subject: str, html: str) -> None:
    """Update the email block for a scan record after sending."""
    existing = await scans_col().find_one({"url": url})
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
    await scans_col().update_one({"url": url}, {"$set": {"email": email_block}})
    print(f"[db] email record saved for {url} → {recipient}")


async def schedule_email(
    url: str,
    recipient: str,
    subject: str,
    html: str,
    scheduled_at: str,
    settings: dict,
) -> None:
    """Save an email with a scheduled_at time and the sending settings."""
    existing = await scans_col().find_one({"url": url})
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
    await scans_col().update_one({"url": url}, {"$set": {"email": email_block}})
    print(f"[db] email scheduled for {url} → {recipient} at {scheduled_at}")


async def cancel_scheduled_email(url: str) -> None:
    """Cancel a scheduled email by reverting to a draft state."""
    existing = await scans_col().find_one({"url": url})
    if not existing or not existing.get("email"):
        return
    email_block = dict(existing["email"])
    email_block.pop("scheduled_at", None)
    email_block.pop("settings", None)
    if email_block.get("status") == "scheduled":
        email_block["status"] = "draft"
    await scans_col().update_one({"url": url}, {"$set": {"email": email_block}})
    print(f"[db] email schedule canceled for {url}")


async def get_scheduled_emails() -> list:
    """Return a list of records that currently have a scheduled email."""
    cursor = scans_col().find({"email.status": "scheduled"})
    return await cursor.to_list(length=None)


async def get_full_scan(url: str) -> dict | None:
    """Return full scan record with screenshot joined from screenshots collection."""
    record = await scans_col().find_one({"url": url}, {"_id": 0})
    if not record:
        return None
    shot = await screenshots_col().find_one({"url": url}, {"_id": 0})
    if shot:
        record = {**record, "screenshot_b64": shot.get("screenshot_b64", "")}
    return record


async def get_email_statuses(urls: list[str]) -> dict:
    """Return {url: email_block} for a list of URLs — used for polling."""
    cursor = scans_col().find(
        {"url": {"$in": urls}}, {"_id": 0, "url": 1, "email": 1}
    )
    docs = await cursor.to_list(length=None)
    return {d["url"]: d.get("email") for d in docs}


async def get_global_settings() -> dict:
    """Return global settings from a special record in scans collection."""
    record = await scans_col().find_one({"type": "__global_settings__"})
    if not record:
        return {"bounce_check_interval": 10}
    return record.get("settings", {"bounce_check_interval": 10})


async def update_global_settings(settings: dict) -> None:
    """Update global settings in a special record in scans collection."""
    await scans_col().update_one(
        {"type": "__global_settings__"},
        {"$set": {"type": "__global_settings__", "settings": settings}},
        upsert=True,
    )
    print("[db] global settings updated")


# ── History queries (used by routes_history) ──────────────────────────────────


async def list_scans(
    page: int = 1,
    per_page: int = 20,
    sort_by: str = "scanned_at",
    sort_dir: int = -1,
    filter_email: str = "all",
    filter_score_min: int = 0,
    filter_score_max: int = 100,
    search: str = "",
) -> tuple[list, int]:
    """Paginated scan list for the History page."""
    query: dict = {"type": {"$ne": "__global_settings__"}}
    if filter_email == "sent":
        query["email.sent_at"] = {"$exists": True}
    elif filter_email == "scheduled":
        query["email.status"] = "scheduled"
    elif filter_email == "none":
        query["email"] = {"$exists": False}
    elif filter_email == "not_sent":
        query["$or"] = [
            {"email": {"$exists": False}},
            {"email.sent_at": {"$exists": False}},
        ]
    elif filter_email == "got_response":
        query["email.got_response"] = True
    elif filter_email == "bounced":
        query["email.status"] = "bounced"
    elif filter_email == "cant_deliver":
        query["email.status"] = "cant_deliver"
    elif filter_email == "dont_contact":
        query["email.status"] = "dont_contact"
    if filter_score_min > 0 or filter_score_max < 100:
        query["score"] = {"$gte": filter_score_min, "$lte": filter_score_max}
    if search:
        query["$or"] = [
            {"url": {"$regex": search, "$options": "i"}},
            {"title": {"$regex": search, "$options": "i"}},
        ]

    total = await scans_col().count_documents(query)
    skip = (page - 1) * per_page
    cursor = (
        scans_col()
        .find(query, {"_id": 0, "issues": 0})
        .sort(sort_by, sort_dir)
        .skip(skip)
        .limit(per_page)
    )
    records = await cursor.to_list(length=per_page)
    return records, total


async def delete_scan(url: str) -> bool:
    """Delete a scan record and its screenshot."""
    r1 = await scans_col().delete_one({"url": url})
    await screenshots_col().delete_one({"url": url})
    return r1.deleted_count > 0


async def toggle_got_response(url: str) -> bool:
    """Flip email.got_response for a scan. Returns new value."""
    existing = await scans_col().find_one({"url": url})
    if not existing:
        return False
    current = existing.get("email", {}).get("got_response", False)
    new_val = not current
    await scans_col().update_one(
        {"url": url}, {"$set": {"email.got_response": new_val}}
    )
    return new_val


async def set_dont_contact(url: str, status: str) -> None:
    """Set email.status for dont_contact toggling."""
    await scans_col().update_one(
        {"url": url}, {"$set": {"email.status": status}}, upsert=False
    )


async def save_email_draft(url: str, html: str) -> None:
    """Save draft email HTML without marking as sent."""
    await scans_col().update_one(
        {"url": url},
        {"$set": {"email.html": html}},
        upsert=False,
    )


async def update_email_recipient(url: str, recipient: str) -> None:
    await scans_col().update_one(
        {"url": url}, {"$set": {"email.recipient": recipient}}, upsert=False
    )


async def save_email_subject(url: str, subject: str) -> None:
    await scans_col().update_one(
        {"url": url}, {"$set": {"email.subject": subject}}, upsert=False
    )


# ── Prospects (Discover) ───────────────────────────────────────────────────────


async def upsert_prospect(data: dict) -> None:
    website = data.get("website", "")
    if not website:
        return
    await prospects_col().update_one(
        {"website": website}, {"$set": data}, upsert=True
    )


async def list_prospects(
    page: int = 1,
    per_page: int = 25,
    sort_by: str = "discovered_at",
    sort_dir: int = -1,
    filter_status: str = "all",
    filter_has_email: str = "all",
    search: str = "",
) -> tuple[list, int]:
    query: dict = {}
    if filter_status != "all":
        query["status"] = filter_status
    if filter_has_email == "yes":
        query["email"] = {"$exists": True, "$ne": ""}
    elif filter_has_email == "no":
        # Use $and to avoid collision if search also needs $or
        query["$and"] = [{"$or": [{"email": {"$exists": False}}, {"email": ""}]}]
    if search:
        search_clause = {"$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"website": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]}
        if "$and" in query:
            query["$and"].append(search_clause)
        else:
            query.update(search_clause)
    total = await prospects_col().count_documents(query)
    skip = (page - 1) * per_page
    cursor = (
        prospects_col()
        .find(query, {"_id": 0})
        .sort(sort_by, sort_dir)
        .skip(skip)
        .limit(per_page)
    )
    records = await cursor.to_list(length=per_page)
    return records, total


async def get_prospect(website: str) -> dict | None:
    return await prospects_col().find_one({"website": website}, {"_id": 0})


async def update_prospect_status(website: str, status: str) -> None:
    await prospects_col().update_one(
        {"website": website}, {"$set": {"status": status}}, upsert=False
    )


async def update_prospect_email(website: str, email: str) -> None:
    await prospects_col().update_one(
        {"website": website}, {"$set": {"email": email}}, upsert=False
    )


async def delete_prospects(websites: list[str]) -> int:
    r = await prospects_col().delete_many({"website": {"$in": websites}})
    return r.deleted_count


async def toggle_prospect_response(website: str) -> bool:
    doc = await prospects_col().find_one({"website": website})
    if not doc:
        return False
    new_val = not doc.get("email_got_response", False)
    await prospects_col().update_one(
        {"website": website}, {"$set": {"email_got_response": new_val}}
    )
    return new_val
