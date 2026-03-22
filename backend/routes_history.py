"""
History API routes — /api/history/*
"""
from fastapi import APIRouter, HTTPException

from .db import (
    scans_db, screenshots_db, ScanRecord,
    upsert_scan, get_full_scan,
)
from .models import SaveEmailDraftRequest

router = APIRouter()


@router.get("/api/history")
async def get_history(
    page: int = 1,
    per_page: int = 20,
    sort_by: str = "scanned_at",
    sort_dir: str = "desc",
    filter_email: str = "all",
    filter_score_min: int = 0,
    filter_score_max: int = 100,
):
    """Paginated, sortable, filterable list of scan records (no screenshot blobs)."""
    all_records = scans_db.all()

    # Filter
    if filter_email == "sent":
        all_records = [r for r in all_records if r.get("email", {}).get("sent_at")]
    elif filter_email == "not_sent":
        all_records = [r for r in all_records if not r.get("email", {}).get("sent_at")]
    elif filter_email == "got_response":
        all_records = [r for r in all_records if r.get("email", {}).get("got_response")]

    if filter_score_min > 0 or filter_score_max < 100:
        all_records = [
            r for r in all_records
            if filter_score_min <= (r.get("score") or 0) <= filter_score_max
        ]

    # Sort
    reverse = sort_dir == "desc"
    if sort_by == "score":
        all_records.sort(key=lambda r: r.get("score") or 0, reverse=reverse)
    elif sort_by == "total_issues":
        all_records.sort(key=lambda r: r.get("total_issues") or 0, reverse=reverse)
    elif sort_by == "email_sent":
        all_records.sort(key=lambda r: r.get("email", {}).get("sent_at") or "", reverse=reverse)
    else:
        all_records.sort(key=lambda r: r.get("scanned_at", ""), reverse=reverse)

    total        = len(all_records)
    start        = (page - 1) * per_page
    page_records = all_records[start:start + per_page]

    slim = []
    for r in page_records:
        slim.append({
            "url":          r.get("url"),
            "scan_mode":    r.get("scan_mode"),
            "score":        r.get("score"),
            "title":        r.get("title"),
            "total_issues": r.get("total_issues"),
            "issue_counts": r.get("issue_counts"),
            "scanned_at":   r.get("scanned_at"),
            "email": {
                "recipient":    r.get("email", {}).get("recipient"),
                "sent_at":      r.get("email", {}).get("sent_at"),
                "got_response": r.get("email", {}).get("got_response", False),
            } if r.get("email") else None,
        })
    return {"records": slim, "total": total, "page": page, "per_page": per_page}


@router.get("/api/history/check")
async def check_history(url: str):
    """Check if a URL has been scanned. Returns lightweight record summary."""
    record = scans_db.get(ScanRecord.url == url)
    if not record:
        return {"exists": False}
    return {
        "exists":     True,
        "score":      record.get("score"),
        "title":      record.get("title"),
        "scanned_at": record.get("scanned_at"),
        "email": {
            "recipient":    record.get("email", {}).get("recipient"),
            "sent_at":      record.get("email", {}).get("sent_at"),
            "got_response": record.get("email", {}).get("got_response", False),
        } if record.get("email") else None,
    }


@router.get("/api/history/entry")
async def get_history_entry(url: str):
    """Full scan record including screenshot — for rehydrating the results page."""
    record = get_full_scan(url)
    if not record:
        raise HTTPException(404, "No record found for this URL")
    return record


@router.patch("/api/history/response")
async def toggle_response(url: str):
    """Toggle got_response flag."""
    record = scans_db.get(ScanRecord.url == url)
    if not record or not record.get("email"):
        raise HTTPException(404, "No email record found for this URL")
    current     = record["email"].get("got_response", False)
    email_block = {**record["email"], "got_response": not current}
    scans_db.update({"email": email_block}, ScanRecord.url == url)
    return {"got_response": not current}


@router.delete("/api/history/entry")
async def delete_history_entry(url: str):
    """Delete a scan record and its screenshot."""
    removed = scans_db.remove(ScanRecord.url == url)
    screenshots_db.remove(ScanRecord.url == url)
    if not removed:
        raise HTTPException(404, "No record found for this URL")
    return {"ok": True}


@router.post("/api/history/save-email")
async def save_email_draft(url: str, subject: str, body: SaveEmailDraftRequest):
    """Save a generated email draft (not yet sent)."""
    record = scans_db.get(ScanRecord.url == url)
    if not record:
        raise HTTPException(404, "No scan record for this URL")
    existing_email = record.get("email") or {}
    scans_db.update(
        {"email": {**existing_email, "subject": subject, "html": body.html}},
        ScanRecord.url == url,
    )
    return {"ok": True}


@router.post("/api/history/update-email-recipient")
async def update_email_recipient(url: str, recipient: str):
    """Update recipient address when user edits it in the email drawer."""
    record = scans_db.get(ScanRecord.url == url)
    if not record:
        return {"ok": False}
    existing_email = record.get("email") or {}
    scans_db.update(
        {"email": {**existing_email, "recipient": recipient}},
        ScanRecord.url == url,
    )
    return {"ok": True}


@router.post("/api/history/save-deep-scan")
async def save_deep_scan(body: dict):
    """Explicitly save a deep scan to history."""
    try:
        upsert_scan(body)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/api/history/full-check")
async def check_url_in_history(url: str):
    """Full record check including email state (used by batch pre-scan check)."""
    record = scans_db.get(ScanRecord.url == url)
    if not record:
        return {"exists": False}
    return {"exists": True, "record": record}
