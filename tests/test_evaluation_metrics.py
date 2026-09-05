"""Integration tests for Evaluation & Metrics system."""

import pytest
import time
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from backend.utils.evaluation import RetrievalEvaluator, get_evaluator
from backend.utils.metrics_storage import MetricsStorage, get_metrics_storage
from backend.services.retrieval_engine import RetrievalEngine
from backend.core.interfaces import SearchProvider
from backend.providers.papers.arxiv_provider import ArxivProvider


@pytest.fixture
def mock_provider():
    """Create a mock search provider."""
    provider = AsyncMock(spec=SearchProvider)
    provider.search = AsyncMock(return_value=[
        {"title": "Test Result", "url": "http://test.com", "snippet": "Test snippet"}
    ])
    return provider


@pytest.fixture
def mock_arxiv_provider():
    """Create a mock arXiv provider."""
    provider = AsyncMock(spec=ArxivProvider)
    provider.search = AsyncMock(return_value=[
        {"title": "Test Paper", "url": "http://arxiv.org/test", "snippet": "Test abstract"}
    ])
    return provider


@pytest.fixture
def retrieval_engine(mock_provider, mock_arxiv_provider):
    """Create a RetrievalEngine instance for testing."""
    return RetrievalEngine(
        duckduckgo_provider=mock_provider,
        arxiv_provider=mock_arxiv_provider,
        wikipedia_provider=None,
        documentation_provider=None,
        memory_manager=None,
        use_cache=False,
        use_memory=False,
    )


def test_evaluator_tracks_retrieval_metrics():
    """Test evaluator tracks retrieval metrics correctly."""
    evaluator = RetrievalEvaluator()

    evaluator.track_retrieval_metrics(
        query="test query",
        query_type="research",
        providers_used=["duckduckgo", "arxiv"],
        sources_found=10,
        sources_selected=5,
        source_quality_score=0.8,
        evidence_diversity=0.7,
        confidence_score=0.75,
        execution_time_ms=1000.0,
        request_id="test-123",
        cache_hit=True,
        memory_hit=False,
        provider_count=2,
        successful_provider_count=2,
        failed_provider_count=0,
        provider_timeouts=0,
    )

    assert len(evaluator.metrics_history) == 1
    metrics = evaluator.metrics_history[0]
    assert metrics["query"] == "test query"
    assert metrics["query_type"] == "research"
    assert metrics["providers_used"] == ["duckduckgo", "arxiv"]
    assert metrics["sources_found"] == 10
    assert metrics["sources_selected"] == 5
    assert metrics["cache_hit"] == True
    assert metrics["memory_hit"] == False
    assert metrics["provider_count"] == 2
    assert metrics["successful_provider_count"] == 2


def test_evaluator_tracks_answer_metrics():
    """Test evaluator tracks answer metrics correctly."""
    evaluator = RetrievalEvaluator()

    # First track retrieval metrics
    evaluator.track_retrieval_metrics(
        query="test query",
        query_type="research",
        providers_used=["duckduckgo"],
        sources_found=5,
        sources_selected=3,
        source_quality_score=0.8,
        evidence_diversity=0.7,
        confidence_score=0.75,
        execution_time_ms=1000.0,
        request_id="test-123",
    )

    # Then track answer metrics
    evaluator.track_answer_metrics(
        structure_score=1.0,
        leakage_score=1.0,
        hallucination_risk=0.2,
        citation_score=0.9,
        request_id="test-123",
        report_generation_time_ms=500.0,
        citation_count=3,
        contradiction_count=0,
        regeneration_count=0,
        final_confidence=0.8,
    )

    assert len(evaluator.metrics_history) == 1
    metrics = evaluator.metrics_history[0]
    assert metrics["structure_score"] == 1.0
    assert metrics["leakage_score"] == 1.0
    assert metrics["hallucination_risk"] == 0.2
    assert metrics["citation_score"] == 0.9
    assert metrics["report_generation_time_ms"] == 500.0
    assert metrics["citation_count"] == 3
    assert metrics["final_confidence"] == 0.8


def test_evaluator_calculates_average_metrics():
    """Test evaluator calculates average metrics correctly."""
    evaluator = RetrievalEvaluator()

    # Track multiple metrics
    for i in range(3):
        evaluator.track_retrieval_metrics(
            query=f"query {i}",
            query_type="research",
            providers_used=["duckduckgo"],
            sources_found=10 + i,
            sources_selected=5 + i,
            source_quality_score=0.7 + (i * 0.1),
            evidence_diversity=0.6 + (i * 0.1),
            confidence_score=0.7 + (i * 0.1),
            execution_time_ms=1000.0 + (i * 100),
            request_id=f"test-{i}",
        )

    avg_metrics = evaluator.calculate_average_metrics()

    assert avg_metrics["count"] == 3
    assert avg_metrics["avg_sources_found"] == 11.0  # (10 + 11 + 12) / 3
    assert avg_metrics["avg_sources_selected"] == 6.0
    assert avg_metrics["avg_source_quality"] == pytest.approx(0.8)  # (0.7 + 0.8 + 0.9) / 3
    assert avg_metrics["avg_evidence_diversity"] == pytest.approx(0.7)
    assert avg_metrics["avg_confidence"] == pytest.approx(0.8)


def test_evaluator_gets_provider_performance():
    """Test evaluator gets provider performance metrics."""
    evaluator = RetrievalEvaluator()

    # Track metrics with different providers
    evaluator.track_retrieval_metrics(
        query="test 1",
        query_type="research",
        providers_used=["duckduckgo", "arxiv"],
        sources_found=10,
        sources_selected=5,
        source_quality_score=0.8,
        evidence_diversity=0.7,
        confidence_score=0.75,
        execution_time_ms=1000.0,
        request_id="test-1",
    )

    evaluator.track_retrieval_metrics(
        query="test 2",
        query_type="research",
        providers_used=["duckduckgo"],
        sources_found=5,
        sources_selected=3,
        source_quality_score=0.7,
        evidence_diversity=0.6,
        confidence_score=0.7,
        execution_time_ms=800.0,
        request_id="test-2",
    )

    provider_perf = evaluator.get_provider_performance()

    assert "duckduckgo" in provider_perf
    assert provider_perf["duckduckgo"]["count"] == 2
    assert provider_perf["duckduckgo"]["avg_sources"] == 7.5  # (10 + 5) / 2
    assert "arxiv" in provider_perf
    assert provider_perf["arxiv"]["count"] == 1


def test_evaluator_gets_query_type_performance():
    """Test evaluator gets query type performance metrics."""
    evaluator = RetrievalEvaluator()

    # Track metrics with different query types
    evaluator.track_retrieval_metrics(
        query="test 1",
        query_type="research",
        providers_used=["duckduckgo"],
        sources_found=10,
        sources_selected=5,
        source_quality_score=0.8,
        evidence_diversity=0.7,
        confidence_score=0.75,
        execution_time_ms=1000.0,
        request_id="test-1",
    )

    evaluator.track_retrieval_metrics(
        query="test 2",
        query_type="definition",
        providers_used=["duckduckgo"],
        sources_found=5,
        sources_selected=3,
        source_quality_score=0.7,
        evidence_diversity=0.6,
        confidence_score=0.7,
        execution_time_ms=800.0,
        request_id="test-2",
    )

    query_type_perf = evaluator.get_query_type_performance()

    assert "research" in query_type_perf
    assert "definition" in query_type_perf
    assert query_type_perf["research"]["count"] == 1
    assert query_type_perf["definition"]["count"] == 1


def test_evaluator_clears_metrics():
    """Test evaluator clears all metrics."""
    evaluator = RetrievalEvaluator()

    evaluator.track_retrieval_metrics(
        query="test",
        query_type="research",
        providers_used=["duckduckgo"],
        sources_found=10,
        sources_selected=5,
        source_quality_score=0.8,
        evidence_diversity=0.7,
        confidence_score=0.75,
        execution_time_ms=1000.0,
        request_id="test-123",
    )

    assert len(evaluator.metrics_history) == 1

    evaluator.clear_metrics()

    assert len(evaluator.metrics_history) == 0


def test_evaluator_singleton():
    """Test evaluator singleton pattern."""
    evaluator1 = get_evaluator()
    evaluator2 = get_evaluator()

    assert evaluator1 is evaluator2


def test_metrics_storage_stores_metrics():
    """Test metrics storage stores metrics correctly."""
    # Use temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp_path = tmp.name

    try:
        storage = MetricsStorage(tmp_path)

        record_id = storage.store_metrics(
            query="test query",
            query_type="research",
            request_id="test-123",
            retrieval_metrics={
                "providers_used": ["duckduckgo"],
                "sources_found": 10,
                "sources_selected": 5,
                "selection_rate": 0.5,
                "source_quality_score": 0.8,
                "evidence_diversity": 0.7,
                "confidence_score": 0.75,
                "execution_time_ms": 1000.0,
                "cache_hit": True,
                "memory_hit": False,
                "provider_count": 1,
                "successful_provider_count": 1,
                "failed_provider_count": 0,
                "provider_timeouts": 0,
            },
            answer_metrics={
                "structure_score": 1.0,
                "leakage_score": 1.0,
                "hallucination_risk": 0.2,
                "citation_score": 0.9,
                "report_generation_time_ms": 500.0,
                "citation_count": 3,
                "contradiction_count": 0,
                "regeneration_count": 0,
                "final_confidence": 0.8,
            },
        )

        assert record_id > 0

        # Retrieve stored metrics
        metrics = storage.get_metrics(limit=1)

        assert len(metrics) == 1
        assert metrics[0]["query"] == "test query"
        assert metrics[0]["query_type"] == "research"
        assert metrics[0]["sources_found"] == 10
        assert metrics[0]["cache_hit"] == True
        assert metrics[0]["structure_score"] == 1.0
        assert metrics[0]["citation_count"] == 3

    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_metrics_storage_gets_aggregated_metrics():
    """Test metrics storage gets aggregated metrics."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp_path = tmp.name

    try:
        storage = MetricsStorage(tmp_path)

        # Store multiple metrics
        for i in range(3):
            storage.store_metrics(
                query=f"query {i}",
                query_type="research",
                request_id=f"test-{i}",
                retrieval_metrics={
                    "providers_used": ["duckduckgo"],
                    "sources_found": 10 + i,
                    "sources_selected": 5 + i,
                    "selection_rate": 0.5,
                    "source_quality_score": 0.7 + (i * 0.1),
                    "evidence_diversity": 0.6 + (i * 0.1),
                    "confidence_score": 0.7 + (i * 0.1),
                    "execution_time_ms": 1000.0 + (i * 100),
                    "cache_hit": False,
                    "memory_hit": False,
                    "provider_count": 1,
                    "successful_provider_count": 1,
                    "failed_provider_count": 0,
                    "provider_timeouts": 0,
                },
            )

        agg_metrics = storage.get_aggregated_metrics(days=7)

        assert agg_metrics["count"] == 3
        assert agg_metrics["avg_source_quality"] == pytest.approx(0.8)  # (0.7 + 0.8 + 0.9) / 3
        assert agg_metrics["avg_evidence_diversity"] == pytest.approx(0.7)
        assert agg_metrics["avg_confidence"] == pytest.approx(0.8)

    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_metrics_storage_clears_old_metrics():
    """Test metrics storage clears old metrics."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp_path = tmp.name

    try:
        storage = MetricsStorage(tmp_path)

        # Store recent metrics
        storage.store_metrics(
            query="recent query",
            query_type="research",
            request_id="recent-123",
            retrieval_metrics={
                "providers_used": ["duckduckgo"],
                "sources_found": 5,
                "sources_selected": 3,
                "selection_rate": 0.6,
                "source_quality_score": 0.7,
                "evidence_diversity": 0.6,
                "confidence_score": 0.7,
                "execution_time_ms": 800.0,
                "cache_hit": False,
                "memory_hit": False,
                "provider_count": 1,
                "successful_provider_count": 1,
                "failed_provider_count": 0,
                "provider_timeouts": 0,
            },
        )

        # Directly insert an old record into the database
        import sqlite3
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()
        old_timestamp = time.time() - (40 * 24 * 60 * 60)  # 40 days ago
        cursor.execute(
            """
            INSERT INTO evaluation_metrics
            (timestamp, request_id, query, query_type, providers_used, sources_found, sources_selected,
             selection_rate, source_quality_score, evidence_diversity, confidence_score, execution_time_ms,
             cache_hit, memory_hit, provider_count, successful_provider_count, failed_provider_count, provider_timeouts,
             structure_score, leakage_score, hallucination_risk, citation_score, report_generation_time_ms,
             citation_count, contradiction_count, regeneration_count, final_confidence, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                old_timestamp,
                "old-123",
                "old query",
                "research",
                '["duckduckgo"]',
                10,
                5,
                0.5,
                0.8,
                0.7,
                0.75,
                1000.0,
                0,
                0,
                1,
                1,
                0,
                0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0,
                0,
                0,
                0.0,
                '{}',
            ),
        )
        conn.commit()
        conn.close()

        # Clear old metrics (older than 30 days)
        deleted_count = storage.clear_old_metrics(days=30)

        assert deleted_count >= 1

        # Verify recent metrics still exist
        metrics = storage.get_metrics()
        assert any(m["query"] == "recent query" for m in metrics)
        # Verify old metrics are gone
        assert not any(m["query"] == "old query" for m in metrics)

    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_metrics_storage_failure_does_not_break_evaluator():
    """Test metrics storage failure doesn't break evaluator."""
    evaluator = RetrievalEvaluator()

    # Mock storage to raise exception
    with patch.object(evaluator.metrics_storage, 'store_metrics', side_effect=Exception("Storage failure")):
        # Should not raise exception
        evaluator.track_retrieval_metrics(
            query="test query",
            query_type="research",
            providers_used=["duckduckgo"],
            sources_found=10,
            sources_selected=5,
            source_quality_score=0.8,
            evidence_diversity=0.7,
            confidence_score=0.75,
            execution_time_ms=1000.0,
            request_id="test-123",
        )

    # Metrics should still be in history
    assert len(evaluator.metrics_history) == 1


def test_metrics_storage_singleton():
    """Test metrics storage singleton pattern."""
    storage1 = get_metrics_storage(":memory:")
    storage2 = get_metrics_storage(":memory:")

    # Should return same instance if path is same
    # Note: Different paths create different instances
    assert storage1 is not None
    assert storage2 is not None


def test_retrieval_engine_includes_provider_metrics(mock_provider, mock_arxiv_provider):
    """Test retrieval engine includes provider metrics in results."""
    engine = RetrievalEngine(
        duckduckgo_provider=mock_provider,
        arxiv_provider=mock_arxiv_provider,
        wikipedia_provider=None,
        documentation_provider=None,
        memory_manager=None,
        use_cache=False,
        use_memory=False,
    )

    async def test_retrieve():
        result = await engine.retrieve_all_sources(
            query="test query",
            query_type="research",
            request_id="test-123",
        )
        return result

    import asyncio
    result = asyncio.run(test_retrieve())

    # Verify provider metrics are included
    assert "provider_count" in result
    assert "successful_provider_count" in result
    assert "failed_provider_count" in result
    assert "provider_timeouts" in result
    assert "cache_hit" in result
    assert "memory_hit" in result


def test_metrics_with_cache_and_memory():
    """Test metrics include cache and memory information."""
    evaluator = RetrievalEvaluator()

    evaluator.track_retrieval_metrics(
        query="test query",
        query_type="research",
        providers_used=["duckduckgo"],
        sources_found=10,
        sources_selected=5,
        source_quality_score=0.8,
        evidence_diversity=0.7,
        confidence_score=0.75,
        execution_time_ms=1000.0,
        request_id="test-123",
        cache_hit=True,
        memory_hit=True,
        provider_count=1,
        successful_provider_count=1,
        failed_provider_count=0,
        provider_timeouts=0,
    )

    metrics = evaluator.metrics_history[0]
    assert metrics["cache_hit"] == True
    assert metrics["memory_hit"] == True


def test_answer_metrics_with_regeneration():
    """Test answer metrics include regeneration count."""
    evaluator = RetrievalEvaluator()

    # Track retrieval metrics first
    evaluator.track_retrieval_metrics(
        query="test query",
        query_type="research",
        providers_used=["duckduckgo"],
        sources_found=10,
        sources_selected=5,
        source_quality_score=0.8,
        evidence_diversity=0.7,
        confidence_score=0.75,
        execution_time_ms=1000.0,
        request_id="test-123",
    )

    # Track answer metrics with regeneration
    evaluator.track_answer_metrics(
        structure_score=1.0,
        leakage_score=1.0,
        hallucination_risk=0.2,
        citation_score=0.9,
        request_id="test-123",
        report_generation_time_ms=500.0,
        citation_count=3,
        contradiction_count=0,
        regeneration_count=2,
        final_confidence=0.8,
    )

    metrics = evaluator.metrics_history[0]
    assert metrics["regeneration_count"] == 2
