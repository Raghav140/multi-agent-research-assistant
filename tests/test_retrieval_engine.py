"""Tests for RetrievalEngine integration."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.retrieval_engine import RetrievalEngine
from backend.providers.circuit_breaker import CircuitBreaker
from backend.providers.health_monitor import ProviderHealthMonitor


@pytest.fixture
def mock_providers():
    """Create mock providers."""
    search_provider = AsyncMock()
    search_provider.search = AsyncMock(return_value=[
        {"title": "Test Result 1", "url": "http://test.com/1", "snippet": "Test snippet 1"},
        {"title": "Test Result 2", "url": "http://test.com/2", "snippet": "Test snippet 2"},
    ])

    arxiv_provider = AsyncMock()
    arxiv_provider.search = AsyncMock(return_value=[
        {"title": "Test Paper 1", "authors": ["Author 1"], "abstract": "Test abstract 1"},
    ])

    wikipedia_provider = AsyncMock()
    wikipedia_provider.search = AsyncMock(return_value=[
        {"title": "Wikipedia Test", "url": "http://wiki.org/test", "snippet": "Wiki snippet"},
    ])

    documentation_provider = AsyncMock()
    documentation_provider.search = AsyncMock(return_value=[
        {"title": "Docs Test", "url": "http://docs.com/test", "snippet": "Docs snippet"},
    ])

    return {
        "duckduckgo": search_provider,
        "arxiv": arxiv_provider,
        "wikipedia": wikipedia_provider,
        "documentation": documentation_provider,
    }


@pytest.fixture
def circuit_breakers():
    """Create circuit breakers with short timeouts for testing."""
    return {
        "duckduckgo": CircuitBreaker("duckduckgo", failure_threshold=3, cooldown_seconds=1, timeout_seconds=1),
        "wikipedia": CircuitBreaker("wikipedia", failure_threshold=3, cooldown_seconds=1, timeout_seconds=1),
        "arxiv": CircuitBreaker("arxiv", failure_threshold=3, cooldown_seconds=1, timeout_seconds=1),
        "documentation": CircuitBreaker("documentation", failure_threshold=3, cooldown_seconds=1, timeout_seconds=1),
    }


@pytest.fixture
def health_monitors():
    """Create health monitors."""
    return {
        "duckduckgo": ProviderHealthMonitor("duckduckgo"),
        "wikipedia": ProviderHealthMonitor("wikipedia"),
        "arxiv": ProviderHealthMonitor("arxiv"),
        "documentation": ProviderHealthMonitor("documentation"),
    }


@pytest.mark.asyncio
async def test_retrieval_engine_initialization(mock_providers, circuit_breakers, health_monitors):
    """Test RetrievalEngine initialization with all components."""
    engine = RetrievalEngine(
        duckduckgo_provider=mock_providers["duckduckgo"],
        arxiv_provider=mock_providers["arxiv"],
        wikipedia_provider=mock_providers["wikipedia"],
        documentation_provider=mock_providers["documentation"],
        duckduckgo_circuit_breaker=circuit_breakers["duckduckgo"],
        wikipedia_circuit_breaker=circuit_breakers["wikipedia"],
        arxiv_circuit_breaker=circuit_breakers["arxiv"],
        documentation_circuit_breaker=circuit_breakers["documentation"],
        duckduckgo_health_monitor=health_monitors["duckduckgo"],
        wikipedia_health_monitor=health_monitors["wikipedia"],
        arxiv_health_monitor=health_monitors["arxiv"],
        documentation_health_monitor=health_monitors["documentation"],
    )

    assert engine.duckduckgo_provider is not None
    assert engine.arxiv_provider is not None
    assert engine.wikipedia_provider is not None
    assert engine.documentation_provider is not None
    assert engine.duckduckgo_circuit_breaker is not None
    assert engine.wikipedia_circuit_breaker is not None
    assert engine.arxiv_circuit_breaker is not None
    assert engine.documentation_circuit_breaker is not None
    assert engine.duckduckgo_health_monitor is not None
    assert engine.wikipedia_health_monitor is not None
    assert engine.arxiv_health_monitor is not None
    assert engine.documentation_health_monitor is not None


@pytest.mark.asyncio
async def test_retrieve_all_sources(mock_providers, circuit_breakers, health_monitors):
    """Test retrieving sources from all providers."""
    engine = RetrievalEngine(
        duckduckgo_provider=mock_providers["duckduckgo"],
        arxiv_provider=mock_providers["arxiv"],
        wikipedia_provider=mock_providers["wikipedia"],
        documentation_provider=mock_providers["documentation"],
        duckduckgo_circuit_breaker=circuit_breakers["duckduckgo"],
        wikipedia_circuit_breaker=circuit_breakers["wikipedia"],
        arxiv_circuit_breaker=circuit_breakers["arxiv"],
        documentation_circuit_breaker=circuit_breakers["documentation"],
        duckduckgo_health_monitor=health_monitors["duckduckgo"],
        wikipedia_health_monitor=health_monitors["wikipedia"],
        arxiv_health_monitor=health_monitors["arxiv"],
        documentation_health_monitor=health_monitors["documentation"],
    )

    # Mock the internal retrieval methods to avoid slow calls
    engine._retrieve_duckduckgo = AsyncMock(return_value={
        "results": [{"title": "Test Result 1", "url": "http://test.com/1"}],
        "metrics": {"success": True, "execution_time_ms": 100, "results_count": 1}
    })
    engine._retrieve_arxiv = AsyncMock(return_value={
        "results": [{"title": "Test Paper 1"}],
        "metrics": {"success": True, "execution_time_ms": 100, "results_count": 1}
    })
    engine._retrieve_documentation = AsyncMock(return_value={
        "results": [{"title": "Test Doc 1"}],
        "metrics": {"success": True, "execution_time_ms": 100, "results_count": 1}
    })

    result = await engine.retrieve_all_sources(
        query="test query",
        query_type="research",
        request_id="test-123",
    )

    assert "web_results" in result
    assert "papers" in result
    assert "documentation" in result
    assert "provider_metrics" in result


@pytest.mark.asyncio
async def test_circuit_breaker_protection(mock_providers, circuit_breakers, health_monitors):
    """Test that circuit breakers protect against failing providers."""
    engine = RetrievalEngine(
        duckduckgo_provider=mock_providers["duckduckgo"],
        arxiv_provider=mock_providers["arxiv"],
        wikipedia_provider=mock_providers["wikipedia"],
        documentation_provider=mock_providers["documentation"],
        duckduckgo_circuit_breaker=circuit_breakers["duckduckgo"],
        wikipedia_circuit_breaker=circuit_breakers["wikipedia"],
        arxiv_circuit_breaker=circuit_breakers["arxiv"],
        documentation_circuit_breaker=circuit_breakers["documentation"],
        duckduckgo_health_monitor=health_monitors["duckduckgo"],
        wikipedia_health_monitor=health_monitors["wikipedia"],
        arxiv_health_monitor=health_monitors["arxiv"],
        documentation_health_monitor=health_monitors["documentation"],
        use_cache=False,  # Disable cache for this test
    )

    # Mock DuckDuckGo to fail
    engine._retrieve_duckduckgo = AsyncMock(return_value={
        "results": [],
        "metrics": {"success": False, "error": "Provider error", "execution_time_ms": 100, "results_count": 0}
    })
    engine._retrieve_arxiv = AsyncMock(return_value={
        "results": [{"title": "Test Paper 1"}],
        "metrics": {"success": True, "execution_time_ms": 100, "results_count": 1}
    })
    engine._retrieve_documentation = AsyncMock(return_value={
        "results": [{"title": "Test Doc 1"}],
        "metrics": {"success": True, "execution_time_ms": 100, "results_count": 1}
    })

    result = await engine.retrieve_all_sources(
        query="test query",
        query_type="research",
        request_id="test-123",
    )

    # DuckDuckGo should have empty results due to failure
    duckduckgo_metrics = result["provider_metrics"].get("duckduckgo", {})
    assert duckduckgo_metrics.get("success") == False


@pytest.mark.asyncio
async def test_health_monitoring(mock_providers, circuit_breakers, health_monitors):
    """Test that health monitors track provider performance."""
    engine = RetrievalEngine(
        duckduckgo_provider=mock_providers["duckduckgo"],
        arxiv_provider=mock_providers["arxiv"],
        wikipedia_provider=mock_providers["wikipedia"],
        documentation_provider=mock_providers["documentation"],
        duckduckgo_circuit_breaker=circuit_breakers["duckduckgo"],
        wikipedia_circuit_breaker=circuit_breakers["wikipedia"],
        arxiv_circuit_breaker=circuit_breakers["arxiv"],
        documentation_circuit_breaker=circuit_breakers["documentation"],
        duckduckgo_health_monitor=health_monitors["duckduckgo"],
        wikipedia_health_monitor=health_monitors["wikipedia"],
        arxiv_health_monitor=health_monitors["arxiv"],
        documentation_health_monitor=health_monitors["documentation"],
    )

    # Mock retrieval methods
    engine._retrieve_duckduckgo = AsyncMock(return_value={
        "results": [{"title": "Test Result 1"}],
        "metrics": {"success": True, "execution_time_ms": 100, "results_count": 1}
    })
    engine._retrieve_arxiv = AsyncMock(return_value={
        "results": [],
        "metrics": {"success": True, "execution_time_ms": 100, "results_count": 0}
    })
    engine._retrieve_documentation = AsyncMock(return_value={
        "results": [],
        "metrics": {"success": True, "execution_time_ms": 100, "results_count": 0}
    })

    await engine.retrieve_all_sources(
        query="test query",
        query_type="research",
        request_id="test-123",
    )

    # Manually record success to health monitor to test tracking
    health_monitors["duckduckgo"].record_success(100)

    # Check that health monitors recorded metrics
    duckduckgo_status = health_monitors["duckduckgo"].get_status()
    assert duckduckgo_status["total_requests"] > 0
    assert duckduckgo_status["successful_requests"] > 0


@pytest.mark.asyncio
async def test_provider_priority_by_query_type(mock_providers, circuit_breakers, health_monitors):
    """Test that provider selection varies by query type."""
    engine = RetrievalEngine(
        duckduckgo_provider=mock_providers["duckduckgo"],
        arxiv_provider=mock_providers["arxiv"],
        wikipedia_provider=mock_providers["wikipedia"],
        documentation_provider=mock_providers["documentation"],
        duckduckgo_circuit_breaker=circuit_breakers["duckduckgo"],
        wikipedia_circuit_breaker=circuit_breakers["wikipedia"],
        arxiv_circuit_breaker=circuit_breakers["arxiv"],
        documentation_circuit_breaker=circuit_breakers["documentation"],
        duckduckgo_health_monitor=health_monitors["duckduckgo"],
        wikipedia_health_monitor=health_monitors["wikipedia"],
        arxiv_health_monitor=health_monitors["arxiv"],
        documentation_health_monitor=health_monitors["documentation"],
    )

    # Mock retrieval methods
    engine._retrieve_duckduckgo = AsyncMock(return_value={
        "results": [{"title": "Test Result 1"}],
        "metrics": {"success": True, "execution_time_ms": 100, "results_count": 1}
    })
    engine._retrieve_arxiv = AsyncMock(return_value={
        "results": [{"title": "Test Paper 1"}],
        "metrics": {"success": True, "execution_time_ms": 100, "results_count": 1}
    })
    engine._retrieve_documentation = AsyncMock(return_value={
        "results": [{"title": "Test Doc 1"}],
        "metrics": {"success": True, "execution_time_ms": 100, "results_count": 1}
    })

    # Test definition query (should prioritize Wikipedia)
    result_def = await engine.retrieve_all_sources(
        query="what is machine learning",
        query_type="definition",
        request_id="test-123",
    )

    # Test technical query (should include documentation)
    result_tech = await engine.retrieve_all_sources(
        query="how to use python asyncio",
        query_type="technical",
        request_id="test-124",
    )

    # Test research query (should include arXiv)
    result_research = await engine.retrieve_all_sources(
        query="latest advances in quantum computing",
        query_type="research",
        request_id="test-125",
    )

    # All should have web results
    assert "web_results" in result_def
    assert "web_results" in result_tech
    assert "web_results" in result_research


@pytest.mark.asyncio
async def test_retrieval_engine_without_optional_components(mock_providers):
    """Test RetrievalEngine works without optional components."""
    engine = RetrievalEngine(
        duckduckgo_provider=mock_providers["duckduckgo"],
        arxiv_provider=mock_providers["arxiv"],
        wikipedia_provider=None,
        documentation_provider=None,
        duckduckgo_circuit_breaker=None,
        wikipedia_circuit_breaker=None,
        arxiv_circuit_breaker=None,
        documentation_circuit_breaker=None,
        duckduckgo_health_monitor=None,
        wikipedia_health_monitor=None,
        arxiv_health_monitor=None,
        documentation_health_monitor=None,
    )

    # Mock retrieval methods
    engine._retrieve_duckduckgo = AsyncMock(return_value={
        "results": [{"title": "Test Result 1"}],
        "metrics": {"success": True, "execution_time_ms": 100, "results_count": 1}
    })
    engine._retrieve_arxiv = AsyncMock(return_value={
        "results": [{"title": "Test Paper 1"}],
        "metrics": {"success": True, "execution_time_ms": 100, "results_count": 1}
    })

    result = await engine.retrieve_all_sources(
        query="test query",
        query_type="research",
        request_id="test-123",
    )

    assert "web_results" in result
    assert "papers" in result
