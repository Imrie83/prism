"""
Tests for semantic extraction modules (semantic.py and semantic_extractor.py).
"""

import pytest
from bs4 import BeautifulSoup

from backend.semantic import extract_semantic_groups
from backend.semantic_extractor import (
    SemanticElement,
    SemanticGroup,
    PageStructure,
    extract_page_structure,
    build_ai_prompt,
    detect_section_role,
    detect_element_role,
    extract_text,
    extract_direct_elements,
    is_structural,
    extract_groups,
)


class TestExtractSemanticGroups:
    """Test the semantic.py extraction function."""

    def test_extract_from_simple_html(self):
        """Test extraction from simple HTML structure."""
        html = '''
        <html>
        <body>
            <header>
                <h1>Title</h1>
            </header>
            <nav><a href="/">Home</a></nav>
            <footer>Contact</footer>
        </body>
        </html>
        '''
        result = extract_semantic_groups(html)
        assert "PAGE SEMANTIC STRUCTURE" in result
        assert "Title" in result

    def test_extract_headings(self):
        """Test extraction of heading elements."""
        html = '''
        <html>
        <body>
            <section>
                <h1>Main Heading</h1>
                <h2>Sub Heading</h2>
            </section>
        </body>
        </html>
        '''
        result = extract_semantic_groups(html)
        assert "H1: Main Heading" in result
        assert "H2: Sub Heading" in result

    def test_extract_paragraphs(self):
        """Test extraction of paragraph elements."""
        html = '''
        <html>
        <body>
            <section>
                <p>This is a paragraph.</p>
            </section>
        </body>
        </html>
        '''
        result = extract_semantic_groups(html)
        assert "PARA: This is a paragraph." in result

    def test_extract_links(self):
        """Test extraction of link elements."""
        html = '''
        <html>
        <body>
            <nav>
                <a href="/home">Home</a>
            </nav>
        </body>
        </html>
        '''
        result = extract_semantic_groups(html)
        assert "LINK: Home" in result

    def test_extract_buttons(self):
        """Test extraction of button elements."""
        html = '''
        <html>
        <body>
            <section>
                <button>Click Me</button>
            </section>
        </body>
        </html>
        '''
        result = extract_semantic_groups(html)
        assert "BUTTON: Click Me" in result

    def test_extract_images(self):
        """Test extraction of image elements."""
        html = '''
        <html>
        <body>
            <section>
                <img src="image.jpg" alt="Test Image">
            </section>
        </body>
        </html>
        '''
        result = extract_semantic_groups(html)
        assert 'IMG alt="Test Image"' in result

    def test_removes_script_style_tags(self):
        """Test that script and style tags are removed."""
        html = '''
        <html>
        <head>
            <script>alert('test');</script>
            <style>body { color: red; }</style>
        </head>
        <body>
            <p>Visible content</p>
        </body>
        </html>
        '''
        result = extract_semantic_groups(html)
        assert "Visible content" in result
        assert "alert" not in result
        assert "color: red" not in result

    def test_navigation_classification(self):
        """Test that nav elements are classified correctly."""
        html = '''
        <html>
        <body>
            <nav><a href="/">Home</a></nav>
        </body>
        </html>
        '''
        result = extract_semantic_groups(html)
        assert "NAVIGATION" in result

    def test_footer_classification(self):
        """Test that footer elements are classified correctly."""
        html = '''
        <html>
        <body>
            <footer>Contact info</footer>
        </body>
        </html>
        '''
        result = extract_semantic_groups(html)
        assert "FOOTER" in result

    def test_hero_classification(self):
        """Test that hero sections are classified correctly."""
        html = '''
        <html>
        <body>
            <div class="hero">Welcome</div>
        </body>
        </html>
        '''
        result = extract_semantic_groups(html)
        assert "HERO" in result

    def test_truncates_long_content(self):
        """Test that very long content is truncated."""
        long_text = "Word " * 2000
        html = f'''
        <html>
        <body>
            <p>{long_text}</p>
        </body>
        </html>
        '''
        result = extract_semantic_groups(html)
        assert "[... truncated ...]" in result

    def test_limit_groups(self):
        """Test that group count is limited."""
        html = ""
        for i in range(30):
            html += f'<section><h2>Section {i}</h2></section>\n'
        html = f'<html><body>{html}</body></html>'

        result = extract_semantic_groups(html)
        # Should be limited to 20 groups
        group_count = result.count("[GROUP")
        assert group_count <= 20


class TestSemanticExtractor:
    """Test the semantic_extractor.py module."""

    def test_semantic_element_creation(self):
        """Test SemanticElement dataclass creation."""
        element = SemanticElement(
            role="heading",
            text="Test Heading",
            tag="h1",
            attrs={"class": "main-title"},
        )
        assert element.role == "heading"
        assert element.text == "Test Heading"
        assert element.tag == "h1"
        assert element.attrs["class"] == "main-title"

    def test_semantic_group_creation(self):
        """Test SemanticGroup dataclass creation."""
        elements = [
            SemanticElement(role="heading", text="Title", tag="h1", attrs={}),
            SemanticElement(role="paragraph", text="Content", tag="p", attrs={}),
        ]
        group = SemanticGroup(role="hero", elements=elements, depth=1)
        assert group.role == "hero"
        assert len(group.elements) == 2
        assert group.depth == 1

    def test_semantic_group_is_empty(self):
        """Test SemanticGroup.is_empty method."""
        empty_group = SemanticGroup(role="hero", elements=[], depth=0)
        assert empty_group.is_empty() is True

        elements = [SemanticElement(role="heading", text="Title", tag="h1", attrs={})]
        non_empty = SemanticGroup(role="hero", elements=elements, depth=0)
        assert non_empty.is_empty() is False

    def test_semantic_group_text_summary(self):
        """Test SemanticGroup.text_summary method."""
        elements = [
            SemanticElement(role="heading", text="Title", tag="h1", attrs={}),
            SemanticElement(role="paragraph", text="Content", tag="p", attrs={}),
        ]
        group = SemanticGroup(role="hero", elements=elements, depth=0)
        summary = group.text_summary()
        assert "[heading] Title" in summary
        assert "[paragraph] Content" in summary

    def test_page_structure_creation(self):
        """Test PageStructure dataclass creation."""
        groups = [SemanticGroup(role="hero", elements=[], depth=0)]
        structure = PageStructure(
            title="Test Page",
            lang="ja",
            groups=groups,
            meta={"description": "A test page"},
        )
        assert structure.title == "Test Page"
        assert structure.lang == "ja"
        assert len(structure.groups) == 1

    def test_page_structure_to_prompt_text(self):
        """Test PageStructure.to_prompt_text method."""
        elements = [
            SemanticElement(role="heading", text="Welcome", tag="h1", attrs={}),
        ]
        groups = [SemanticGroup(role="hero", elements=elements, depth=0)]
        structure = PageStructure(
            title="Test Page",
            lang="en",
            groups=groups,
            meta={"description": "A test page"},
        )
        text = structure.to_prompt_text()
        assert "PAGE TITLE: Test Page" in text
        assert "PAGE LANGUAGE: en" in text
        assert "META DESCRIPTION: A test page" in text
        assert "HERO" in text
        assert "[heading] Welcome" in text

    def test_page_structure_truncation(self):
        """Test that to_prompt_text truncates long content."""
        long_text = "Word " * 2000
        elements = [
            SemanticElement(role="paragraph", text=long_text, tag="p", attrs={}),
        ]
        groups = [SemanticGroup(role="hero", elements=elements, depth=0)]
        structure = PageStructure(
            title="Test",
            lang="en",
            groups=groups,
            meta={},
        )
        text = structure.to_prompt_text(max_chars=100)
        assert "… (truncated)" in text

    def test_detect_section_role_nav(self):
        """Test detection of nav role."""
        html = '<nav><a href="/">Home</a></nav>'
        soup = BeautifulSoup(html, 'lxml')
        role = detect_section_role(soup.nav)
        assert role == "nav"

    def test_detect_section_role_footer(self):
        """Test detection of footer role."""
        html = '<footer>Copyright 2024</footer>'
        soup = BeautifulSoup(html, 'lxml')
        role = detect_section_role(soup.footer)
        assert role == "footer"

    def test_detect_section_role_by_class(self):
        """Test detection of role by CSS class."""
        html = '<div class="hero-section">Welcome</div>'
        soup = BeautifulSoup(html, 'lxml')
        role = detect_section_role(soup.div)
        assert role == "hero"

    def test_detect_element_role_heading(self):
        """Test detection of heading element role."""
        html = '<h1>Title</h1>'
        soup = BeautifulSoup(html, 'lxml')
        role = detect_element_role(soup.h1)
        assert role == "heading"

    def test_detect_element_role_button(self):
        """Test detection of button element role."""
        html = '<button>Click</button>'
        soup = BeautifulSoup(html, 'lxml')
        role = detect_element_role(soup.button)
        assert role == "button"

    def test_detect_element_role_cta(self):
        """Test detection of CTA link role."""
        html = '<a class="btn-primary">Buy Now</a>'
        soup = BeautifulSoup(html, 'lxml')
        role = detect_element_role(soup.a)
        assert role == "cta"

    def test_extract_text(self):
        """Test text extraction from tag."""
        html = '<p>  Multiple   spaces   here  </p>'
        soup = BeautifulSoup(html, 'lxml')
        text = extract_text(soup.p)
        assert text == "Multiple spaces here"

    def test_extract_text_from_image(self):
        """Test text extraction from img tag (alt text)."""
        html = '<img src="test.jpg" alt="Test Image" title="Title">'
        soup = BeautifulSoup(html, 'lxml')
        text = extract_text(soup.img)
        assert text == "Test Image"

    def test_is_structural_section(self):
        """Test is_structural for section tag."""
        html = '<section><h2>Title</h2><p>Content</p></section>'
        soup = BeautifulSoup(html, 'lxml')
        assert is_structural(soup.section) is True

    def test_is_not_structural_simple_div(self):
        """Test is_structural for simple div with inline content."""
        html = '<div><span>Text</span></div>'
        soup = BeautifulSoup(html, 'lxml')
        # A div with only one inline child is not structural
        assert is_structural(soup.div) is False

    def test_extract_page_structure(self):
        """Test full page structure extraction."""
        html = '''
        <html lang="ja">
        <head>
            <title>Test Page</title>
            <meta name="description" content="A test page">
        </head>
        <body>
            <header>
                <h1>Title</h1>
            </header>
        </body>
        </html>
        '''
        structure = extract_page_structure(html)
        assert structure.title == "Test Page"
        assert structure.lang == "ja"
        assert structure.meta.get("description") == "A test page"

    def test_build_ai_prompt(self):
        """Test building AI prompt from page structure."""
        groups = [
            SemanticGroup(
                role="hero",
                elements=[
                    SemanticElement(role="heading", text="Welcome", tag="h1", attrs={}),
                ],
                depth=0,
            )
        ]
        structure = PageStructure(
            title="Test",
            lang="en",
            groups=groups,
            meta={},
        )
        prompt = build_ai_prompt(structure)
        assert "Analyse this page structure" in prompt
        assert "PAGE TITLE: Test" in prompt
