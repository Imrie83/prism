"""
Semantic HTML extractor for Prism audit.
Parses a rendered HTML page into structured groups (nav, hero, footer, etc.)
so the AI can reason about content and layout without processing raw HTML.
"""
from bs4 import BeautifulSoup, Tag


def extract_semantic_groups(html: str) -> str:
    """Parse HTML into labelled semantic groups, return as structured text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "meta", "link", "head"]):
        tag.decompose()

    def classify_container(tag) -> str:
        name     = tag.name.lower() if tag.name else ""
        combined = f"{name} {' '.join(tag.get('class', []))} {tag.get('role', '')} {tag.get('id', '')}".lower()
        if any(k in combined for k in ["hero", "jumbotron", "banner", "splash"]):   return "hero"
        if any(k in combined for k in ["nav", "menu", "navigation"]):               return "navigation"
        if any(k in combined for k in ["footer", "foot"]):                          return "footer"
        if any(k in combined for k in ["header", "masthead"]):                      return "header"
        if any(k in combined for k in ["cta", "call-to-action", "action"]):         return "cta"
        if any(k in combined for k in ["contact", "form", "inquiry"]):              return "contact-form"
        if any(k in combined for k in ["service", "product", "feature"]):           return "services"
        if any(k in combined for k in ["about", "company", "team", "story"]):       return "about"
        if any(k in combined for k in ["testimonial", "review", "client"]):         return "social-proof"
        if name in ("header",):                                                      return "header"
        if name in ("footer",):                                                      return "footer"
        if name in ("nav",):                                                         return "navigation"
        if name in ("section", "article", "main", "aside"):                         return name
        return "section"

    def extract_elements(container, depth: int = 0) -> list:
        if depth > 4:
            return []
        elements = []
        for tag in container.find_all(True, recursive=False):
            if not isinstance(tag, Tag):
                continue
            name = tag.name.lower()
            text = tag.get_text(" ", strip=True)
            if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                if text: elements.append({"role": "heading", "level": name, "text": text[:300]})
            elif name == "p":
                if text: elements.append({"role": "paragraph", "text": text[:500]})
            elif name == "a":
                if text: elements.append({"role": "link", "text": text[:200], "href": tag.get("href", "")[:100]})
            elif name == "button" or ("btn" in " ".join(tag.get("class", [])).lower()):
                if text: elements.append({"role": "button", "text": text[:200]})
            elif name in ("input", "textarea", "select"):
                elements.append({"role": "form-field", "placeholder": tag.get("placeholder", tag.get("name", tag.get("type", "field")))[:100]})
            elif name == "img":
                elements.append({"role": "image", "alt": tag.get("alt", "[no alt]")[:200], "src": tag.get("src", "")[:80]})
            elif name == "li":
                if text: elements.append({"role": "list-item", "text": text[:300]})
            elif name in ("div", "span", "section", "article", "ul", "ol"):
                elements.extend(extract_elements(tag, depth + 1))
        return elements

    SELECTORS = [
        "header", "nav", "main", "article", "section", "aside", "footer",
        "[role='banner']", "[role='navigation']", "[role='main']", "[role='contentinfo']",
    ]

    visited = set()
    groups  = []

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

    # Fallback: any unvisited body direct children
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
            role = el.get("role", "?")
            if   role == "heading":    lines.append(f"  {el['level'].upper()}: {el['text']}")
            elif role == "paragraph":  lines.append(f"  PARA: {el['text']}")
            elif role == "button":     lines.append(f"  BUTTON: {el['text']}")
            elif role == "link":       lines.append(f"  LINK: {el['text']}  → {el.get('href', '')}")
            elif role == "image":      lines.append(f'  IMG alt="{el["alt"]}"')
            elif role == "form-field": lines.append(f"  FIELD: {el['placeholder']}")
            elif role == "list-item":  lines.append(f"  • {el['text']}")
        lines.append("")

    result = "\n".join(lines)
    if len(result) > 6000:
        result = result[:6000] + "\n[... truncated ...]"
    print(f"[extractor] {len(groups)} groups, {len(result)} chars")
    return result
