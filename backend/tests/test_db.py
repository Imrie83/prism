"""
Tests for backend.db module.
"""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from backend.db import (
    upsert_scan,
    update_email,
    get_full_scan,
    migrate_legacy_db,
    scans_db,
    screenshots_db,
    ScanRecord,
)


class TestUpsertScan:
    """Test upsert_scan function."""

    def test_upsert_new_scan(self, mock_tinydb):
        """Test upserting a new scan record."""
        mock_db, records = mock_tinydb
        with patch("backend.db.scans_db", mock_db):
            data = {
                "url": "https://example.com",
                "score": 70,
                "title": "Test Site",
                "summary": "A test site",
                "totalIssues": 5,
                "issueCounts": {"high": 1, "medium": 2, "low": 2},
                "issues": [],
                "scan_mode": "shallow",
                "screenshot": "base64data",
                "emails_found": ["test@example.com"],
            }
            upsert_scan(data)

            # Check scan record was created
            assert len(records) == 1
            assert records[0]["url"] == "https://example.com"
            assert records[0]["score"] == 70
            assert "scanned_at" in records[0]

    def test_upsert_existing_scan(self, mock_tinydb):
        """Test updating an existing scan record."""
        mock_db, records = mock_tinydb

        # Pre-populate with existing record
        existing = {
            "url": "https://example.com",
            "score": 50,
            "title": "Old Title",
            "emails_found": [],
            "email": {"recipient": "old@example.com"},
        }
        records.append(existing)

        with patch("backend.db.scans_db", mock_db):
            data = {
                "url": "https://example.com",
                "score": 75,
                "title": "New Title",
                "summary": "Updated",
                "totalIssues": 3,
                "issueCounts": {"high": 0, "medium": 1, "low": 2},
                "issues": [],
                "scan_mode": "shallow",
                "screenshot": "newbase64",
                "emails_found": ["new@example.com"],
            }
            upsert_scan(data)

            # Should update existing, not create new
            assert len(records) == 1
            assert records[0]["score"] == 75
            assert records[0]["title"] == "New Title"
            # Should preserve existing email block
            assert records[0]["email"]["recipient"] == "old@example.com"

    def test_upsert_without_url(self, mock_tinydb):
        """Test upsert with missing URL."""
        mock_db, records = mock_tinydb
        with patch("backend.db.scans_db", mock_db):
            data = {
                "score": 70,
                "title": "Test",
            }
            upsert_scan(data)
            # Should not insert without URL
            assert len(records) == 0


class TestUpdateEmail:
    """Test update_email function."""

    def test_update_email_existing_record(self, mock_tinydb):
        """Test updating email on existing scan."""
        mock_db, records = mock_tinydb

        # Pre-populate
        records.append({
            "url": "https://example.com",
            "score": 70,
            "emails_found": [],
        })

        with patch("backend.db.scans_db", mock_db):
            update_email(
                url="https://example.com",
                recipient="test@example.com",
                subject="Test Subject",
                html="<html>Test</html>",
            )

            assert len(records) == 1
            assert records[0]["email"]["recipient"] == "test@example.com"
            assert records[0]["email"]["subject"] == "Test Subject"
            assert "sent_at" in records[0]["email"]

    def test_update_email_missing_record(self, mock_tinydb):
        """Test updating email when no scan record exists."""
        mock_db, records = mock_tinydb
        with patch("backend.db.scans_db", mock_db), \
             patch("builtins.print") as mock_print:
            update_email(
                url="https://notfound.com",
                recipient="test@example.com",
                subject="Test",
                html="<html>Test</html>",
            )
            # Should print warning
            assert any("no scan record" in str(call).lower() for call in mock_print.call_args_list)

    def test_update_email_preserves_response(self, mock_tinydb):
        """Test that got_response is preserved when updating email."""
        mock_db, records = mock_tinydb

        records.append({
            "url": "https://example.com",
            "score": 70,
            "emails_found": [],
            "email": {
                "recipient": "old@example.com",
                "got_response": True,
            },
        })

        with patch("backend.db.scans_db", mock_db):
            update_email(
                url="https://example.com",
                recipient="new@example.com",
                subject="New Subject",
                html="<html>New</html>",
            )

            # Should preserve got_response
            assert records[0]["email"]["got_response"] is True


class TestGetFullScan:
    """Test get_full_scan function."""

    def test_get_existing_scan(self, mock_tinydb):
        """Test retrieving a full scan with screenshot."""
        mock_scans = mock_tinydb[0]
        mock_screenshots = MagicMock()
        mock_screenshots.get.return_value = {"screenshot_b64": "base64data"}

        # Pre-populate scans
        mock_scans._records = [{
            "url": "https://example.com",
            "score": 70,
            "title": "Test",
        }]

        with patch("backend.db.scans_db", mock_scans), \
             patch("backend.db.screenshots_db", mock_screenshots):
            result = get_full_scan("https://example.com")
            assert result is not None
            assert result["score"] == 70
            assert result["screenshot_b64"] == "base64data"

    def test_get_nonexistent_scan(self, mock_tinydb):
        """Test retrieving a scan that doesn't exist."""
        mock_db = mock_tinydb[0]
        mock_db.get.return_value = None

        with patch("backend.db.scans_db", mock_db):
            result = get_full_scan("https://notfound.com")
            assert result is None


class TestMigrateLegacyDb:
    """Test migrate_legacy_db function."""

    def test_no_legacy_db(self):
        """Test migration when no legacy db exists."""
        with patch("os.path.exists", return_value=False):
            with patch("builtins.print") as mock_print:
                migrate_legacy_db()
                # Should return early without doing anything
                assert not any("migrating" in str(call).lower() for call in mock_print.call_args_list)

    def test_migrate_records(self):
        """Test migrating records from legacy db."""
        legacy_records = [
            {
                "url": "https://example.com",
                "score": 70,
                "screenshot_b64": "base64data",
            },
            {
                "url": "https://example2.com",
                "score": 80,
                "screenshot_b64": "base64data2",
            },
        ]

        mock_legacy_db = MagicMock()
        mock_legacy_db.all.return_value = legacy_records
        mock_legacy_db.close = MagicMock()

        mock_scans = MagicMock()
        mock_screenshots = MagicMock()

        with patch("os.path.exists", return_value=True), \
             patch("backend.db.TinyDB") as mock_tinydb, \
             patch("backend.db.scans_db", mock_scans), \
             patch("backend.db.screenshots_db", mock_screenshots), \
             patch("os.rename") as mock_rename, \
             patch("builtins.print"):

            # First call creates legacy db, subsequent calls are for scans/screenshots
            mock_tinydb.side_effect = [mock_legacy_db, mock_scans, mock_screenshots]

            migrate_legacy_db()

            # Should have upserted to scans and screenshots
            assert mock_scans.upsert.call_count == 2
            assert mock_screenshots.upsert.call_count == 2
            # Should rename legacy db
            assert mock_rename.called

    def test_migrate_skip_no_url(self):
        """Test migration skips records without URL."""
        legacy_records = [
            {
                "url": "",
                "score": 70,
            },
            {
                "url": "https://example.com",
                "score": 80,
            },
        ]

        mock_legacy_db = MagicMock()
        mock_legacy_db.all.return_value = legacy_records
        mock_legacy_db.close = MagicMock()

        mock_scans = MagicMock()
        mock_screenshots = MagicMock()

        with patch("os.path.exists", return_value=True), \
             patch("backend.db.TinyDB") as mock_tinydb, \
             patch("backend.db.scans_db", mock_scans), \
             patch("backend.db.screenshots_db", mock_screenshots), \
             patch("os.rename"), \
             patch("builtins.print"):

            mock_tinydb.side_effect = [mock_legacy_db, mock_scans, mock_screenshots]
            migrate_legacy_db()

            # Should only process 1 record (the one with URL)
            assert mock_scans.upsert.call_count == 1
