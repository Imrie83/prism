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

from .db import (
    prospects_col,
    scans_col,
    list_prospects,
    get_prospect,
    upsert_prospect,
    update_prospect_status,
    update_prospect_email,
    delete_prospects,
    toggle_prospect_response,
)
from .models import DiscoverSearchRequest

router = APIRouter()


@router.post("/api/discover/search")
async def discover_search(req: DiscoverSearchRequest):
    """Scrape Google Maps — streams NDJSON progress events, final line is the result."""
    session_id = str(uuid.uuid4())[:8]
    # Collect already-scanned URLs (from scan history)
    cursor = scans_col().find({}, {"_id": 0, "url": 1})
    scanned_docs = await cursor.to_list(length=None)
    scanned_urls = {d["url"] for d in scanned_docs if d.get("url")}
    # Collect already-discovered websites (from prospects) — skip these too
    cursor2 = prospects_col().find({}, {"_id": 0, "website": 1})
    prospect_docs = await cursor2.to_list(length=None)
    known_websites = {d["website"] for d in prospect_docs if d.get("website")}
    print(
        f"[discover] session={session_id} keywords={req.keywords!r} location={req.location!r} limit={req.limit} "
        f"(skipping {len(scanned_urls)} scanned + {len(known_websites)} already-discovered)"
    )

    async def stream():
        saved = []
        skipped_no_website = 0
        skipped_already_scanned = 0
        skipped_already_discovered = 0

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
                            # Demote "new" records from other sessions to "pending"
                            await prospects_col().update_many(
                                {
                                    "status": "new",
                                    "session_id": {"$ne": session_id},
                                },
                                {"$set": {"status": "pending"}},
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
                                if website in known_websites:
                                    skipped_already_discovered += 1
                                    continue
                                biz["session_id"] = session_id
                                biz["keywords"] = req.keywords
                                biz["location"] = req.location
                                biz["status"] = "new"
                                biz["discovered_at"] = time.strftime(
                                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                                )
                                await prospects_col().insert_one(biz)
                                known_websites.add(website)  # prevent duplicates within this batch
                                saved.append(biz)

                            print(
                                f"[discover] saved={len(saved)} skipped_no_site={skipped_no_website} "
                                f"skipped_scanned={skipped_already_scanned} "
                                f"skipped_discovered={skipped_already_discovered}"
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
                                        "skipped_already_discovered": skipped_already_discovered,
                                    }
                                ).encode()
                                + b"\n"
                            )
                        else:
                            yield json.dumps(event).encode() + b"\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@router.get("/api/discover/prospects")
async def get_prospects(
    page: int = 1,
    per_page: int = 500,
    sort_by: str = "discovered_at",
    sort_dir: str = "desc",
    filter_status: str = "all",
    filter_has_email: str = "all",
    search: str = "",
):
    """Return saved prospects, paginated and filterable."""
    mongo_dir = -1 if sort_dir == "desc" else 1
    records, total = await list_prospects(
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=mongo_dir,
        filter_status=filter_status,
        filter_has_email=filter_has_email,
        search=search,
    )
    return {"records": records, "total": total}


@router.get("/api/discover/sessions")
async def get_sessions():
    """Return distinct discover sessions with metadata."""
    cursor = prospects_col().find({}, {"_id": 0})
    records = await cursor.to_list(length=None)
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
async def get_prospect_route(website: str):
    """Look up a single prospect by website URL."""
    record = await get_prospect(website)
    return {"record": record}


@router.patch("/api/discover/status")
async def update_status(body: dict):
    website = body.get("website")
    status = body.get("status")
    if not website or not status:
        raise HTTPException(400, "website and status required")
    await update_prospect_status(website, status)
    return {"ok": True}


@router.delete("/api/discover/prospect")
async def delete_prospect(website: str):
    await delete_prospects([website])
    return {"ok": True}


@router.delete("/api/discover/prospects/bulk")
async def delete_prospects_bulk(body: dict):
    websites = body.get("websites", [])
    count = await delete_prospects(websites)
    return {"ok": True, "deleted": count}


@router.patch("/api/discover/email")
async def update_email(body: dict):
    website = body.get("website")
    email = body.get("email")
    if not website:
        raise HTTPException(400, "website required")
    await update_prospect_email(website, email)
    return {"ok": True}


@router.patch("/api/discover/response")
async def toggle_response(body: dict):
    website = body.get("website")
    if not website:
        raise HTTPException(400, "website required")
    new_val = await toggle_prospect_response(website)
    return {"got_response": new_val}
