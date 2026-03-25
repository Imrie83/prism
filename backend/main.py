"""
Shinrai Prism Audit — FastAPI Backend
Run with: python -m uvicorn main:app --reload --port 8000

Structure:
  main.py            — app init, core scan/crawl/agent routes
  models.py          — Pydantic request/response models
  db.py              — TinyDB setup, migration, helpers
  ai_client.py       — Ollama / OpenAI / Claude provider clients
  prompts.py         — Audit, email, and agent prompt strings + builders
  semantic.py        — HTML → semantic groups extractor
  email_service.py   — Email generation, report card, send
  routes_history.py  — /api/history/* routes
  routes_discover.py — /api/discover/* routes
"""

import asyncio
import json
import os
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .ai_client import (
    call_ai,
    call_ollama,
    call_openai,
    call_claude,
    call_ollama_chat,
    _extract_json,
)
from .db import upsert_scan, get_scheduled_emails, update_email
from .models import (
    AnalyzeRequest,
    CrawlRequest,
    AgentChatRequest,
)
from .prompts import build_audit_system_prompt, build_audit_user_prompt, AGENT_SYSTEM
from .routes_history import router as history_router
from .routes_discover import router as discover_router
from .utils import extract_emails_from_html

app = FastAPI(title="Prism Audit API", version="1.5.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(history_router)
app.include_router(discover_router)

# ── Email service routes (imported to keep main.py lean) ─────────────────────
from .email_service import router as email_router

app.include_router(email_router)


# ── Task registry ─────────────────────────────────────────────────────────────
ACTIVE_TASKS: dict[str, tuple] = {}


def register_task(
    task_id: str, task: asyncio.Task, cancel_event: asyncio.Event
) -> None:
    ACTIVE_TASKS[task_id] = (task, cancel_event)


def unregister_task(task_id: str) -> None:
    ACTIVE_TASKS.pop(task_id, None)


def cancel_task(task_id: str) -> bool:
    entry = ACTIVE_TASKS.get(task_id)
    if not entry:
        return False
    task, event = entry
    event.set()
    task.cancel()
    unregister_task(task_id)
    return True


# ── Screenshot helpers ────────────────────────────────────────────────────────


async def take_screenshot(url: str, service_url: str) -> tuple[str, str, int]:
    """Returns (screenshot_b64, html, page_height)."""
    print(f"[screenshot] capturing {url}")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{service_url.rstrip('/')}/screenshot", json={"url": url}
        )
        r.raise_for_status()
        data = r.json()
        page_height = data.get("pageHeight", 0)
        print(
            f"[screenshot] done, html={len(data.get('html', ''))} chars pageHeight={page_height}px"
        )
        return data["screenshot"], data.get("html", ""), page_height


async def take_screenshot_offset(
    url: str, service_url: str, offset_y: int
) -> str | None:
    """Returns second screenshot b64 (or None if page not tall enough)."""
    print(f"[screenshot-offset] capturing {url} from y={offset_y}")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{service_url.rstrip('/')}/screenshot-offset",
            json={"url": url, "offset_y": offset_y},
        )
        r.raise_for_status()
        data = r.json()
        shot = data.get("screenshot")
        if shot:
            print(f"[screenshot-offset] done, clipHeight={data.get('clipHeight')}px")
        else:
            print("[screenshot-offset] page not tall enough, skipping")
        return shot


# ── Core routes ───────────────────────────────────────────────────────────────


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/test-ai")
async def test_ai(req: AnalyzeRequest):
    """Quick connectivity test — sends a tiny prompt, returns raw AI response."""
    import time

    t0 = time.monotonic()
    test_prompt = 'Return this exact JSON and nothing else: {"ok": true, "message": "API connection working"}'
    test_system = "You are a test endpoint. Return only the JSON object requested, no markdown, no explanation."

    print(f"[test-ai] ▶ testing provider={req.settings.ai_provider}")
    try:
        if req.settings.ai_provider == "claude":
            raw, usage = await call_claude(
                test_prompt,
                test_system,
                req.settings.anthropic_api_key,
                req.settings.anthropic_model,
            )
        elif req.settings.ai_provider == "openai":
            raw, usage = await call_openai(
                test_prompt,
                test_system,
                req.settings.openai_api_key,
                req.settings.openai_model,
            )
        else:
            raw, usage = await call_ollama(
                test_prompt,
                test_system,
                req.settings.ollama_base_url,
                req.settings.ollama_model,
            )

        elapsed = round(time.monotonic() - t0, 2)
        try:
            parsed = json.loads(_extract_json(raw))
            parse_ok = True
            parse_error = None
        except Exception as pe:
            parse_ok = False
            parse_error = str(pe)
            parsed = None

        return {
            "success": True,
            "elapsed_s": elapsed,
            "provider": req.settings.ai_provider,
            "model": usage.get("model"),
            "tokens": usage,
            "raw_response": raw,
            "raw_length": len(raw),
            "first_chars": repr(raw[:100]),
            "json_parse_ok": parse_ok,
            "json_parse_error": parse_error,
            "parsed": parsed,
        }
    except Exception as e:
        elapsed = round(time.monotonic() - t0, 2)
        tb = traceback.format_exc()
        print(f"[test-ai] ✗ FAILED after {elapsed}s:\n{tb}")
        return {
            "success": False,
            "elapsed_s": elapsed,
            "provider": req.settings.ai_provider,
            "error": str(e),
            "traceback": tb,
        }


@app.get("/api/check-ollama")
async def check_ollama(base_url: str = "http://localhost:11434"):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{base_url.rstrip('/')}/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            return {"ok": True, "models": models}
    except Exception as e:
        return {"ok": False, "error": str(e), "type": type(e).__name__}


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    task_id = req.task_id or f"analyze-{id(req)}"
    print(
        f"[analyze] task_id={task_id} url={req.url} provider={req.settings.ai_provider}"
    )

    cancel_event = asyncio.Event()
    task = asyncio.create_task(_do_analyze(req, cancel_event))
    register_task(task_id, task, cancel_event)

    async def stream():
        try:
            while not task.done():
                yield b"\n"
                await asyncio.sleep(15)
            if task.cancelled():
                yield json.dumps({"cancelled": True}).encode() + b"\n"
                return
            exc = task.exception()
            if exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                print(f"[analyze] ✗ task raised: {error_msg}\n{traceback.format_exc()}")
                yield json.dumps({"error": error_msg}).encode() + b"\n"
            else:
                yield json.dumps(task.result()).encode() + b"\n"
        except asyncio.CancelledError:
            yield json.dumps({"cancelled": True}).encode() + b"\n"
        finally:
            unregister_task(task_id)

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.post("/api/cancel/{task_id}")
async def cancel(task_id: str):
    ok = cancel_task(task_id)
    print(f"[cancel] task_id={task_id} found={ok}")
    return {"cancelled": ok, "task_id": task_id}


@app.get("/api/tasks")
async def list_tasks():
    return {"active": list(ACTIVE_TASKS.keys())}


async def _do_analyze(
    req: AnalyzeRequest, cancel_event: asyncio.Event | None = None
) -> dict:
    import time

    t0 = time.monotonic()
    vision = req.vision_mode
    print(
        f"[analyze] ═══ START url={req.url} mode={'vision' if vision else 'standard'}"
    )
    print(
        f"[analyze]   provider={req.settings.ai_provider} model={req.settings.ollama_model or req.settings.openai_model or req.settings.anthropic_model}"
    )

    if cancel_event and cancel_event.is_set():
        raise asyncio.CancelledError()

    # Always use the server-side screenshot service URL from the environment.
    # The client-supplied settings.screenshot_service_url is for the UI's own
    # health checks (localhost:3000) and must not be used for server-to-server calls.
    screenshot_svc = os.environ.get(
        "SCREENSHOT_SERVICE_URL", req.settings.screenshot_service_url
    )

    t1 = time.monotonic()
    screenshot_b64, html, page_height = await take_screenshot(req.url, screenshot_svc)
    print(
        f"[analyze]   ✓ screenshot done in {time.monotonic() - t1:.1f}s | html={len(html)} chars | image={len(screenshot_b64) // 1024}KB | pageHeight={page_height}px"
    )

    images: list[str] = [screenshot_b64]
    if vision and page_height > 7999:
        print(
            f"[analyze]   → page tall ({page_height}px), taking second screenshot from y=7999..."
        )
        t1b = time.monotonic()
        screenshot2 = await take_screenshot_offset(req.url, screenshot_svc, 7999)
        if screenshot2:
            images.append(screenshot2)
            print(
                f"[analyze]   ✓ second screenshot done in {time.monotonic() - t1b:.1f}s | {len(screenshot2) // 1024}KB"
            )

    if cancel_event and cancel_event.is_set():
        raise asyncio.CancelledError()

    system_prompt = build_audit_system_prompt(
        vision_mode=vision, scan_mode=req.scan_mode
    )
    prompt = build_audit_user_prompt(html, vision_mode=vision)
    emails_found = extract_emails_from_html(html)

    print(
        f"[analyze]   → calling AI | mode={'vision' if vision else 'standard'} | images={len(images)} | prompt={len(prompt)} chars"
    )
    t2 = time.monotonic()
    data = await call_ai(prompt, system_prompt, req.settings, images)
    usage = data.pop("_usage", {})
    print(
        f"[analyze]   ✓ AI done in {time.monotonic() - t2:.1f}s | score={data.get('score')} issues={len(data.get('issues', []))}"
    )

    data.setdefault("score", 50)
    data.setdefault("issues", [])
    data.setdefault("summary", "")
    data["issueCounts"] = {
        "high": sum(1 for i in data["issues"] if i.get("severity") == "high"),
        "medium": sum(1 for i in data["issues"] if i.get("severity") == "medium"),
        "low": sum(1 for i in data["issues"] if i.get("severity") == "low"),
    }
    data["screenshot"] = screenshot_b64
    data["url"] = req.url
    data["scan_mode"] = req.scan_mode
    data["_tokens"] = usage
    data["emails_found"] = emails_found
    print(f"[analyze]   emails found: {emails_found}")

    if "totalIssues" not in data:
        c = data["issueCounts"]
        data["totalIssues"] = c["high"] + c["medium"] + c["low"]

    total = time.monotonic() - t0
    print(
        f"[analyze] ═══ DONE in {total:.1f}s | score={data['score']} | issues: high={data['issueCounts']['high']} med={data['issueCounts']['medium']} low={data['issueCounts']['low']} | tokens={usage.get('total_tokens', '?')}"
    )

    if req.scan_mode in ("shallow", "batch"):
        try:
            upsert_scan(data)
        except Exception as db_err:
            print(f"[db] ⚠ save failed: {db_err}")
    return data


@app.post("/api/crawl")
async def crawl(req: CrawlRequest):
    base_domain = urlparse(req.url).netloc
    visited: set = set()
    to_visit = [req.url]
    found = []

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        while to_visit and len(found) < req.max_pages:
            url = to_visit.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                r = await client.get(
                    url, headers={"User-Agent": "Mozilla/5.0 (Prism Audit Bot)"}
                )
                if "text/html" not in r.headers.get("content-type", ""):
                    continue
                found.append(url)
                for link in re.findall(r'href=["\']([^"\']+)["\']', r.text):
                    abs_link = urljoin(url, link).split("#")[0].split("?")[0]
                    p = urlparse(abs_link)
                    if (
                        p.netloc == base_domain
                        and abs_link not in visited
                        and abs_link not in to_visit
                        and not any(
                            abs_link.endswith(x)
                            for x in [
                                ".pdf",
                                ".jpg",
                                ".png",
                                ".gif",
                                ".css",
                                ".js",
                                ".xml",
                            ]
                        )
                    ):
                        to_visit.append(abs_link)
            except Exception:
                continue

    return {"urls": found, "total": len(found)}


@app.post("/api/agent-chat")
async def agent_chat(req: AgentChatRequest):
    print(
        f"[agent-chat] provider={req.settings.ai_provider} model={req.settings.ollama_model}"
    )
    system = AGENT_SYSTEM.format(context=req.scan_context[:6000])
    messages = [{"role": "system", "content": system}] + [
        {"role": m.role, "content": m.content} for m in req.messages
    ]
    try:
        if req.settings.ai_provider == "openai":
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {req.settings.openai_api_key}"},
                    json={"model": req.settings.openai_model, "messages": messages},
                )
                r.raise_for_status()
                reply = r.json()["choices"][0]["message"]["content"]
        elif req.settings.ai_provider == "claude":
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": req.settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": req.settings.anthropic_model,
                        "max_tokens": 1024,
                        "system": system,
                        "messages": [
                            {"role": m.role, "content": m.content} for m in req.messages
                        ],
                    },
                )
                r.raise_for_status()
                reply = r.json()["content"][0]["text"]
        else:
            reply = await call_ollama_chat(
                messages, req.settings.ollama_base_url, req.settings.ollama_model
            )
        return {"reply": reply}
    except Exception as e:
        print(f"[agent-chat] ERROR:\n{traceback.format_exc()}")
        raise HTTPException(502, f"Agent error: {e}")
