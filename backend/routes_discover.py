"""
Discover API routes — /api/discover/*
"""

import json
import os
import time
import uuid

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .db import scans_db, prospects_db, ProspectRecord
from .models import DiscoverSearchRequest

router = APIRouter()


@router.post("/api/discover/search")
async def discover_search(req: DiscoverSearchRequest):
    """Scrape Google Maps — streams NDJSON progress events, final line is the result."""
    session_id = str(uuid.uuid4())[:8]
    scanned_urls = {r.get("url", "") for r in scans_db.all()}
    print(
        f"[discover] session={session_id} keywords={req.keywords!r} location={req.location!r} limit={req.limit}"
    )

    async def stream():
        saved = []
        skipped_no_website = 0
        skipped_already_scanned = 0

        svc_url = os.environ.get("DISCOVER_SERVICE_URL", "http://discover:3001")
        async with httpx.AsyncClient(timeout=900.0) as client:
            async with client.stream(
                "POST",
                f"{svc_url}/discover",
                json={
                    "keywords": req.keywords,
                    "location": req.location,
                    "limit": req.limit,
                },
            ) as r:
                r.raise_for_status()
                buffer = ""
                async for chunk in r.aiter_text():
                    buffer += chunk
                    lines = buffer.split("\n")
                    buffer = lines.pop()
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                        except Exception:
                            continue

                        if event.get("type") == "done":
                            # Demote existing "new" records from other sessions to "pending"
                            # so only the current session's results show as "New"
                            prospects_db.update(
                                {"status": "pending"},
                                (ProspectRecord.status == "new")
                                & (ProspectRecord.session_id != session_id),
                            )
                            for biz in event.get("businesses", []):
                                website = (biz.get("website") or "").strip()
                                if not website:
                                    skipped_no_website += 1
                                    continue
                                if not website.startswith("http"):
                                    website = "https://" + website
                                biz["website"] = website
                                if website in scanned_urls:
                                    skipped_already_scanned += 1
                                    continue
                                biz["session_id"] = session_id
                                biz["keywords"] = req.keywords
                                biz["location"] = req.location
                                biz["status"] = "new"
                                biz["discovered_at"] = time.strftime(
                                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                                )
                                existing = prospects_db.get(
                                    ProspectRecord.website == website
                                )
                                if not existing:
                                    prospects_db.insert(biz)
                                elif existing.get("status") not in (
                                    "scanned",
                                    "emailed",
                                ):
                                    prospects_db.update(
                                        biz, ProspectRecord.website == website
                                    )
                                saved.append(biz)

                            print(
                                f"[discover] saved={len(saved)} skipped_no_site={skipped_no_website} skipped_scanned={skipped_already_scanned}"
                            )
                            yield (
                                json.dumps(
                                    {
                                        "type": "result",
                                        "session_id": session_id,
                                        "total_found": len(event.get("businesses", [])),
                                        "saved": len(saved),
                                        "skipped_no_website": skipped_no_website,
                                        "skipped_already_scanned": skipped_already_scanned,
                                    }
                                ).encode()
                                + b"\n"
                            )
                        else:
                            yield json.dumps(event).encode() + b"\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@router.get("/api/discover/prospects")
async def get_prospects(
    session_id: str | None = None,
    sort_by: str = "discovered_at",
    sort_dir: str = "desc",
    filter_status: str = "all",
    filter_has_email: str = "all",
):
    """Return saved prospects, optionally filtered by session."""
    records = prospects_db.all()

    if session_id:
        records = [r for r in records if r.get("session_id") == session_id]
    if filter_status != "all":
        records = [r for r in records if r.get("status") == filter_status]
    if filter_has_email == "yes":
        records = [r for r in records if r.get("email")]
    elif filter_has_email == "no":
        records = [r for r in records if not r.get("email")]

    reverse = sort_dir == "desc"
    if sort_by == "rating":
        records.sort(key=lambda r: float(r.get("rating") or 0), reverse=reverse)
    elif sort_by == "name":
        records.sort(key=lambda r: r.get("name", ""), reverse=reverse)
    elif sort_by == "status":
        records.sort(key=lambda r: r.get("status", ""), reverse=reverse)
    else:
        records.sort(key=lambda r: r.get("discovered_at", ""), reverse=reverse)

    return {"records": records, "total": len(records)}


@router.get("/api/discover/sessions")
async def get_sessions():
    """Return distinct discover sessions with metadata."""
    records = prospects_db.all()
    sessions: dict = {}
    for r in records:
        sid = r.get("session_id")
        if not sid:
            continue
        if sid not in sessions:
            sessions[sid] = {
                "session_id": sid,
                "keywords": r.get("keywords", ""),
                "location": r.get("location", ""),
                "discovered_at": r.get("discovered_at", ""),
                "count": 0,
                "scanned": 0,
            }
        sessions[sid]["count"] += 1
        if r.get("status") in ("scanned", "emailed"):
            sessions[sid]["scanned"] += 1
    return {
        "sessions": sorted(
            sessions.values(), key=lambda s: s["discovered_at"], reverse=True
        )
    }


@router.get("/api/discover/prospect")
async def get_prospect(website: str):
    """Look up a single prospect by website URL."""
    record = prospects_db.get(ProspectRecord.website == website)
    if not record:
        return {"record": None}
    return {"record": record}


@router.patch("/api/discover/status")
async def update_prospect_status(body: dict):
    website = body.get("website")
    status = body.get("status")
    if not website or not status:
        raise HTTPException(400, "website and status required")
    prospects_db.update({"status": status}, ProspectRecord.website == website)
    return {"ok": True}


@router.delete("/api/discover/prospect")
async def delete_prospect(website: str):
    prospects_db.remove(ProspectRecord.website == website)
    return {"ok": True}


@router.patch("/api/discover/email")
async def update_prospect_email(body: dict):
    website = body.get("website")
    email = body.get("email")
    if not website:
        raise HTTPException(400, "website required")
    prospects_db.update({"email": email}, ProspectRecord.website == website)
    return {"ok": True}
