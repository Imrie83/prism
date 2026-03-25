"""
Tests for backend.main module.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json

from fastapi.testclient import TestClient

from backend.main import app, ACTIVE_TASKS, register_task, unregister_task, cancel_task


client = TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self):
        """Test GET /api/health endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestTestAiEndpoint:
    """Test AI connectivity test endpoint."""

    @pytest.mark.asyncio
    async def test_test_ai_ollama(self):
        """Test AI connectivity with Ollama provider."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": '{"ok": true}'},
            "prompt_eval_count": 10,
            "eval_count": 5,
        }
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            response = client.post(
                "/api/test-ai",
                json={
                    "url": "https://example.com",
                    "settings": {
                        "ai_provider": "ollama",
                        "ollama_base_url": "http://localhost:11434",
                        "ollama_model": "qwen3.5:9b",
                        "openai_api_key": "",
                        "openai_model": "gpt-4o-mini",
                        "anthropic_api_key": "",
                        "anthropic_model": "claude-sonnet-4-6",
                        "screenshot_service_url": "http://screenshot:3000",
                        "max_deep_pages": 20,
                    },
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["provider"] == "ollama"

    def test_test_ai_openai(self):
        """Test AI connectivity with OpenAI provider."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            response = client.post(
                "/api/test-ai",
                json={
                    "url": "https://example.com",
                    "settings": {
                        "ai_provider": "openai",
                        "ollama_base_url": "http://localhost:11434",
                        "ollama_model": "qwen3.5:9b",
                        "openai_api_key": "sk-test",
                        "openai_model": "gpt-4o-mini",
                        "anthropic_api_key": "",
                        "anthropic_model": "claude-sonnet-4-6",
                        "screenshot_service_url": "http://screenshot:3000",
                        "max_deep_pages": 20,
                    },
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["provider"] == "openai"


class TestCheckOllamaEndpoint:
    """Test Ollama connectivity check endpoint."""

    def test_check_ollama_success(self):
        """Test successful Ollama check."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [{"name": "qwen3.5:9b"}, {"name": "llama2:latest"}],
        }
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            response = client.get("/api/check-ollama")
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is True
            assert "qwen3.5:9b" in data["models"]

    def test_check_ollama_failure(self):
        """Test failed Ollama check."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Connection refused")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            response = client.get("/api/check-ollama")
            assert response.status_code == 200
            data = response.json()
            assert data["ok"] is False


class TestAnalyzeEndpoint:
    """Test analyze endpoint."""

    @pytest.mark.asyncio
    async def test_analyze_shallow(self):
        """Test shallow mode analysis."""
        mock_screenshot_response = MagicMock()
        mock_screenshot_response.json.return_value = {
            "screenshot": "base64data",
            "html": "<html><body>Test</body></html>",
            "pageHeight": 1200,
        }
        mock_screenshot_response.status_code = 200

        mock_ai_response = MagicMock()
        mock_ai_response.json.return_value = {
            "score": 70,
            "summary": "Good site",
            "title": "Test Site",
            "issues": [],
        }

        with patch("backend.main.take_screenshot") as mock_screenshot, \
             patch("backend.main.call_ai") as mock_ai, \
             patch("backend.main.upsert_scan") as mock_upsert, \
             patch("backend.main.extract_emails_from_html") as mock_emails:

            mock_screenshot.return_value = ("base64data", "<html>Test</html>", 1200)
            mock_ai.return_value = {
                "score": 70,
                "summary": "Good site",
                "title": "Test Site",
                "issues": [],
                "_usage": {"total_tokens": 150},
            }
            mock_emails.return_value = ["test@example.com"]

            response = client.post(
                "/api/analyze",
                json={
                    "url": "https://example.com",
                    "settings": {
                        "ai_provider": "ollama",
                        "ollama_base_url": "http://localhost:11434",
                        "ollama_model": "qwen3.5:9b",
                        "openai_api_key": "",
                        "openai_model": "gpt-4o-mini",
                        "anthropic_api_key": "",
                        "anthropic_model": "claude-sonnet-4-6",
                        "screenshot_service_url": "http://screenshot:3000",
                        "max_deep_pages": 20,
                    },
                    "scan_mode": "shallow",
                    "vision_mode": False,
                },
            )
            assert response.status_code == 200
            # Response is streaming, just verify it succeeds


class TestCrawlEndpoint:
    """Test crawl endpoint."""

    def test_crawl_basic(self):
        """Test basic crawl functionality."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.headers = {"content-type": "text/html"}
            mock_response.text = '''
                <html>
                <body>
                    <a href="/page1">Page 1</a>
                    <a href="/page2">Page 2</a>
                </body>
                </html>
            '''
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            response = client.post(
                "/api/crawl",
                json={"url": "https://example.com", "max_pages": 5},
            )
            assert response.status_code == 200
            data = response.json()
            assert "urls" in data
            assert "total" in data

    def test_crawl_excludes_non_html(self):
        """Test crawl excludes non-HTML files."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            html_response = MagicMock()
            html_response.headers = {"content-type": "text/html"}
            html_response.text = '''
                <html>
                <body>
                    <a href="/page.pdf">PDF</a>
                    <a href="/image.png">Image</a>
                    <a href="/page1">Page 1</a>
                </body>
                </html>
            '''

            mock_client.get.return_value = html_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            response = client.post(
                "/api/crawl",
                json={"url": "https://example.com", "max_pages": 10},
            )
            assert response.status_code == 200
            data = response.json()
            # Should only include page1, not .pdf or .png
            for url in data["urls"]:
                assert not url.endswith(".pdf")
                assert not url.endswith(".png")


class TestAgentChatEndpoint:
    """Test agent chat endpoint."""

    @pytest.mark.asyncio
    async def test_agent_chat_ollama(self):
        """Test agent chat with Ollama."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": "I can help you with that!"},
        }
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            response = client.post(
                "/api/agent-chat",
                json={
                    "messages": [
                        {"role": "user", "content": "How do I fix navigation issues?"},
                    ],
                    "scan_context": "Site has untranslated navigation",
                    "settings": {
                        "ai_provider": "ollama",
                        "ollama_base_url": "http://localhost:11434",
                        "ollama_model": "qwen3.5:9b",
                        "openai_api_key": "",
                        "openai_model": "gpt-4o-mini",
                        "anthropic_api_key": "",
                        "anthropic_model": "claude-sonnet-4-6",
                        "screenshot_service_url": "http://screenshot:3000",
                        "max_deep_pages": 20,
                    },
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert "reply" in data


class TestTaskRegistry:
    """Test task registry functionality."""

    @pytest.mark.asyncio
    async def test_register_task(self):
        """Test registering a task."""
        import asyncio

        task = asyncio.create_task(asyncio.sleep(0.1))
        event = asyncio.Event()

        register_task("test-task", task, event)
        assert "test-task" in ACTIVE_TASKS

        # Clean up
        unregister_task("test-task")

    @pytest.mark.asyncio
    async def test_unregister_task(self):
        """Test unregistering a task."""
        import asyncio

        task = asyncio.create_task(asyncio.sleep(0.1))
        event = asyncio.Event()

        register_task("test-task", task, event)
        unregister_task("test-task")
        assert "test-task" not in ACTIVE_TASKS

    @pytest.mark.asyncio
    async def test_cancel_task(self):
        """Test cancelling a task."""
        import asyncio

        task = asyncio.create_task(asyncio.sleep(10))
        event = asyncio.Event()

        register_task("test-task", task, event)
        result = cancel_task("test-task")
        assert result is True
        assert "test-task" not in ACTIVE_TASKS

    def test_cancel_nonexistent_task(self):
        """Test cancelling a non-existent task."""
        result = cancel_task("nonexistent-task")
        assert result is False


class TestListTasksEndpoint:
    """Test tasks listing endpoint."""

    def test_list_tasks_empty(self):
        """Test listing tasks when none are active."""
        # Clear any existing tasks
        ACTIVE_TASKS.clear()
        response = client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["active"] == []

    @pytest.mark.asyncio
    async def test_list_tasks_with_active(self):
        """Test listing active tasks."""
        import asyncio

        # Clear and add a test task
        ACTIVE_TASKS.clear()
        task = asyncio.create_task(asyncio.sleep(0.1))
        event = asyncio.Event()
        ACTIVE_TASKS["test-task"] = (task, event)

        try:
            response = client.get("/api/tasks")
            assert response.status_code == 200
            data = response.json()
            assert "test-task" in data["active"]
        finally:
            # Clean up
            task.cancel()
            try:
                pass
            except:
                pass
            ACTIVE_TASKS.clear()


class TestCancelEndpoint:
    """Test cancel endpoint."""

    @pytest.mark.asyncio
    async def test_cancel_existing_task(self):
        """Test cancelling an existing task."""
        import asyncio

        task = asyncio.create_task(asyncio.sleep(10))
        event = asyncio.Event()
        ACTIVE_TASKS["cancel-test"] = (task, event)

        try:
            response = client.post("/api/cancel/cancel-test")
            assert response.status_code == 200
            data = response.json()
            assert data["cancelled"] is True
            assert data["task_id"] == "cancel-test"
        finally:
            try:
                task.cancel()
            except:
                pass
            ACTIVE_TASKS.pop("cancel-test", None)

    def test_cancel_nonexistent_task(self):
        """Test cancelling a task that doesn't exist."""
        response = client.post("/api/cancel/nonexistent-task")
        assert response.status_code == 200
        data = response.json()
        assert data["cancelled"] is False
        assert data["task_id"] == "nonexistent-task"
