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

from .ai_client import call_ai, call_claude, call_openai, call_ollama, _extract_json, call_ai_batch
from .db import update_email
import os

from dotenv import load_dotenv
load_dotenv()

from .models import (
    AISettings,
    GenerateEmailRequest,
    RebuildCardRequest,
    SendEmailRequest,
    ScheduleEmailRequest,
    CancelScheduleRequest,
    BatchGenerateEmailRequest,
)
from .prompts import EMAIL_SYSTEM, EMAIL_SYSTEM_EXPERIMENTAL

router = APIRouter()


# ── Report card builder ───────────────────────────────────────────────────────

JP_TYPE = {
    "untranslated_nav_ui": "未翻訳ナビ・UI",
    "untranslated_body": "未翻訳本文",
    "untranslated_japanese": "未翻訳テキスト",
    "untranslated_image_text": "画像内の未翻訳テキスト",
    "machine_translation": "機械翻訳の問題",
    "grammar_error": "文法エラー",
    "awkward_phrasing": "不自然な表現",
    "missing_context": "文脈の欠如",
    "cultural_mismatch": "文化的ミスマッチ",
    "weak_cta": "弱いCTA",
    "date_number_format": "日付・数字の形式",
    "visual_hierarchy": "視覚的階層の問題",
    "poor_contrast": "コントラスト不足",
    "cluttered_layout": "レイアウトの混雑",
    "colour_psychology": "色彩の問題",
    "missing_cta_visual": "CTAボタンの欠如",
    "broken_layout": "レイアウトの崩れ",
    "small_text": "テキストが小さすぎる",
    "inconsistent_style": "スタイルの不統一",
    "japanese_font_romaji": "日本語フォントの問題",
    "image_quality": "画像品質の問題",
    "mobile_usability": "モバイル対応の問題",
    "navigation_ux": "ナビゲーションの問題",
    "social_proof": "社会的証明の欠如",
    "contact_accessibility": "連絡先のアクセス性",
    "form_ux": "フォームのUX問題",
    "pdf_heavy": "PDF依存の問題",
    "trust_signals": "信頼シグナルの欠如",
    "western_ux_patterns": "欧米UXパターンの欠如",
}

JP_SEV = {"high": "重要", "medium": "中程度", "low": "軽微"}
SEV_COLOR = {"high": "#dc2626", "medium": "#d97706", "low": "#16a34a"}

TEXT_TYPES = {
    "untranslated_nav_ui",
    "untranslated_body",
    "untranslated_japanese",
    "machine_translation",
    "grammar_error",
    "awkward_phrasing",
    "missing_context",
    "cultural_mismatch",
    "weak_cta",
    "date_number_format",
    "untranslated_image_text",
}
VISUAL_TYPES = {
    "visual_hierarchy",
    "cluttered_layout",
    "poor_contrast",
    "broken_layout",
    "small_text",
    "inconsistent_style",
    "colour_psychology",
    "image_quality",
    "japanese_font_romaji",
    "missing_cta_visual",
    "mobile_usability",
}
UX_TYPES = {
    "navigation_ux",
    "social_proof",
    "contact_accessibility",
    "form_ux",
    "pdf_heavy",
    "trust_signals",
    "western_ux_patterns",
}


def build_report_card_html(scan: dict, report_summary: list[str] | None = None) -> str:
    score = scan.get("score", 0)
    url = scan.get("url", "")
    summary = scan.get("summary", "")
    issues = scan.get("issues", [])
    total = scan.get("totalIssues", len(issues))

    score_color = "#dc2626" if score < 45 else "#d97706" if score < 75 else "#16a34a"
    score_text  = "#991b1b" if score < 45 else "#92400e" if score < 75 else "#166534"
    jp_score_label = "要対応" if score < 45 else "要改善" if score < 75 else "良好"
    domain = url.replace("https://", "").replace("http://", "").split("/")[0]

    pct = max(0, min(100, score))
    circ = 213.6
    dash_offset = round(circ - (pct / 100) * circ, 1)

    ring_svg = (
        '<svg width="80" height="80" viewBox="0 0 80 80">'
        '<circle cx="40" cy="40" r="34" fill="none" stroke="#e5e7eb" stroke-width="8"/>'
        f'<circle cx="40" cy="40" r="34" fill="none" stroke="{score_color}" stroke-width="8"'
        f' stroke-dasharray="{circ}" stroke-dashoffset="{dash_offset}"'
        ' stroke-linecap="round" transform="rotate(-90 40 40)"/>'
        f'<text x="40" y="37" text-anchor="middle" font-size="20" font-weight="800"'
        f' fill="{score_color}" font-family="-apple-system,sans-serif">{score}</text>'
        '<text x="40" y="49" text-anchor="middle" font-size="9" fill="#9ca3af"'
        ' font-family="-apple-system,sans-serif">/100</text>'
        '</svg>'
    )

    counts = scan.get("issueCounts", {})
    pills_html = ""
    for sev, bg, border, col, label in [
        ("high",   "#fef2f2", "#fecaca", "#991b1b", "重要"),
        ("medium", "#fffbeb", "#fde68a", "#92400e", "中程度"),
        ("low",    "#f0fdf4", "#bbf7d0", "#166534", "軽微"),
    ]:
        n = counts.get(sev, 0)
        if n:
            pills_html += (
                f'<span style="font-size:11px;font-weight:700;color:{col};'
                f'background:{bg};padding:3px 9px;border-radius:20px;'
                f'border:0.5px solid {border};white-space:nowrap;margin-right:5px;">'
                f'&#9650; {n} {label}</span>'
            )

    if report_summary:
        cards_meta = [
            ("現状",       "#fca5a5", "#991b1b"),
            ("改善の機会", "#93c5fd", "#1d4ed8"),
            ("ご提案",     "#6ee7b7", "#065f46"),
        ]
        para_cards = ""
        for i, para in enumerate(report_summary[:3]):
            if not para:
                continue
            lbl, b_col, l_col = cards_meta[i] if i < len(cards_meta) else cards_meta[-1]
            para_cards += (
                f'<div style="margin-bottom:10px;padding:12px 14px;'
                f'background:#f9fafb;border-radius:8px;border-left:3px solid {b_col};">'
                f'<div style="font-size:10px;font-weight:700;color:{l_col};'
                f'letter-spacing:0.07em;text-transform:uppercase;margin-bottom:6px;">{lbl}</div>'
                f'<p style="font-size:12px;color:#374151;line-height:1.75;margin:0;">{para}</p>'
                f'</div>'
            )

        header = (
            '<div style="background:#1e2d7d;padding:16px 22px;'
            'display:flex;align-items:center;justify-content:space-between;">'
            '<div style="display:flex;align-items:center;gap:10px;">'
            '<div style="width:28px;height:28px;border-radius:6px;'
            'background:rgba(165,180,252,0.18);'
            'display:flex;align-items:center;justify-content:center;">'
            '<div style="width:11px;height:11px;border-radius:50%;background:#a5b4fc;"></div>'
            '</div>'
            '<div>'
            '<div style="color:#ffffff;font-size:12px;font-weight:700;'
            'letter-spacing:0.06em;text-transform:uppercase;">Shinrai Audit</div>'
            '<div style="color:#818cf8;font-size:10px;margin-top:1px;">'
            '信頼ウェブ &middot; English Readiness Report</div>'
            '</div>'
            '</div>'
            f'<div style="color:#a5b4fc;font-size:11px;font-family:monospace;'
            f'background:rgba(255,255,255,0.07);padding:4px 10px;'
            f'border-radius:6px;border:0.5px solid rgba(165,180,252,0.2);">{domain}</div>'
            '</div>'
        )
        score_band = (
            '<div style="display:flex;align-items:stretch;border-bottom:0.5px solid #e5e7eb;">'
            '<div style="padding:20px 22px;display:flex;flex-direction:column;'
            'align-items:center;justify-content:center;gap:6px;'
            'border-right:0.5px solid #e5e7eb;min-width:110px;">'
            + ring_svg +
            f'<div style="font-size:11px;font-weight:700;color:{score_text};'
            f'letter-spacing:0.04em;">{jp_score_label}</div>'
            '</div>'
            '<div style="padding:18px 20px;flex:1;">'
            '<div style="font-size:10px;color:#6b7280;font-weight:700;'
            'letter-spacing:0.07em;text-transform:uppercase;margin-bottom:10px;">英語対応スコア</div>'
            f'<div style="display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap;">{pills_html}</div>'
            f'<div style="font-size:10px;color:#9ca3af;">合計 {total} 件の改善点を検出</div>'
            '</div>'
            '</div>'
        )
        section_label = (
            '<div style="padding:14px 22px 4px;display:flex;align-items:center;gap:10px;">'
            '<div style="width:3px;height:14px;background:#2e3fa3;border-radius:2px;"></div>'
            '<span style="font-size:10px;font-weight:700;color:#2e3fa3;'
            'letter-spacing:0.08em;text-transform:uppercase;">現状と改善の機会</span>'
            '</div>'
        )
        footer = (
            '<div style="padding:10px 22px;border-top:0.5px solid #e5e7eb;'
            'display:flex;align-items:center;justify-content:space-between;background:#f8faff;">'
            '<span style="font-size:10px;color:#9ca3af;">Shinrai Prism Audit &middot; 信頼ウェブ</span>'
            '<span style="font-size:10px;color:#9ca3af;">詳細レポートはお問い合わせください</span>'
            '</div>'
        )
        return (
            '<div style="font-family:-apple-system,BlinkMacSystemFont,Hiragino Sans,Yu Gothic,sans-serif;'
            'background:#ffffff;border:0.5px solid #e5e7eb;border-radius:16px;'
            'overflow:hidden;max-width:520px;margin:0 auto;">'
            + header + score_band + section_label
            + f'<div style="padding:8px 22px 18px;">{para_cards}</div>'
            + footer
            + '</div>'
        )

    # ── Issue table fallback ──────────────────────────────────────────────────
    picked: list = []
    for category in (TEXT_TYPES, VISUAL_TYPES, UX_TYPES):
        for sev in ("high", "medium", "low"):
            for iss in issues:
                if (
                    iss.get("type") in category
                    and iss.get("severity") == sev
                    and iss not in picked
                ):
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
        sev = iss.get("severity", "medium")
        col = SEV_COLOR.get(sev, "#888")
        itype = iss.get("type", "")
        jp_type = JP_TYPE.get(itype, itype.replace("_", " "))
        jp_sev = JP_SEV.get(sev, sev)
        expl = iss.get("explanation", "")
        issues_html += (
            f'<div style="border:1px solid #e5e7eb;border-left:3px solid {col};border-radius:6px;'
            f'padding:10px 14px;margin-bottom:8px;background:#fff;">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap;">'
            f'<span style="width:8px;height:8px;border-radius:50%;background:{col};'
            f'display:inline-block;flex-shrink:0;"></span>'
            f'<span style="font-weight:600;font-size:12px;color:#111;">{jp_type}</span>'
            f'<span style="margin-left:auto;font-size:10px;font-weight:700;color:{col};'
            f'background:{col}18;padding:2px 6px;border-radius:4px;">{jp_sev}</span>'
            f'</div>'
            f'<p style="font-size:11px;color:#6b7280;margin:0;line-height:1.6;">{expl}</p>'
            f'</div>'
        )

    ring2 = (
        f'<div style="position:relative;width:80px;height:80px;flex-shrink:0;">'
        f'<div style="width:80px;height:80px;border-radius:50%;'
        f'background:conic-gradient({score_color} {pct}%, #e5e7eb {pct}% 100%);'
        f'display:flex;align-items:center;justify-content:center;">'
        f'<div style="width:58px;height:58px;border-radius:50%;background:#f9fafb;'
        f'display:flex;flex-direction:column;align-items:center;justify-content:center;">'
        f'<span style="font-size:20px;font-weight:800;color:{score_color};line-height:1;">{score}</span>'
        f'<span style="font-size:9px;color:#9ca3af;">/100</span>'
        f'</div></div></div>'
    )

    return (
        '<div style="font-family:-apple-system,BlinkMacSystemFont,Hiragino Sans,Yu Gothic,sans-serif;'
        'background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;'
        'overflow:hidden;max-width:520px;margin:0 auto;">'
        f'<div style="background:#2e3fa3;padding:12px 18px;display:flex;align-items:center;gap:10px;">'
        f'<span style="color:#fff;font-size:12px;font-weight:700;letter-spacing:0.05em;">SHINRAI AUDIT</span>'
        f'<span style="color:#a5b4fc;font-size:11px;margin-left:auto;font-family:monospace;">{domain}</span>'
        f'</div>'
        f'<div style="padding:16px 18px;display:flex;align-items:flex-start;gap:16px;background:#fff;border-bottom:1px solid #e5e7eb;">'
        + ring2 +
        f'<div style="flex:1;min-width:0;">'
        f'<div style="font-size:11px;color:#6b7280;font-weight:600;letter-spacing:0.05em;margin-bottom:6px;">英語対応スコア — {jp_score_label}</div>'
        f'<div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:4px;">{pills_html}</div>'
        f'<div style="font-size:10px;color:#9ca3af;margin-top:4px;">合計 {total} 件の改善点を検出</div>'
        f'<p style="font-size:11px;color:#374151;line-height:1.6;margin:8px 0 0;">{summary}</p>'
        f'</div></div>'
        f'<div style="padding:14px 18px 16px;">'
        f'<div style="font-size:11px;color:#6b7280;font-weight:600;letter-spacing:0.05em;margin-bottom:10px;">主な改善点</div>'
        + (issues_html if issues_html else '<p style="font-size:11px;color:#9ca3af;">改善点なし</p>') +
        '</div>'
        '<div style="background:#f3f4f6;padding:12px 18px;border-top:1px solid #e5e7eb;text-align:center;">'
        '<span style="font-size:10px;color:#9ca3af;">Shinrai Prism Audit &middot; 信頼ウェブ &middot; 詳細レポートはお問い合わせください</span>'
        '</div>'
        '</div>'
    )


# ── Email generation helpers ──────────────────────────────────────────────────


async def _translate_scan_for_card(scan: dict, ai_settings: AISettings) -> dict:
    """Translate summary + issue text to Japanese for the report card (deep scan mode)."""
    summary = scan.get("summary", "")
    issues = scan.get("issues", [])
    strings = [summary] if summary else [""]
    for iss in issues:
        strings.append(iss.get("location", ""))
        strings.append(iss.get("explanation", "")[:120])

    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(strings))
    prompt = f"Translate the following numbered English strings to natural Japanese.\nReturn ONLY a JSON array of translated strings in the same order, same count.\nKeep proper nouns, URLs, and brand names unchanged.\n\n{numbered}"
    system = "You are a professional English-to-Japanese translator. Return only a JSON array of strings."

    try:
        if ai_settings.ai_provider == "claude":
            raw, _ = await call_claude(
                prompt,
                system,
                ai_settings.anthropic_api_key,
                ai_settings.anthropic_model,
            )
        elif ai_settings.ai_provider == "openai":
            raw, _ = await call_openai(
                prompt, system, ai_settings.openai_api_key, ai_settings.openai_model
            )
        else:
            raw, _ = await call_ollama(
                prompt, system, ai_settings.ollama_base_url, ai_settings.ollama_model
            )
        translated = json.loads(_extract_json(raw))
        if not isinstance(translated, list) or len(translated) < len(strings):
            raise ValueError("translation list length mismatch")
    except Exception as e:
        print(f"[translate-card] ⚠ translation failed ({e}), using original English")
        return scan

    scan_jp = dict(scan)
    scan_jp["summary"] = translated[0] if translated else summary
    jp_issues = []
    for idx, iss in enumerate(issues):
        jp_iss = dict(iss)
        loc_i = 1 + idx * 2
        expl_i = 1 + idx * 2 + 1
        if loc_i < len(translated):
            jp_iss["location"] = translated[loc_i]
        if expl_i < len(translated):
            jp_iss["explanation"] = translated[expl_i]
        jp_issues.append(jp_iss)
    scan_jp["issues"] = jp_issues
    print(f"[translate-card] ✓ translated {len(strings)} strings to Japanese")
    return scan_jp



# ── Shared email helpers ──────────────────────────────────────────────────────


def build_email_prompt(scan: dict) -> str:
    """Build the AI prompt for a cold outreach email from a scan result.

    Single source of truth — used by both single and batch email generation.
    """
    url = scan.get("url", "their website")
    score = scan.get("score", "N/A")
    summary = scan.get("summary", "")
    title = scan.get("title", "")
    issues = scan.get("issues", [])

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
    positives_text = (
        ", ".join(positives[:2])
        if positives
        else "a site that clearly reflects genuine expertise in its field"
    )

    opportunity_hints = []
    for iss in issues[:8]:
        loc = iss.get("location", "")
        itype = iss.get("type", "")
        if itype in ("untranslated_nav_ui", "untranslated_body", "untranslated_japanese") and loc:
            opportunity_hints.append(
                f"making navigation and key content accessible to English readers (currently Japanese-only in the {loc})"
            )
        elif itype in ("machine_translation", "grammar_error", "awkward_phrasing") and loc:
            opportunity_hints.append(
                "replacing stilted auto-translated text with natural English that builds trust"
            )
        elif itype in ("weak_cta", "missing_cta_visual") and loc:
            opportunity_hints.append(
                "adding a clear English call-to-action so international visitors know how to book or contact"
            )
        elif itype in ("trust_signals", "social_proof", "contact_accessibility"):
            opportunity_hints.append(
                "adding English trust signals (reviews, contact info) that Western visitors expect"
            )
        elif itype in ("mobile_usability", "navigation_ux"):
            opportunity_hints.append(
                "improving the mobile and navigation experience for international visitors"
            )
        if len(opportunity_hints) >= 2:
            break
    hints_text = (
        "; and ".join(opportunity_hints[:2])
        if opportunity_hints
        else "making the site fully navigable and readable for English-speaking visitors"
    )

    return f"""Write a bilingual cold outreach email for this Japanese business. Follow your system prompt's writing philosophy — natural, human, specific to this site.

SITE DETAILS:
  URL: {url}
  Page title: {title or "unknown"}
  English-readiness score: {score}/100
  What the site is about: {summary}

GENUINE STRENGTHS of this site (draw the compliment from one of these — be specific):
  {positives_text}

WHAT AN INTERNATIONAL VISITOR EXPERIENCES on this site:
  {hints_text}

Use this to describe the real experience — not just a list of missing elements, but what it means for someone who arrives curious and wants to book, enquire, or learn more. If the site is largely untranslated, say so in human terms: they can see it's a quality business, but can't navigate, can't find prices, can't work out how to get in touch.

SERVICES MOST RELEVANT HERE (pick 1-2, weave in naturally):
  - English translation and localisation of Japanese content
  - Natural English copywriting (replacing machine-translated text)
  - Full web development and redesign
  - UX improvements for international visitors

The personalised audit report is embedded directly below this message — reference it naturally, once.

Return the bilingual email as JSON following your system prompt exactly."""


def build_email_html(ai_data: dict, report_card_html: str | None, sender: dict) -> dict:
    """Render the final email HTML from AI response data.

    Single source of truth — used by both single and batch email generation.

    Args:
        ai_data: parsed AI response (subject, jp_paragraphs, en_paragraphs).
                 _usage key is popped and returned separately.
        report_card_html: pre-rendered audit card HTML, or None.
        sender: dict with keys name, title, email, website.

    Returns:
        {"subject": str, "html": str, "_tokens": dict}
    """
    usage = ai_data.pop("_usage", {})
    subject = ai_data.get("subject", "")
    jp_paras = ai_data.get("jp_paragraphs", [])
    en_paras = ai_data.get("en_paragraphs", [])
    report_summary = ai_data.get("report_card_summary_jp") or None

    s = sender or {}
    name = s.get("name", "")
    title = s.get("title", "")
    email = s.get("email", "").strip()
    website = s.get("website", "").strip().rstrip("/")
    if not website.startswith("http"):
        website = "https://" + website if website else ""

    def paras_html(paras: list) -> str:
        return "".join(
            f'<p style="font-size:15px;color:#374151;line-height:1.8;margin:0 0 16px;">{p}</p>'
            for p in paras
            if p
        )

    card_block = (
        f'<!--SHINRAI-CARD-START--><div style="margin:32px 0;">{report_card_html}</div><!--SHINRAI-CARD-END-->'
        if report_card_html
        else ""
    )
    btn_style = (
        "display:inline-block;background:#2e3fa3;color:#ffffff;font-weight:700;"
        "font-size:15px;text-decoration:none;padding:14px 36px;"
        "border-radius:8px;letter-spacing:0.03em;"
    )
    sig_style = "font-size:13px;color:#374151;line-height:2.2;margin:0;"
    hr_light = '<hr style="border:none;border-top:1px solid #e5e7eb;margin:28px 0;">'
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


async def _do_generate_email(
    prompt: str,
    system: str,
    ai_settings: AISettings,
    report_card_html: str | None = None,
    sender: dict | None = None,
    scan_for_card: dict | None = None,
) -> dict:
    import time

    t0 = time.monotonic()
    print(f"[generate-email]   → calling AI provider={ai_settings.ai_provider}")
    data = await call_ai(prompt, system, ai_settings)
    jp_paras = data.get("jp_paragraphs", [])
    en_paras = data.get("en_paragraphs", [])
    report_summary = data.get("report_card_summary_jp") or None
    # Rebuild card with AI-generated narrative summary if available, else use pre-built
    if report_summary and scan_for_card is not None:
        final_card_html = build_report_card_html(scan_for_card, report_summary=report_summary)
    else:
        final_card_html = report_card_html
    print(
        f"[generate-email] ═══ DONE in {time.monotonic() - t0:.1f}s | "
        f"tokens={data.get('_usage', {}).get('total_tokens', '?')} | "
        f"jp={len(jp_paras)} en={len(en_paras)} paras | "
        f"card={'narrative' if report_summary else 'issue-table'}"
    )
    return build_email_html(data, final_card_html, sender or {})


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post("/api/generate-email")
async def generate_email(req: GenerateEmailRequest):
    """Streams keepalives while AI writes the email — prevents gateway 504s."""
    s = req.settings
    _tpl = EMAIL_SYSTEM_EXPERIMENTAL if getattr(s, "email_prompt_variant", "standard") == "experimental" else EMAIL_SYSTEM
    system = _tpl.format(
        name=s.your_name,
        title=s.your_title,
        website=s.your_website,
        email=s.your_email,
    )
    scan = req.scan_result

    # Deep scans: translate card text to Japanese before rendering
    scan_mode = scan.get("scan_mode", "shallow")
    if scan_mode == "deep":
        audit_settings = AISettings(
            ai_provider=s.ai_provider,
            ollama_base_url=s.ollama_base_url,
            ollama_model=s.ollama_model,
            openai_api_key=s.openai_api_key,
            anthropic_api_key=s.anthropic_api_key,
            anthropic_model="claude-haiku-4-5-20251001"
            if s.ai_provider == "claude"
            else s.anthropic_model,
        )
        scan_for_card = await _translate_scan_for_card(scan, audit_settings)
    else:
        scan_for_card = scan

    report_card_html = build_report_card_html(scan_for_card)
    prompt = build_email_prompt(scan)

    ai_settings = AISettings(
        ai_provider=s.ai_provider,
        ollama_base_url=s.ollama_base_url,
        ollama_model=s.ollama_model,
        openai_api_key=s.openai_api_key,
        anthropic_api_key=s.anthropic_api_key,
        anthropic_model=s.anthropic_model,
    )

    url = scan.get("url", "?")
    score = scan.get("score", "?")
    print(f"[generate-email] ═══ START url={url} score={score} provider={ai_settings.ai_provider}")
    print(f"[generate-email]   report card html: {len(report_card_html)} chars")

    async def stream():
        sender = {
            "name": s.your_name,
            "title": s.your_title,
            "email": s.your_email,
            "website": s.your_website,
        }
        task = asyncio.create_task(
            _do_generate_email(prompt, system, ai_settings, report_card_html, sender, scan_for_card)
        )
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
    scan = dict(req.scan_result)
    all_issues = scan.get("issues", [])
    selected = [
        all_issues[i] for i in req.selected_issue_indices if 0 <= i < len(all_issues)
    ]
    card_html = build_report_card_html({**scan, "issues": selected})
    return {
        "card_html": card_html,
        "card_block": f'<!--SHINRAI-CARD-START--><div style="margin:32px 0;">{card_html}</div><!--SHINRAI-CARD-END-->',
    }


@router.post("/api/send-email")
async def api_send_email(req: SendEmailRequest):
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    s = req.settings
    if not s.gmail_address or not s.gmail_app_password:
        raise HTTPException(400, "Gmail address and app password are required")

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = req.subject
        visible_from = s.from_address.strip() if s.from_address.strip() else s.gmail_address
        msg["From"] = f"{s.your_name} <{visible_from}>"
        msg["To"] = req.to
        msg.attach(MIMEText(req.html, "html", "utf-8"))

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.ehlo()
            smtp.login(s.gmail_address, s.gmail_app_password)
            smtp.sendmail(s.gmail_address, req.to, msg.as_string())

        try:
            await update_email(req.url, req.to, req.subject, req.html)
        except Exception as db_err:
            print(f"[db] ⚠ email save failed: {db_err}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Failed to send: {e}")


from .db import schedule_email, cancel_scheduled_email


@router.post("/api/schedule-email")
async def api_schedule_email(req: ScheduleEmailRequest):
    try:
        await schedule_email(
            url=req.url,
            recipient=req.to,
            subject=req.subject,
            html=req.html,
            scheduled_at=req.scheduled_at,
            settings=req.settings.model_dump(),
        )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(502, f"Failed to schedule: {e}")


@router.post("/api/cancel-scheduled-email")
async def api_cancel_scheduled_email(req: CancelScheduleRequest):
    try:
        await cancel_scheduled_email(req.url)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(502, f"Failed to cancel schedule: {e}")


# ── Batch email generation ─────────────────────────────────────────────────────


@router.post("/api/batch-generate-email")
async def batch_generate_email(req: BatchGenerateEmailRequest):
    """Generate emails for multiple scan results using Anthropic Batch API (50% cost).
    Streams keepalives then final NDJSON result keyed by URL.
    For Ollama/OpenAI falls back to sequential.
    """
    task = asyncio.create_task(_do_batch_generate_email(req))

    async def stream():
        while not task.done():
            yield b"\n"
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=15.0)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break
        try:
            result = task.result()
            yield json.dumps(result).encode() + b"\n"
        except Exception as e:
            print(f"[batch-email] FAILED:\n{traceback.format_exc()}")
            yield json.dumps({"error": str(e)}).encode() + b"\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


async def _do_batch_generate_email(req: BatchGenerateEmailRequest) -> dict:
    import time

    t0 = time.monotonic()
    s = req.settings
    _tpl = EMAIL_SYSTEM_EXPERIMENTAL if getattr(s, "email_prompt_variant", "standard") == "experimental" else EMAIL_SYSTEM
    system = _tpl.format(
        name=s.your_name,
        title=s.your_title,
        website=s.your_website,
        email=s.your_email,
    )
    ai_settings = AISettings(
        ai_provider=s.ai_provider,
        ollama_base_url=s.ollama_base_url,
        ollama_model=s.ollama_model,
        openai_api_key=s.openai_api_key,
        anthropic_api_key=s.anthropic_api_key,
        anthropic_model=s.anthropic_model,
    )
    sender = {
        "name": s.your_name,
        "title": s.your_title,
        "email": s.your_email,
        "website": s.your_website,
    }

    # Build batch requests — reuse the same prompt builder as single email
    batch_requests = []
    card_map: dict[str, str] = {}  # url -> report_card_html

    for item in req.items:
        scan = item.scan_result
        url = scan.get("url", "unknown")
        card_map[url] = build_report_card_html(scan)
        batch_requests.append({
            "custom_id": url,
            "system": system,
            "prompt": build_email_prompt(scan),  # ← same function as single path
            "images": None,
        })

    print(f"[batch-email] ═══ START {len(batch_requests)} emails provider={ai_settings.ai_provider}")
    ai_results = await call_ai_batch(batch_requests, ai_settings)

    # Format results — reuse the same HTML builder as single path
    results: dict = {}
    for url, data in ai_results.items():
        if data.get("error"):
            results[url] = {"error": data["error"], "url": url}
            continue
        try:
            report_summary = data.get("report_card_summary_jp") or None
            scan = next((item.scan_result for item in req.items if item.scan_result.get("url") == url), {})
            final_card = build_report_card_html(scan, report_summary=report_summary)
            results[url] = build_email_html(data, final_card, sender)
        except Exception as e:
            results[url] = {"error": str(e), "url": url}

    elapsed = time.monotonic() - t0
    print(f"[batch-email] ═══ DONE {len(results)} emails in {elapsed:.1f}s")
    return {"results": results}
