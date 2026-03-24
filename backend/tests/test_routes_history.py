"""
Tests for backend.routes_history module.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


class TestGetHistory:
    """Test GET /api/history endpoint."""

    def test_get_history_empty(self):
        """Test getting history when empty."""
        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.all.return_value = []
            response = client.get("/api/history")
            assert response.status_code == 200
            data = response.json()
            assert data["records"] == []
            assert data["total"] == 0
            assert data["page"] == 1
            assert data["per_page"] == 20

    def test_get_history_with_records(self):
        """Test getting history with records."""
        records = [
            {
                "url": "https://example1.com",
                "score": 75,
                "title": "Site 1",
                "total_issues": 5,
                "issue_counts": {"high": 1, "medium": 2, "low": 2},
                "scanned_at": "2024-01-15T10:00:00Z",
                "scan_mode": "shallow",
            },
            {
                "url": "https://example2.com",
                "score": 50,
                "title": "Site 2",
                "total_issues": 10,
                "issue_counts": {"high": 3, "medium": 4, "low": 3},
                "scanned_at": "2024-01-16T10:00:00Z",
                "scan_mode": "deep",
            },
        ]

        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.all.return_value = records
            response = client.get("/api/history")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert len(data["records"]) == 2
            # Should be sorted by scanned_at desc
            assert data["records"][0]["url"] == "https://example2.com"

    def test_get_history_pagination(self):
        """Test history pagination."""
        records = [
            {"url": f"https://example{i}.com", "scanned_at": f"2024-01-{i:02d}T10:00:00Z"}
            for i in range(1, 26)
        ]

        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.all.return_value = records
            response = client.get("/api/history?page=2")
            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 2
            assert len(data["records"]) == 5  # Last 5 of 25

    def test_get_history_filter_by_email_sent(self):
        """Test filtering history by email sent."""
        records = [
            {
                "url": "https://sent.com",
                "scanned_at": "2024-01-15T10:00:00Z",
                "email": {"sent_at": "2024-01-15T11:00:00Z"},
            },
            {
                "url": "https://notsent.com",
                "scanned_at": "2024-01-16T10:00:00Z",
            },
        ]

        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.all.return_value = records
            response = client.get("/api/history?filter_email=sent")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["records"][0]["url"] == "https://sent.com"

    def test_get_history_filter_by_response(self):
        """Test filtering history by response received."""
        records = [
            {
                "url": "https://responded.com",
                "scanned_at": "2024-01-15T10:00:00Z",
                "email": {"sent_at": "2024-01-15T11:00:00Z", "got_response": True},
            },
            {
                "url": "https://noresponse.com",
                "scanned_at": "2024-01-16T10:00:00Z",
                "email": {"sent_at": "2024-01-16T11:00:00Z", "got_response": False},
            },
        ]

        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.all.return_value = records
            response = client.get("/api/history?filter_email=got_response")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["records"][0]["url"] == "https://responded.com"

    def test_get_history_filter_by_score_range(self):
        """Test filtering history by score range."""
        records = [
            {"url": "https://low.com", "score": 30, "scanned_at": "2024-01-15T10:00:00Z"},
            {"url": "https://mid.com", "score": 60, "scanned_at": "2024-01-16T10:00:00Z"},
            {"url": "https://high.com", "score": 90, "scanned_at": "2024-01-17T10:00:00Z"},
        ]

        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.all.return_value = records
            response = client.get("/api/history?filter_score_min=50&filter_score_max=70")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["records"][0]["url"] == "https://mid.com"

    def test_get_history_sort_by_score(self):
        """Test sorting history by score."""
        records = [
            {"url": "https://mid.com", "score": 60, "scanned_at": "2024-01-15T10:00:00Z"},
            {"url": "https://low.com", "score": 30, "scanned_at": "2024-01-16T10:00:00Z"},
            {"url": "https://high.com", "score": 90, "scanned_at": "2024-01-17T10:00:00Z"},
        ]

        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.all.return_value = records
            response = client.get("/api/history?sort_by=score&sort_dir=desc")
            assert response.status_code == 200
            data = response.json()
            assert data["records"][0]["url"] == "https://high.com"
            assert data["records"][2]["url"] == "https://low.com"


class TestCheckHistory:
    """Test GET /api/history/check endpoint."""

    def test_check_existing_url(self):
        """Test checking an existing URL."""
        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.get.return_value = {
                "url": "https://example.com",
                "score": 75,
                "title": "Test Site",
                "scanned_at": "2024-01-15T10:00:00Z",
            }
            response = client.get("/api/history/check?url=https://example.com")
            assert response.status_code == 200
            data = response.json()
            assert data["exists"] is True
            assert data["score"] == 75
            assert data["title"] == "Test Site"

    def test_check_nonexistent_url(self):
        """Test checking a non-existent URL."""
        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.get.return_value = None
            response = client.get("/api/history/check?url=https://notfound.com")
            assert response.status_code == 200
            data = response.json()
            assert data["exists"] is False


class TestGetHistoryEntry:
    """Test GET /api/history/entry endpoint."""

    def test_get_existing_entry(self):
        """Test getting an existing history entry."""
        with patch("backend.routes_history.get_full_scan") as mock_get:
            mock_get.return_value = {
                "url": "https://example.com",
                "score": 75,
                "screenshot_b64": "base64data",
            }
            response = client.get("/api/history/entry?url=https://example.com")
            assert response.status_code == 200
            data = response.json()
            assert data["url"] == "https://example.com"
            assert data["screenshot_b64"] == "base64data"

    def test_get_nonexistent_entry(self):
        """Test getting a non-existent entry."""
        with patch("backend.routes_history.get_full_scan") as mock_get:
            mock_get.return_value = None
            response = client.get("/api/history/entry?url=https://notfound.com")
            assert response.status_code == 404


class TestToggleResponse:
    """Test PATCH /api/history/response endpoint."""

    def test_toggle_response_true_to_false(self):
        """Test toggling response from True to False."""
        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.get.return_value = {
                "url": "https://example.com",
                "email": {"got_response": True},
            }
            response = client.patch("/api/history/response?url=https://example.com")
            assert response.status_code == 200
            data = response.json()
            assert data["got_response"] is False
            mock_db.update.assert_called_once()

    def test_toggle_response_false_to_true(self):
        """Test toggling response from False to True."""
        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.get.return_value = {
                "url": "https://example.com",
                "email": {"got_response": False},
            }
            response = client.patch("/api/history/response?url=https://example.com")
            assert response.status_code == 200
            data = response.json()
            assert data["got_response"] is True

    def test_toggle_response_no_email_record(self):
        """Test toggling when no email record exists."""
        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.get.return_value = {"url": "https://example.com"}
            response = client.patch("/api/history/response?url=https://example.com")
            assert response.status_code == 404


class TestDeleteHistoryEntry:
    """Test DELETE /api/history/entry endpoint."""

    def test_delete_existing_entry(self):
        """Test deleting an existing entry."""
        with patch("backend.routes_history.scans_db") as mock_scans, \
             patch("backend.routes_history.screenshots_db") as mock_screenshots:
            mock_scans.remove.return_value = [1]
            response = client.delete("/api/history/entry?url=https://example.com")
            assert response.status_code == 200
            assert response.json()["ok"] is True
            mock_scans.remove.assert_called_once()
            mock_screenshots.remove.assert_called_once()

    def test_delete_nonexistent_entry(self):
        """Test deleting a non-existent entry."""
        with patch("backend.routes_history.scans_db") as mock_scans:
            mock_scans.remove.return_value = []
            response = client.delete("/api/history/entry?url=https://notfound.com")
            assert response.status_code == 404


class TestSaveEmailDraft:
    """Test POST /api/history/save-email endpoint."""

    def test_save_email_draft_success(self):
        """Test saving an email draft."""
        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.get.return_value = {
                "url": "https://example.com",
                "score": 75,
            }
            response = client.post(
                "/api/history/save-email?url=https://example.com&subject=Test",
                json={"html": "<html>Test</html>"},
            )
            assert response.status_code == 200
            assert response.json()["ok"] is True
            mock_db.update.assert_called_once()

    def test_save_email_draft_no_scan(self):
        """Test saving draft when no scan exists."""
        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.get.return_value = None
            response = client.post(
                "/api/history/save-email?url=https://notfound.com&subject=Test",
                json={"html": "<html>Test</html>"},
            )
            assert response.status_code == 404


class TestUpdateEmailRecipient:
    """Test POST /api/history/update-email-recipient endpoint."""

    def test_update_recipient_success(self):
        """Test updating email recipient."""
        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.get.return_value = {
                "url": "https://example.com",
                "email": {"subject": "Test", "html": "<html></html>"},
            }
            response = client.post(
                "/api/history/update-email-recipient?url=https://example.com&recipient=new@example.com"
            )
            assert response.status_code == 200
            assert response.json()["ok"] is True
            mock_db.update.assert_called_once()

    def test_update_recipient_no_scan(self):
        """Test updating recipient when no scan exists."""
        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.get.return_value = None
            response = client.post(
                "/api/history/update-email-recipient?url=https://notfound.com&recipient=test@example.com"
            )
            assert response.status_code == 200
            assert response.json()["ok"] is False


class TestSaveDeepScan:
    """Test POST /api/history/save-deep-scan endpoint."""

    def test_save_deep_scan_success(self):
        """Test saving a deep scan."""
        with patch("backend.routes_history.upsert_scan") as mock_upsert:
            response = client.post(
                "/api/history/save-deep-scan",
                json={
                    "url": "https://example.com",
                    "score": 80,
                    "scan_mode": "deep",
                },
            )
            assert response.status_code == 200
            assert response.json()["ok"] is True
            mock_upsert.assert_called_once()

    def test_save_deep_scan_error(self):
        """Test saving a deep scan with error."""
        with patch("backend.routes_history.upsert_scan") as mock_upsert:
            mock_upsert.side_effect = Exception("DB Error")
            response = client.post(
                "/api/history/save-deep-scan",
                json={"url": "https://example.com"},
            )
            assert response.status_code == 500


class TestFullCheck:
    """Test GET /api/history/full-check endpoint."""

    def test_full_check_existing(self):
        """Test full check for existing URL."""
        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.get.return_value = {
                "url": "https://example.com",
                "score": 75,
                "email": {"sent_at": "2024-01-15T10:00:00Z"},
            }
            response = client.get("/api/history/full-check?url=https://example.com")
            assert response.status_code == 200
            data = response.json()
            assert data["exists"] is True
            assert data["record"]["url"] == "https://example.com"

    def test_full_check_nonexistent(self):
        """Test full check for non-existent URL."""
        with patch("backend.routes_history.scans_db") as mock_db:
            mock_db.get.return_value = None
            response = client.get("/api/history/full-check?url=https://notfound.com")
            assert response.status_code == 200
            data = response.json()
            assert data["exists"] is False
