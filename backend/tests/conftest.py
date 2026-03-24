"""
Pytest configuration and fixtures for Prism backend tests.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.main import app
from backend.models import (
    AISettings,
    AnalyzeRequest,
    CrawlRequest,
    AgentChatRequest,
    AgentMessage,
    GenerateEmailRequest,
    SendEmailRequest,
    SendEmailSettings,
    EmailSettings,
    DiscoverSearchRequest,
    RebuildCardRequest,
    SaveEmailDraftRequest,
)


@pytest.fixture
def client():
    """Return a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_db_path():
    """Create temporary database files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        scans_path = os.path.join(tmpdir, "scans.json")
        screenshots_path = os.path.join(tmpdir, "screenshots.json")
        prospects_path = os.path.join(tmpdir, "prospects.json")

        with patch("backend.db.scans_db") as mock_scans, \
             patch("backend.db.screenshots_db") as mock_screenshots, \
             patch("backend.db.prospects_db") as mock_prospects:

            # Configure mock TinyDB instances
            mock_scans.all.return_value = []
            mock_screenshots.all.return_value = []
            mock_prospects.all.return_value = []

            yield {
                "scans": mock_scans,
                "screenshots": mock_screenshots,
                "prospects": mock_prospects,
            }


@pytest.fixture
def mock_tinydb():
    """Create a mock TinyDB with full CRUD operations."""
    records = []

    def get_all():
        return records

    def insert(data):
        if isinstance(data, list):
            records.extend(data)
            return list(range(len(records) - len(data), len(records)))
        else:
            records.append(data)
            return len(records) - 1

    def upsert(data, cond):
        # Simple upsert based on url
        url = data.get("url", "")
        for i, r in enumerate(records):
            if cond(r):
                records[i] = {**r, **data}
                return
        records.append(data)

    def remove(cond):
        nonlocal records
        records = [r for r in records if not cond(r)]

    def get(cond):
        for r in records:
            if cond(r):
                return r
        return None

    def update(data, cond):
        for i, r in enumerate(records):
            if cond(r):
                records[i] = {**r, **data}

    mock = MagicMock()
    mock.all = get_all
    mock.insert = insert
    mock.upsert = upsert
    mock.remove = remove
    mock.get = get
    mock.update = update

    return mock, records


@pytest.fixture
def ai_settings_ollama():
    """Ollama AI settings fixture."""
    return AISettings(
        ai_provider="ollama",
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen3.5:9b",
        openai_api_key="",
        openai_model="gpt-4o-mini",
        anthropic_api_key="",
        anthropic_model="claude-sonnet-4-6",
        screenshot_service_url="http://screenshot:3000",
        max_deep_pages=20,
    )


@pytest.fixture
def ai_settings_openai():
    """OpenAI settings fixture."""
    return AISettings(
        ai_provider="openai",
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen3.5:9b",
        openai_api_key="sk-test-key",
        openai_model="gpt-4o-mini",
        anthropic_api_key="",
        anthropic_model="claude-sonnet-4-6",
        screenshot_service_url="http://screenshot:3000",
        max_deep_pages=20,
    )


@pytest.fixture
def ai_settings_claude():
    """Anthropic Claude settings fixture."""
    return AISettings(
        ai_provider="claude",
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen3.5:9b",
        openai_api_key="",
        openai_model="gpt-4o-mini",
        anthropic_api_key="test-api-key",
        anthropic_model="claude-sonnet-4-6",
        screenshot_service_url="http://screenshot:3000",
        max_deep_pages=20,
    )


@pytest.fixture
def sample_scan_result():
    """Sample scan result for testing."""
    return {
        "url": "https://example.com",
        "title": "Example Business",
        "score": 65,
        "summary": "Good foundation with some translation issues",
        "totalIssues": 8,
        "issueCounts": {"high": 2, "medium": 4, "low": 2},
        "issues": [
            {
                "type": "untranslated_nav_ui",
                "severity": "high",
                "location": "main navigation",
                "original": "ホーム",
                "suggestion": "Change to 'Home'",
                "explanation": "Navigation must be in English for Western users",
            },
            {
                "type": "machine_translation",
                "severity": "medium",
                "location": "hero section",
                "original": "We are the best company",
                "suggestion": "Use more natural English phrasing",
                "explanation": "Sounds robotic and unnatural",
            },
            {
                "type": "grammar_error",
                "severity": "low",
                "location": "footer",
                "original": "Contact to us",
                "suggestion": "Change to 'Contact us'",
                "explanation": "Minor grammatical error",
            },
        ],
        "scan_mode": "shallow",
        "screenshot": "base64encodedstring",
        "emails_found": ["contact@example.com"],
    }


@pytest.fixture
def sample_prospect():
    """Sample prospect for testing."""
    return {
        "name": "Test Business",
        "website": "https://testbusiness.com",
        "email": "info@testbusiness.com",
        "phone": "+81-3-1234-5678",
        "rating": "4.5",
        "keywords": "test keywords",
        "location": "Tokyo, Japan",
        "session_id": "abc123",
        "status": "new",
        "discovered_at": "2024-01-15T10:30:00Z",
    }


@pytest.fixture
def sample_email_settings():
    """Sample email settings fixture."""
    return EmailSettings(
        ai_provider="ollama",
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen3.5:9b",
        openai_api_key="",
        anthropic_api_key="",
        anthropic_model="claude-sonnet-4-6",
        your_name="Test User",
        your_title="Test Title",
        your_email="test@example.com",
        your_website="https://test.example.com",
    )


@pytest.fixture
def mock_httpx_response():
    """Factory for mock httpx responses."""
    def _create(json_data=None, text_data=None, status_code=200, headers=None):
        response = MagicMock()
        response.status_code = status_code
        response.headers = headers or {}
        if json_data is not None:
            response.json.return_value = json_data
            response.text = json.dumps(json_data)
        elif text_data is not None:
            response.text = text_data
            response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        else:
            response.json.return_value = {}
            response.text = ""
        response.is_success = 200 <= status_code < 300
        response.raise_for_status = MagicMock()
        if not response.is_success:
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=MagicMock(),
                response=response,
            )
        return response
    return _create


@pytest.fixture
def mock_screenshot_service(mock_httpx_response):
    """Mock screenshot service responses."""
    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("httpx.AsyncClient.get") as mock_get:

        async def mock_post_async(*args, **kwargs):
            url = args[0] if args else kwargs.get("url", "")
            if "/screenshot" in url:
                return mock_httpx_response(
                    json_data={
                        "screenshot": "iVBORw0KGgo=test",
                        "html": "<html><body>Test</body></html>",
                        "pageHeight": 1200,
                    }
                )
            elif "/screenshot-offset" in url:
                return mock_httpx_response(
                    json_data={
                        "screenshot": "iVBORw0KGgo=offset",
                        "clipHeight": 800,
                    }
                )
            return mock_httpx_response(json_data={})

        async def mock_get_async(*args, **kwargs):
            return mock_httpx_response(json_data={})

        mock_post.side_effect = mock_post_async
        mock_get.side_effect = mock_get_async

        yield mock_post, mock_get


@pytest.fixture
def mock_ai_response():
    """Mock AI client responses."""
    with patch("backend.ai_client.call_ollama") as mock_ollama, \
         patch("backend.ai_client.call_openai") as mock_openai, \
         patch("backend.ai_client.call_claude") as mock_claude:

        async def ollama_response(*args, **kwargs):
            return (
                '{"score": 70, "summary": "Test", "issues": [], "title": "Test"}',
                {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                    "provider": "ollama",
                    "model": "qwen3.5:9b",
                },
            )

        async def openai_response(*args, **kwargs):
            return (
                '{"score": 70, "summary": "Test", "issues": [], "title": "Test"}',
                {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                },
            )

        async def claude_response(*args, **kwargs):
            return (
                '{"score": 70, "summary": "Test", "issues": [], "title": "Test"}',
                {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                    "provider": "claude",
                    "model": "claude-sonnet-4-6",
                },
            )

        mock_ollama.side_effect = ollama_response
        mock_openai.side_effect = openai_response
        mock_claude.side_effect = claude_response

        yield mock_ollama, mock_openai, mock_claude


@pytest.fixture
def sample_html():
    """Sample HTML for semantic extraction tests."""
    return """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <title>Test Business</title>
        <meta name="description" content="A test business website">
    </head>
    <body>
        <header class="site-header">
            <nav>
                <ul>
                    <li><a href="/">ホーム</a></li>
                    <li><a href="/about">About</a></li>
                    <li><a href="/contact">Contact</a></li>
                </ul>
            </nav>
        </header>
        <main>
            <section class="hero">
                <h1>Welcome to Test Business</h1>
                <p>We provide excellent services</p>
                <button class="cta">Learn More</button>
            </section>
            <section class="about">
                <h2>About Us</h2>
                <p>Founded in 2020</p>
            </section>
        </main>
        <footer>
            <p>Contact us at info@test.com</p>
        </footer>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_with_emails():
    """Sample HTML containing various email addresses."""
    return """
    <html>
    <body>
        <p>Contact us at info@example.com or support@example.com</p>
        <a href="mailto:sales@example.com">Email Sales</a>
        <script>
            var email = "script@example.com";
        </script>
        <p>Invalid: user@example, admin@placeholder.com</p>
    </body>
    </html>
    """


@pytest.fixture
def sample_japanese_html():
    """Sample Japanese business website HTML."""
    return """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <title>日本料理店 - Traditional Japanese Restaurant</title>
    </head>
    <body>
        <nav class="gnav">
            <ul>
                <li><a href="/">ホーム</a></li>
                <li><a href="/menu">お品書き</a></li>
                <li><a href="/access">アクセス</a></li>
            </ul>
        </nav>
        <header class="hero-section">
            <h1>本格日本料理</h1>
            <p>Authentic Japanese cuisine in Tokyo</p>
        </header>
        <section class="about-company">
            <h2>店舗紹介</h2>
            <p>Established 1985</p>
        </section>
        <footer class="site-footer">
            <p>Contact: info@japaneserestaurant.com</p>
        </footer>
    </body>
    </html>
    """


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
