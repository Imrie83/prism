"""
History API routes — /api/history/*
"""

from fastapi import APIRouter, HTTPException

from .db import (
    list_scans,
    get_full_scan,
    delete_scan,
    toggle_got_response,
    set_dont_contact,
    save_email_draft,
    update_email_recipient,
    save_email_subject,
    upsert_scan,
    get_email_statuses,
    get_global_settings,
    update_global_settings,
    scans_col,
)
from .models import SaveEmailDraftRequest

router = APIRouter()

SORT_MAP = {
    "scanned_at": "scanned_at",
    "score": "score",
    "total_issues": "total_issues",
    "email_sent": "email.sent_at",
}


@router.get("/api/history")
async def get_history(
    page: int = 1,
    per_page: int = 20,
    sort_by: str = "scanned_at",
    sort_dir: str = "desc",
    filter_email: str = "all",
    filter_score_min: int = 0,
    filter_score_max: int = 100,
    search: str = "",
):
    """Paginated, sortable, filterable list of scan records."""
    mongo_sort = SORT_MAP.get(sort_by, "scanned_at")
    mongo_dir = -1 if sort_dir == "desc" else 1
    records, total = await list_scans(
        page=page,
        per_page=per_page,
        sort_by=mongo_sort,
        sort_dir=mongo_dir,
        filter_email=filter_email,
        filter_score_min=filter_score_min,
        filter_score_max=filter_score_max,
        search=search,
    )
    slim = []
    for r in records:
        slim.append(
            {
                "url": r.get("url"),
                "scan_mode": r.get("scan_mode"),
                "score": r.get("score"),
                "title": r.get("title"),
                "total_issues": r.get("total_issues"),
                "issue_counts": r.get("issue_counts"),
                "scanned_at": r.get("scanned_at"),
                "email": {
                    "recipient": r.get("email", {}).get("recipient"),
                    "sent_at": r.get("email", {}).get("sent_at"),
                    "status": r.get("email", {}).get("status"),
                    "scheduled_at": r.get("email", {}).get("scheduled_at"),
                    "got_response": r.get("email", {}).get("got_response", False),
                }
                if r.get("email")
                else None,
            }
        )
    return {"records": slim, "total": total, "page": page, "per_page": per_page}


@router.get("/api/settings")
async def get_settings():
    """Return global server-side settings."""
    return await get_global_settings()


@router.post("/api/settings")
async def update_settings(body: dict):
    """Update global server-side settings."""
    await update_global_settings(body)
    return {"ok": True}


@router.get("/api/history/check")
async def check_history(url: str):
    """Check if a URL has been scanned. Returns lightweight record summary."""
    record = await scans_col().find_one({"url": url}, {"_id": 0, "issues": 0})
    if not record:
        return {"exists": False}
    return {
        "exists": True,
        "score": record.get("score"),
        "title": record.get("title"),
        "scanned_at": record.get("scanned_at"),
        "email": {
            "recipient": record.get("email", {}).get("recipient"),
            "sent_at": record.get("email", {}).get("sent_at"),
            "status": record.get("email", {}).get("status"),
            "scheduled_at": record.get("email", {}).get("scheduled_at"),
            "got_response": record.get("email", {}).get("got_response", False),
        }
        if record.get("email")
        else None,
    }


@router.get("/api/history/entry")
async def get_history_entry(url: str):
    """Full scan record including screenshot — for rehydrating the results page."""
    record = await get_full_scan(url)
    if not record:
        raise HTTPException(404, "No record found for this URL")
    return record


@router.patch("/api/history/response")
async def toggle_response(url: str):
    """Toggle got_response flag."""
    new_val = await toggle_got_response(url)
    return {"got_response": new_val}


@router.delete("/api/history/entry")
async def delete_history_entry(url: str):
    """Delete a scan record and its screenshot."""
    ok = await delete_scan(url)
    if not ok:
        raise HTTPException(404, "No record found for this URL")
    return {"ok": True}


@router.post("/api/history/save-email")
async def save_email_draft_route(url: str, subject: str, body: SaveEmailDraftRequest):
    """Save a generated email draft (not yet sent)."""
    await save_email_subject(url, subject)
    await save_email_draft(url, body.html)
    return {"ok": True}


@router.post("/api/history/update-email-recipient")
async def update_email_recipient_route(url: str, recipient: str):
    """Update recipient address when user edits it in the email drawer."""
    await update_email_recipient(url, recipient)
    return {"ok": True}


@router.patch("/api/history/status")
async def update_history_status(body: dict):
    """Update status indicator (like dont_contact) for a history record."""
    url = body.get("url")
    status = body.get("status")
    if not url:
        raise HTTPException(400, "url required")
    await set_dont_contact(url, status)
    return {"ok": True}


@router.post("/api/history/save-deep-scan")
async def save_deep_scan(body: dict):
    """Explicitly save a deep scan to history."""
    try:
        await upsert_scan(body)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/api/history/full-check")
async def check_url_in_history(url: str):
    """Full record check including email state (used by batch pre-scan check)."""
    record = await scans_col().find_one({"url": url}, {"_id": 0, "issues": 0})
    if not record:
        return {"exists": False}
    return {"exists": True, "record": record}


@router.get("/api/email-status")
async def get_email_status_bulk(urls: str):
    """Poll email statuses for a comma-separated list of URLs.
    Used by the frontend to update status without a full page refresh.
    """
    url_list = [u.strip() for u in urls.split(",") if u.strip()]
    if not url_list:
        return {}
    statuses = await get_email_statuses(url_list)
    return statuses
