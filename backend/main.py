"""
Shinrai Prism Audit — FastAPI Backend
Run with: python -m uvicorn main:app --reload --port 8000
"""

import asyncio
import json
import os
import re
import smtplib
import ssl
import traceback
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from tinydb import TinyDB, Query

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── Email extraction ──────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE,
)
# Domains we never want to surface (tracking pixels, CDNs, common false positives)
_EMAIL_BLOCKLIST = {
    "example.com", "example.jp", "sentry.io", "cloudflare.com",
    "googleapis.com", "gstatic.com", "w3.org", "schema.org",
    "openstreetmap.org", "gravatar.com", "placeholder.com",
}

def extract_emails_from_html(html: str) -> list[str]:
    """Return deduplicated list of likely contact emails found in raw HTML."""
    found = {}
    for m in _EMAIL_RE.finditer(html):
        addr = m.group(0).lower().rstrip(".")
        domain = addr.split("@")[-1]
        if domain in _EMAIL_BLOCKLIST:
            continue
        # Prefer addresses that look like contact/info/hello/support over generic
        priority = 0 if re.search(r'^(info|contact|hello|support|sales|enqui)', addr) else 1
        if addr not in found or priority < found[addr]:
            found[addr] = priority
    # Sort: priority addresses first, then alphabetical
    return sorted(found.keys(), key=lambda a: (found[a], a))


app = FastAPI(title="Prism Audit API", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Database ─────────────────────────────────────────────────────────────────
os.makedirs("/app/data", exist_ok=True)
db = TinyDB("/app/data/db.json", indent=2, ensure_ascii=False)
ScanRecord = Query()

def db_upsert_scan(data: dict):
    """Upsert a scan record keyed by url. Preserves existing email block."""
    url = data.get("url", "")
    if not url:
        return
    existing = db.get(ScanRecord.url == url)
    email_block = existing.get("email") if existing else None
    record = {
        "url":          url,
        "scan_mode":    data.get("scan_mode", "shallow"),
        "score":        data.get("score", 0),
        "title":        data.get("title", ""),
        "summary":      data.get("summary", ""),
        "total_issues": data.get("totalIssues", 0),
        "issue_counts": data.get("issueCounts", {}),
        "issues":       data.get("issues", []),
        "screenshot_b64": data.get("screenshot", ""),
        "scanned_at":   datetime.now(timezone.utc).isoformat(),
    }
    if email_block:
        record["email"] = email_block
    db.upsert(record, ScanRecord.url == url)
    print(f"[db] upserted scan for {url}")

def db_update_email(url: str, recipient: str, subject: str, html: str):
    """Update the email block for a URL after sending."""
    existing = db.get(ScanRecord.url == url)
    if not existing:
        print(f"[db] ⚠ no scan record for {url} — email block not saved")
        return
    email_block = {
        "recipient":    recipient,
        "subject":      subject,
        "html":         html,
        "sent_at":      datetime.now(timezone.utc).isoformat(),
        "got_response": existing.get("email", {}).get("got_response", False),
    }
    db.update({"email": email_block}, ScanRecord.url == url)
    print(f"[db] email record saved for {url} → {recipient}")


# ── Task registry — allows frontend to cancel running AI tasks ────────────────
# Maps task_id → (asyncio.Task, asyncio.Event)
# The Event is set when a cancel is requested; tasks check it periodically.
ACTIVE_TASKS: dict[str, tuple] = {}

def register_task(task_id: str, task: asyncio.Task, cancel_event: asyncio.Event):
    ACTIVE_TASKS[task_id] = (task, cancel_event)

def unregister_task(task_id: str):
    ACTIVE_TASKS.pop(task_id, None)

def cancel_task(task_id: str) -> bool:
    entry = ACTIVE_TASKS.get(task_id)
    if not entry:
        return False
    task, event = entry
    event.set()       # signal the task to stop gracefully
    task.cancel()     # also hard-cancel the asyncio task
    unregister_task(task_id)
    return True


# ── Models ────────────────────────────────────────────────────────────────────

class AISettings(BaseModel):
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    screenshot_service_url: str = "http://screenshot:3000"
    max_deep_pages: int = 20


class AnalyzeRequest(BaseModel):
    url: str
    settings: AISettings
    task_id: str | None = None   # client-provided ID for cancellation
    scan_mode: str = "shallow"   # "shallow" | "deep" | "batch"


class CrawlRequest(BaseModel):
    url: str
    max_pages: int = 20


class EmailSettings(BaseModel):
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    your_name: str = "Marcin Zielinski"
    your_title: str = "English Localization Specialist"
    your_email: str = ""
    your_website: str = "https://imrie83.github.io/shinrai/"


class GenerateEmailRequest(BaseModel):
    scan_result: dict[str, Any]
    settings: EmailSettings
    dashboard_screenshot: str | None = None  # base64 of the Prism results UI screenshot (optional)


class SendEmailSettings(BaseModel):
    gmail_address: str
    gmail_app_password: str
    your_name: str = "Marcin Zielinski"
    from_address: str = ""  # visible From address, e.g. zielinski.marcin@shinrai.pro


class SendEmailRequest(BaseModel):
    to: str
    subject: str
    html: str
    url: str = ""   # source URL — used to link email record to scan in DB
    settings: SendEmailSettings


class AgentMessage(BaseModel):
    role: str
    content: str


class AgentChatRequest(BaseModel):
    messages: list[AgentMessage]
    scan_context: str
    settings: AISettings


# ── Prompts ───────────────────────────────────────────────────────────────────

VISION_SYSTEM_PROMPT = """You are an expert English localisation, UX, and cross-cultural web auditor specialising in Japanese websites targeting Western audiences.

You receive BOTH a screenshot of the page AND its structured semantic content. Use both together.

IMPORTANT — LOGOS & BRAND MARKS: Do NOT flag logos, brand marks, or favicon images for containing Japanese text. Logos are intentional brand assets and should be ignored entirely when assessing translation issues.

Analyse across these dimensions:

TEXT & TRANSLATION
- untranslated_japanese: Japanese text that should be in English (EXCLUDE logos and brand marks)
- untranslated_image_text: Text embedded in images that is in Japanese (EXCLUDE logos and brand marks)
- machine_translation: Stilted, unnatural, or clearly auto-translated English
- grammar_error: Grammatical or spelling mistakes in English content
- awkward_phrasing: Technically correct but unnatural-sounding English
- missing_context: Content that makes no sense without Japanese cultural knowledge
- cultural_mismatch: Concepts, idioms, or references that don't resonate with Westerners
- weak_cta: Vague, indirect, or missing calls-to-action (Japanese indirectness doesn't work well in English)

VISUAL & LAYOUT (analyse these from the screenshot carefully)
- visual_hierarchy: Poor use of size, weight, colour to guide the eye — Western readers expect clear F-pattern or Z-pattern flow
- poor_contrast: Text or UI elements that are hard to read due to insufficient contrast (check against WCAG 2.1 AA)
- cluttered_layout: Dense, information-overloaded layouts that overwhelm Western visitors used to whitespace
- colour_psychology: Colour choices that send unintended signals to Western audiences (e.g. white for mourning in Japan vs West)
- missing_cta_visual: No visually prominent button or action area above the fold
- broken_layout: Elements that overlap, overflow, or misalign
- small_text: Body text below 14px or headings that don't stand out
- inconsistent_style: Mixed font families, inconsistent spacing, mismatched visual components
- japanese_font_romaji: Latin text rendered in a Japanese font that looks wrong/cramped
- image_quality: Low-res, pixelated, or stock-photo-heavy imagery that reduces trust
- western_ux_patterns: Missing patterns Westerners expect (hamburger menu, breadcrumbs, footer nav, social proof)
- trust_signals: Missing trust indicators (testimonials, certifications, contact info prominently placed)

JAPANESE WEB UX PATTERNS — pay special attention to these common issues that Western users find off-putting:
- Marquee/ticker text scrolling across the screen
- Excessive use of blinking or animated elements
- Font sizes that vary wildly across a single page
- Overuse of underlines on non-link text
- Multiple competing banner ads or announcement bars stacked at the top
- Tab-heavy navigation with 10+ items in the main nav
- Walls of small-print text with no visual breathing room
- Popup or overlay abuse on page load
- Mobile viewport not configured (zoomed-out desktop layout on mobile)

SCORING — be realistic and granular. Use the FULL 0–100 range:
- 85–100: Near-perfect English readiness. Very minor polish only.
- 70–84: Good foundation. A few notable issues but generally accessible to Westerners.
- 50–69: Moderate issues. Western visitors will notice problems. Some friction.
- 30–49: Significant issues. Core content is hard to navigate or understand.
- 0–29: Major overhaul needed. Barely accessible to English-speaking audiences.
Most real Japanese business sites score between 25–65. Do NOT cluster scores around 50–60. Be honest — if the site is poor, score it in the 20s or 30s. If it genuinely impresses, score it in the 80s.

SEVERITY BALANCE — you MUST include a mix of severities:
- High: 2–4 issues maximum. Reserve for genuinely blocking problems.
- Medium: 2–4 issues.
- Low: AT LEAST 1 low-severity issue. Low issues are real but minor — small polish items, subtle UX improvements, nice-to-haves.
Never return all high or all medium. Every audit must have at least one low.

VARIETY — spread issues across TEXT, VISUAL, and UX categories. Do not return 5+ issues all of the same type. Actively look for Japanese-specific UX anti-patterns (listed above) even on otherwise decent sites.

For EACH issue found, provide:
- type: one of the types above
- severity: "high" | "medium" | "low"
- location: brief description of WHERE on the page (e.g. "hero section", "navigation bar", "footer")
- original: the exact text or describe the visual element (if applicable)
- suggestion: specific, actionable fix
- explanation: brief reason this issue matters for the target audience

Count ALL issues you find across the page. Then return full detail for the 8 most impactful only (highest severity first, variety across text/visual/UX — include at least one low). Report the real total count separately.

Keep field values concise — location (≤8 words), original (≤15 words), suggestion (≤20 words), explanation (≤20 words).

LANGUAGE INSTRUCTIONS — follow exactly:
{language_instruction}

Return JSON only — no markdown, no code fences, no explanation before or after.
CRITICAL: All string values must be valid JSON. If you need to reference UI text that contains
double-quote characters, use single quotes instead (e.g. use 'notice' section, not "notice" section).
Never place a bare double-quote inside a JSON string value.

{{
  "score": <0-100, higher = better English-readiness for Western audiences>,
  "summary": "{summary_instruction}",
  "title": "<detected page title or company name>",
  "totalIssues": <integer — total count of ALL issues found across the entire page>,
  "issues": [top 8 issues with full detail, at least one must be low severity],
  "issueCounts": {{ "high": N, "medium": N, "low": N }}
}}"""

AGENT_SYSTEM = """You are an expert English localization and UX analyst for Japanese websites.
You have access to a detailed scan report. Answer questions about the findings, explain issues,
prioritise fixes, and suggest implementation approaches. Be specific and actionable.

Scan data:
{context}"""

EMAIL_SYSTEM = """You write bilingual cold outreach emails (Japanese + English) for Shinrai Web.

SENDER
  Name:    {name}
  Title:   {title}
  Email:   {email}
  Website: {website}
  Company: Shinrai Web (信頼ウェブ)

GOAL: Get them curious enough to visit {website} or reply.

TONE: Warm and direct. Sound like a person, not a marketing department.
No buzzwords: "leverage", "seamlessly", "holistic", "impactful", "unlock potential".

VARIATION — every email must feel different. Vary:
- The opening hook: sometimes lead with a genuine compliment about the design, sometimes the product/service, sometimes the ambition you sense in the site
- The angle: sometimes focus on the untapped English-speaking audience, sometimes on trust-building, sometimes on the gap between the site's quality and its English presentation
- The closing: sometimes a soft question, sometimes a direct invitation to visit the site, sometimes a gentle offer to share one specific finding
- Sentence rhythm: mix short punchy sentences with longer reflective ones. Avoid formulaic paragraph lengths.

CONTENT RULES:
- jp_paragraphs: 2-3 short paragraphs in natural Japanese Keigo. Do NOT include 御担当者様 — it is added automatically.
- en_paragraphs: 2-3 short paragraphs. Do NOT start with "Hi there" or any greeting — it is added automatically.
- Start with something specific and genuine you noticed about the site — the industry, a product detail, the visual style, or the company's apparent mission
- Hint at opportunity for English-speaking visitors — never frame as criticism
- Be specific to THIS site — avoid generic phrases that could apply to any Japanese business
- Reference the audit report with ONE sentence only
- Do NOT mention issue counts or specific problem names
- Do NOT write any HTML — return plain text paragraphs only

Return JSON only — no markdown, no explanation:
{{
  "subject": "<Japanese subject line — specific to their site, genuine curiosity>",
  "jp_paragraphs": ["<paragraph 1 in Japanese>", "<paragraph 2>", "<paragraph 3>"],
  "en_paragraphs": ["<paragraph 1 in English>", "<paragraph 2>", "<paragraph 3>"]
}}"""


# ── AI helpers ────────────────────────────────────────────────────────────────

async def call_ollama(prompt: str, system: str, base_url: str, model: str, image_b64: str | None = None) -> tuple[str, dict]:
    user_msg: dict = {"role": "user", "content": prompt}
    if image_b64:
        user_msg["images"] = [image_b64]

    url = f"{base_url.rstrip('/')}/api/chat"
    prompt_tokens = (len(system) + len(prompt)) // 4  # rough estimate before call
    print(f"[ollama] ▶ POST {url}")
    print(f"[ollama]   model={model} | has_image={image_b64 is not None} | prompt_chars={len(system)+len(prompt)} (~{prompt_tokens} tokens)")

    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(url, json={
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                user_msg,
            ],
            "format": "json",
            "options": {"temperature": 0.2, "num_ctx": 8192},
        })
        print(f"[ollama]   status={r.status_code}")
        r.raise_for_status()
        rj = r.json()
        content = rj["message"]["content"]
        # Ollama returns eval_count (output tokens) and prompt_eval_count (input tokens)
        usage = {
            "prompt_tokens":     rj.get("prompt_eval_count", prompt_tokens),
            "completion_tokens": rj.get("eval_count", len(content) // 4),
            "total_tokens":      rj.get("prompt_eval_count", prompt_tokens) + rj.get("eval_count", len(content) // 4),
            "provider":          "ollama",
            "model":             model,
        }
        print(f"[ollama]   ✓ response_chars={len(content)} | tokens: prompt={usage['prompt_tokens']} completion={usage['completion_tokens']} total={usage['total_tokens']}")
        return content, usage


async def call_ollama_chat(messages: list, base_url: str, model: str) -> str:
    url = f"{base_url.rstrip('/')}/api/chat"
    total_chars = sum(len(m.get("content","")) for m in messages)
    print(f"[ollama-chat] ▶ POST {url} model={model} | messages={len(messages)} total_chars={total_chars} (~{total_chars//4} tokens)")
    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(url, json={
            "model": model,
            "stream": False,
            "messages": messages,
            "options": {"temperature": 0.3, "num_ctx": 8192},
        })
        rj = r.json()
        reply = rj["message"]["content"]
        print(f"[ollama-chat] ✓ status={r.status_code} | tokens: prompt={rj.get('prompt_eval_count','?')} completion={rj.get('eval_count','?')}")
        r.raise_for_status()
        return reply


async def call_openai(prompt: str, system: str, api_key: str, model: str, image_b64: str | None = None) -> tuple[str, dict]:
    content: list = []
    if image_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}})
    content.append({"type": "text", "text": prompt})
    print(f"[openai] ▶ POST chat/completions model={model} | has_image={image_b64 is not None} | prompt_chars={len(system)+len(prompt)}")
    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
                "response_format": {"type": "json_object"},
            },
        )
        r.raise_for_status()
        rj = r.json()
        reply = rj["choices"][0]["message"]["content"]
        u = rj.get("usage", {})
        usage = {
            "prompt_tokens":     u.get("prompt_tokens", 0),
            "completion_tokens": u.get("completion_tokens", 0),
            "total_tokens":      u.get("total_tokens", 0),
            "provider": "openai", "model": model,
        }
        print(f"[openai] ✓ tokens: prompt={usage['prompt_tokens']} completion={usage['completion_tokens']} total={usage['total_tokens']}")
        return reply, usage


async def call_claude(prompt: str, system: str, api_key: str, model: str, image_b64: str | None = None) -> tuple[str, dict]:
    content: list = []
    if image_b64:
        # Strip data URI prefix if present (e.g. "data:image/jpeg;base64,")
        clean_b64 = image_b64
        if "," in image_b64[:50]:
            clean_b64 = image_b64.split(",", 1)[1]
        # Detect actual format from first bytes
        import base64 as _b64
        try:
            header = _b64.b64decode(clean_b64[:20])
            media_type = "image/png" if header[:4] == b"\x89PNG" else "image/jpeg"
        except Exception:
            media_type = "image/jpeg"
        content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": clean_b64}})
    content.append({"type": "text", "text": prompt})
    print(f"[claude] ▶ POST messages model={model} | has_image={image_b64 is not None} | prompt_chars={len(system)+len(prompt)}")
    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            json={"model": model, "max_tokens": 8192, "system": system, "messages": [{"role": "user", "content": content}]},
        )
        if not r.is_success:
            err_body = ""
            try: err_body = r.json()
            except: err_body = r.text[:500]
            print(f"[claude] ✗ {r.status_code} error body: {err_body}")
            # If image is causing issues, retry without it
            if r.status_code == 400 and image_b64 and "image" in str(err_body).lower():
                print("[claude] ⚠ Retrying without image due to 400 error")
                content_no_img = [c for c in content if c.get("type") != "image"]
                r2 = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                    json={"model": model, "max_tokens": 8192, "system": system, "messages": [{"role": "user", "content": content_no_img}]},
                )
                r2.raise_for_status()
                r = r2
            else:
                r.raise_for_status()
        rj = r.json()
        reply = rj["content"][0]["text"]
        u = rj.get("usage", {})
        stop_reason = rj.get("stop_reason", "unknown")
        usage = {
            "prompt_tokens":     u.get("input_tokens", 0),
            "completion_tokens": u.get("output_tokens", 0),
            "total_tokens":      u.get("input_tokens", 0) + u.get("output_tokens", 0),
            "provider": "claude", "model": model,
            "stop_reason": stop_reason,
        }
        if stop_reason == "max_tokens":
            print(f"[claude] ⚠ WARNING: response hit max_tokens limit — output was TRUNCATED. Raise max_tokens.")
        print(f"[claude] ✓ tokens: prompt={usage['prompt_tokens']} completion={usage['completion_tokens']} total={usage['total_tokens']} stop={stop_reason}")
        return reply, usage


def _extract_json(raw: str) -> str:
    """Strip markdown fences and find the outermost JSON object or array."""
    raw = raw.strip()
    # Remove ```json ... ``` or ``` ... ``` fences
    if raw.startswith("```"):
        lines = raw.split("\n")
        inner = []
        for line in lines[1:]:
            if line.strip() == "```":
                break
            inner.append(line)
        raw = "\n".join(inner).strip()
    # Find the first { or [ and matching close
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = raw.find(start_char)
        if start != -1:
            end = raw.rfind(end_char)
            if end != -1 and end > start:
                return raw[start:end+1]
    return raw


def _repair_json(raw: str) -> str:
    """Fix unescaped double-quotes inside JSON string values — the most common
    LLM mistake (e.g. "original": "'notice" section..." where the interior " breaks parsing).

    Strategy: process line by line. For any line that looks like a JSON key-value pair
    with a string value, extract the value portion and escape any unescaped interior quotes.
    Also removes trailing commas before } or ].
    """
    import re

    # Pass 1: trailing commas
    raw = re.sub(r',\s*([}\]])', r'\1', raw)

    lines = raw.split('\n')
    out = []
    for line in lines:
        # Match: optional whitespace + "key": "value" + optional comma
        m = re.match(r'^(\s*"[^"]+?"\s*:\s*)"(.*)"(,?)$', line)
        if m:
            prefix   = m.group(1)   # e.g. '      "original": '
            value    = m.group(2)   # raw value between outermost quotes
            trailing = m.group(3)   # optional trailing comma

            # Escape unescaped interior quotes while preserving already-escaped ones
            ph = '\x00QUOT\x00'
            value = value.replace('\\"', ph)   # protect already-escaped
            value = value.replace('"'  , '\\"')  # escape bare quotes
            value = value.replace(ph   , '\\"')  # restore (now also escaped)

            out.append(f'{prefix}"{value}"{trailing}')
        else:
            out.append(line)

    return '\n'.join(out)


async def call_ai(prompt: str, system: str, settings: AISettings, image_b64: str | None = None) -> dict:
    """Returns parsed JSON dict from AI. Includes '_usage' key with token counts."""
    if settings.ai_provider == "openai":
        raw, usage = await call_openai(prompt, system, settings.openai_api_key, settings.openai_model, image_b64)
    elif settings.ai_provider == "claude":
        raw, usage = await call_claude(prompt, system, settings.anthropic_api_key, settings.anthropic_model, image_b64)
    else:
        raw, usage = await call_ollama(prompt, system, settings.ollama_base_url, settings.ollama_model, image_b64)

    # Check for truncation before even trying to parse
    if usage.get("stop_reason") == "max_tokens":
        raise ValueError(
            f"AI response was truncated (hit max_tokens={usage.get('completion_tokens')} limit). "
            f"The JSON is incomplete and cannot be parsed. Try reducing max_deep_pages or the number of issues requested."
        )

    print(f"[call_ai] raw response length={len(raw)} first_chars={repr(raw[:80])}")
    cleaned = _extract_json(raw)
    print(f"[call_ai] after extraction length={len(cleaned)} first_chars={repr(cleaned[:80])}")

    # Attempt 1: standard parse
    try:
        result = json.loads(cleaned)
        print(f"[call_ai] ✓ JSON parsed OK")
    except json.JSONDecodeError as e1:
        print(f"[call_ai] standard parse failed ({e1}), attempting repair...")
        # Attempt 2: repair then parse
        try:
            repaired = _repair_json(cleaned)
            result = json.loads(repaired)
            print(f"[call_ai] ✓ JSON parsed OK after repair")
        except json.JSONDecodeError as e2:
            # Dump full response for debugging
            print(f"[call_ai] ✗ JSON repair also failed: {e2}")
            print(f"[call_ai] FULL RAW RESPONSE ({len(raw)} chars):\n{raw}")
            raise ValueError(f"AI returned invalid JSON (even after repair): {e2}. Raw (first 200): {raw[:200]!r}")

    result["_usage"] = usage
    return result


# ── Screenshot ────────────────────────────────────────────────────────────────

async def take_screenshot(url: str, service_url: str) -> tuple[str, str]:
    print(f"[screenshot] capturing {url}")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{service_url.rstrip('/')}/screenshot", json={"url": url})
        r.raise_for_status()
        data = r.json()
        print(f"[screenshot] done, html={len(data.get('html', ''))} chars")
        return data["screenshot"], data.get("html", "")


def extract_semantic_groups(html: str) -> str:
    """Parse HTML into semantic groups preserving DOM context."""
    from bs4 import BeautifulSoup, Tag

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "meta", "link", "head"]):
        tag.decompose()

    def classify_container(tag) -> str:
        name = tag.name.lower() if tag.name else ""
        combined = f"{name} {' '.join(tag.get('class', []))} {tag.get('role', '')} {tag.get('id', '')}".lower()
        if any(k in combined for k in ["hero", "jumbotron", "banner", "splash"]): return "hero"
        if any(k in combined for k in ["nav", "menu", "navigation"]): return "navigation"
        if any(k in combined for k in ["footer", "foot"]): return "footer"
        if any(k in combined for k in ["header", "masthead"]): return "header"
        if any(k in combined for k in ["cta", "call-to-action", "action"]): return "cta"
        if any(k in combined for k in ["contact", "form", "inquiry"]): return "contact-form"
        if any(k in combined for k in ["service", "product", "feature"]): return "services"
        if any(k in combined for k in ["about", "company", "team", "story"]): return "about"
        if any(k in combined for k in ["testimonial", "review", "client"]): return "social-proof"
        if name in ("header",): return "header"
        if name in ("footer",): return "footer"
        if name in ("nav",): return "navigation"
        if name in ("section", "article", "main", "aside"): return name
        return "section"

    def extract_elements(container, depth=0) -> list:
        if depth > 4: return []
        elements = []
        for tag in container.find_all(True, recursive=False):
            if not isinstance(tag, Tag): continue
            name = tag.name.lower()
            text = tag.get_text(" ", strip=True)
            if name in ("h1","h2","h3","h4","h5","h6"):
                if text: elements.append({"role": "heading", "level": name, "text": text[:300]})
            elif name == "p":
                if text: elements.append({"role": "paragraph", "text": text[:500]})
            elif name == "a":
                if text: elements.append({"role": "link", "text": text[:200], "href": tag.get("href","")[:100]})
            elif name == "button" or ("btn" in " ".join(tag.get("class",[])).lower()):
                if text: elements.append({"role": "button", "text": text[:200]})
            elif name in ("input","textarea","select"):
                elements.append({"role": "form-field", "placeholder": tag.get("placeholder", tag.get("name", tag.get("type","field")))[:100]})
            elif name == "img":
                elements.append({"role": "image", "alt": tag.get("alt","[no alt]")[:200], "src": tag.get("src","")[:80]})
            elif name == "li":
                if text: elements.append({"role": "list-item", "text": text[:300]})
            elif name in ("div","span","section","article","ul","ol"):
                elements.extend(extract_elements(tag, depth+1))
        return elements

    SELECTORS = ["header","nav","main","article","section","aside","footer",
                 "[role='banner']","[role='navigation']","[role='main']","[role='contentinfo']"]

    visited = set()
    groups = []

    for selector in SELECTORS:
        try:
            for el in soup.select(selector):
                eid = id(el)
                if eid in visited: continue
                visited.add(eid)
                for d in el.find_all(True): visited.add(id(d))
                elements = extract_elements(el)
                if elements:
                    groups.append({"type": classify_container(el), "elements": elements})
        except Exception:
            continue

    # Fallback: unvisited body direct children
    body = soup.find("body")
    if body:
        for child in body.find_all(True, recursive=False):
            if id(child) not in visited and isinstance(child, Tag):
                elements = extract_elements(child)
                if elements:
                    groups.append({"type": classify_container(child), "elements": elements})

    lines = ["=== PAGE SEMANTIC STRUCTURE ===\n"]
    for i, g in enumerate(groups[:20]):
        lines.append(f"[GROUP {i+1}: {g['type'].upper()}]")
        for el in g["elements"][:15]:
            role = el.get("role","?")
            if role == "heading": lines.append(f"  {el['level'].upper()}: {el['text']}")
            elif role == "paragraph": lines.append(f"  PARA: {el['text']}")
            elif role == "button": lines.append(f"  BUTTON: {el['text']}")
            elif role == "link": lines.append(f"  LINK: {el['text']}  → {el.get('href','')}")
            elif role == "image": lines.append(f"  IMG alt=\"{el['alt']}\"")
            elif role == "form-field": lines.append(f"  FIELD: {el['placeholder']}")
            elif role == "list-item": lines.append(f"  • {el['text']}")
        lines.append("")

    result = "\n".join(lines)
    if len(result) > 6000:
        result = result[:6000] + "\n[... truncated ...]"
    print(f"[extractor] {len(groups)} groups, {len(result)} chars")
    return result


def build_user_prompt(html: str) -> str:
    semantic = extract_semantic_groups(html)
    return f"Analyse this Japanese company website. Semantic page structure:\n\n{semantic}"



# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/test-ai")
async def test_ai(req: AnalyzeRequest):
    """Cheap connectivity test — sends a tiny prompt, returns raw response.
    Use this to verify API keys and JSON parsing without burning scan tokens."""
    import time
    t0 = time.monotonic()
    test_prompt = 'Return this exact JSON and nothing else: {"ok": true, "message": "API connection working"}' 
    test_system = "You are a test endpoint. Return only the JSON object requested, no markdown, no explanation."
    
    print(f"[test-ai] ▶ testing provider={req.settings.ai_provider} model={req.settings.ollama_model or req.settings.anthropic_model or req.settings.openai_model}")
    try:
        # Call the AI directly — bypass full scan pipeline
        if req.settings.ai_provider == "claude":
            raw, usage = await call_claude(test_prompt, test_system, req.settings.anthropic_api_key, req.settings.anthropic_model)
        elif req.settings.ai_provider == "openai":
            raw, usage = await call_openai(test_prompt, test_system, req.settings.openai_api_key, req.settings.openai_model)
        else:
            raw, usage = await call_ollama(test_prompt, test_system, req.settings.ollama_base_url, req.settings.ollama_model)
        
        elapsed = round(time.monotonic() - t0, 2)
        print(f"[test-ai] ✓ raw response ({len(raw)} chars): {repr(raw[:200])}")
        
        # Try to parse
        try:
            cleaned = _extract_json(raw)
            parsed = json.loads(cleaned)
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
    print(f"[analyze] task_id={task_id} url={req.url} provider={req.settings.ai_provider}")
    cancel_event = asyncio.Event()

    async def stream():
        task = asyncio.create_task(_do_analyze(req, cancel_event))
        register_task(task_id, task, cancel_event)
        try:
            while not task.done():
                yield b"\n"
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
                except asyncio.TimeoutError:
                    if cancel_event.is_set():
                        task.cancel()
                        yield json.dumps({"cancelled": True}).encode() + b"\n"
                        return
                    continue
                except Exception:
                    break
            try:
                result = task.result()
                print(f"[analyze] done score={result.get('score')} issues={len(result.get('issues', []))}")
                yield json.dumps(result).encode() + b"\n"
            except asyncio.CancelledError:
                yield json.dumps({"cancelled": True}).encode() + b"\n"
            except Exception as e:
                tb = traceback.format_exc()
                print(f"[analyze] ✗ FAILED:\n{tb}")
                # Surface the actual error message back to the frontend
                error_msg = str(e)
                # For ValueError (our JSON parse errors) the message is already descriptive
                yield json.dumps({"error": error_msg}).encode() + b"\n"
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


async def _do_analyze(req: AnalyzeRequest, cancel_event: asyncio.Event | None = None) -> dict:
    import time
    t0 = time.monotonic()
    print(f"[analyze] ═══ START url={req.url}")
    print(f"[analyze]   provider={req.settings.ai_provider} model={req.settings.ollama_model or req.settings.openai_model or req.settings.anthropic_model}")

    if cancel_event and cancel_event.is_set():
        raise asyncio.CancelledError()

    print(f"[analyze]   → taking screenshot...")
    t1 = time.monotonic()
    screenshot_b64, html = await take_screenshot(req.url, req.settings.screenshot_service_url)
    print(f"[analyze]   ✓ screenshot done in {time.monotonic()-t1:.1f}s | html={len(html)} chars | image={len(screenshot_b64)//1024}KB")

    if cancel_event and cancel_event.is_set():
        raise asyncio.CancelledError()

    prompt = build_user_prompt(html)
    print(f"[analyze]   → calling AI | prompt={len(prompt)} chars | system={len(VISION_SYSTEM_PROMPT)} chars")
    t2 = time.monotonic()
    if req.scan_mode == "deep":
        summary_instruction = (
            "2 sentence candid internal assessment — be specific and direct about the main issues found"
        )
        language_instruction = (
            "Write all text fields (summary, location, explanation, suggestion, original) in English."
        )
    else:
        # shallow / batch — summary and issues go into the report card sent to the Japanese client
        summary_instruction = (
            "2 sentence opportunity-framed summary in Japanese — highlight what the site does well and what "
            "English-speaking visitors could gain; focus on potential, never mention problems or failures"
        )
        language_instruction = (
            "Write the summary field in Japanese. "
            "Write the explanation field in Japanese — this text appears in the client-facing report card shown to the Japanese business owner. "
            "Write location, original, and suggestion in English (internal use only). "
            "Do NOT write explanation in English under any circumstances."
        )
    system_prompt = VISION_SYSTEM_PROMPT.format(
        summary_instruction=summary_instruction,
        language_instruction=language_instruction,
    )
    data = await call_ai(prompt, system_prompt, req.settings, screenshot_b64)
    usage = data.pop("_usage", {})
    print(f"[analyze]   ✓ AI done in {time.monotonic()-t2:.1f}s | score={data.get('score')} issues={len(data.get('issues',[]))}")

    data.setdefault("score", 50)
    data.setdefault("issues", [])
    data.setdefault("summary", "")
    data["issueCounts"] = {
        "high":   sum(1 for i in data["issues"] if i.get("severity") == "high"),
        "medium": sum(1 for i in data["issues"] if i.get("severity") == "medium"),
        "low":    sum(1 for i in data["issues"] if i.get("severity") == "low"),
    }
    data["screenshot"] = screenshot_b64
    data["url"] = req.url
    data["scan_mode"] = req.scan_mode
    data["_tokens"] = usage
    data["emails_found"] = extract_emails_from_html(html)
    print(f"[analyze]   emails found: {data['emails_found']}")
    counts = data["issueCounts"]
    # Use AI-reported totalIssues if present, fall back to counting what was returned
    if "totalIssues" not in data:
        data["totalIssues"] = counts["high"] + counts["medium"] + counts["low"]

    # Pre-translate summary + issue text to Japanese now (Haiku, fast+cheap)
    # so email generation never needs a second AI call for translation

    total = time.monotonic() - t0
    print(f"[analyze] ═══ DONE in {total:.1f}s | score={data['score']} | issues: high={data['issueCounts']['high']} med={data['issueCounts']['medium']} low={data['issueCounts']['low']} | tokens={usage.get('total_tokens','?')})")
    # Auto-save to DB (shallow/batch only — deep scans are internal, not outreach)
    if req.scan_mode in ("shallow", "batch"):
        try:
            db_upsert_scan(data)
        except Exception as db_err:
            print(f"[db] ⚠ save failed: {db_err}")
    return data


@app.post("/api/crawl")
async def crawl(req: CrawlRequest):
    from urllib.parse import urljoin, urlparse
    import re

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
                r = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Prism Audit Bot)"})
                if "text/html" not in r.headers.get("content-type", ""):
                    continue
                found.append(url)
                for link in re.findall(r'href=["\']([^"\']+)["\']', r.text):
                    abs_link = urljoin(url, link).split("#")[0].split("?")[0]
                    p = urlparse(abs_link)
                    if (p.netloc == base_domain
                            and abs_link not in visited
                            and abs_link not in to_visit
                            and not any(abs_link.endswith(x) for x in [".pdf",".jpg",".png",".gif",".css",".js",".xml"])):
                        to_visit.append(abs_link)
            except Exception:
                continue

    return {"urls": found, "total": len(found)}


@app.post("/api/generate-email")
async def generate_email(req: GenerateEmailRequest):
    """Streams keepalives while AI writes the email — prevents gateway 504s."""
    import time
    s = req.settings
    system = EMAIL_SYSTEM.format(
        name=s.your_name, title=s.your_title,
        website=s.your_website, email=s.your_email
    )

    scan = req.scan_result
    url   = scan.get("url", "their website")
    score = scan.get("score", "N/A")
    summary = scan.get("summary", "")
    title   = scan.get("title", "")
    issues  = scan.get("issues", [])

    # Build 2-3 specific "positive observations" from the scan data
    # We look at what the AI flagged but phrase as compliments about the site context
    issue_types = [i.get("type","") for i in issues]
    issue_locs  = [i.get("location","") for i in issues]
    
    # Pick up to 2 high-value observations that are interesting/specific
    opportunity_hints = []
    for issue in issues[:6]:
        loc = issue.get("location","")
        itype = issue.get("type","")
        if itype in ("untranslated_japanese","grammar_error","awkward_phrasing") and loc:
            opportunity_hints.append(f"English text opportunities in the {loc}")
        elif itype in ("visual_hierarchy","cluttered_layout","colour_psychology") and loc:
            opportunity_hints.append(f"visual presentation in the {loc}")
        elif itype in ("weak_cta","missing_cta_visual") and loc:
            opportunity_hints.append(f"call-to-action clarity for the {loc}")
        elif itype in ("trust_signals","western_ux_patterns") and loc:
            opportunity_hints.append(f"trust signals for Western visitors near the {loc}")
        if len(opportunity_hints) >= 2:
            break

    hints_text = " and ".join(opportunity_hints[:2]) if opportunity_hints else "English localisation and UX for Western visitors"

    # Email-generation model (Sonnet or whatever is configured for email)
    ai_settings = AISettings(
        ai_provider=s.ai_provider,
        ollama_base_url=s.ollama_base_url,
        ollama_model=s.ollama_model,
        openai_api_key=s.openai_api_key,
        anthropic_api_key=s.anthropic_api_key,
        anthropic_model=s.anthropic_model,
    )

    # shallow/batch: AI already wrote Japanese — no translation needed
    # deep: translate summary + explanations from English to Japanese for the card
    scan_mode = scan.get("scan_mode", "shallow")
    if scan_mode == "deep":
        audit_settings = AISettings(
            ai_provider=s.ai_provider,
            ollama_base_url=s.ollama_base_url,
            ollama_model=s.ollama_model,
            openai_api_key=s.openai_api_key,
            anthropic_api_key=s.anthropic_api_key,
            anthropic_model="claude-haiku-4-5-20251001" if s.ai_provider == "claude" else s.anthropic_model,
        )
        scan_for_card = await _translate_scan_for_card(scan, audit_settings)
    else:
        scan_for_card = scan  # already Japanese
    report_card_html = _build_report_card_html(scan_for_card)

    total_issues = scan.get("totalIssues", len(issues))

    prompt = f"""Write a bilingual marketing outreach email for this Japanese company.

SITE DETAILS (use these to make the email feel personal and researched):
  URL: {url}
  Page title: {title or "unknown"}
  English-readiness score: {score}/100
  What we analysed: {summary}

SPECIFIC OPPORTUNITY AREAS to hint at (frame as upside, not problems):
  {hints_text}

IMPORTANT TONE NOTES:
- Start by mentioning something genuinely positive about the site
- Naturally pivot to the opportunity for English-speaking visitors
- ALWAYS mention that our core service is English translation and localisation of Japanese website content — this must be clear in both languages
- The report card is already embedded — reference it with ONE sentence only
- Do NOT say the site has problems, bugs, or issues
- Do NOT list specific findings — hint at opportunity areas only
- Do NOT mention any issue counts or numbers in the email body

Return the bilingual email following your system prompt instructions exactly."""

    print(f"[generate-email] ═══ START url={url} score={score} provider={ai_settings.ai_provider}")
    print(f"[generate-email]   opportunity hints: {hints_text}")
    print(f"[generate-email]   report card html: {len(report_card_html)} chars")

    async def stream():
        sender = {"name": s.your_name, "title": s.your_title, "email": s.your_email, "website": s.your_website}
        task = asyncio.create_task(_do_generate_email(prompt, system, ai_settings, report_card_html, sender))
        while not task.done():
            yield b"\n"
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break
        try:
            result = task.result()
            yield json.dumps(result).encode() + b"\n"
        except Exception as e:
            print(f"[generate-email] FAILED:\n{traceback.format_exc()}")
            yield json.dumps({"error": str(e)}).encode() + b"\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


async def _translate_scan_for_card(scan: dict, ai_settings: AISettings) -> dict:
    """Translate summary + issue location/explanation to Japanese in one batched AI call.
    Returns a copy of scan with Japanese strings. Falls back to original on error."""
    summary = scan.get("summary", "")
    issues  = scan.get("issues", [])

    # Build a numbered list of strings to translate
    strings = [summary] if summary else [""]
    for iss in issues:
        strings.append(iss.get("location", ""))
        strings.append(iss.get("explanation", "")[:120])

    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(strings))

    prompt = f"""Translate the following numbered English strings to natural Japanese.
Return ONLY a JSON array of translated strings in the same order, same count.
Keep proper nouns, URLs, and brand names unchanged.
Do not add explanation or commentary.

{numbered}"""
    system = "You are a professional English-to-Japanese translator. Return only a JSON array of strings."

    try:
        raw, _ = await (
            call_claude(prompt, system, ai_settings.anthropic_api_key, ai_settings.anthropic_model)
            if ai_settings.ai_provider == "claude" else
            call_openai(prompt, system, ai_settings.openai_api_key, ai_settings.openai_model)
            if ai_settings.ai_provider == "openai" else
            call_ollama(prompt, system, ai_settings.ollama_base_url, ai_settings.ollama_model)
        )
        cleaned = _extract_json(raw)
        translated = json.loads(cleaned)
        if not isinstance(translated, list) or len(translated) < len(strings):
            raise ValueError("translation list length mismatch")
    except Exception as e:
        print(f"[translate-card] ⚠ translation failed ({e}), using original English")
        return scan  # graceful fallback

    # Rebuild scan with translated strings
    scan_jp = dict(scan)
    scan_jp["summary"] = translated[0] if translated else summary
    jp_issues = []
    for idx, iss in enumerate(issues):
        jp_iss = dict(iss)
        loc_i  = 1 + idx * 2
        expl_i = 1 + idx * 2 + 1
        if loc_i < len(translated):
            jp_iss["location"] = translated[loc_i]
        if expl_i < len(translated):
            jp_iss["explanation"] = translated[expl_i]
        jp_issues.append(jp_iss)
    scan_jp["issues"] = jp_issues
    print(f"[translate-card] ✓ translated {len(strings)} strings to Japanese")
    return scan_jp


def _build_report_card_html(scan: dict) -> str:
    """Build light-theme HTML report card for email embedding.
    - 3 sample issues chosen for variety (one text, one visual, one UX)
    - Summary and issue labels in Japanese
    - CTA button linking to Shinrai Web
    """
    score   = scan.get("score", 0)
    summary = scan.get("summary", "")
    url     = scan.get("url", "")
    issues  = scan.get("issues", [])
    total   = scan.get("totalIssues", len(issues))

    # Score colour
    if score >= 75:   score_color = "#16a34a"
    elif score >= 45: score_color = "#d97706"
    else:             score_color = "#dc2626"

    # Pick up to 5 issues: first pass gets one per category (variety), fill remaining by severity
    TEXT_TYPES   = {"untranslated_japanese","machine_translation","grammar_error","awkward_phrasing","missing_context","cultural_mismatch","weak_cta"}
    VISUAL_TYPES = {"visual_hierarchy","cluttered_layout","poor_contrast","broken_layout","small_text","inconsistent_style","colour_psychology","image_quality","japanese_font_romaji"}
    UX_TYPES     = {"missing_cta_visual","western_ux_patterns","trust_signals","untranslated_image_text"}

    picked = []
    for category in (TEXT_TYPES, VISUAL_TYPES, UX_TYPES):
        # prefer high severity within each category
        for sev in ("high", "medium", "low"):
            for iss in issues:
                if iss.get("type") in category and iss.get("severity") == sev and iss not in picked:
                    picked.append(iss)
                    break
            if len(picked) > len([p for p in picked if p.get("type") not in category]):
                break  # got one for this category

    # Fill remaining slots up to 5 from whatever issues are left
    for iss in issues:
        if len(picked) >= 5:
            break
        if iss not in picked:
            picked.append(iss)

    # Japanese translations for issue types
    JP_TYPE = {
        "untranslated_japanese":  "未翻訳テキスト",
        "untranslated_image_text":"画像内の未翻訳テキスト",
        "machine_translation":    "機械翻訳の問題",
        "grammar_error":          "文法エラー",
        "awkward_phrasing":       "不自然な表現",
        "missing_context":        "文脈の欠如",
        "cultural_mismatch":      "文化的ミスマッチ",
        "weak_cta":               "弱いCTA",
        "visual_hierarchy":       "視覚的階層の問題",
        "poor_contrast":          "コントラスト不足",
        "cluttered_layout":       "レイアウトの混雑",
        "colour_psychology":      "色彩の問題",
        "missing_cta_visual":     "CTAボタンの欠如",
        "broken_layout":          "レイアウトの崩れ",
        "small_text":             "テキストが小さすぎる",
        "inconsistent_style":     "スタイルの不統一",
        "japanese_font_romaji":   "日本語フォントの問題",
        "image_quality":          "画像品質の問題",
        "western_ux_patterns":    "欧米UXパターンの欠如",
        "trust_signals":          "信頼シグナルの欠如",
    }
    JP_SEV = {"high": "重要", "medium": "中程度", "low": "軽微"}
    SEV_COLOR = {"high": "#dc2626", "medium": "#d97706", "low": "#16a34a"}

    issues_html = ""
    for iss in picked[:5]:
        sev    = iss.get("severity", "medium")
        col    = SEV_COLOR.get(sev, "#888")
        itype  = iss.get("type", "")
        jp_type = JP_TYPE.get(itype, itype.replace("_", " "))
        jp_sev  = JP_SEV.get(sev, sev)
        expl   = iss.get("explanation", "")
        issues_html += f"""
        <div style="border:1px solid #e5e7eb;border-left:3px solid {col};border-radius:6px;
                    padding:10px 14px;margin-bottom:8px;background:#fff;">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap;">
            <span style="width:8px;height:8px;border-radius:50%;background:{col};
                         display:inline-block;flex-shrink:0;"></span>
            <span style="font-weight:600;font-size:12px;color:#111;">{jp_type}</span>
            <span style="margin-left:auto;font-size:10px;font-weight:700;color:{col};
                         background:{col}18;padding:2px 6px;border-radius:4px;">{jp_sev}</span>
          </div>
          <p style="font-size:11px;color:#6b7280;margin:0;line-height:1.6;">{expl}</p>
        </div>"""

    # CSS-only score ring
    pct = max(0, min(100, score))
    ring_html = f"""
      <div style="position:relative;width:80px;height:80px;flex-shrink:0;">
        <div style="width:80px;height:80px;border-radius:50%;
                    background:conic-gradient({score_color} {pct}%, #e5e7eb {pct}% 100%);
                    display:flex;align-items:center;justify-content:center;">
          <div style="width:58px;height:58px;border-radius:50%;background:#f9fafb;
                      display:flex;flex-direction:column;align-items:center;justify-content:center;">
            <span style="font-size:20px;font-weight:800;color:{score_color};line-height:1;">{score}</span>
            <span style="font-size:9px;color:#9ca3af;">/100</span>
          </div>
        </div>
      </div>"""

    counts = scan.get("issueCounts", {})
    counts_html = ""
    for sev, col in [("high","#dc2626"),("medium","#d97706"),("low","#16a34a")]:
        n = counts.get(sev, 0)
        if n:
            jp_s = JP_SEV.get(sev, sev)
            counts_html += f'<span style="font-size:11px;font-weight:600;color:{col};margin-right:10px;">▲ {n} {jp_s}</span>'

    # Japanese score label
    if score >= 75:   jp_score_label = "良好"
    elif score >= 45: jp_score_label = "要改善"
    else:             jp_score_label = "要対応"

    domain = url.replace("https://","").replace("http://","").split("/")[0]
    jp_summary = summary
    total_label = f"合計 {total} 件の改善点を検出"

    return f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans','Yu Gothic',sans-serif;
                           background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;
                           overflow:hidden;max-width:520px;margin:0 auto;">
  <div style="background:#2e3fa3;padding:12px 18px;display:flex;align-items:center;gap:10px;">
    <span style="color:#fff;font-size:12px;font-weight:700;letter-spacing:0.05em;">SHINRAI AUDIT</span>
    <span style="color:#a5b4fc;font-size:11px;margin-left:auto;font-family:monospace;">{domain}</span>
  </div>
  <div style="padding:16px 18px;display:flex;align-items:flex-start;gap:16px;background:#fff;
              border-bottom:1px solid #e5e7eb;">
    {ring_html}
    <div style="flex:1;min-width:0;">
      <div style="font-size:11px;color:#6b7280;font-weight:600;letter-spacing:0.05em;margin-bottom:4px;">
        英語対応スコア — {jp_score_label}
      </div>
      {counts_html}
      <div style="font-size:10px;color:#9ca3af;margin-top:3px;">{total_label}</div>
      <p style="font-size:11px;color:#374151;line-height:1.6;margin:8px 0 0;">{jp_summary}</p>
    </div>
  </div>
  <div style="padding:14px 18px 16px;">
    <div style="font-size:11px;color:#6b7280;font-weight:600;letter-spacing:0.05em;margin-bottom:10px;">
      主な改善点
    </div>
    {issues_html if issues_html else '<p style="font-size:11px;color:#9ca3af;">改善点なし</p>'}
  </div>
  <div style="background:#f3f4f6;padding:12px 18px;border-top:1px solid #e5e7eb;text-align:center;">
    <span style="font-size:10px;color:#9ca3af;display:block;margin-bottom:8px;">
      Shinrai Prism Audit · 信頼ウェブ · 詳細レポートはお問い合わせください
    </span>
  </div>
</div>"""




async def _do_generate_email(prompt: str, system: str, ai_settings: AISettings,
                             report_card_html: str | None = None,
                             sender: dict | None = None) -> dict:
    import time
    t0 = time.monotonic()
    print(f"[generate-email]   → calling AI provider={ai_settings.ai_provider}")
    data = await call_ai(prompt, system, ai_settings, image_b64=None)
    usage = data.pop("_usage", {})
    subject     = data.get("subject", "")
    jp_paras    = data.get("jp_paragraphs", [])
    en_paras    = data.get("en_paragraphs", [])
    print(f"[generate-email] ═══ DONE in {time.monotonic()-t0:.1f}s | tokens={usage.get('total_tokens','?')} | jp={len(jp_paras)} en={len(en_paras)} paras")

    s = sender or {}
    name    = s.get("name", "")
    title   = s.get("title", "")
    email   = s.get("email", "").strip()
    website = s.get("website", "").strip().rstrip("/")
    if not website.startswith("http"):
        website = "https://" + website if website else ""
    print(f"[generate-email]   sender: name={name!r} email={email!r} website={website!r}")

    # Build paragraph HTML
    def paras_html(paras):
        return "".join(
            f'<p style="font-size:15px;color:#374151;line-height:1.8;margin:0 0 16px;">{p}</p>'
            for p in paras if p
        )

    card_block = f'<!--SHINRAI-CARD-START--><div style="margin:32px 0;">{report_card_html}</div><!--SHINRAI-CARD-END-->' if report_card_html else ""

    # CTA button style (reused for both sections)
    btn_style = (
        'display:inline-block;background:#2e3fa3;color:#ffffff;font-weight:700;' 
        'font-size:15px;text-decoration:none;padding:14px 36px;' 
        'border-radius:8px;letter-spacing:0.03em;'
    )
    sig_style  = "font-size:13px;color:#374151;line-height:2.2;margin:0;"
    hr_light   = '<hr style="border:none;border-top:1px solid #e5e7eb;margin:28px 0;">'
    hr_section = '<hr style="border:none;border-top:2px solid #e5e7eb;margin:0;">'

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Georgia,'Hiragino Mincho ProN','Yu Mincho',serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;">
<tr><td align="center" style="padding:24px 16px;">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">

  <!-- HEADER -->
  <tr><td style="background:#2e3fa3;padding:24px 32px;text-align:center;">
    <div style="color:#ffffff;font-size:18px;font-weight:800;letter-spacing:0.04em;margin-bottom:6px;">SHINRAI WEB | 信頼ウェブ</div>
    <div style="color:#a5b4fc;font-size:13px;">English Localisation for Japanese Businesses</div>
  </td></tr>

  <!-- JAPANESE BODY -->
  <tr><td style="padding:36px 40px 28px;">
    <p style="font-size:15px;color:#374151;line-height:1.8;margin:0 0 20px;">御担当者様、</p>
    {paras_html(jp_paras)}
    <div style="text-align:center;margin:28px 0;">
      <a href="{website}" style="{btn_style}">詳しくはこちら →</a>
    </div>
    {hr_light}
    <p style="{sig_style}">
      {name}<br>
      {title}<br> Shinrai Web (信頼ウェブ)<br>
      {email}<br>
      <a href="{website}" style="color:#2e3fa3;text-decoration:none;">{website}</a>
    </p>
  </td></tr>

  <!-- REPORT CARD -->
  <tr><td style="padding:0 40px;">
    {card_block}
  </td></tr>

  <!-- SECTION DIVIDER -->
  <tr><td>{hr_section}</td></tr>

  <!-- ENGLISH BODY -->
  <tr><td style="padding:36px 40px 28px;">
    <p style="font-size:15px;color:#374151;line-height:1.8;margin:0 0 20px;">Hi there,</p>
    {paras_html(en_paras)}
    <div style="text-align:center;margin:28px 0;">
      <a href="{website}" style="{btn_style}">See Our Work →</a>
    </div>
    {hr_light}
    <p style="{sig_style}">
      Best regards,<br>
      {name}<br>
      {title}<br> Shinrai Web (信頼ウェブ)<br>
      {email}<br>
      <a href="{website}" style="color:#2e3fa3;text-decoration:none;">{website}</a>
    </p>
  </td></tr>

  <!-- FOOTER -->
  <tr><td style="background:#1e2d7d;padding:18px 32px;text-align:center;">
    <p style="color:#a5b4fc;font-size:11px;margin:0;">
      Shinrai Web · <a href="{website}" style="color:#a5b4fc;">{website}</a> · {email}
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body></html>"""

    return {"subject": subject, "html": html, "_tokens": usage}


class RebuildCardRequest(BaseModel):
    scan_result: dict[str, Any]
    selected_issue_indices: list[int]  # indices into scan_result["issues"] to include

@app.post("/api/rebuild-card")
async def rebuild_card(req: RebuildCardRequest):
    """Rebuild the report card HTML with a specific subset of issues.
    Does NOT call AI — just re-renders the template with the chosen issues.
    Returns the full email HTML with the new card swapped in.
    """
    scan = dict(req.scan_result)
    all_issues = scan.get("issues", [])
    # Filter to selected indices only (clamp to valid range)
    selected = [all_issues[i] for i in req.selected_issue_indices if 0 <= i < len(all_issues)]
    scan_with_selected = {**scan, "issues": selected}

    # For deep scans the issues are in English — translate before building card
    scan_mode = scan.get("scan_mode", "shallow")
    if scan_mode == "deep":
        # We can't do async translation without AI settings here, so just use as-is
        # (deep mode rebuild is a best-effort — explanations stay in English)
        card_html = _build_report_card_html(scan_with_selected)
    else:
        card_html = _build_report_card_html(scan_with_selected)

    return {
        "card_html": card_html,
        "card_block": f'<!--SHINRAI-CARD-START--><div style="margin:32px 0;">{card_html}</div><!--SHINRAI-CARD-END-->',
    }


@app.post("/api/send-email")
async def send_email(req: SendEmailRequest):
    s = req.settings
    if not s.gmail_address or not s.gmail_app_password:
        raise HTTPException(400, "Gmail credentials not configured.")
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = req.subject
        visible_from = s.from_address.strip() if s.from_address.strip() else s.gmail_address
        msg["From"] = f"{s.your_name} <{visible_from}>"
        msg["To"] = req.to
        msg.attach(MIMEText(req.html, "html", "utf-8"))
        # Use STARTTLS on port 587 — more reliable than SMTP_SSL in Docker
        # where the system cert store may not include the full Gmail chain
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.ehlo()
            smtp.login(s.gmail_address, s.gmail_app_password)
            smtp.sendmail(s.gmail_address, req.to, msg.as_string())
        # Save email record to DB
        try:
            db_update_email(req.url, req.to, req.subject, req.html)
        except Exception as db_err:
            print(f"[db] ⚠ email save failed: {db_err}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Failed to send: {e}")


# ── History endpoints ────────────────────────────────────────────────────────

@app.get("/api/history")
async def get_history(page: int = 1, per_page: int = 20):
    """Paginated list of all scan records (summary fields only, no screenshot)."""
    all_records = db.all()
    # Sort by scanned_at descending
    all_records.sort(key=lambda r: r.get("scanned_at", ""), reverse=True)
    total = len(all_records)
    start = (page - 1) * per_page
    page_records = all_records[start:start + per_page]
    # Strip screenshot from list view
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


@app.get("/api/history/check")
async def check_history(url: str):
    """Check if a URL has been scanned before. Called before starting a new scan."""
    record = db.get(ScanRecord.url == url)
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


@app.get("/api/history/entry")
async def get_history_entry(url: str):
    """Full scan record including screenshot — for rehydrating the results page."""
    record = db.get(ScanRecord.url == url)
    if not record:
        raise HTTPException(404, "No record found for this URL")
    return record


@app.patch("/api/history/response")
async def toggle_response(url: str):
    """Toggle got_response flag for a URL's email record."""
    record = db.get(ScanRecord.url == url)
    if not record or not record.get("email"):
        raise HTTPException(404, "No email record found for this URL")
    current = record["email"].get("got_response", False)
    email_block = {**record["email"], "got_response": not current}
    db.update({"email": email_block}, ScanRecord.url == url)
    return {"got_response": not current}


@app.delete("/api/history/entry")
async def delete_history_entry(url: str):
    """Delete a scan record entirely."""
    removed = db.remove(ScanRecord.url == url)
    if not removed:
        raise HTTPException(404, "No record found for this URL")
    return {"ok": True}


class SaveEmailDraftRequest(BaseModel):
    html: str

@app.post("/api/history/save-email")
async def save_email_draft(url: str, subject: str, body: SaveEmailDraftRequest):
    """Save a generated (but not yet sent) email draft to the DB record."""
    record = db.get(ScanRecord.url == url)
    if not record:
        raise HTTPException(404, "No scan record for this URL")
    existing_email = record.get("email") or {}
    email_block = {
        **existing_email,
        "subject": subject,
        "html":    body.html,
        # preserve recipient/sent_at/got_response if they exist
    }
    db.update({"email": email_block}, ScanRecord.url == url)
    return {"ok": True}


@app.post("/api/history/update-email-recipient")
async def update_email_recipient(url: str, recipient: str):
    """Update recipient in DB when user types in email drawer."""
    record = db.get(ScanRecord.url == url)
    if not record:
        return {"ok": False}
    existing_email = record.get("email") or {}
    db.update({"email": {**existing_email, "recipient": recipient}}, ScanRecord.url == url)
    return {"ok": True}


@app.post("/api/history/save-deep-scan")
async def save_deep_scan(body: dict):
    """Explicitly save a deep scan to history when user requests it."""
    try:
        db_upsert_scan(body)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/history/check")
async def check_url_in_history(url: str):
    record = db.get(ScanRecord.url == url)
    if not record:
        return {"exists": False}
    return {"exists": True, "record": record}


@app.post("/api/agent-chat")
async def agent_chat(req: AgentChatRequest):
    print(f"[agent-chat] provider={req.settings.ai_provider} model={req.settings.ollama_model}")
    system = AGENT_SYSTEM.format(context=req.scan_context[:6000])
    messages = [{"role": "system", "content": system}] + \
               [{"role": m.role, "content": m.content} for m in req.messages]
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
                    headers={"x-api-key": req.settings.anthropic_api_key, "anthropic-version": "2023-06-01"},
                    json={"model": req.settings.anthropic_model, "max_tokens": 1024,
                          "system": system,
                          "messages": [{"role": m.role, "content": m.content} for m in req.messages]},
                )
                r.raise_for_status()
                reply = r.json()["content"][0]["text"]
        else:
            reply = await call_ollama_chat(messages, req.settings.ollama_base_url, req.settings.ollama_model)
        return {"reply": reply}
    except Exception as e:
        print(f"[agent-chat] ERROR:\n{traceback.format_exc()}")
        raise HTTPException(502, f"Agent error: {e}")
