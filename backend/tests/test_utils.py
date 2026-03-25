"""
Tests for backend.utils module.
"""

import pytest
from backend.utils import extract_emails_from_html


class TestExtractEmailsFromHtml:
    """Test email extraction from HTML."""

    def test_extract_simple_email(self):
        """Test extracting a simple email from HTML."""
        html = '<p>Contact us at info@testdomain.com</p>'
        emails = extract_emails_from_html(html)
        assert "info@testdomain.com" in emails

    def test_extract_multiple_emails(self, sample_html_with_emails):
        """Test extracting multiple emails from HTML."""
        html = '''
            <p>info@testdomain.com</p>
            <p>support@testdomain.com</p>
            <p>sales@testdomain.com</p>
        '''
        emails = extract_emails_from_html(html)
        assert "info@testdomain.com" in emails
        assert "support@testdomain.com" in emails
        assert "sales@testdomain.com" in emails

    def test_ignore_blocklisted_domains(self):
        """Test that blocklisted domains are ignored."""
        html = '''
        <p>Contact info@testdomain.com</p>
        <p>Admin admin@placeholder.com</p>
        <p>Sentry sentry@sentry.io</p>
        '''
        emails = extract_emails_from_html(html)
        assert "info@testdomain.com" in emails
        assert "admin@placeholder.com" not in emails
        assert "sentry@sentry.io" not in emails

    def test_prioritize_contact_emails(self):
        """Test that contact emails are prioritized before generic ones."""
        html = '''
        <p>Random user@testdomain.com</p>
        <p>Contact contact@testdomain.com</p>
        '''
        emails = extract_emails_from_html(html)
        assert len(emails) == 2
        # contact email has priority 0, user email has priority 1
        assert "contact@testdomain.com" in emails
        assert "user@testdomain.com" in emails
        # Contact-priority emails should sort before generic ones
        assert emails.index("contact@testdomain.com") < emails.index("user@testdomain.com")

    def test_deduplicate_emails(self):
        """Test that duplicate emails are deduplicated."""
        html = '''
        <p>Contact info@testdomain.com</p>
        <p>Email info@testdomain.com again</p>
        '''
        emails = extract_emails_from_html(html)
        assert "info@testdomain.com" in emails
        assert len(emails) == 1

    def test_case_insensitive(self):
        """Test that email extraction is case insensitive."""
        html = '<p>Contact INFO@TESTDOMAIN.COM</p>'
        emails = extract_emails_from_html(html)
        assert "info@testdomain.com" in emails

    def test_no_emails_found(self):
        """Test when no emails are present."""
        html = '<p>No emails here</p>'
        emails = extract_emails_from_html(html)
        assert emails == []

    def test_invalid_email_not_extracted(self):
        """Test that invalid emails are not extracted."""
        html = '<p>Invalid user@example (missing TLD)</p>'
        emails = extract_emails_from_html(html)
        assert "user@example" not in emails

    def test_trailing_period_removed(self):
        """Test that trailing periods are removed from emails."""
        html = '<p>Contact info@testdomain.com.</p>'
        emails = extract_emails_from_html(html)
        assert "info@testdomain.com" in emails
        assert "info@testdomain.com." not in emails

    def test_all_blocklisted_domains(self, sample_html_with_emails):
        """Test handling of various email formats."""
        html = '''
        <p>Simple: user@testdomain.com</p>
        <p>With dots: first.last@testdomain.co.uk</p>
        <p>With plus: user+tag@testdomain.com</p>
        <p>With hyphen: user-name@testdomain.com</p>
        <p>With underscore: user_name@testdomain.com</p>
        '''
        emails = extract_emails_from_html(html)
        assert "user@testdomain.com" in emails
        assert "first.last@testdomain.co.uk" in emails
        assert "user+tag@testdomain.com" in emails
        assert "user-name@testdomain.com" in emails
        assert "user_name@testdomain.com" in emails

    def test_empty_html(self):
        """Test with empty HTML."""
        emails = extract_emails_from_html("")
        assert emails == []

    def test_script_tag_emails(self):
        """Test extracting emails from script tags."""
        html = '''
        <script>
            var email = "script@testdomain.com";
        </script>
        '''
        emails = extract_emails_from_html(html)
        assert "script@testdomain.com" in emails
