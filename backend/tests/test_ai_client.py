"""
Tests for backend.ai_client module.
"""

import json
import base64
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

from backend.ai_client import (
    call_ollama,
    call_openai,
    call_claude,
    call_ollama_chat,
    call_ai,
    _extract_json,
    _repair_json,
)
from backend.models import AISettings


class TestExtractJson:
    """Test JSON extraction from raw strings."""

    def test_extract_plain_json(self):
        """Test extraction from plain JSON."""
        raw = '{"key": "value"}'
        result = _extract_json(raw)
        assert result == '{"key": "value"}'

    def test_extract_from_markdown_fence(self):
        """Test extraction from markdown code fence."""
        raw = '```json\n{"key": "value"}\n```'
        result = _extract_json(raw)
        assert result == '{"key": "value"}'

    def test_extract_from_json_block(self):
        """Test extraction from JSON block."""
        raw = '```\n{"key": "value"}\n```'
        result = _extract_json(raw)
        assert result == '{"key": "value"}'

    def test_extract_array(self):
        """Test extraction of JSON array."""
        raw = '[1, 2, 3]'
        result = _extract_json(raw)
        assert result == '[1, 2, 3]'

    def test_extract_with_leading_trailing_text(self):
        """Test extraction with surrounding text."""
        raw = 'Here is the result: {"key": "value"} Hope that helps!'
        result = _extract_json(raw)
        assert result == '{"key": "value"}'


class TestRepairJson:
    """Test JSON repair functionality."""

    def test_repair_trailing_commas(self):
        """Test repairing trailing commas."""
        raw = '{"a": 1, "b": 2,}'
        result = _repair_json(raw)
        assert '"b": 2}' in result
        assert ',}' not in result

    def test_repair_unescaped_quotes(self):
        """Test repairing unescaped quotes in values."""
        raw = '{"text": "Say "hello" to them"}'
        result = _repair_json(raw)
        assert '\\"hello\\"' in result


class TestCallOllama:
    """Test Ollama API calls."""

    @pytest.mark.asyncio
    async def test_call_ollama_success(self):
        """Test successful Ollama API call."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": '{"result": "test"}'},
            "prompt_eval_count": 100,
            "eval_count": 50,
        }
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            with patch("httpx.AsyncClient.__aenter__", return_value=mock_response):
                with patch("httpx.AsyncClient.__aexit__", return_value=None):
                    # We need to mock the async context manager properly
                    pass

        # Use a simpler mocking approach
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_client):
            content, usage = await call_ollama(
                prompt="Test prompt",
                system="Test system",
                base_url="http://localhost:11434",
                model="qwen3.5:9b",
            )
            assert '{"result": "test"}' in content
            assert usage["provider"] == "ollama"
            assert usage["model"] == "qwen3.5:9b"

    @pytest.mark.asyncio
    async def test_call_ollama_with_images(self):
        """Test Ollama API call with images."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"content": '{"result": "test"}'},
            "prompt_eval_count": 200,
            "eval_count": 50,
        }
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_client):
            content, usage = await call_ollama(
                prompt="Test prompt",
                system="Test system",
                base_url="http://localhost:11434",
                model="qwen3.5:9b",
                images=["base64image1", "base64image2"],
            )
            # Check that images were passed in the request
            call_args = mock_client.post.call_args
            json_data = call_args[1]["json"]
            assert "images" in json_data["messages"][1]
            assert len(json_data["messages"][1]["images"]) == 2


class TestCallOpenAI:
    """Test OpenAI API calls."""

    @pytest.mark.asyncio
    async def test_call_openai_success(self):
        """Test successful OpenAI API call."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"result": "test"}'}}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        }
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_client):
            content, usage = await call_openai(
                prompt="Test prompt",
                system="Test system",
                api_key="sk-test",
                model="gpt-4o-mini",
            )
            assert '{"result": "test"}' in content
            assert usage["provider"] == "openai"
            assert usage["total_tokens"] == 150

    @pytest.mark.asyncio
    async def test_call_openai_with_images(self):
        """Test OpenAI API call with images."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"result": "test"}'}}],
            "usage": {"prompt_tokens": 200, "completion_tokens": 50, "total_tokens": 250},
        }
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_client):
            content, usage = await call_openai(
                prompt="Test prompt",
                system="Test system",
                api_key="sk-test",
                model="gpt-4o-mini",
                images=["base64image"],
            )
            # Check image format
            call_args = mock_client.post.call_args
            json_data = call_args[1]["json"]
            content_list = json_data["messages"][1]["content"]
            assert len(content_list) == 2  # Image + text
            assert content_list[0]["type"] == "image_url"


class TestCallClaude:
    """Test Claude API calls."""

    @pytest.mark.asyncio
    async def test_call_claude_success(self):
        """Test successful Claude API call."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"text": '{"result": "test"}'}],
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "stop_reason": "end_turn",
        }
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_client):
            content, usage = await call_claude(
                prompt="Test prompt",
                system="Test system",
                api_key="test-key",
                model="claude-sonnet-4-6",
            )
            assert '{"result": "test"}' in content
            assert usage["provider"] == "claude"
            assert usage["stop_reason"] == "end_turn"

    @pytest.mark.asyncio
    async def test_call_claude_max_tokens_warning(self):
        """Test Claude API call with max_tokens stop."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"text": '{"result": "cut off"'}],  # Incomplete JSON
            "usage": {"input_tokens": 100, "output_tokens": 4096},
            "stop_reason": "max_tokens",
        }
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("builtins.print") as mock_print:
                content, usage = await call_claude(
                    prompt="Test prompt",
                    system="Test system",
                    api_key="test-key",
                    model="claude-sonnet-4-6",
                )
                # Should print warning about truncation
                warning_calls = [call for call in mock_print.call_args_list if "WARNING" in str(call)]
                assert len(warning_calls) > 0


class TestCallAi:
    """Test the unified call_ai function."""

    @pytest.mark.asyncio
    async def test_call_ai_ollama(self, ai_settings_ollama):
        """Test call_ai with Ollama provider."""
        with patch("backend.ai_client.call_ollama") as mock_call:
            mock_call.return_value = (
                '{"score": 70, "title": "Test", "issues": []}',
                {"provider": "ollama", "model": "qwen3.5:9b", "total_tokens": 150},
            )
            result = await call_ai(
                prompt="Test",
                system="System",
                settings=ai_settings_ollama,
            )
            assert result["score"] == 70
            assert "_usage" in result
            assert result["_usage"]["provider"] == "ollama"

    @pytest.mark.asyncio
    async def test_call_ai_openai(self, ai_settings_openai):
        """Test call_ai with OpenAI provider."""
        with patch("backend.ai_client.call_openai") as mock_call:
            mock_call.return_value = (
                '{"score": 75, "title": "Test", "issues": []}',
                {"provider": "openai", "model": "gpt-4o-mini", "total_tokens": 200},
            )
            result = await call_ai(
                prompt="Test",
                system="System",
                settings=ai_settings_openai,
            )
            assert result["score"] == 75

    @pytest.mark.asyncio
    async def test_call_ai_claude(self, ai_settings_claude):
        """Test call_ai with Claude provider."""
        with patch("backend.ai_client.call_claude") as mock_call:
            mock_call.return_value = (
                '{"score": 80, "title": "Test", "issues": []}',
                {"provider": "claude", "model": "claude-sonnet-4-6", "total_tokens": 180},
            )
            result = await call_ai(
                prompt="Test",
                system="System",
                settings=ai_settings_claude,
            )
            assert result["score"] == 80

    @pytest.mark.asyncio
    async def test_call_ai_max_tokens_error(self, ai_settings_ollama):
        """Test call_ai raises error on max_tokens."""
        with patch("backend.ai_client.call_ollama") as mock_call:
            mock_call.return_value = (
                '{"score":',
                {"provider": "ollama", "model": "qwen3.5:9b", "stop_reason": "max_tokens"},
            )
            with pytest.raises(ValueError) as exc_info:
                await call_ai(
                    prompt="Test",
                    system="System",
                    settings=ai_settings_ollama,
                )
            assert "truncated" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_call_ai_json_repair(self, ai_settings_ollama):
        """Test call_ai attempts to repair invalid JSON."""
        with patch("backend.ai_client.call_ollama") as mock_call:
            # JSON with trailing comma that needs repair
            mock_call.return_value = (
                '{"score": 70, "title": "Test", "issues": [],}',
                {"provider": "ollama", "model": "qwen3.5:9b"},
            )
            result = await call_ai(
                prompt="Test",
                system="System",
                settings=ai_settings_ollama,
            )
            # Should successfully parse after repair
            assert result["score"] == 70
