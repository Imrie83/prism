"""
Tests for backend.models module.
"""

import pytest
from pydantic import ValidationError

from backend.models import (
    AISettings,
    AnalyzeRequest,
    CrawlRequest,
    EmailSettings,
    GenerateEmailRequest,
    SendEmailSettings,
    SendEmailRequest,
    AgentMessage,
    AgentChatRequest,
    RebuildCardRequest,
    SaveEmailDraftRequest,
    DiscoverSearchRequest,
)


class TestAISettings:
    """Test AISettings model."""

    def test_default_values(self):
        """Test AISettings with default values."""
        settings = AISettings()
        assert settings.ai_provider == "ollama"
        assert settings.ollama_base_url == "http://localhost:11434"
        assert settings.ollama_model == "qwen3.5:9b"
        assert settings.openai_api_key == ""
        assert settings.openai_model == "gpt-4o-mini"
        assert settings.anthropic_api_key == ""
        assert settings.anthropic_model == "claude-sonnet-4-6"
        assert settings.screenshot_service_url == "http://screenshot:3000"
        assert settings.max_deep_pages == 20

    def test_custom_values(self):
        """Test AISettings with custom values."""
        settings = AISettings(
            ai_provider="openai",
            openai_api_key="sk-test-key",
            openai_model="gpt-4",
            max_deep_pages=50,
        )
        assert settings.ai_provider == "openai"
        assert settings.openai_api_key == "sk-test-key"
        assert settings.openai_model == "gpt-4"
        assert settings.max_deep_pages == 50

    def test_claude_provider(self):
        """Test AISettings with Claude provider."""
        settings = AISettings(
            ai_provider="claude",
            anthropic_api_key="test-key",
            anthropic_model="claude-opus-4",
        )
        assert settings.ai_provider == "claude"
        assert settings.anthropic_api_key == "test-key"


class TestAnalyzeRequest:
    """Test AnalyzeRequest model."""

    def test_minimal_request(self):
        """Test AnalyzeRequest with minimal required fields."""
        settings = AISettings()
        req = AnalyzeRequest(url="https://example.com", settings=settings)
        assert req.url == "https://example.com"
        assert req.scan_mode == "shallow"
        assert req.vision_mode is False
        assert req.task_id is None

    def test_full_request(self):
        """Test AnalyzeRequest with all fields."""
        settings = AISettings(ai_provider="openai")
        req = AnalyzeRequest(
            url="https://example.com",
            settings=settings,
            task_id="task-123",
            scan_mode="deep",
            vision_mode=True,
        )
        assert req.url == "https://example.com"
        assert req.scan_mode == "deep"
        assert req.vision_mode is True
        assert req.task_id == "task-123"

    def test_scan_modes(self):
        """Test different scan modes."""
        settings = AISettings()
        for mode in ["shallow", "deep", "batch"]:
            req = AnalyzeRequest(
                url="https://example.com",
                settings=settings,
                scan_mode=mode,
            )
            assert req.scan_mode == mode


class TestCrawlRequest:
    """Test CrawlRequest model."""

    def test_default_max_pages(self):
        """Test CrawlRequest with default max_pages."""
        req = CrawlRequest(url="https://example.com")
        assert req.url == "https://example.com"
        assert req.max_pages == 20

    def test_custom_max_pages(self):
        """Test CrawlRequest with custom max_pages."""
        req = CrawlRequest(url="https://example.com", max_pages=50)
        assert req.max_pages == 50


class TestEmailSettings:
    """Test EmailSettings model."""

    def test_default_values(self):
        """Test EmailSettings with default values."""
        settings = EmailSettings()
        assert settings.ai_provider == "ollama"
        assert settings.your_name == "Marcin Zielinski"
        assert settings.your_title == "English Localization Specialist"
        assert settings.your_email == ""

    def test_custom_sender_info(self):
        """Test EmailSettings with custom sender info."""
        settings = EmailSettings(
            your_name="Test User",
            your_title="Test Title",
            your_email="test@example.com",
        )
        assert settings.your_name == "Test User"
        assert settings.your_title == "Test Title"
        assert settings.your_email == "test@example.com"


class TestGenerateEmailRequest:
    """Test GenerateEmailRequest model."""

    def test_minimal_request(self, sample_scan_result, ai_settings_ollama):
        """Test GenerateEmailRequest with minimal fields."""
        settings = EmailSettings(
            ai_provider=ai_settings_ollama.ai_provider,
            ollama_base_url=ai_settings_ollama.ollama_base_url,
            ollama_model=ai_settings_ollama.ollama_model,
        )
        req = GenerateEmailRequest(
            scan_result=sample_scan_result,
            settings=settings,
        )
        assert req.scan_result == sample_scan_result
        assert req.dashboard_screenshot is None


class TestSendEmailRequest:
    """Test SendEmailRequest model."""

    def test_full_request(self):
        """Test SendEmailRequest with all fields."""
        settings = SendEmailSettings(
            gmail_address="sender@gmail.com",
            gmail_app_password="apppassword123",
            your_name="Test Sender",
            from_address="noreply@example.com",
        )
        req = SendEmailRequest(
            to="recipient@example.com",
            subject="Test Subject",
            html="<html><body>Test</body></html>",
            url="https://example.com",
            settings=settings,
        )
        assert req.to == "recipient@example.com"
        assert req.subject == "Test Subject"
        assert req.html == "<html><body>Test</body></html>"
        assert req.url == "https://example.com"
        assert req.settings.gmail_address == "sender@gmail.com"


class TestAgentMessage:
    """Test AgentMessage model."""

    def test_message_creation(self):
        """Test AgentMessage creation."""
        msg = AgentMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_system_message(self):
        """Test system AgentMessage."""
        msg = AgentMessage(role="system", content="You are helpful")
        assert msg.role == "system"
        assert msg.content == "You are helpful"


class TestAgentChatRequest:
    """Test AgentChatRequest model."""

    def test_chat_request(self, ai_settings_ollama):
        """Test AgentChatRequest with messages."""
        messages = [
            AgentMessage(role="user", content="Hello"),
            AgentMessage(role="assistant", content="Hi there"),
        ]
        req = AgentChatRequest(
            messages=messages,
            scan_context="Test context",
            settings=ai_settings_ollama,
        )
        assert len(req.messages) == 2
        assert req.scan_context == "Test context"


class TestRebuildCardRequest:
    """Test RebuildCardRequest model."""

    def test_rebuild_request(self, sample_scan_result):
        """Test RebuildCardRequest."""
        req = RebuildCardRequest(
            scan_result=sample_scan_result,
            selected_issue_indices=[0, 1],
        )
        assert req.scan_result == sample_scan_result
        assert req.selected_issue_indices == [0, 1]


class TestSaveEmailDraftRequest:
    """Test SaveEmailDraftRequest model."""

    def test_save_request(self):
        """Test SaveEmailDraftRequest."""
        html = "<html><body>Email content</body></html>"
        req = SaveEmailDraftRequest(html=html)
        assert req.html == html


class TestDiscoverSearchRequest:
    """Test DiscoverSearchRequest model."""

    def test_minimal_request(self):
        """Test DiscoverSearchRequest with minimal fields."""
        req = DiscoverSearchRequest(keywords="japanese restaurant")
        assert req.keywords == "japanese restaurant"
        assert req.location == ""
        assert req.limit == 120

    def test_full_request(self):
        """Test DiscoverSearchRequest with all fields."""
        req = DiscoverSearchRequest(
            keywords="japanese restaurant",
            location="Tokyo",
            limit=50,
        )
        assert req.keywords == "japanese restaurant"
        assert req.location == "Tokyo"
        assert req.limit == 50

    def test_limit_validation(self):
        """Test that limit accepts various values."""
        for limit in [1, 10, 50, 100, 200]:
            req = DiscoverSearchRequest(
                keywords="test",
                limit=limit,
            )
            assert req.limit == limit
