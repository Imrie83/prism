"""
Email service routes for Prism:
  POST /api/generate-email  — AI-generated bilingual outreach email
  POST /api/rebuild-card    — re-render report card with selected issues
  POST /api/send-email      — send via Gmail SMTP
"""
import asyncio
import json
import smtplib
import ssl
import traceback

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .ai_client import call_ai, call_claude, call_openai, call_ollama, _extract_json
from .db import update_email
from .models import (
    AISettings, GenerateEmailRequest, RebuildCardRequest, SendEmailRequest,
)
from .prompts import EMAIL_SYSTEM

router = APIRouter()


# ── Report card builder ───────────────────────────────────────────────────────

JP_TYPE = {
    "untranslated_nav_ui":    "未翻訳ナビ・UI",
    "untranslated_body":      "未翻訳本文",
    "untranslated_japanese":  "未翻訳テキスト",
    "untranslated_image_text":"画像内の未翻訳テキスト",
    "machine_translation":    "機械翻訳の問題",
    "grammar_error":          "文法エラー",
    "awkward_phrasing":       "不自然な表現",
    "missing_context":        "文脈の欠如",
    "cultural_mismatch":      "文化的ミスマッチ",
    "weak_cta":               "弱いCTA",
    "date_number_format":     "日付・数字の形式",
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
    "mobile_usability":       "モバイル対応の問題",
    "navigation_ux":          "ナビゲーションの問題",
    "social_proof":           "社会的証明の欠如",
    "contact_accessibility":  "連絡先のアクセス性",
    "form_ux":                "フォームのUX問題",
    "pdf_heavy":              "PDF依存の問題",
    "trust_signals":          "信頼シグナルの欠如",
    "western_ux_patterns":    "欧米UXパターンの欠如",
}

JP_SEV    = {"high": "重要", "medium": "中程度", "low": "軽微"}
SEV_COLOR = {"high": "#dc2626", "medium": "#d97706", "low": "#16a34a"}

TEXT_TYPES   = {
    "untranslated_nav_ui", "untranslated_body", "untranslated_japanese",
    "machine_translation", "grammar_error", "awkward_phrasing",
    "missing_context", "cultural_mismatch", "weak_cta", "date_number_format",
    "untranslated_image_text",
}
VISUAL_TYPES = {
    "visual_hierarchy", "cluttered_layout", "poor_contrast", "broken_layout",
    "small_text", "inconsistent_style", "colour_psychology", "image_quality",
    "japanese_font_romaji", "missing_cta_visual", "mobile_usability",
}
UX_TYPES     = {
    "navigation_ux", "social_proof", "contact_accessibility",
    "form_ux", "pdf_heavy", "trust_signals", "western_ux_patterns",
}


def build_report_card_html(scan: dict) -> str:
    """Build light-theme HTML report card for email embedding."""
    score   = scan.get("score", 0)
    summary = scan.get("summary", "")
    url     = scan.get("url", "")
    issues  = scan.get("issues", [])
    total   = scan.get("totalIssues", len(issues))

    score_color = "#16a34a" if score >= 75 else "#d97706" if score >= 45 else "#dc2626"

    # Pick up to 5 issues with category variety
    picked: list = []
    for category in (TEXT_TYPES, VISUAL_TYPES, UX_TYPES):
        for sev in ("high", "medium", "low"):
            for iss in issues:
                if iss.get("type") in category and iss.get("severity") == sev and iss not in picked:
                    picked.append(iss)
                    break
            if any(p.get("type") in category for p in picked):
                break
    for iss in issues:
        if len(picked) >= 5:
            break
        if iss not in picked:
            picked.append(iss)

    issues_html = ""
    for iss in picked[:5]:
        sev     = iss.get("severity", "medium")
        col     = SEV_COLOR.get(sev, "#888")
        itype   = iss.get("type", "")
        jp_type = JP_TYPE.get(itype, itype.replace("_", " "))
        jp_sev  = JP_SEV.get(sev, sev)
        expl    = iss.get("explanation", "")
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

    pct      = max(0, min(100, score))
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

    counts       = scan.get("issueCounts", {})
    counts_html  = ""
    for sev, col in [("high", "#dc2626"), ("medium", "#d97706"), ("low", "#16a34a")]:
        n = counts.get(sev, 0)
        if n:
            counts_html += f'<span style="font-size:11px;font-weight:600;color:{col};margin-right:10px;">▲ {n} {JP_SEV.get(sev, sev)}</span>'

    jp_score_label = "良好" if score >= 75 else "要改善" if score >= 45 else "要対応"
    domain         = url.replace("https://", "").replace("http://", "").split("/")[0]
    total_label    = f"合計 {total} 件の改善点を検出"

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
      <p style="font-size:11px;color:#374151;line-height:1.6;margin:8px 0 0;">{summary}</p>
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


# ── Email generation helpers ──────────────────────────────────────────────────

async def _translate_scan_for_card(scan: dict, ai_settings: AISettings) -> dict:
    """Translate summary + issue text to Japanese for the report card (deep scan mode)."""
    summary = scan.get("summary", "")
    issues  = scan.get("issues", [])
    strings = [summary] if summary else [""]
    for iss in issues:
        strings.append(iss.get("location", ""))
        strings.append(iss.get("explanation", "")[:120])

    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(strings))
    prompt   = f"Translate the following numbered English strings to natural Japanese.\nReturn ONLY a JSON array of translated strings in the same order, same count.\nKeep proper nouns, URLs, and brand names unchanged.\n\n{numbered}"
    system   = "You are a professional English-to-Japanese translator. Return only a JSON array of strings."

    try:
        if ai_settings.ai_provider == "claude":
            raw, _ = await call_claude(prompt, system, ai_settings.anthropic_api_key, ai_settings.anthropic_model)
        elif ai_settings.ai_provider == "openai":
            raw, _ = await call_openai(prompt, system, ai_settings.openai_api_key, ai_settings.openai_model)
        else:
            raw, _ = await call_ollama(prompt, system, ai_settings.ollama_base_url, ai_settings.ollama_model)
        translated = json.loads(_extract_json(raw))
        if not isinstance(translated, list) or len(translated) < len(strings):
            raise ValueError("translation list length mismatch")
    except Exception as e:
        print(f"[translate-card] ⚠ translation failed ({e}), using original English")
        return scan

    scan_jp             = dict(scan)
    scan_jp["summary"]  = translated[0] if translated else summary
    jp_issues           = []
    for idx, iss in enumerate(issues):
        jp_iss = dict(iss)
        loc_i  = 1 + idx * 2
        expl_i = 1 + idx * 2 + 1
        if loc_i < len(translated):
            jp_iss["location"]    = translated[loc_i]
        if expl_i < len(translated):
            jp_iss["explanation"] = translated[expl_i]
        jp_issues.append(jp_iss)
    scan_jp["issues"] = jp_issues
    print(f"[translate-card] ✓ translated {len(strings)} strings to Japanese")
    return scan_jp


async def _do_generate_email(
    prompt: str,
    system: str,
    ai_settings: AISettings,
    report_card_html: str | None = None,
    sender: dict | None = None,
) -> dict:
    import time
    t0    = time.monotonic()
    print(f"[generate-email]   → calling AI provider={ai_settings.ai_provider}")
    data  = await call_ai(prompt, system, ai_settings)
    usage = data.pop("_usage", {})

    subject  = data.get("subject", "")
    jp_paras = data.get("jp_paragraphs", [])
    en_paras = data.get("en_paragraphs", [])
    print(f"[generate-email] ═══ DONE in {time.monotonic()-t0:.1f}s | tokens={usage.get('total_tokens', '?')} | jp={len(jp_paras)} en={len(en_paras)} paras")

    s       = sender or {}
    name    = s.get("name", "")
    title   = s.get("title", "")
    email   = s.get("email", "").strip()
    website = s.get("website", "").strip().rstrip("/")
    if not website.startswith("http"):
        website = "https://" + website if website else ""

    def paras_html(paras: list) -> str:
        return "".join(
            f'<p style="font-size:15px;color:#374151;line-height:1.8;margin:0 0 16px;">{p}</p>'
            for p in paras if p
        )

    card_block = (
        f'<!--SHINRAI-CARD-START--><div style="margin:32px 0;">{report_card_html}</div><!--SHINRAI-CARD-END-->'
        if report_card_html else ""
    )
    btn_style  = ('display:inline-block;background:#2e3fa3;color:#ffffff;font-weight:700;'
                  'font-size:15px;text-decoration:none;padding:14px 36px;'
                  'border-radius:8px;letter-spacing:0.03em;')
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
  <tr><td style="background:#2e3fa3;padding:24px 32px;text-align:center;">
    <div style="color:#ffffff;font-size:18px;font-weight:800;letter-spacing:0.04em;margin-bottom:6px;">SHINRAI WEB | 信頼ウェブ</div>
    <div style="color:#a5b4fc;font-size:13px;">English Localisation for Japanese Businesses</div>
  </td></tr>
  <tr><td style="padding:36px 40px 28px;">
    <p style="font-size:15px;color:#374151;line-height:1.8;margin:0 0 20px;">御担当者様、</p>
    {paras_html(jp_paras)}
    <div style="text-align:center;margin:28px 0;">
      <a href="{website}" style="{btn_style}">詳しくはこちら →</a>
    </div>
    {hr_light}
    <p style="{sig_style}">{name}<br>{title}<br>Shinrai Web (信頼ウェブ)<br>{email}<br>
      <a href="{website}" style="color:#2e3fa3;text-decoration:none;">{website}</a></p>
  </td></tr>
  <tr><td style="padding:0 40px;">{card_block}</td></tr>
  <tr><td>{hr_section}</td></tr>
  <tr><td style="padding:36px 40px 28px;">
    <p style="font-size:15px;color:#374151;line-height:1.8;margin:0 0 20px;">Hi there,</p>
    {paras_html(en_paras)}
    <div style="text-align:center;margin:28px 0;">
      <a href="{website}" style="{btn_style}">See Our Work →</a>
    </div>
    {hr_light}
    <p style="{sig_style}">Best regards,<br>{name}<br>{title}<br>Shinrai Web (信頼ウェブ)<br>{email}<br>
      <a href="{website}" style="color:#2e3fa3;text-decoration:none;">{website}</a></p>
  </td></tr>
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


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/api/generate-email")
async def generate_email(req: GenerateEmailRequest):
    """Streams keepalives while AI writes the email — prevents gateway 504s."""
    import time
    s      = req.settings
    system = EMAIL_SYSTEM.format(
        name=s.your_name, title=s.your_title,
        website=s.your_website, email=s.your_email,
    )
    scan    = req.scan_result
    url     = scan.get("url", "their website")
    score   = scan.get("score", "N/A")
    summary = scan.get("summary", "")
    title   = scan.get("title", "")
    issues  = scan.get("issues", [])

    # Infer positives from what ISN'T broken
    issue_types_set = {i.get("type", "") for i in issues}
    severity_counts: dict[str, int] = {}
    for iss in issues:
        sev = iss.get("severity", "medium")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    positives = []
    if "broken_layout" not in issue_types_set and "poor_contrast" not in issue_types_set:
        positives.append("clean, well-structured visual layout")
    if "image_quality" not in issue_types_set:
        positives.append("good quality photography or imagery")
    if "cluttered_layout" not in issue_types_set:
        positives.append("good use of whitespace and clear organisation")
    if "visual_hierarchy" not in issue_types_set:
        positives.append("clear visual hierarchy and readable structure")
    if severity_counts.get("high", 0) == 0:
        positives.append("solid technical foundation with no critical issues")
    if score and int(score) >= 60:
        positives.append("site that already shows real care and attention")
    positives_text = ", ".join(positives[:2]) if positives else "a site that clearly reflects genuine expertise in its field"

    # Build opportunity hints
    opportunity_hints = []
    for iss in issues[:8]:
        loc   = iss.get("location", "")
        itype = iss.get("type", "")
        if itype in ("untranslated_nav_ui", "untranslated_body", "untranslated_japanese") and loc:
            opportunity_hints.append(f"making navigation and key content accessible to English readers (currently Japanese-only in the {loc})")
        elif itype in ("machine_translation", "grammar_error", "awkward_phrasing") and loc:
            opportunity_hints.append("replacing stilted auto-translated text with natural English that builds trust")
        elif itype in ("weak_cta", "missing_cta_visual") and loc:
            opportunity_hints.append("adding a clear English call-to-action so international visitors know how to book or contact")
        elif itype in ("trust_signals", "social_proof", "contact_accessibility"):
            opportunity_hints.append("adding English trust signals (reviews, contact info) that Western visitors expect")
        elif itype in ("mobile_usability", "navigation_ux"):
            opportunity_hints.append("improving the mobile and navigation experience for international visitors")
        if len(opportunity_hints) >= 2:
            break
    hints_text = "; and ".join(opportunity_hints[:2]) if opportunity_hints else "making the site fully navigable and readable for English-speaking visitors"

    ai_settings = AISettings(
        ai_provider=s.ai_provider,
        ollama_base_url=s.ollama_base_url,
        ollama_model=s.ollama_model,
        openai_api_key=s.openai_api_key,
        anthropic_api_key=s.anthropic_api_key,
        anthropic_model=s.anthropic_model,
    )

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
        scan_for_card = scan

    report_card_html = build_report_card_html(scan_for_card)

    prompt = f"""Write a bilingual cold outreach email for this Japanese business. Follow your system prompt structure precisely.

SITE DETAILS:
  URL: {url}
  Page title: {title or "unknown"}
  English-readiness score: {score}/100
  What the site is about: {summary}

GENUINE POSITIVES to draw the compliment from (use one of these specifically):
  {positives_text}

SPECIFIC OPPORTUNITY to mention (frame as upside — what international visitors could gain):
  {hints_text}

SERVICES TO REFERENCE (choose the 2 most relevant to this site's situation):
  - English translation and localisation of Japanese website content
  - Natural English copywriting (replacing machine-translated text)
  - Full web development and redesign if they want to go further
  - UX improvements for international visitors

REMEMBER:
- Open with a formal self-introduction, not a compliment
- Acknowledge their time is valuable before making your pitch
- The compliment must be SPECIFIC to this site, not generic
- Keep English under 150 words total
- One clear ask at the end — nothing more
- The personalised report is available at {req.settings.your_website}

Return the bilingual email as JSON following your system prompt exactly."""

    print(f"[generate-email] ═══ START url={url} score={score} provider={ai_settings.ai_provider}")
    print(f"[generate-email]   opportunity hints: {hints_text}")
    print(f"[generate-email]   report card html: {len(report_card_html)} chars")

    async def stream():
        sender = {"name": s.your_name, "title": s.your_title, "email": s.your_email, "website": s.your_website}
        task   = asyncio.create_task(_do_generate_email(prompt, system, ai_settings, report_card_html, sender))
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


@router.post("/api/rebuild-card")
async def rebuild_card(req: RebuildCardRequest):
    """Re-render the report card HTML with a specific subset of issues."""
    scan       = dict(req.scan_result)
    all_issues = scan.get("issues", [])
    selected   = [all_issues[i] for i in req.selected_issue_indices if 0 <= i < len(all_issues)]
    card_html  = build_report_card_html({**scan, "issues": selected})
    return {
        "card_html":  card_html,
        "card_block": f'<!--SHINRAI-CARD-START--><div style="margin:32px 0;">{card_html}</div><!--SHINRAI-CARD-END-->',
    }


@router.post("/api/send-email")
async def send_email(req: SendEmailRequest):
    from email.mime.multipart import MIMEMultipart
    from email.mime.text      import MIMEText

    s = req.settings
    if not s.gmail_address or not s.gmail_app_password:
        raise HTTPException(400, "Gmail credentials not configured.")
    try:
        msg              = MIMEMultipart("alternative")
        msg["Subject"]   = req.subject
        visible_from     = s.from_address.strip() if s.from_address.strip() else s.gmail_address
        msg["From"]      = f"{s.your_name} <{visible_from}>"
        msg["To"]        = req.to
        msg.attach(MIMEText(req.html, "html", "utf-8"))

        ctx                  = ssl.create_default_context()
        ctx.check_hostname   = False
        ctx.verify_mode      = ssl.CERT_NONE
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.ehlo()
            smtp.login(s.gmail_address, s.gmail_app_password)
            smtp.sendmail(s.gmail_address, req.to, msg.as_string())

        try:
            update_email(req.url, req.to, req.subject, req.html)
        except Exception as db_err:
            print(f"[db] ⚠ email save failed: {db_err}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Failed to send: {e}")
