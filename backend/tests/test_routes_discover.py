"""
Tests for backend.routes_discover module.
"""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


class TestDiscoverSearch:
    """Test POST /api/discover/search endpoint."""

    def test_discover_search_success(self):
        """Test successful discover search."""
        # Build a proper async context manager mock for client.stream()
        mock_response = MagicMock()

        async def _aiter_text():
            yield json.dumps({"type": "done", "businesses": [
                {"name": "Test Business", "website": "https://test.com", "rating": "4.5"},
                {"name": "Another Business", "website": "https://another.com"},
            ]})

        mock_response.aiter_text = _aiter_text
        mock_response.raise_for_status = MagicMock()

        stream_cm = MagicMock()
        stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        stream_cm.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.stream.return_value = stream_cm
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("backend.routes_discover.prospects_db") as mock_prospects, \
             patch("backend.routes_discover.scans_db") as mock_scans:
            mock_scans.all.return_value = []
            mock_prospects.get.return_value = None

            response = client.post(
                "/api/discover/search",
                json={"keywords": "japanese restaurant", "location": "Tokyo", "limit": 10},
            )
            assert response.status_code == 200

    def test_discover_search_missing_website(self):
        """Test discover search skips businesses without websites."""
        # Build a proper async context manager mock for client.stream()
        mock_response = MagicMock()

        async def _aiter_text_empty():
            yield json.dumps({"type": "done", "businesses": [
                {"name": "No URL Business"},
            ]})

        mock_response.aiter_text = _aiter_text_empty
        mock_response.raise_for_status = MagicMock()

        stream_cm = MagicMock()
        stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        stream_cm.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.stream.return_value = stream_cm
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client), \
             patch("backend.routes_discover.scans_db") as mock_scans, \
             patch("backend.routes_discover.prospects_db"):
            mock_scans.all.return_value = []
            response = client.post(
                "/api/discover/search",
                json={"keywords": "test", "limit": 5},
            )
            # Response will be streaming
            assert response.status_code == 200


class TestGetProspects:
    """Test GET /api/discover/prospects endpoint."""

    def test_get_prospects_empty(self):
        """Test getting prospects when none exist."""
        with patch("backend.routes_discover.prospects_db") as mock_db:
            mock_db.all.return_value = []
            response = client.get("/api/discover/prospects")
            assert response.status_code == 200
            data = response.json()
            assert data["records"] == []
            assert data["total"] == 0

    def test_get_prospects_with_session_filter(self):
        """Test getting prospects filtered by session."""
        records = [
            {"name": "Biz1", "session_id": "session1", "status": "new"},
            {"name": "Biz2", "session_id": "session2", "status": "new"},
        ]

        with patch("backend.routes_discover.prospects_db") as mock_db:
            mock_db.all.return_value = records
            response = client.get("/api/discover/prospects?session_id=session1")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["records"][0]["name"] == "Biz1"

    def test_get_prospects_with_status_filter(self):
        """Test getting prospects filtered by status."""
        records = [
            {"name": "Biz1", "status": "new", "discovered_at": "2024-01-15T10:00:00Z"},
            {"name": "Biz2", "status": "scanned", "discovered_at": "2024-01-16T10:00:00Z"},
        ]

        with patch("backend.routes_discover.prospects_db") as mock_db:
            mock_db.all.return_value = records
            response = client.get("/api/discover/prospects?filter_status=scanned")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["records"][0]["name"] == "Biz2"

    def test_get_prospects_sort_by_rating(self):
        """Test sorting prospects by rating."""
        records = [
            {"name": "Low", "rating": "3.0", "discovered_at": "2024-01-15T10:00:00Z"},
            {"name": "High", "rating": "5.0", "discovered_at": "2024-01-16T10:00:00Z"},
        ]

        with patch("backend.routes_discover.prospects_db") as mock_db:
            mock_db.all.return_value = records
            response = client.get("/api/discover/prospects?sort_by=rating&sort_dir=desc")
            assert response.status_code == 200
            data = response.json()
            assert data["records"][0]["name"] == "High"


class TestGetSessions:
    """Test GET /api/discover/sessions endpoint."""

    def test_get_sessions_empty(self):
        """Test getting sessions when none exist."""
        with patch("backend.routes_discover.prospects_db") as mock_db:
            mock_db.all.return_value = []
            response = client.get("/api/discover/sessions")
            assert response.status_code == 200
            data = response.json()
            assert data["sessions"] == []

    def test_get_sessions_grouped(self):
        """Test getting sessions grouped by session_id."""
        records = [
            {
                "name": "Biz1",
                "session_id": "abc123",
                "keywords": "restaurant",
                "location": "Tokyo",
                "discovered_at": "2024-01-15T10:00:00Z",
                "status": "new",
            },
            {
                "name": "Biz2",
                "session_id": "abc123",
                "keywords": "restaurant",
                "location": "Tokyo",
                "discovered_at": "2024-01-15T10:00:00Z",
                "status": "scanned",
            },
            {
                "name": "Biz3",
                "session_id": "def456",
                "keywords": "hotel",
                "location": "Osaka",
                "discovered_at": "2024-01-14T10:00:00Z",
                "status": "new",
            },
        ]

        with patch("backend.routes_discover.prospects_db") as mock_db:
            mock_db.all.return_value = records
            response = client.get("/api/discover/sessions")
            assert response.status_code == 200
            data = response.json()
            assert len(data["sessions"]) == 2
            # Sessions should be sorted by discovered_at desc
            assert data["sessions"][0]["session_id"] == "abc123"
            # Check counts
            abc_session = next(s for s in data["sessions"] if s["session_id"] == "abc123")
            assert abc_session["count"] == 2
            assert abc_session["scanned"] == 1


class TestGetProspect:
    """Test GET /api/discover/prospect endpoint."""

    def test_get_existing_prospect(self):
        """Test getting an existing prospect."""
        with patch("backend.routes_discover.prospects_db") as mock_db:
            mock_db.get.return_value = {
                "name": "Test Business",
                "website": "https://test.com",
                "email": "test@test.com",
            }
            response = client.get("/api/discover/prospect?website=https://test.com")
            assert response.status_code == 200
            data = response.json()
            assert data["record"]["name"] == "Test Business"

    def test_get_nonexistent_prospect(self):
        """Test getting a non-existent prospect."""
        with patch("backend.routes_discover.prospects_db") as mock_db:
            mock_db.get.return_value = None
            response = client.get("/api/discover/prospect?website=https://notfound.com")
            assert response.status_code == 200
            data = response.json()
            assert data["record"] is None


class TestUpdateProspectStatus:
    """Test PATCH /api/discover/status endpoint."""

    def test_update_status_success(self):
        """Test updating prospect status."""
        with patch("backend.routes_discover.prospects_db") as mock_db:
            response = client.patch(
                "/api/discover/status",
                json={"website": "https://test.com", "status": "scanned"},
            )
            assert response.status_code == 200
            assert response.json()["ok"] is True
            mock_db.update.assert_called_once()

    def test_update_status_missing_fields(self):
        """Test updating status with missing fields."""
        response = client.patch(
            "/api/discover/status",
            json={"website": "https://test.com"},
        )
        assert response.status_code == 400


class TestDeleteProspect:
    """Test DELETE /api/discover/prospect endpoint."""

    def test_delete_prospect(self):
        """Test deleting a prospect."""
        with patch("backend.routes_discover.prospects_db") as mock_db:
            response = client.delete("/api/discover/prospect?website=https://test.com")
            assert response.status_code == 200
            assert response.json()["ok"] is True
            mock_db.remove.assert_called_once()


class TestUpdateProspectEmail:
    """Test PATCH /api/discover/email endpoint."""

    def test_update_email_success(self):
        """Test updating prospect email."""
        with patch("backend.routes_discover.prospects_db") as mock_db:
            response = client.patch(
                "/api/discover/email",
                json={"website": "https://test.com", "email": "new@test.com"},
            )
            assert response.status_code == 200
            assert response.json()["ok"] is True
            mock_db.update.assert_called_once()

    def test_update_email_missing_website(self):
        """Test updating email without website."""
        response = client.patch(
            "/api/discover/email",
            json={"email": "test@test.com"},
        )
        assert response.status_code == 400
