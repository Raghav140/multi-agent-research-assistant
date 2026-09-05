"""Tests for report generation optimization.

Tests for:
- Meta-commentary detection
- Post-processing
- Deterministic fallback
- Regeneration limits
- Timeout handling
"""

import pytest
from backend.graph.nodes.report import (
    detect_meta_commentary,
    post_process_report,
    generate_deterministic_fallback,
    validate_report_output,
)


class TestMetaCommentaryDetection:
    """Test meta-commentary detection."""

    def test_detects_we_are_writing(self):
        """Test detection of 'we are writing' pattern."""
        report = "We are writing a markdown report with specific sections."
        has_meta, reason = detect_meta_commentary(report)
        assert has_meta is True
        assert "we are writing" in reason

    def test_detects_the_user_says(self):
        """Test detection of 'the user says' pattern."""
        report = "The user says: Write ONLY a Markdown report."
        has_meta, reason = detect_meta_commentary(report)
        assert has_meta is True
        assert "the user says" in reason

    def test_detects_instructions_colon(self):
        """Test detection of 'instructions:' pattern."""
        report = "Instructions: Write a concise report."
        has_meta, reason = detect_meta_commentary(report)
        assert has_meta is True
        assert "instructions:" in reason

    def test_detects_let_me_think(self):
        """Test detection of 'let me think' pattern."""
        report = "Let me think about how to structure this."
        has_meta, reason = detect_meta_commentary(report)
        assert has_meta is True
        assert "let me think" in reason

    def test_detects_step_by_step(self):
        """Test detection of 'step by step' pattern."""
        report = "Step by step: First, I will analyze the sources."
        has_meta, reason = detect_meta_commentary(report)
        assert has_meta is True
        assert "step by step" in reason

    def test_valid_report_passes(self):
        """Test that valid report passes meta-commentary detection."""
        report = """## Executive Summary

This is a valid report about artificial intelligence.

## Key Findings

- AI is a field of computer science
- Machine learning is a subset of AI

## Detailed Analysis

Artificial intelligence involves creating systems that can perform tasks requiring human intelligence.

## Evidence

Based on the retrieved sources, AI has evolved significantly.

## References

[1] Wikipedia"""
        has_meta, reason = detect_meta_commentary(report)
        assert has_meta is False
        assert reason == ""

    def test_empty_report_fails(self):
        """Test that empty report fails."""
        report = ""
        has_meta, reason = detect_meta_commentary(report)
        assert has_meta is True
        assert "empty" in reason.lower()

    def test_short_report_fails(self):
        """Test that very short report fails."""
        report = "AI"
        has_meta, reason = detect_meta_commentary(report)
        assert has_meta is True
        assert "too short" in reason.lower()

    def test_meta_commentary_in_first_200_chars(self):
        """Test that detection only checks first 200 characters."""
        # Create a report where "We are writing" is definitely after 200 characters
        report = "## Executive Summary\n\n" + "Valid content. " * 30 + "\n\nWe are writing a report."
        has_meta, reason = detect_meta_commentary(report)
        assert has_meta is False  # "We are writing" is after first 200 chars


class TestPostProcessing:
    """Test report post-processing."""

    def test_strips_leading_whitespace(self):
        """Test stripping leading whitespace."""
        report = "   \n\n## Executive Summary\n\nContent"
        processed = post_process_report(report)
        assert processed.startswith("## Executive Summary")
        assert not processed.startswith(" ")

    def test_strips_trailing_whitespace(self):
        """Test stripping trailing whitespace."""
        report = "## Executive Summary\n\nContent\n\n   "
        processed = post_process_report(report)
        assert processed.endswith("Content")
        assert not processed.endswith(" ")

    def test_removes_markdown_fences(self):
        """Test removal of markdown code fences."""
        report = "```\n## Executive Summary\n\nContent\n```"
        processed = post_process_report(report)
        assert not processed.startswith("```")
        assert not processed.endswith("```")
        assert processed.startswith("## Executive Summary")

    def test_locates_executive_summary(self):
        """Test locating Executive Summary when preceded by intro."""
        report = "Here is the report:\n\n## Executive Summary\n\nContent"
        processed = post_process_report(report)
        assert processed.startswith("## Executive Summary")

    def test_normalizes_duplicated_blank_lines(self):
        """Test normalization of duplicated blank lines."""
        report = "## Executive Summary\n\n\n\n\nContent"
        processed = post_process_report(report)
        assert "\n\n\n\n" not in processed
        assert "\n\n" in processed

    def test_preserves_valid_report(self):
        """Test that valid report is preserved."""
        report = """## Executive Summary

This is a valid report.

## Key Findings

- Finding 1
- Finding 2

## Detailed Analysis

Detailed content here.

## Evidence

Evidence here.

## References

[1] Source"""
        processed = post_process_report(report)
        assert processed == report

    def test_handles_none(self):
        """Test handling of None input."""
        processed = post_process_report(None)
        assert processed is None

    def test_handles_empty_string(self):
        """Test handling of empty string."""
        processed = post_process_report("")
        assert processed == ""


class TestDeterministicFallback:
    """Test deterministic fallback generation."""

    def test_generates_fallback_with_sources(self):
        """Test fallback generation with sources."""
        user_query = "What is artificial intelligence?"
        search_results = [
            {
                "title": "Artificial Intelligence - Wikipedia",
                "snippet": "AI is the capability of computational systems to perform tasks typically associated with human intelligence.",
                "url": "https://en.wikipedia.org/wiki/AI",
            }
        ]
        research_papers = []

        fallback = generate_deterministic_fallback(user_query, search_results, research_papers)

        assert "## Executive Summary" in fallback
        assert "## Key Findings" in fallback
        assert "## Detailed Analysis" in fallback
        assert "## Evidence" in fallback
        assert "## References" in fallback
        assert user_query in fallback
        assert "Artificial Intelligence - Wikipedia" in fallback
        assert "[1]" in fallback

    def test_generates_fallback_with_papers(self):
        """Test fallback generation with papers."""
        user_query = "What is machine learning?"
        search_results = []
        research_papers = [
            {
                "title": "Machine Learning Paper",
                "abstract": "This paper discusses machine learning algorithms.",
                "pdf_url": "https://arxiv.org/pdf/1234.pdf",
            }
        ]

        fallback = generate_deterministic_fallback(user_query, search_results, research_papers)

        assert "## Executive Summary" in fallback
        assert "Machine Learning Paper" in fallback
        assert "[1]" in fallback
        assert "arxiv.org" in fallback

    def test_handles_no_sources(self):
        """Test fallback with no sources."""
        user_query = "What is quantum computing?"
        search_results = []
        research_papers = []

        fallback = generate_deterministic_fallback(user_query, search_results, research_papers)

        assert "## Executive Summary" in fallback
        assert "No sources were retrieved" in fallback
        assert "No sources available" in fallback

    def test_limits_to_top_5_sources(self):
        """Test that fallback limits to top 5 sources."""
        user_query = "Test query"
        search_results = [
            {"title": f"Source {i}", "snippet": f"Snippet {i}", "url": f"https://example.com/{i}"}
            for i in range(1, 10)
        ]
        research_papers = []

        fallback = generate_deterministic_fallback(user_query, search_results, research_papers)

        # Should only have references 1-5
        assert "[6]" not in fallback
        assert "[5]" in fallback

    def test_preserves_citations(self):
        """Test that citations are preserved."""
        user_query = "Test query"
        search_results = [
            {"title": "Source 1", "snippet": "Snippet 1", "url": "https://example.com/1"},
            {"title": "Source 2", "snippet": "Snippet 2", "url": "https://example.com/2"},
        ]
        research_papers = []

        fallback = generate_deterministic_fallback(user_query, search_results, research_papers)

        assert "[1]" in fallback
        assert "[2]" in fallback
        assert "Source 1 [1]" in fallback or "Source 1" in fallback


class TestReportValidation:
    """Test report validation with new functions."""

    def test_valid_report_passes(self):
        """Test that valid report passes validation."""
        report = """## Executive Summary

This is a valid report.

## Key Findings

- Finding 1

## Detailed Analysis

Analysis here.

## Evidence

Evidence here.

## References

[1] Source"""
        is_valid, reason = validate_report_output(report)
        assert is_valid is True
        assert reason == "Validation passed"

    def test_meta_commentary_fails(self):
        """Test that meta-commentary fails validation."""
        report = """We are writing a markdown report.

## Executive Summary

Content"""
        is_valid, reason = validate_report_output(report)
        assert is_valid is False
        # Meta-commentary is now caught by the "does not start with Executive Summary" check
        assert "Executive Summary" in reason

    def test_missing_executive_summary_fails(self):
        """Test that missing Executive Summary fails."""
        report = """## Key Findings

Content"""
        is_valid, reason = validate_report_output(report)
        assert is_valid is False
        assert "Executive Summary" in reason

    def test_missing_required_section_fails(self):
        """Test that missing required section fails."""
        report = """## Executive Summary

Content"""
        is_valid, reason = validate_report_output(report)
        assert is_valid is False
        assert "Missing required section" in reason


class TestIntegration:
    """Integration tests for report generation pipeline."""

    def test_meta_commentary_then_post_processing(self):
        """Test meta-commentary detection followed by post-processing."""
        meta_report = "We are writing a report.\n\n## Executive Summary\n\nContent"

        # First detect meta-commentary
        has_meta, _ = detect_meta_commentary(meta_report)
        assert has_meta is True

        # Post-processing removes the meta-commentary intro
        processed = post_process_report(meta_report)
        # After post-processing, it should start with Executive Summary
        assert processed.startswith("## Executive Summary")
        # And should no longer be detected as meta-commentary
        has_meta_after, _ = detect_meta_commentary(processed)
        assert has_meta_after is False

    def test_post_processing_then_validation(self):
        """Test post-processing followed by validation."""
        report_with_intro = "Here is the report:\n\n## Executive Summary\n\nContent\n\n## Key Findings\n\n- Finding\n\n## Detailed Analysis\n\nAnalysis\n\n## Evidence\n\nEvidence\n\n## References\n\n[1] Source"

        # Post-process to remove intro
        processed = post_process_report(report_with_intro)

        # Should now pass validation
        is_valid, reason = validate_report_output(processed)
        assert is_valid is True

    def test_fallback_structure(self):
        """Test that fallback has correct structure."""
        user_query = "Test query"
        search_results = [
            {"title": "Test Source", "snippet": "Test snippet", "url": "https://example.com"}
        ]

        fallback = generate_deterministic_fallback(user_query, search_results, [])

        # Validate structure
        is_valid, reason = validate_report_output(fallback)
        assert is_valid is True, f"Fallback validation failed: {reason}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
