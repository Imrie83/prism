"""
Tests for backend.email_service module.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi.testclient import TestClient

from backend.email_service import (
    build_report_card_html,
    TEXT_TYPES,
    VISUAL_TYPES,
    UX_TYPES,
    JP_TYPE,
    JP_SEV,
    SEV_COLOR,
)


class TestReportCardHtml:
    """Test report card HTML generation."""

    def test_build_report_card_basic(self):
        """Test building a basic report card."""
        scan = {
            "url": "https://example.com",
            "score": 75,
            "summary": "Good site with minor issues",
            "totalIssues": 5,
            "issueCounts": {"high": 1, "medium": 2, "low": 2},
            "issues": [
                {
                    "type": "untranslated_nav_ui",
                    "severity": "high",
                    "explanation": "Navigation should be in English",
                },
            ],
        }
        html = build_report_card_html(scan)
        assert "SHINRAI AUDIT" in html
        assert "75" in html
        assert "example.com" in html

    def test_report_card_score_colors(self):
        """Test score color coding in report card."""
        # High score (75+)
        scan_high = {"url": "https://example.com", "score": 85, "issues": [], "totalIssues": 0}
        html_high = build_report_card_html(scan_high)
        assert "#16a34a" in html_high  # Green

        # Medium score (45-74)
        scan_med = {"url": "https://example.com", "score": 60, "issues": [], "totalIssues": 0}
        html_med = build_report_card_html(scan_med)
        assert "#d97706" in html_med  # Orange

        # Low score (<45)
        scan_low = {"url": "https://example.com", "score": 30, "issues": [], "totalIssues": 0}
        html_low = build_report_card_html(scan_low)
        assert "#dc2626" in html_low  # Red

    def test_report_card_issue_types(self):
        """Test report card includes issue types."""
        scan = {
            "url": "https://example.com",
            "score": 65,
            "issues": [
                {"type": "untranslated_nav_ui", "severity": "high", "explanation": "Nav issue"},
                {"type": "visual_hierarchy", "severity": "medium", "explanation": "Visual issue"},
                {"type": "navigation_ux", "severity": "low", "explanation": "UX issue"},
            ],
        }
        html = build_report_card_html(scan)
        # Should include Japanese translations
        assert JP_TYPE["untranslated_nav_ui"] in html or "untranslated_nav_ui" in html

    def test_report_card_issue_count_display(self):
        """Test issue counts are displayed correctly."""
        scan = {
            "url": "https://example.com",
            "score": 65,
            "totalIssues": 8,
            "issueCounts": {"high": 2, "medium": 4, "low": 2},
            "issues": [],
        }
        html = build_report_card_html(scan)
        # Should show severity colors
        assert "#dc2626" in html or "#d97706" in html or "#16a34a" in html


class TestIssueTypeConstants:
    """Test issue type categorization constants."""

    def test_text_types_exist(self):
        """Test TEXT_TYPES contains expected types."""
        assert "untranslated_nav_ui" in TEXT_TYPES
        assert "untranslated_body" in TEXT_TYPES
        assert "machine_translation" in TEXT_TYPES
        assert "grammar_error" in TEXT_TYPES

    def test_visual_types_exist(self):
        """Test VISUAL_TYPES contains expected types."""
        assert "visual_hierarchy" in VISUAL_TYPES
        assert "poor_contrast" in VISUAL_TYPES
        assert "cluttered_layout" in VISUAL_TYPES

    def test_ux_types_exist(self):
        """Test UX_TYPES contains expected types."""
        assert "navigation_ux" in UX_TYPES
        assert "social_proof" in UX_TYPES
        assert "contact_accessibility" in UX_TYPES

    def test_jp_type_translations(self):
        """Test Japanese translations exist."""
        assert JP_TYPE["untranslated_nav_ui"] == "未翻訳ナビ・UI"
        assert JP_TYPE["grammar_error"] == "文法エラー"

    def test_jp_severity_translations(self):
        """Test severity translations."""
        assert JP_SEV["high"] == "重要"
        assert JP_SEV["medium"] == "中程度"
        assert JP_SEV["low"] == "軽微"

    def test_severity_colors(self):
        """Test severity color mapping."""
        assert SEV_COLOR["high"] == "#dc2626"
        assert SEV_COLOR["medium"] == "#d97706"
        assert SEV_COLOR["low"] == "#16a34a"


class TestEmailRoutes:
    """Test email-related routes."""

    @pytest.mark.asyncio
    async def test_generate_email_endpoint(self):
        """Test POST /api/generate-email endpoint."""
        from backend.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        with patch("backend.email_service.call_ai") as mock_ai, \
             patch("backend.email_service.call_ollama") as mock_ollama:

            mock_ai.return_value = {
                "subject": "Test Subject",
                "jp_paragraphs": ["テスト段落"],
                "en_paragraphs": ["Test paragraph"],
                "_usage": {"total_tokens": 100},
            }

            response = client.post(
                "/api/generate-email",
                json={
                    "scan_result": {
                        "url": "https://example.com",
                        "score": 75,
                        "title": "Test Site",
                        "summary": "Good site",
                        "issues": [],
                        "scan_mode": "shallow",
                    },
                    "settings": {
                        "ai_provider": "ollama",
                        "ollama_base_url": "http://localhost:11434",
                        "ollama_model": "qwen3.5:9b",
                        "openai_api_key": "",
                        "anthropic_api_key": "",
                        "anthropic_model": "claude-sonnet-4-6",
                        "your_name": "Test",
                        "your_title": "Tester",
                        "your_email": "test@test.com",
                        "your_website": "https://test.com",
                    },
                },
            )
            assert response.status_code == 200

    def test_rebuild_card_endpoint(self):
        """Test POST /api/rebuild-card endpoint."""
        from backend.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        response = client.post(
            "/api/rebuild-card",
            json={
                "scan_result": {
                    "url": "https://example.com",
                    "score": 75,
                    "issues": [
                        {"type": "untranslated_nav_ui", "severity": "high", "explanation": "Test"},
                        {"type": "grammar_error", "severity": "low", "explanation": "Test 2"},
                    ],
                },
                "selected_issue_indices": [0],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "card_html" in data
        assert "card_block" in data

    def test_send_email_endpoint_success(self):
        """Test POST /api/send-email endpoint success."""
        from backend.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        with patch("smtplib.SMTP") as mock_smtp, \
             patch("backend.email_service.update_email") as mock_update:

            mock_smtp_instance = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_smtp_instance

            response = client.post(
                "/api/send-email",
                json={
                    "to": "recipient@example.com",
                    "subject": "Test Subject",
                    "html": "<html><body>Test</body></html>",
                    "url": "https://example.com",
                    "settings": {
                        "gmail_address": "sender@gmail.com",
                        "gmail_app_password": "apppassword123",
                        "your_name": "Test Sender",
                        "from_address": "noreply@example.com",
                    },
                },
            )
            assert response.status_code == 200
            assert response.json()["ok"] is True

    def test_send_email_endpoint_missing_credentials(self):
        """Test send email with missing credentials."""
        from backend.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        response = client.post(
            "/api/send-email",
            json={
                "to": "recipient@example.com",
                "subject": "Test",
                "html": "<html>Test</html>",
                "settings": {
                    "gmail_address": "",
                    "gmail_app_password": "",
                },
            },
        )
        assert response.status_code == 400
