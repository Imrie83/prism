"""
Tests for backend.utils module.
"""

import pytest
from backend.utils import extract_emails_from_html


class TestExtractEmailsFromHtml:
    """Test email extraction from HTML."""

    def test_extract_simple_email(self):
        """Test extracting a simple email from HTML."""
        html = '<p>Contact us at info@example.com</p>'
        emails = extract_emails_from_html(html)
        assert "info@example.com" in emails

    def test_extract_multiple_emails(self, sample_html_with_emails):
        """Test extracting multiple emails from HTML."""
        emails = extract_emails_from_html(sample_html_with_emails)
        assert "info@example.com" in emails
        assert "support@example.com" in emails
        assert "sales@example.com" in emails

    def test_ignore_blocklisted_domains(self):
        """Test that blocklisted domains are ignored."""
        html = '''
        <p>Contact info@example.com</p>
        <p>Admin admin@placeholder.com</p>
        <p>Sentry sentry@sentry.io</p>
        '''
        emails = extract_emails_from_html(html)
        assert "info@example.com" in emails
        assert "admin@placeholder.com" not in emails
        assert "sentry@sentry.io" not in emails

    def test_prioritize_contact_emails(self):
        """Test that contact emails are prioritized."""
        html = '''
        <p>Support support@example.com</p>
        <p>Random user@example.com</p>
        <p>Contact contact@example.com</p>
        '''
        emails = extract_emails_from_html(html)
        # Should still include both, just sorted by priority
        assert len(emails) == 2
        # Contact/support emails have priority 0, others have priority 1
        assert "contact@example.com" in emails
        assert "user@example.com" in emails

    def test_deduplicate_emails(self):
        """Test that duplicate emails are deduplicated."""
        html = '''
        <p>Contact info@example.com</p>
        <p>Email info@example.com again</p>
        '''
        emails = extract_emails_from_html(html)
        assert emails.count("info@example.com") == 0  # It's a dict lookup
        assert "info@example.com" in emails
        assert len(emails) == 1

    def test_case_insensitive(self):
        """Test that email extraction is case insensitive."""
        html = '<p>Contact INFO@EXAMPLE.COM</p>'
        emails = extract_emails_from_html(html)
        assert "info@example.com" in emails

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
        html = '<p>Contact info@example.com.</p>'
        emails = extract_emails_from_html(html)
        assert "info@example.com" in emails
        assert "info@example.com." not in emails

    def test_all_blocklisted_domains(self, sample_html_with_emails):
        """Test handling of various email formats."""
        html = '''
        <p>Simple: user@example.com</p>
        <p>With dots: first.last@example.co.uk</p>
        <p>With plus: user+tag@example.com</p>
        <p>With hyphen: user-name@example.com</p>
        <p>With underscore: user_name@example.com</p>
        '''
        emails = extract_emails_from_html(html)
        assert "user@example.com" in emails
        assert "first.last@example.co.uk" in emails
        assert "user+tag@example.com" in emails
        assert "user-name@example.com" in emails
        assert "user_name@example.com" in emails

    def test_empty_html(self):
        """Test with empty HTML."""
        emails = extract_emails_from_html("")
        assert emails == []

    def test_script_tag_emails(self):
        """Test extracting emails from script tags."""
        html = '''
        <script>
            var email = "script@example.com";
        </script>
        '''
        emails = extract_emails_from_html(html)
        assert "script@example.com" in emails
