"""
AI provider clients for Prism.

Supports Ollama (local), OpenAI, and Anthropic Claude.
All functions return (response_text, usage_dict) tuples.
call_ai() dispatches to the right provider and returns parsed JSON.
"""

import json
import re

import os

import httpx
from dotenv import load_dotenv
load_dotenv()

from .models import AISettings


async def call_ollama(
    prompt: str,
    system: str,
    base_url: str,
    model: str,
    images: list[str] | None = None,
) -> tuple[str, dict]:
    user_msg: dict = {"role": "user", "content": prompt}
    if images:
        user_msg["images"] = images  # Ollama supports multiple images natively

    url = f"{base_url.rstrip('/')}/api/chat"
    prompt_tokens = (len(system) + len(prompt)) // 4
    print(f"[ollama] ▶ POST {url}")
    print(
        f"[ollama]   model={model} | images={len(images) if images else 0} | prompt_chars={len(system) + len(prompt)} (~{prompt_tokens} tokens)"
    )

    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(
            url,
            json={
                "model": model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    user_msg,
                ],
                "format": "json",
                "options": {"temperature": 0.2, "num_ctx": 8192},
            },
        )
        print(f"[ollama]   status={r.status_code}")
        r.raise_for_status()
        rj = r.json()
        content = rj["message"]["content"]
        usage = {
            "prompt_tokens": rj.get("prompt_eval_count", prompt_tokens),
            "completion_tokens": rj.get("eval_count", len(content) // 4),
            "total_tokens": rj.get("prompt_eval_count", prompt_tokens)
            + rj.get("eval_count", len(content) // 4),
            "provider": "ollama",
            "model": model,
        }
        print(
            f"[ollama]   ✓ response_chars={len(content)} | tokens: prompt={usage['prompt_tokens']} completion={usage['completion_tokens']} total={usage['total_tokens']}"
        )
        return content, usage


async def call_ollama_chat(messages: list, base_url: str, model: str) -> str:
    url = f"{base_url.rstrip('/')}/api/chat"
    total_chars = sum(len(m.get("content", "")) for m in messages)
    print(
        f"[ollama-chat] ▶ POST {url} model={model} | messages={len(messages)} total_chars={total_chars} (~{total_chars // 4} tokens)"
    )
    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(
            url,
            json={
                "model": model,
                "stream": False,
                "messages": messages,
                "options": {"temperature": 0.3, "num_ctx": 8192},
            },
        )
        rj = r.json()
        reply = rj["message"]["content"]
        print(
            f"[ollama-chat] ✓ status={r.status_code} | tokens: prompt={rj.get('prompt_eval_count', '?')} completion={rj.get('eval_count', '?')}"
        )
        r.raise_for_status()
        return reply


async def call_openai(
    prompt: str,
    system: str,
    api_key: str,
    model: str,
    images: list[str] | None = None,
) -> tuple[str, dict]:
    content: list = []
    for img in images or []:
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}}
        )
    content.append({"type": "text", "text": prompt})
    print(
        f"[openai] ▶ POST chat/completions model={model} | images={len(images) if images else 0} | prompt_chars={len(system) + len(prompt)}"
    )
    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', api_key)}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": content},
                ],
                "response_format": {"type": "json_object"},
            },
        )
        r.raise_for_status()
        rj = r.json()
        reply = rj["choices"][0]["message"]["content"]
        u = rj.get("usage", {})
        usage = {
            "prompt_tokens": u.get("prompt_tokens", 0),
            "completion_tokens": u.get("completion_tokens", 0),
            "total_tokens": u.get("total_tokens", 0),
            "provider": "openai",
            "model": model,
        }
        print(
            f"[openai] ✓ tokens: prompt={usage['prompt_tokens']} completion={usage['completion_tokens']} total={usage['total_tokens']}"
        )
        return reply, usage


async def call_claude(
    prompt: str,
    system: str,
    api_key: str,
    model: str,
    images: list[str] | None = None,
) -> tuple[str, dict]:
    import base64 as _b64

    content: list = []
    for img in images or []:
        clean_b64 = img
        if "," in img[:50]:
            clean_b64 = img.split(",", 1)[1]
        try:
            header = _b64.b64decode(clean_b64[:20])
            media_type = "image/png" if header[:4] == b"\x89PNG" else "image/jpeg"
        except Exception:
            media_type = "image/jpeg"
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": clean_b64,
                },
            }
        )
    content.append({"type": "text", "text": prompt})
    print(
        f"[claude] ▶ POST messages model={model} | images={len(images) if images else 0} | prompt_chars={len(system) + len(prompt)}"
    )

    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": os.environ.get("ANTHROPIC_API_KEY", api_key),
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 8192,
                "system": system,
                "messages": [{"role": "user", "content": content}],
            },
        )
        if not r.is_success:
            err_body = ""
            try:
                err_body = r.json()
            except Exception:
                err_body = r.text[:500]
            print(f"[claude] ✗ {r.status_code} error body: {err_body}")
            # Retry without images on 400
            if r.status_code == 400 and images and "image" in str(err_body).lower():
                print("[claude] ⚠ Retrying without images due to 400 error")
                content_no_img = [c for c in content if c.get("type") != "image"]
                r2 = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": os.environ.get("ANTHROPIC_API_KEY", api_key),
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": 8192,
                        "system": system,
                        "messages": [{"role": "user", "content": content_no_img}],
                    },
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
            "prompt_tokens": u.get("input_tokens", 0),
            "completion_tokens": u.get("output_tokens", 0),
            "total_tokens": u.get("input_tokens", 0) + u.get("output_tokens", 0),
            "provider": "claude",
            "model": model,
            "stop_reason": stop_reason,
        }
        if stop_reason == "max_tokens":
            print(
                "[claude] ⚠ WARNING: response hit max_tokens limit — output was TRUNCATED."
            )
        print(
            f"[claude] ✓ tokens: prompt={usage['prompt_tokens']} completion={usage['completion_tokens']} total={usage['total_tokens']} stop={stop_reason}"
        )
        return reply, usage


def _extract_json(raw: str) -> str:
    """Strip markdown fences and find the outermost JSON object or array."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        inner = []
        for line in lines[1:]:
            if line.strip() == "```":
                break
            inner.append(line)
        raw = "\n".join(inner).strip()
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = raw.find(start_char)
        if start != -1:
            end = raw.rfind(end_char)
            if end != -1 and end > start:
                return raw[start : end + 1]
    return raw


def _repair_json(raw: str) -> str:
    """Fix unescaped double-quotes inside JSON string values — the most common LLM mistake."""
    # Pass 1: trailing commas
    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    lines = raw.split("\n")
    out = []
    for line in lines:
        m = re.match(r'^(\s*"[^"]+?"\s*:\s*)"(.*)"(,?)$', line)
        if m:
            prefix = m.group(1)
            value = m.group(2)
            trailing = m.group(3)
            ph = "\x00QUOT\x00"
            value = value.replace('\\"', ph)
            value = value.replace('"', '\\"')
            value = value.replace(ph, '\\"')
            out.append(f'{prefix}"{value}"{trailing}')
        else:
            out.append(line)
    return "\n".join(out)


async def call_ai(
    prompt: str,
    system: str,
    settings: AISettings,
    images: list[str] | None = None,
) -> dict:
    """Dispatch to the configured AI provider, parse JSON, return dict with _usage key."""
    if settings.ai_provider == "openai":
        raw, usage = await call_openai(
            prompt, system, getattr(settings, "openai_api_key", ""), settings.openai_model, images
        )
    elif settings.ai_provider == "claude":
        raw, usage = await call_claude(
            prompt, system, getattr(settings, "anthropic_api_key", ""), settings.anthropic_model, images
        )
    else:
        raw, usage = await call_ollama(
            prompt, system, settings.ollama_base_url, settings.ollama_model, images
        )

    if usage.get("stop_reason") == "max_tokens":
        raise ValueError(
            f"AI response was truncated (hit max_tokens={usage.get('completion_tokens')} limit). "
            "The JSON is incomplete and cannot be parsed. Try reducing max_deep_pages or the number of issues requested."
        )

    print(f"[call_ai] raw response length={len(raw)} first_chars={repr(raw[:80])}")
    cleaned = _extract_json(raw)
    print(
        f"[call_ai] after extraction length={len(cleaned)} first_chars={repr(cleaned[:80])}"
    )

    try:
        result = json.loads(cleaned)
        print("[call_ai] ✓ JSON parsed OK")
    except json.JSONDecodeError as e1:
        print(f"[call_ai] standard parse failed ({e1}), attempting repair...")
        try:
            repaired = _repair_json(cleaned)
            result = json.loads(repaired)
            print("[call_ai] ✓ JSON parsed OK after repair")
        except json.JSONDecodeError as e2:
            print(f"[call_ai] ✗ JSON repair also failed: {e2}")
            print(f"[call_ai] FULL RAW RESPONSE ({len(raw)} chars):\n{raw}")
            raise ValueError(
                f"AI returned invalid JSON (even after repair): {e2}. Raw (first 200): {raw[:200]!r}"
            )

    result["_usage"] = usage
    return result


# ── Anthropic Message Batches API ─────────────────────────────────────────────

async def submit_claude_batch(
    requests: list[dict],
    api_key: str,
    model: str,
) -> tuple[str, dict[str, str]]:
    """Submit a batch of Claude requests. Returns (batch_id, safe_to_original_map).

    The Anthropic Batch API requires custom_id to match ^[a-zA-Z0-9_-]{1,64}$.
    URLs contain characters that fail this — so we generate safe internal IDs
    (req_0001 …) and return a mapping back to the caller's original custom_ids.
    """
    import base64 as _b64

    safe_to_original: dict[str, str] = {}
    batch_requests = []
    for idx, req in enumerate(requests):
        safe_id = f"req_{idx:04d}"
        safe_to_original[safe_id] = req["custom_id"]
        content: list = []
        for img in req.get("images") or []:
            clean_b64 = img
            if "," in img[:50]:
                clean_b64 = img.split(",", 1)[1]
            try:
                header = _b64.b64decode(clean_b64[:20])
                media_type = "image/png" if header[:4] == b"\x89PNG" else "image/jpeg"
            except Exception:
                media_type = "image/jpeg"
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": clean_b64},
                }
            )
        content.append({"type": "text", "text": req["prompt"]})
        batch_requests.append(
            {
                "custom_id": safe_id,
                "params": {
                    "model": model,
                    "max_tokens": 8192,
                    "system": req["system"],
                    "messages": [{"role": "user", "content": content}],
                },
            }
        )

    print(f"[claude-batch] ▶ submitting {len(batch_requests)} requests")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages/batches",
            headers={
                "x-api-key": os.environ.get("ANTHROPIC_API_KEY", api_key),
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "message-batches-2024-09-24",
                "Content-Type": "application/json",
            },
            json={"requests": batch_requests},
        )
        if not r.is_success:
            print(f"[claude-batch] ✗ submission failed {r.status_code}: {r.text[:500]}")
            r.raise_for_status()
        batch_id = r.json()["id"]
        print(f"[claude-batch] ✓ batch_id={batch_id}")
        return batch_id, safe_to_original

async def poll_claude_batch(batch_id: str, api_key: str, safe_to_original: dict[str, str] | None = None) -> dict[str, dict]:
    """Poll until batch completes. Returns {original_custom_id: parsed_result_dict}.

    safe_to_original maps the internal safe IDs (req_0001 …) back to the
    caller's original custom_ids (e.g. URLs). If None, uses the raw IDs.
    Polls with exponential back-off (5s → 60s cap).
    """
    import asyncio

    delay = 5
    url = f"https://api.anthropic.com/v1/messages/batches/{batch_id}"
    headers = {
        "x-api-key": os.environ.get("ANTHROPIC_API_KEY", api_key),
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "message-batches-2024-09-24",
    }
    while True:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            batch = r.json()
        status = batch["processing_status"]
        counts = batch.get("request_counts", {})
        print(
            f"[claude-batch] status={status} processing={counts.get('processing',0)} "
            f"succeeded={counts.get('succeeded',0)} errored={counts.get('errored',0)}"
        )
        if status == "ended":
            break
        await asyncio.sleep(min(delay, 60))
        delay = min(delay * 1.5, 60)

    # Fetch results
    results_url = batch.get("results_url")
    if not results_url:
        raise ValueError("[claude-batch] batch ended but no results_url")

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.get(results_url, headers=headers)
        r.raise_for_status()
        raw = r.text

    out: dict[str, dict] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        safe_id = obj.get("custom_id", "")
        # Translate back to the original custom_id (e.g. URL)
        original_id = (safe_to_original or {}).get(safe_id, safe_id)
        result = obj.get("result", {})
        if result.get("type") != "succeeded":
            print(f"[claude-batch] ⚠ request {original_id} not succeeded: {result.get('type')}")
            out[original_id] = {"error": result.get("type", "unknown")}
            continue
        message = result.get("message", {})
        raw_text = message["content"][0]["text"]
        u = message.get("usage", {})
        usage = {
            "prompt_tokens": u.get("input_tokens", 0),
            "completion_tokens": u.get("output_tokens", 0),
            "total_tokens": u.get("input_tokens", 0) + u.get("output_tokens", 0),
            "provider": "claude",
            "model": message.get("model", ""),
        }
        cleaned = _extract_json(raw_text)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            repaired = _repair_json(cleaned)
            parsed = json.loads(repaired)
        parsed["_usage"] = usage
        out[original_id] = parsed

    print(f"[claude-batch] ✓ fetched {len(out)} results")
    return out

async def call_ai_batch(
    requests: list[dict],
    settings: "AISettings",
) -> dict[str, dict]:
    """Run multiple AI requests as a batch (Claude only) or sequentially (others).

    Each item in `requests`: {custom_id, system, prompt, images?}
    Returns {custom_id: parsed_result_dict_with_usage}
    """
    if settings.ai_provider == "claude":
        api_key = getattr(settings, "anthropic_api_key", "")
        model = settings.anthropic_model
        batch_id, safe_to_original = await submit_claude_batch(requests, api_key, model)
        return await poll_claude_batch(batch_id, api_key, safe_to_original)
    else:
        # Fallback: run sequentially for Ollama / OpenAI
        results: dict[str, dict] = {}
        for req in requests:
            try:
                result = await call_ai(
                    req["prompt"], req["system"], settings, req.get("images")
                )
                results[req["custom_id"]] = result
            except Exception as e:
                results[req["custom_id"]] = {"error": str(e)}
        return results
