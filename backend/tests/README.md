# Backend Tests

This directory contains comprehensive Python tests for the Prism backend.

## Test Structure

```
backend/tests/
├── __init__.py              # Makes tests a Python package
├── conftest.py              # Pytest fixtures and configuration
├── pytest.ini               # Pytest configuration
├── requirements-dev.txt     # Test dependencies
├── test_models.py           # Pydantic model tests
├── test_utils.py            # Utility function tests
├── test_semantic.py         # Semantic extraction tests
├── test_ai_client.py        # AI client tests
├── test_db.py               # Database layer tests
├── test_routes_discover.py  # Discover routes tests
├── test_routes_history.py   # History routes tests
├── test_email_service.py    # Email service tests
├── test_main.py             # Main app routes tests
└── test_prompts.py          # Prompt building tests
```

## Running Tests

### Install dependencies

```bash
cd backend
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Run all tests

```bash
cd backend
pytest
```

### Run specific test file

```bash
pytest tests/test_models.py
```

### Run with coverage

```bash
pytest --cov=backend --cov-report=html
```

### Run only unit tests (skip slow tests)

```bash
pytest -m "not slow"
```

### Run with verbose output

```bash
pytest -vv
```

## Test Categories

### Unit Tests
Fast, isolated tests that don't require external services:
- `test_models.py` - Pydantic model validation
- `test_utils.py` - Utility functions
- `test_semantic.py` - HTML parsing and extraction
- `test_prompts.py` - Prompt building

### Integration Tests
Tests that mock external services:
- `test_ai_client.py` - AI provider clients (mocked HTTP)
- `test_db.py` - Database operations (mocked TinyDB)
- `test_routes_*.py` - API routes (mocked dependencies)
- `test_email_service.py` - Email generation and sending
- `test_main.py` - Core API endpoints

## Key Fixtures (conftest.py)

- `client` - FastAPI test client
- `ai_settings_*` - AI settings for different providers
- `sample_scan_result` - Example scan result data
- `sample_prospect` - Example prospect data
- `sample_html` - Sample HTML for parsing tests
- `mock_tinydb` - Mocked TinyDB instance

## Writing New Tests

### Basic test structure

```python
def test_something():
    """Test description."""
    result = function_to_test()
    assert result == expected_value
```

### Using fixtures

```python
def test_with_fixture(client, sample_scan_result):
    """Test using fixtures."""
    response = client.post("/api/analyze", json=sample_scan_result)
    assert response.status_code == 200
```

### Async tests

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await async_function()
    assert result is not None
```

## Mocking External Services

### Mock httpx calls

```python
from unittest.mock import patch, MagicMock

with patch("httpx.AsyncClient.post") as mock_post:
    mock_response = MagicMock()
    mock_response.json.return_value = {"key": "value"}
    mock_post.return_value = mock_response
    # Test code here
```

### Mock database

```python
with patch("backend.db.scans_db") as mock_db:
    mock_db.all.return_value = []
    # Test code here
```

## Continuous Integration

These tests are designed to run in CI environments without requiring:
- Real AI providers (Ollama, OpenAI, Claude)
- Screenshot service
- Discover service
- SMTP server

All external dependencies are mocked.
