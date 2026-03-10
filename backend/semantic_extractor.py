"""
Semantic HTML extractor — groups page elements by DOM context,
preserving semantic relationships between headings, paragraphs, CTAs, buttons etc.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional
from bs4 import BeautifulSoup, Tag


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class SemanticElement:
    role: str           # heading | paragraph | button | cta | link | image | list | label | input | nav-item
    text: str
    tag: str
    attrs: dict = field(default_factory=dict)


@dataclass
class SemanticGroup:
    role: str           # hero | nav | main-content | cta-section | footer | form | sidebar | card | unknown
    elements: list[SemanticElement] = field(default_factory=list)
    depth: int = 0

    def is_empty(self) -> bool:
        return not any(e.text.strip() for e in self.elements)

    def text_summary(self) -> str:
        parts = []
        for e in self.elements:
            t = e.text.strip()
            if t:
                parts.append(f"[{e.role}] {t}")
        return " | ".join(parts)


@dataclass
class PageStructure:
    title: str
    lang: str
    groups: list[SemanticGroup]
    meta: dict = field(default_factory=dict)

    def to_prompt_text(self, max_chars: int = 5000) -> str:
        lines = []
        if self.title:
            lines.append(f"PAGE TITLE: {self.title}")
        if self.lang:
            lines.append(f"PAGE LANGUAGE: {self.lang}")
        if self.meta.get("description"):
            lines.append(f"META DESCRIPTION: {self.meta['description']}")
        lines.append("")

        for i, group in enumerate(self.groups):
            if group.is_empty():
                continue
            lines.append(f"--- SECTION {i+1}: {group.role.upper()} ---")
            for el in group.elements:
                t = el.text.strip()
                if t:
                    lines.append(f"  [{el.role}] {t}")
            lines.append("")

        full = "\n".join(lines)
        if len(full) > max_chars:
            full = full[:max_chars] + "\n… (truncated)"
        return full


# ── Role detection ─────────────────────────────────────────────────────────────

SECTION_ROLE_SIGNALS = {
    "hero":         ["hero", "banner", "jumbotron", "masthead", "splash", "top", "main-visual"],
    "nav":          ["nav", "navigation", "menu", "header", "site-header", "navbar", "topbar", "gnav"],
    "footer":       ["footer", "site-footer", "foot"],
    "cta-section":  ["cta", "call-to-action", "action", "get-started", "signup", "contact", "inquiry", "お問い合わせ"],
    "form":         ["form", "contact-form", "inquiry-form", "login", "register", "search"],
    "sidebar":      ["sidebar", "aside", "side", "widget"],
    "card":         ["card", "item", "product", "service", "feature", "tile"],
    "main-content": ["content", "main", "body", "article", "post", "about", "news"],
}

def detect_section_role(tag: Tag) -> str:
    # Check semantic HTML tags first
    if tag.name == "nav":      return "nav"
    if tag.name == "footer":   return "footer"
    if tag.name == "header":   return "hero"
    if tag.name == "aside":    return "sidebar"
    if tag.name == "main":     return "main-content"
    if tag.name == "form":     return "form"

    # Check class/id/aria-label
    signals = []
    for attr in ["class", "id", "aria-label", "data-section"]:
        val = tag.get(attr, "")
        if isinstance(val, list): val = " ".join(val)
        signals.append(val.lower())
    combined = " ".join(signals)

    for role, keywords in SECTION_ROLE_SIGNALS.items():
        for kw in keywords:
            if kw in combined:
                return role

    # Check child tags for form elements → form section
    if tag.find(["input", "textarea", "select"]):
        return "form"

    return "unknown"


def detect_element_role(tag: Tag) -> Optional[str]:
    name = tag.name
    if name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        return "heading"
    if name == "p":
        return "paragraph"
    if name == "button":
        return "button"
    if name == "a":
        # CTA if has button-like class or is standalone prominent link
        classes = " ".join(tag.get("class", [])).lower()
        if any(k in classes for k in ["btn", "button", "cta", "primary", "action"]):
            return "cta"
        return "link"
    if name in ["input", "textarea"]:
        return "input"
    if name == "label":
        return "label"
    if name in ["ul", "ol"]:
        return "list"
    if name == "img":
        return "image"
    if name == "li":
        return "list-item"
    return None


def extract_text(tag: Tag) -> str:
    """Get meaningful text from a tag, collapsing whitespace."""
    if tag.name == "img":
        return tag.get("alt", "") or tag.get("title", "")
    text = tag.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


# ── Containment sections ───────────────────────────────────────────────────────

SECTION_TAGS = {"section", "article", "div", "header", "footer", "nav", "aside", "main", "form"}
ELEMENT_TAGS = {"h1","h2","h3","h4","h5","h6","p","button","a","input","textarea","label","ul","ol","li","img","span","strong"}

MIN_SECTION_ELEMENTS = 1   # a group needs at least 1 meaningful element


def is_structural(tag: Tag) -> bool:
    """Does this tag act as a meaningful section container?"""
    if tag.name not in SECTION_TAGS:
        return False
    # Skip tiny wrappers with just one child
    children = [c for c in tag.children if isinstance(c, Tag)]
    if len(children) <= 1 and tag.name == "div":
        return False
    # Skip if it only contains inline elements
    block_children = [c for c in children if c.name in SECTION_TAGS | {"p","h1","h2","h3","h4","h5","h6","ul","ol","form","button"}]
    return len(block_children) > 0 or tag.name in {"section","article","nav","header","footer","aside","main","form"}


def extract_direct_elements(tag: Tag) -> list[SemanticElement]:
    """Extract meaningful leaf elements directly inside a tag (not recurse into sub-sections)."""
    elements = []
    for child in tag.children:
        if not isinstance(child, Tag):
            continue
        if is_structural(child):
            continue  # this child is itself a section, skip
        role = detect_element_role(child)
        if role:
            text = extract_text(child)
            if text and len(text) > 1:
                attrs = {}
                if child.name == "a": attrs["href"] = child.get("href", "")
                if child.name == "img": attrs["src"] = child.get("src", "")[:80]
                elements.append(SemanticElement(role=role, text=text[:300], tag=child.name, attrs=attrs))
        else:
            # Recurse into non-section wrappers (div.text, span, etc.)
            if child.name in {"div", "span", "section"} and not is_structural(child):
                inner = extract_direct_elements(child)
                elements.extend(inner)
    return elements


def extract_groups(soup: BeautifulSoup, max_groups: int = 30) -> list[SemanticGroup]:
    """Walk the DOM and extract semantic groups."""
    groups: list[SemanticGroup] = []
    visited: set[int] = set()

    # Remove noise
    for tag in soup.find_all(["script", "style", "noscript", "svg", "iframe", "head"]):
        tag.decompose()

    def walk(node: Tag, depth: int = 0):
        if depth > 8 or len(groups) >= max_groups:
            return
        if id(node) in visited:
            return
        visited.add(id(node))

        if is_structural(node):
            role = detect_section_role(node)
            elements = extract_direct_elements(node)
            if elements:
                g = SemanticGroup(role=role, elements=elements, depth=depth)
                if not g.is_empty():
                    groups.append(g)

            # Recurse into structural children
            for child in node.children:
                if isinstance(child, Tag) and is_structural(child):
                    walk(child, depth + 1)

    body = soup.find("body")
    if body:
        walk(body)
    else:
        walk(soup)

    return groups


# ── Main entry point ───────────────────────────────────────────────────────────

def extract_page_structure(html: str) -> PageStructure:
    soup = BeautifulSoup(html, "lxml")

    # Title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Lang
    html_tag = soup.find("html")
    lang = html_tag.get("lang", "") if html_tag else ""

    # Meta
    meta = {}
    desc = soup.find("meta", attrs={"name": "description"})
    if desc: meta["description"] = desc.get("content", "")
    kw = soup.find("meta", attrs={"name": "keywords"})
    if kw: meta["keywords"] = kw.get("content", "")

    groups = extract_groups(soup)

    return PageStructure(title=title, lang=lang, groups=groups, meta=meta)


def build_ai_prompt(structure: PageStructure, max_chars: int = 5000) -> str:
    return f"""Analyse this page structure for English localization and UX issues.
Each section shows semantic groups extracted from the DOM — preserving context between headings, body copy, CTAs and buttons.

{structure.to_prompt_text(max_chars)}"""
