"""
Semantic HTML extractor for Prism audit.
Parses a rendered HTML page into structured groups (nav, hero, footer, etc.)
so the AI can reason about content and layout without processing raw HTML.

Key design decisions:
- Footer is always extracted, regardless of group count — contact info, address,
  phone, and business registration live there and must never be truncated away.
- Groups cap raised to 30 (from 20) and elements per group to 20 (from 15).
- Total output cap raised to 10000 chars (from 6000).
"""

from bs4 import BeautifulSoup, Tag


def extract_semantic_groups(html: str) -> str:
    """Parse HTML into labelled semantic groups, return as structured text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "meta", "link", "head"]):
        tag.decompose()

    def classify_container(tag) -> str:
        name = tag.name.lower() if tag.name else ""
        combined = f"{name} {' '.join(tag.get('class', []))} {tag.get('role', '')} {tag.get('id', '')}".lower()
        if any(k in combined for k in ["hero", "jumbotron", "banner", "splash"]):
            return "hero"
        if any(k in combined for k in ["nav", "menu", "navigation"]):
            return "navigation"
        if any(k in combined for k in ["footer", "foot"]):
            return "footer"
        if any(k in combined for k in ["header", "masthead"]):
            return "header"
        if any(k in combined for k in ["cta", "call-to-action", "action"]):
            return "cta"
        if any(k in combined for k in ["contact", "form", "inquiry"]):
            return "contact-form"
        if any(k in combined for k in ["service", "product", "feature"]):
            return "services"
        if any(k in combined for k in ["about", "company", "team", "story"]):
            return "about"
        if any(k in combined for k in ["testimonial", "review", "client"]):
            return "social-proof"
        if name in ("header",):
            return "header"
        if name in ("footer",):
            return "footer"
        if name in ("nav",):
            return "navigation"
        if name in ("section", "article", "main", "aside"):
            return name
        return "section"

    def extract_elements(container, depth: int = 0) -> list:
        if depth > 5:
            return []
        name = container.name.lower() if container.name else ""

        text = container.get_text(" ", strip=True)
        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return [{"role": "heading", "level": name, "text": text[:300]}] if text else []
        if name == "p":
            return [{"role": "paragraph", "text": text[:500]}] if text else []
        if name == "a":
            return [
                {
                    "role": "link",
                    "text": text[:200],
                    "href": container.get("href", "")[:100],
                }
            ] if text else []
        if name == "button" or ("btn" in " ".join(container.get("class", [])).lower()):
            return [{"role": "button", "text": text[:200]}] if text else []
        if name == "li":
            return [{"role": "list-item", "text": text[:300]}] if text else []
        if name in ("input", "textarea", "select"):
            return [
                {
                    "role": "form-field",
                    "placeholder": container.get(
                        "placeholder", container.get("name", container.get("type", "field"))
                    )[:100],
                }
            ]
        if name == "img":
            return [
                {
                    "role": "image",
                    "alt": container.get("alt", "[no alt]")[:200],
                    "src": container.get("src", "")[:80],
                }
            ]

        elements = []
        for tag in container.find_all(True, recursive=False):
            if isinstance(tag, Tag):
                elements.extend(extract_elements(tag, depth + 1))

        if (
            not elements
            and text
            and name in ("div", "section", "article", "header", "footer", "nav", "aside", "main", "span", "address")
        ):
            elements.append({"role": "paragraph", "text": text[:500]})

        return elements

    SELECTORS = [
        "header",
        "nav",
        "main",
        "article",
        "section",
        "aside",
        "[role='banner']",
        "[role='navigation']",
        "[role='main']",
        "[role='contentinfo']",
    ]

    visited = set()
    groups = []

    # ── Always extract footer first ───────────────────────────────────────────
    # Contact details, address, phone, business registration, and social links
    # live in the footer and must never be lost to group-count truncation.
    footer_els = soup.select("footer, [role='contentinfo'], [class*='footer'], [id*='footer']")
    footer_groups_added = set()
    for el in footer_els:
        eid = id(el)
        if eid in footer_groups_added:
            continue
        footer_groups_added.add(eid)
        visited.add(eid)
        for d in el.find_all(True):
            visited.add(id(d))
        elements = extract_elements(el)
        if elements:
            groups.append({"type": "footer", "elements": elements, "_priority": True})

    # ── Then process all other semantic sections ──────────────────────────────
    for selector in SELECTORS:
        try:
            for el in soup.select(selector):
                eid = id(el)
                if eid in visited:
                    continue
                visited.add(eid)
                for d in el.find_all(True):
                    visited.add(id(d))
                elements = extract_elements(el)
                if elements:
                    groups.append({"type": classify_container(el), "elements": elements})
        except Exception:
            continue

    # ── Fallback: unvisited body direct children ──────────────────────────────
    body = soup.find("body")
    if body:
        for child in body.find_all(True, recursive=False):
            if id(child) not in visited and isinstance(child, Tag):
                elements = extract_elements(child)
                if elements:
                    groups.append({"type": classify_container(child), "elements": elements})

    # ── Render — footer first, then rest, cap at 30 groups ───────────────────
    priority = [g for g in groups if g.get("_priority")]
    rest = [g for g in groups if not g.get("_priority")]
    ordered = priority + rest

    lines = ["=== PAGE SEMANTIC STRUCTURE ===\n"]
    for i, g in enumerate(ordered[:30]):
        lines.append(f"[GROUP {i + 1}: {g['type'].upper()}]")
        for el in g["elements"][:20]:
            role = el.get("role", "?")
            if role == "heading":
                lines.append(f"  {el['level'].upper()}: {el['text']}")
            elif role == "paragraph":
                lines.append(f"  PARA: {el['text']}")
            elif role == "button":
                lines.append(f"  BUTTON: {el['text']}")
            elif role == "link":
                lines.append(f"  LINK: {el['text']}  → {el.get('href', '')}")
            elif role == "image":
                lines.append(f'  IMG alt="{el["alt"]}"')
            elif role == "form-field":
                lines.append(f"  FIELD: {el['placeholder']}")
            elif role == "list-item":
                lines.append(f"  • {el['text']}")
        lines.append("")

    result = "\n".join(lines)
    if len(result) > 10000:
        result = result[:10000] + "\n[... truncated ...]"
    print(f"[extractor] {len(ordered)} groups ({len(priority)} footer-priority), {len(result)} chars")
    return result
