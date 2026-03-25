import asyncio
import os
import smtplib
import ssl
import imaplib
import email
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from urllib.parse import urlparse

from dotenv import load_dotenv
load_dotenv()

from .db import (
    scans_db,
    prospects_db,
    ScanRecord,
    ProspectRecord,
    get_scheduled_emails,
    update_email,
    schedule_email
)

def extract_bounced_address(msg):
    # Simplified parsing for mailer-daemon bounced emails
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "message/delivery-status":
                payload = part.get_payload()
                if isinstance(payload, list):
                    for p in payload:
                        body += str(p.get_payload())
                else:
                    body += str(payload)
            elif content_type == "text/plain":
                body += str(part.get_payload(decode=True))
    else:
        body = str(msg.get_payload(decode=True))
    
    match = re.search(r"Final-Recipient:\s*rfc822;\s*([^\s]+)", body, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match2 = re.search(r"Failed-Recipient:\s*([^\s]+)", body, re.IGNORECASE)
    if match2:
        return match2.group(1).strip()
    match3 = re.search(r"failed permanently:\s*([^\s]+)", body, re.IGNORECASE)
    if match3:
        return match3.group(1).strip()
        
    return None

async def email_bounce_monitor_loop():
    interval = int(os.environ.get("BOUNCE_CHECK_INTERVAL_MINUTES", "10"))
    while True:
        try:
            gmail_address = os.environ.get("GMAIL_ADDRESS")
            gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
            
            if not gmail_address or not gmail_app_password:
                await asyncio.sleep(interval * 60)
                continue
                
            def check_imap():
                bounced = []
                try:
                    mail = imaplib.IMAP4_SSL("imap.gmail.com")
                    mail.login(gmail_address, gmail_app_password)
                    mail.select("inbox")
                    status, messages = mail.search(None, '(UNSEEN FROM "mailer-daemon@googlemail.com")')
                    if status == "OK" and messages[0]:
                        for num in messages[0].split():
                            res, data = mail.fetch(num, "(RFC822)")
                            if res == "OK":
                                raw_email = data[0][1]
                                msg = email.message_from_bytes(raw_email)
                                failed_email = extract_bounced_address(msg)
                                if failed_email:
                                    bounced.append(failed_email)
                    mail.logout()
                except Exception as e:
                    print(f"[bounce_monitor] IMAP error: {e}")
                return bounced

            bounced_emails = await asyncio.to_thread(check_imap)
            
            for b_email in bounced_emails:
                b_email = b_email.lower().strip()
                record = scans_db.get(ScanRecord.email.recipient == b_email)
                if not record:
                    continue
                
                url = record.get("url")
                email_block = record.get("email", {})
                is_fallback = email_block.get("is_fallback", False)
                settings = email_block.get("settings", {})
                
                if is_fallback:
                    print(f"[bounce_monitor] Fallback email bounced too for {url}. Giving up.")
                    prospects_db.update({"status": "cant_deliver"}, ProspectRecord.website == url)
                    email_block["status"] = "cant_deliver"
                    scans_db.update({"email": email_block}, ScanRecord.url == url)
                else:
                    print(f"[bounce_monitor] Initial email bounced for {url}. Attempting fallback.")
                    prospects_db.update({"status": "bounced"}, ProspectRecord.website == url)
                    email_block["status"] = "bounced"
                    scans_db.update({"email": email_block}, ScanRecord.url == url)
                    
                    found_emails = record.get("emails_found", [])
                    fallback = f"contact@{urlparse(url).netloc.replace('www.', '')}"
                    if found_emails and fallback in found_emails:
                        found_emails.remove(fallback)
                    
                    next_email = found_emails[0] if found_emails else fallback
                    print(f"[bounce_monitor] Auto-scheduling fallback to {next_email}")
                    
                    req_settings = {
                        "your_name": settings.get("your_name", "Marcin Zielinski"),
                        "from_address": settings.get("from_address", "")
                    }
                    schedule_email(
                        url=url,
                        recipient=next_email,
                        subject=email_block.get("subject", ""),
                        html=email_block.get("html", ""),
                        scheduled_at=datetime.now(timezone.utc).isoformat(),
                        settings=req_settings
                    )
                    
                    updated = scans_db.get(ScanRecord.url == url)
                    updated_email = updated.get("email", {})
                    updated_email["is_fallback"] = True
                    scans_db.update({"email": updated_email}, ScanRecord.url == url)

        except Exception as e:
            print(f"[bounce_monitor] error: {e}")
            
        await asyncio.sleep(interval * 60)
        
async def email_scheduler_loop():
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat()
            scheduled = get_scheduled_emails()
            for record in scheduled:
                email_data = record.get("email", {})
                scheduled_at = email_data.get("scheduled_at")
                if scheduled_at and scheduled_at <= now:
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
                        print(f"[scheduler] Missing global gmail credentials for {url}")
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
                    
                    def send_sync(
                        c=ctx,
                        g_addr=gmail_address,
                        g_pwd=gmail_app_password,
                        recipient=to,
                        msg_str=msg.as_string()
                    ):
                        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
                            smtp.ehlo()
                            smtp.starttls(context=c)
                            smtp.ehlo()
                            smtp.login(g_addr, g_pwd)
                            smtp.sendmail(g_addr, recipient, msg_str)
                    
                    await asyncio.to_thread(send_sync)
                    update_email(url, to, subject, html)
                    # Re-apply is_fallback so we don't lose it on success
                    if email_data.get("is_fallback"):
                         post_send = scans_db.get(ScanRecord.url == url)
                         post_send["email"]["is_fallback"] = True
                         scans_db.update({"email": post_send["email"]}, ScanRecord.url == url)

                    prospects_db.update({"status": "emailed"}, ProspectRecord.website == url)
                    print(f"[scheduler] sent scheduled email for {url}")
        except Exception as e:
            print(f"[scheduler] error: {e}")
            
        await asyncio.sleep(60)

async def main():
    print("[worker] Starting background worker...")
    print(f"[worker] Monitoring bounce for: {os.environ.get('GMAIL_ADDRESS')}")
    asyncio.gather(
        email_scheduler_loop(),
        email_bounce_monitor_loop()
    )
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
