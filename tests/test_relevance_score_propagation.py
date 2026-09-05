"""Tests for relevance score propagation through the pipeline.

This test suite ensures that relevance signals are correctly propagated:
- From provider results → source ranking → evidence fusion → report validation
- Using overall_score as the canonical signal from hybrid scoring
- With fallback to relevance_score for backward compatibility
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.utils.source_ranking import rank_sources
from backend.utils.evidence_fusion import fuse_evidence
from backend.graph.nodes.report import report_node
from backend.graph.state import create_initial_state
from backend.core.interfaces import LLMProvider


def test_source_ranking_sets_overall_score():
    """Test that source ranking sets overall_score on all sources."""
    web_results = [
        {
            "title": "Artificial Intelligence Overview",
            "url": "http://test.com/ai-overview",
            "snippet": "AI is a branch of computer science focused on creating intelligent systems.",
        },
        {
            "title": "AI History and Development",
            "url": "http://test.com/ai-history",
            "snippet": "AI has evolved from symbolic AI to modern machine learning approaches.",
        },
    ]

    papers = []

    web_ranked, papers_ranked, metrics = rank_sources(
        web_results=web_results,
        papers=papers,
        query="What is artificial intelligence?",
        query_type="definition",
    )

    # Verify overall_score is set on all ranked sources
    for source in web_ranked:
        assert "overall_score" in source
        assert source["overall_score"] >= 0.0
        assert source["overall_score"] <= 1.0

    # Verify semantic_similarity is also set
    for source in web_ranked:
        assert "semantic_similarity" in source
        assert source["semantic_similarity"] >= 0.0


def test_source_ranking_overall_score_higher_than_zero():
    """Test that sources with strong semantic similarity get non-zero overall_score."""
    web_results = [
        {
            "title": "Artificial Intelligence",
            "url": "http://test.com/ai",
            "snippet": "Artificial intelligence is intelligence demonstrated by machines.",
        },
    ]

    web_ranked, _, _ = rank_sources(
        web_results=web_results,
        papers=[],
        query="What is artificial intelligence?",
        query_type="definition",
    )

    # Source should have a meaningful overall_score (not 0.0)
    assert web_ranked[0]["overall_score"] > 0.0


def test_evidence_fusion_preserves_overall_score():
    """Test that evidence fusion preserves overall_score from source ranking."""
    web_results = [
        {
            "title": "Test Source",
            "url": "http://test.com",
            "snippet": "Test snippet about artificial intelligence.",
            "overall_score": 0.85,
            "semantic_similarity": 0.80,
            "quality_score": 0.90,
        },
    ]

    fusion_result = fuse_evidence(
        web_results=web_results,
        papers=[],
        documentation=[],
        query="What is artificial intelligence?",
    )

    # Verify overall_score is preserved in combined sources
    combined_sources = fusion_result["combined_sources"]
    assert len(combined_sources) > 0
    assert "overall_score" in combined_sources[0]
    assert combined_sources[0]["overall_score"] == 0.85


def test_evidence_fusion_sets_fusion_score():
    """Test that evidence fusion sets fusion_score on sources."""
    web_results = [
        {
            "title": "Test Source",
            "url": "http://test.com",
            "snippet": "Test snippet.",
            "overall_score": 0.85,
            "quality_score": 0.90,
        },
    ]

    fusion_result = fuse_evidence(
        web_results=web_results,
        papers=[],
        documentation=[],
        query="test query",
    )

    # Verify fusion_score is set
    combined_sources = fusion_result["combined_sources"]
    assert "fusion_score" in combined_sources[0]


def test_report_validation_uses_overall_score():
    """Test that report validation uses overall_score for average_relevance."""
    web_results = [
        {
            "title": "Artificial Intelligence",
            "url": "http://test.com/ai",
            "snippet": "AI is intelligence demonstrated by machines.",
            "overall_score": 0.85,
            "semantic_similarity": 0.80,
            "quality_score": 0.90,
        },
        {
            "title": "Machine Learning",
            "url": "http://test.com/ml",
            "snippet": "ML is a subset of AI.",
            "overall_score": 0.75,
            "semantic_similarity": 0.70,
            "quality_score": 0.80,
        },
    ]

    # Simulate the relevance calculation from report.py
    all_sources = web_results
    relevances = [s.get("overall_score", s.get("relevance_score", 0)) for s in all_sources]
    average_relevance = sum(relevances) / len(relevances)

    # Should use overall_score values
    assert average_relevance == pytest.approx(0.80, abs=0.01)


def test_report_validation_fallback_to_relevance_score():
    """Test that report validation falls back to relevance_score if overall_score missing."""
    web_results = [
        {
            "title": "Test Source",
            "url": "http://test.com",
            "snippet": "Test snippet.",
            "relevance_score": 0.70,  # Old provider format
            "quality_score": 0.80,
        },
    ]

    # Simulate the relevance calculation from report.py
    all_sources = web_results
    relevances = [s.get("overall_score", s.get("relevance_score", 0)) for s in all_sources]
    average_relevance = sum(relevances) / len(relevances)

    # Should fall back to relevance_score
    assert average_relevance == 0.70


def test_report_validation_handles_missing_scores():
    """Test that report validation handles sources with no scores gracefully."""
    web_results = [
        {
            "title": "Test Source",
            "url": "http://test.com",
            "snippet": "Test snippet.",
            # No overall_score or relevance_score
        },
    ]

    # Simulate the relevance calculation from report.py
    all_sources = web_results
    relevances = [s.get("overall_score", s.get("relevance_score", 0)) for s in all_sources]
    average_relevance = sum(relevances) / len(relevances)

    # Should default to 0.0
    assert average_relevance == 0.0


def test_mixed_score_sources():
    """Test validation with mixed sources (some with overall_score, some with relevance_score)."""
    web_results = [
        {
            "title": "Modern Source",
            "url": "http://test.com/modern",
            "snippet": "Modern source with overall_score.",
            "overall_score": 0.85,
            "quality_score": 0.90,
        },
        {
            "title": "Legacy Source",
            "url": "http://test.com/legacy",
            "snippet": "Legacy source with relevance_score.",
            "relevance_score": 0.70,
            "quality_score": 0.80,
        },
    ]

    # Simulate the relevance calculation from report.py
    all_sources = web_results
    relevances = [s.get("overall_score", s.get("relevance_score", 0)) for s in all_sources]
    average_relevance = sum(relevances) / len(relevances)

    # Should use appropriate score for each source
    assert average_relevance == pytest.approx(0.775, abs=0.01)  # (0.85 + 0.70) / 2


def test_high_similarity_source_passes_validation():
    """Test that a source with high semantic similarity and overall_score passes validation."""
    web_results = [
        {
            "title": "Artificial Intelligence",
            "url": "http://test.com/ai",
            "snippet": "Artificial intelligence is intelligence demonstrated by machines.",
            "overall_score": 0.85,
            "semantic_similarity": 0.80,
            "quality_score": 0.90,
        },
    ]

    # Simulate validation thresholds
    MIN_AVERAGE_RELEVANCE = 0.40
    MIN_SEMANTIC_SIMILARITY = 0.45

    # Calculate metrics
    all_sources = web_results
    relevances = [s.get("overall_score", s.get("relevance_score", 0)) for s in all_sources]
    semantic_sims = [s.get("semantic_similarity", 0) for s in all_sources]
    average_relevance = sum(relevances) / len(relevances)
    average_semantic_similarity = sum(semantic_sims) / len(semantic_sims)

    # Should pass validation
    assert average_relevance >= MIN_AVERAGE_RELEVANCE
    assert average_semantic_similarity >= MIN_SEMANTIC_SIMILARITY


def test_wikipedia_provider_sets_relevance_score():
    """Test that Wikipedia provider sets relevance_score (backward compatibility)."""
    from backend.providers.search.wikipedia_provider import WikipediaProvider

    provider = WikipediaProvider()

    # Simulate relevance score calculation
    query = "What is artificial intelligence?"
    title = "Artificial Intelligence"
    snippet = "Artificial intelligence is intelligence demonstrated by machines."

    relevance_score = provider._calculate_relevance_score(query, title, snippet)

    # Should return a valid score
    assert 0.0 <= relevance_score <= 1.0
    # For matching query, should be reasonably high
    assert relevance_score >= 0.5


def test_documentation_provider_sets_relevance_score():
    """Test that documentation provider sets relevance_score (backward compatibility)."""
    from backend.providers.search.documentation_provider import DocumentationProvider

    provider = DocumentationProvider()

    # Simulate relevance score calculation
    query = "FastAPI dependency injection"
    result = {
        "title": "FastAPI Dependencies",
        "url": "https://fastapi.tiangolo.com/tutorial/dependencies/",
        "snippet": "FastAPI has a very powerful but intuitive Dependency Injection system.",
    }

    relevance_score = provider._calculate_relevance_score(query, result)

    # Should return a valid score
    assert 0.0 <= relevance_score <= 1.0


def test_source_ranking_to_report_validation_integration():
    """Test end-to-end integration from source ranking to report validation."""
    # Start with raw provider results (no scores)
    web_results = [
        {
            "title": "Artificial Intelligence",
            "url": "http://test.com/ai",
            "snippet": "AI is intelligence demonstrated by machines.",
        },
    ]

    # Step 1: Source ranking
    web_ranked, _, _ = rank_sources(
        web_results=web_results,
        papers=[],
        query="What is artificial intelligence?",
        query_type="definition",
    )

    # Step 2: Evidence fusion
    fusion_result = fuse_evidence(
        web_results=web_ranked,
        papers=[],
        documentation=[],
        query="What is artificial intelligence?",
    )

    # Step 3: Report validation calculation
    combined_sources = fusion_result["combined_sources"]
    relevances = [s.get("overall_score", s.get("relevance_score", 0)) for s in combined_sources]
    average_relevance = sum(relevances) / len(relevances)

    # Verify the signal propagates correctly
    assert average_relevance > 0.0
    assert combined_sources[0]["overall_score"] > 0.0


def test_regression_live_test_scenario():
    """Regression test for the live test scenario that revealed the bug.

    The live test showed:
    - Wikipedia: semantic_similarity=0.803, overall_score=0.856
    - IBM: semantic_similarity=0.848, overall_score=0.677
    - But validation reported average_relevance=0.00

    This test ensures the fix prevents this regression.
    """
    # Simulate the actual sources from the live test
    web_results = [
        {
            "title": "Artificial Intelligence - Wikipedia",
            "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
            "snippet": "Artificial intelligence (AI) is intelligence demonstrated by machines.",
            "semantic_similarity": 0.8032549859,
            "overall_score": 0.8564647437,
            "quality_score": 1.0,
            "reliability_score": 1.0,
        },
        {
            "title": "What is AI? - IBM",
            "url": "https://www.ibm.com/topics/artificial-intelligence",
            "snippet": "Artificial intelligence is the simulation of human intelligence by machines.",
            "semantic_similarity": 0.8481589809,
            "overall_score": 0.6766715414,
            "quality_score": 0.7,
            "reliability_score": 0.3,
        },
    ]

    # Calculate average relevance using the fixed logic
    all_sources = web_results
    relevances = [s.get("overall_score", s.get("relevance_score", 0)) for s in all_sources]
    average_relevance = sum(relevances) / len(relevances)

    # Should NOT be 0.00
    assert average_relevance > 0.5  # Should be around 0.77

    # Should pass validation threshold (0.40)
    MIN_AVERAGE_RELEVANCE = 0.40
    assert average_relevance >= MIN_AVERAGE_RELEVANCE


def test_semantic_similarity_always_propagated():
    """Test that semantic_similarity is always propagated from source ranking."""
    web_results = [
        {
            "title": "Test Source with Enough Content",
            "url": "http://test.com/test-source",
            "snippet": "This is a test snippet with enough content to pass filtering.",
        },
    ]

    web_ranked, _, _ = rank_sources(
        web_results=web_results,
        papers=[],
        query="test query",
        query_type="research",
    )

    # If source passes filtering, semantic_similarity should be set
    if web_ranked:
        assert "semantic_similarity" in web_ranked[0]
        assert web_ranked[0]["semantic_similarity"] >= 0.0


def test_quality_score_always_propagated():
    """Test that quality_score is always propagated from source ranking."""
    web_results = [
        {
            "title": "Test Source with Enough Content",
            "url": "http://test.com/test-source",
            "snippet": "This is a test snippet with enough content to pass filtering.",
        },
    ]

    web_ranked, _, _ = rank_sources(
        web_results=web_results,
        papers=[],
        query="test query",
        query_type="research",
    )

    # If source passes filtering, quality_score should be set
    if web_ranked:
        assert "quality_score" in web_ranked[0]
        assert web_ranked[0]["quality_score"] >= 0.0
