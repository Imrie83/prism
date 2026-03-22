"""
Shared utility functions for the Prism backend.
"""
import re

_EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE,
)

_EMAIL_BLOCKLIST = {
    "example.com", "example.jp", "sentry.io", "cloudflare.com",
    "googleapis.com", "gstatic.com", "w3.org", "schema.org",
    "openstreetmap.org", "gravatar.com", "placeholder.com",
}


def extract_emails_from_html(html: str) -> list[str]:
    """Return deduplicated list of likely contact emails found in raw HTML."""
    found: dict[str, int] = {}
    for m in _EMAIL_RE.finditer(html):
        addr   = m.group(0).lower().rstrip(".")
        domain = addr.split("@")[-1]
        if domain in _EMAIL_BLOCKLIST:
            continue
        priority = 0 if re.search(r'^(info|contact|hello|support|sales|enqui)', addr) else 1
        if addr not in found or priority < found[addr]:
            found[addr] = priority
    return sorted(found.keys(), key=lambda a: (found[a], a))
