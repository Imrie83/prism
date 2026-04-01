"""
Background worker for Prism.

Two async loops:
  email_scheduler_loop  — sends emails that have reached their scheduled_at time
  email_bounce_monitor_loop — checks IMAP inbox for bounce/delay messages
"""

import asyncio
import os
import smtplib
import ssl
import imaplib
import email
import re
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

from .db import (
    scans_col,
    prospects_col,
    get_scheduled_emails,
    update_email,
    schedule_email,
    ensure_indexes,
)


def extract_bounced_address(msg):
    """Parse a mailer-daemon bounce/delay message.

    Returns (recipient_address, action) where action is e.g. 'failed', 'delayed', or 'unknown'.
    Returns (None, None) if no recipient could be extracted.

    Handles:
    - Standard delivery-status MIME parts (RFC 3464)
    - ProtonMail Bridge format (message/delivery-status sub-messages)
    - Plain-text bounces
    """
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "message/delivery-status":
                # Sub-parts are email.message.Message objects — must use as_string()
                # NOT str(get_payload()) which returns '' for structured sub-messages
                payload = part.get_payload()
                if isinstance(payload, list):
                    for p in payload:
                        body += p.as_string()
                else:
                    body += str(payload)
            elif ct == "text/plain":
                raw = part.get_payload(decode=True)
                if raw:
                    try:
                        body += raw.decode("utf-8", errors="replace")
                    except Exception:
                        body += str(raw)
    else:
        raw = msg.get_payload(decode=True)
        if raw:
            try:
                body += raw.decode("utf-8", errors="replace")
            except Exception:
                body += str(raw)

    if body:
        pass  # body parsed successfully — no need to dump to console

    # Extract the Action field (failed / delayed / etc.)
    action_match = re.search(r"Action:\s*(\S+)", body, re.IGNORECASE)
    action = action_match.group(1).lower() if action_match else "unknown"

    for pattern in [
        r"Final-Recipient:\s*rfc822;\s*([^\s<>]+)",
        r"Original-Recipient:\s*rfc822;\s*([^\s<>]+)",
        r"Failed-Recipient:\s*([^\s<>]+)",
        r"failed permanently:\s*([^\s<>]+)",
    ]:
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            addr = m.group(1).strip().strip("<>")
            return addr, action

    return None, None


async def email_bounce_monitor_loop():
    print("[bounce_monitor] 🔍 Starting bounce monitor loop...", flush=True)
    while True:
        interval = 10  # default; updated from DB settings below
        try:
            from .db import get_global_settings

            settings = await get_global_settings()
            interval = settings.get("bounce_check_interval", 10)
            print(f"[bounce_monitor] ⏱ Next check in {interval}m (from DB settings)", flush=True)

            gmail_address = os.environ.get("GMAIL_ADDRESS")
            gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")

            if not gmail_address or not gmail_app_password:
                print(
                    f"[bounce_monitor] ⚠ Missing GMAIL_ADDRESS or GMAIL_APP_PASSWORD. "
                    f"Waiting {interval}m...",
                    flush=True,
                )
                await asyncio.sleep(interval * 60)
                continue

            imap_server = os.environ.get("EMAIL_IMAP_SERVER", "imap.gmail.com")
            imap_port = int(os.environ.get("EMAIL_IMAP_PORT", "993"))
            # ProtonMail uses MAILER-DAEMON@proton.me (uppercase) — default covers both
            bounce_sender = os.environ.get("EMAIL_BOUNCE_SENDER", "MAILER-DAEMON")
            # Folder to move processed bounces into (must exist in your mailbox)
            bounce_folder = os.environ.get("EMAIL_BOUNCE_FOLDER", "Mail Delivery Fail")

            def check_imap():
                bounced = []
                try:
                    if imap_port == 993:
                        mail = imaplib.IMAP4_SSL(imap_server, imap_port)
                    else:
                        mail = imaplib.IMAP4(imap_server, imap_port)
                        try:
                            mail.starttls()
                        except Exception:
                            pass

                    mail.login(gmail_address, gmail_app_password)
                    mail.select("inbox")

                    # Case-insensitive FROM search — covers mailer-daemon / MAILER-DAEMON
                    status, messages = mail.search(
                        None, f'(UNSEEN FROM "{bounce_sender}")'
                    )
                    if not (status == "OK" and messages[0]):
                        mail.logout()
                        return bounced  # nothing to do, completely silent

                    msg_nums = messages[0].split()
                    print(
                        f"[bounce_monitor] 📬 Found {len(msg_nums)} unread message(s) "
                        f"from {bounce_sender!r} — examining...",
                        flush=True,
                    )

                    # IMAP requires folder names with spaces to be double-quoted
                    imap_folder = (
                        f'"{bounce_folder}"' if " " in bounce_folder else bounce_folder
                    )

                    for num in msg_nums:
                        # BODY.PEEK[] reads without setting \Seen — safe to retry
                        res, data = mail.fetch(num, "(BODY.PEEK[])")
                        if res != "OK":
                            print(f"[bounce_monitor] ⚠ FETCH failed for msg {num}", flush=True)
                            continue

                        raw_email = data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        subj = msg.get("Subject", "(no subject)")
                        frm  = msg.get("From", "(unknown)")

                        failed_email, action = extract_bounced_address(msg)

                        if failed_email:
                            bounced.append((failed_email, action))
                            print(
                                f"[bounce_monitor] 📨 Delivery issue detected: {failed_email}  "
                                f"action={action}  (treating as bounce — scheduling fallback)",
                                flush=True,
                            )
                            # Mark read first (always safe)
                            mail.store(num, "+FLAGS", "\\Seen")
                            # Try to move to bounce folder — folder name with spaces must be quoted
                            try:
                                # Use UID-based copy which is more widely supported
                                uid_res, uid_data = mail.fetch(num, "(UID)")
                                uid = None
                                if uid_res == "OK" and uid_data and uid_data[0]:
                                    uid_match = re.search(rb"UID (\d+)", uid_data[0])
                                    uid = uid_match.group(1).decode() if uid_match else None

                                moved = False
                                if uid:
                                    cp_res, _ = mail.uid("COPY", uid, imap_folder)
                                    if cp_res == "OK":
                                        mail.uid("STORE", uid, "+FLAGS", "\\Deleted")
                                        mail.expunge()
                                        moved = True

                                if not moved:
                                    # Fallback: plain COPY by sequence number
                                    cp_res, _ = mail.copy(num, imap_folder)
                                    if cp_res == "OK":
                                        mail.store(num, "+FLAGS", "\\Deleted")
                                        mail.expunge()
                                        moved = True

                                if moved:
                                    print(
                                        f"[bounce_monitor] 📁 Moved to '{bounce_folder}'",
                                        flush=True,
                                    )
                                else:
                                    print(
                                        f"[bounce_monitor] ⚠ Could not move to '{bounce_folder}' "
                                        f"— message marked read in inbox",
                                        flush=True,
                                    )
                            except Exception as copy_err:
                                print(
                                    f"[bounce_monitor] ⚠ Move to '{bounce_folder}' failed "
                                    f"({copy_err}) — message marked read in inbox",
                                    flush=True,
                                )
                        else:
                            print(
                                f"[bounce_monitor] ⚠ Could not extract address from message "
                                f"(left unread for manual review)",
                                flush=True,
                            )

                    mail.logout()
                except Exception as e:
                    print(f"[bounce_monitor] ⚠ IMAP error: {e}", flush=True)
                    traceback.print_exc()
                return bounced

            bounced_emails = await asyncio.to_thread(check_imap)

            for b_email, action in bounced_emails:
                b_email = b_email.lower().strip()
                print(f"[bounce_monitor] 🔍 Looking up scan record for: {b_email!r}", flush=True)

                # 1. Exact match on stored recipient (normal path — email sent via app)
                record = await scans_col().find_one({"email.recipient": b_email})

                # 2. Case-insensitive match on recipient
                if not record:
                    record = await scans_col().find_one({
                        "email.recipient": {"$regex": f"^{re.escape(b_email)}$", "$options": "i"}
                    })

                # 3. Match against emails_found array (email sent outside app, or pre-migration data)
                if not record:
                    record = await scans_col().find_one({
                        "emails_found": {"$regex": f"^{re.escape(b_email)}$", "$options": "i"}
                    })
                    if record:
                        print(
                            f"[bounce_monitor] ✓ Matched via emails_found array "
                            f"(no sent email block — will still attempt fallback)",
                            flush=True,
                        )

                if not record:
                    print(
                        f"[bounce_monitor] ⚠ No scan record found for {b_email!r} "
                        f"(checked email.recipient and emails_found)",
                        flush=True,
                    )
                    continue

                url = record.get("url")
                email_block = record.get("email", {})
                is_fallback = email_block.get("is_fallback", False)
                email_settings = email_block.get("settings", {})

                if is_fallback:
                    print(
                        f"[bounce_monitor] Fallback email bounced too for {url}. Giving up.",
                        flush=True,
                    )
                    await prospects_col().update_one(
                        {"website": url}, {"$set": {"status": "cant_deliver"}}
                    )
                    await scans_col().update_one(
                        {"url": url},
                        {"$set": {"email.status": "cant_deliver"}},
                    )
                else:
                    print(
                        f"[bounce_monitor] Initial email bounced for {url}. Attempting fallback.",
                        flush=True,
                    )
                    await prospects_col().update_one(
                        {"website": url}, {"$set": {"status": "bounced"}}
                    )
                    await scans_col().update_one(
                        {"url": url}, {"$set": {"email.status": "bounced"}}
                    )

                    found_emails = record.get("emails_found", [])
                    fallback = f"contact@{urlparse(url).netloc.replace('www.', '')}"
                    if found_emails and fallback in found_emails:
                        found_emails.remove(fallback)

                    next_email = found_emails[0] if found_emails else fallback
                    print(
                        f"[bounce_monitor] Auto-scheduling fallback to {next_email}",
                        flush=True,
                    )

                    req_settings = {
                        "your_name": email_settings.get("your_name", "Marcin Zielinski"),
                        "from_address": email_settings.get("from_address", ""),
                    }
                    await schedule_email(
                        url=url,
                        recipient=next_email,
                        subject=email_block.get("subject", ""),
                        html=email_block.get("html", ""),
                        scheduled_at=datetime.now(timezone.utc).isoformat(),
                        settings=req_settings,
                    )
                    await scans_col().update_one(
                        {"url": url}, {"$set": {"email.is_fallback": True}}
                    )

        except Exception as e:
            print(f"[bounce_monitor] ⚠ Loop error: {e}", flush=True)
            traceback.print_exc()

        await asyncio.sleep(interval * 60)


async def email_scheduler_loop():
    print("[scheduler] 🕒 Starting scheduler loop...", flush=True)
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat()
            scheduled = await get_scheduled_emails()
            if scheduled:
                print(
                    f"[scheduler] Checking {len(scheduled)} scheduled email(s)...",
                    flush=True,
                )
            for record in scheduled:
                email_data = record.get("email", {})
                scheduled_at = email_data.get("scheduled_at")
                if not scheduled_at or scheduled_at > now:
                    continue

                url = record.get("url")
                to = email_data.get("recipient")
                subject = email_data.get("subject")
                html = email_data.get("html")
                settings = email_data.get("settings", {})

                gmail_address = os.environ.get("GMAIL_ADDRESS")
                gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
                your_name = settings.get("your_name", "Marcin Zielinski")
                from_address = settings.get("from_address", "")

                if not gmail_address or not gmail_app_password:
                    print(
                        f"[scheduler] ⚠ Missing global gmail credentials for {url}",
                        flush=True,
                    )
                    continue

                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                visible_from = from_address.strip() if from_address.strip() else gmail_address
                msg["From"] = f"{your_name} <{visible_from}>"
                msg["To"] = to
                msg.attach(MIMEText(html, "html", "utf-8"))

                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                smtp_server = os.environ.get("EMAIL_SMTP_SERVER", "smtp.gmail.com")
                smtp_port = int(os.environ.get("EMAIL_SMTP_PORT", "587"))

                def send_sync(
                    c=ctx,
                    g_addr=gmail_address,
                    g_pwd=gmail_app_password,
                    recipient=to,
                    msg_str=msg.as_string(),
                    host=smtp_server,
                    port=smtp_port,
                ):
                    smtp_class = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
                    with smtp_class(host, port) as smtp:
                        smtp.ehlo()
                        if port in (587, 1025):
                            smtp.starttls(context=c)
                            smtp.ehlo()
                        smtp.login(g_addr, g_pwd)
                        smtp.sendmail(g_addr, recipient, msg_str)

                await asyncio.to_thread(send_sync)
                await update_email(url, to, subject, html)

                if email_data.get("is_fallback"):
                    await scans_col().update_one(
                        {"url": url}, {"$set": {"email.is_fallback": True}}
                    )

                await prospects_col().update_one(
                    {"website": url}, {"$set": {"status": "emailed"}}
                )
                print(f"[scheduler] ✅ Sent scheduled email for {url} → {to}", flush=True)

        except Exception as e:
            print(f"[scheduler] ⚠ Loop error: {e}", flush=True)
            traceback.print_exc()

        await asyncio.sleep(60)


async def main():
    print("[worker] 🚀 Starting background worker...", flush=True)
    gmail = os.environ.get("GMAIL_ADDRESS", "(not set)")
    mongo = os.environ.get("MONGO_URL", "mongodb://mongo:27017")
    print(f"[worker] Gmail monitor: {gmail}", flush=True)
    print(f"[worker] MongoDB: {mongo}", flush=True)

    try:
        await ensure_indexes()
    except Exception as e:
        print(f"[worker] ⚠ Could not ensure indexes: {e}", flush=True)

    try:
        await asyncio.gather(
            email_scheduler_loop(),
            email_bounce_monitor_loop(),
        )
    except Exception as e:
        print(f"[worker] ⚠ Critical error in main gather: {e}", flush=True)
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
