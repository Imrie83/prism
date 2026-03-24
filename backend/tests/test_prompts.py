"""
Tests for backend.prompts module.
"""

import pytest
from backend.prompts import (
    PromptBuilder,
    build_audit_system_prompt,
    build_audit_user_prompt,
    _extract_json,
    _repair_json,
    AGENT_SYSTEM,
    EMAIL_SYSTEM,
)


class TestPromptBuilder:
    """Test PromptBuilder class."""

    def test_empty_builder(self):
        """Test empty builder."""
        builder = PromptBuilder()
        assert builder.build() == ""

    def test_single_block(self):
        """Test adding a single block."""
        builder = PromptBuilder()
        builder.set("intro", "This is the introduction.")
        assert builder.build() == "This is the introduction."

    def test_multiple_blocks(self):
        """Test adding multiple blocks."""
        builder = PromptBuilder()
        builder.set("intro", "Introduction.")
        builder.set("body", "Body text.")
        result = builder.build()
        assert "Introduction." in result
        assert "Body text." in result
        # Should be separated by double newlines
        assert "\n\n" in result

    def test_block_replacement(self):
        """Test replacing an existing block."""
        builder = PromptBuilder()
        builder.set("block", "Original")
        builder.set("block", "Updated")
        assert builder.build() == "Updated"

    def test_formatted_block(self):
        """Test block with format parameters."""
        builder = PromptBuilder()
        builder.set("template", "Hello {name}!")
        result = builder.build(name="World")
        assert result == "Hello World!"


class TestBuildAuditSystemPrompt:
    """Test build_audit_system_prompt function."""

    def test_shallow_mode_prompt(self):
        """Test prompt for shallow scan mode."""
        prompt = build_audit_system_prompt(vision_mode=False, scan_mode="shallow")
        # Should include role description
        assert "expert" in prompt.lower() or "localisation" in prompt.lower()
        # Should include scoring guidelines
        assert "SCORING" in prompt
        # Should include issue format
        assert "issue" in prompt.lower()

    def test_deep_mode_prompt(self):
        """Test prompt for deep scan mode."""
        prompt = build_audit_system_prompt(vision_mode=False, scan_mode="deep")
        # Deep mode should have different language instruction
        assert "English" in prompt
        # Should still have core sections
        assert "SCORING" in prompt

    def test_vision_mode_prompt(self):
        """Test prompt for vision mode."""
        prompt = build_audit_system_prompt(vision_mode=True, scan_mode="shallow")
        # Should reference screenshots
        assert "screenshot" in prompt.lower() or "visual" in prompt.lower()


class TestBuildAuditUserPrompt:
    """Test build_audit_user_prompt function."""

    def test_vision_mode_skips_html(self):
        """Test that vision mode skips HTML extraction."""
        html = "<html><body>Test</body></html>"
        prompt = build_audit_user_prompt(html, vision_mode=True)
        # Vision mode should not include semantic groups
        assert "Semantic page structure" not in prompt
        assert "screenshot" in prompt.lower() or "visual" in prompt.lower()

    def test_standard_mode_includes_semantic(self):
        """Test that standard mode includes semantic extraction."""
        html = "<!DOCTYPE html><html><head><title>Test</title></head><body><h1>Heading</h1></body></html>"
        prompt = build_audit_user_prompt(html, vision_mode=False)
        assert "Semantic page structure" in prompt
        assert "PAGE SEMANTIC STRUCTURE" in prompt or "PAGE" in prompt


class TestAgentSystemPrompt:
    """Test AGENT_SYSTEM constant."""

    def test_agent_system_exists(self):
        """Test that AGENT_SYSTEM prompt exists."""
        assert AGENT_SYSTEM is not None
        assert len(AGENT_SYSTEM) > 0

    def test_agent_system_includes_context(self):
        """Test that AGENT_SYSTEM includes context placeholder."""
        assert "{context}" in AGENT_SYSTEM


class TestEmailSystemPrompt:
    """Test EMAIL_SYSTEM constant."""

    def test_email_system_exists(self):
        """Test that EMAIL_SYSTEM prompt exists."""
        assert EMAIL_SYSTEM is not None
        assert len(EMAIL_SYSTEM) > 0

    def test_email_system_includes_placeholders(self):
        """Test that EMAIL_SYSTEM includes all required placeholders."""
        required_placeholders = ["{name}", "{title}", "{email}", "{website}"]
        for placeholder in required_placeholders:
            assert placeholder in EMAIL_SYSTEM, f"Missing placeholder: {placeholder}"

    def test_email_system_structure(self):
        """Test that EMAIL_SYSTEM has required sections."""
        assert "SENDER" in EMAIL_SYSTEM
        assert "SERVICES" in EMAIL_SYSTEM
        assert "STRUCTURE" in EMAIL_SYSTEM
        assert "JSON" in EMAIL_SYSTEM


class TestPromptDimensions:
    """Test audit prompt dimensions."""

    def test_text_dimensions_present(self):
        """Test that text dimensions are included."""
        prompt = build_audit_system_prompt(vision_mode=False, scan_mode="shallow")
        text_issues = [
            "untranslated_nav_ui",
            "untranslated_body",
            "machine_translation",
            "grammar_error",
            "awkward_phrasing",
        ]
        for issue in text_issues:
            assert issue in prompt.lower() or issue.replace("_", " ") in prompt.lower()

    def test_visual_dimensions_present(self):
        """Test that visual dimensions are included."""
        prompt = build_audit_system_prompt(vision_mode=False, scan_mode="shallow")
        visual_issues = [
            "visual_hierarchy",
            "poor_contrast",
            "cluttered_layout",
            "colour_psychology",
        ]
        for issue in visual_issues:
            assert issue in prompt.lower() or issue.replace("_", " ") in prompt.lower()

    def test_ux_dimensions_present(self):
        """Test that UX dimensions are included."""
        prompt = build_audit_system_prompt(vision_mode=False, scan_mode="shallow")
        ux_issues = [
            "navigation_ux",
            "social_proof",
            "contact_accessibility",
            "trust_signals",
        ]
        for issue in ux_issues:
            assert issue in prompt.lower() or issue.replace("_", " ") in prompt.lower()


class TestSeverityGuidance:
    """Test severity guidance in prompts."""

    def test_severity_balance_guidance(self):
        """Test that severity balance guidance exists."""
        prompt = build_audit_system_prompt(vision_mode=False, scan_mode="shallow")
        assert "High:" in prompt or "SEVERITY" in prompt
        assert "Medium:" in prompt or "severity" in prompt.lower()
        assert "Low:" in prompt or "low" in prompt.lower()

    def test_severity_by_category(self):
        """Test severity guidance by category."""
        prompt = build_audit_system_prompt(vision_mode=False, scan_mode="shallow")
        # Should mention that some issues are usually high/medium/low
        assert "usually" in prompt.lower() or "typically" in prompt.lower()


class TestJsonOutputFormat:
    """Test JSON output format specification."""

    def test_json_structure_defined(self):
        """Test that JSON structure is defined."""
        prompt = build_audit_system_prompt(vision_mode=False, scan_mode="shallow")
        # Should include JSON format
        assert '"score"' in prompt or "score" in prompt.lower()
        assert '"summary"' in prompt or "summary" in prompt.lower()
        assert '"issues"' in prompt or "issues" in prompt.lower()

    def test_issue_format_fields(self):
        """Test that issue format fields are specified."""
        prompt = build_audit_system_prompt(vision_mode=False, scan_mode="shallow")
        required_fields = ["type", "severity", "location", "suggestion", "explanation"]
        for field in required_fields:
            assert field in prompt.lower(), f"Missing field: {field}"
