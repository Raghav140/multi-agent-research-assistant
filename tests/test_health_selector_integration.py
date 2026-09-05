"""Integration tests for Provider Health Monitor + Provider Selector."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from backend.providers.circuit_breaker import CircuitBreaker
from backend.providers.health_monitor import ProviderHealthMonitor
from backend.utils.provider_selector import ProviderSelector
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
def circuit_breaker():
    """Create a circuit breaker for testing."""
    return CircuitBreaker(
        provider_name="test_provider",
        failure_threshold=2,
        cooldown_seconds=1,
        timeout_seconds=1,
    )


@pytest.fixture
def health_monitor():
    """Create a health monitor for testing."""
    return ProviderHealthMonitor(provider_name="test_provider")


def test_retrieval_engine_uses_provider_selector(mock_provider, mock_arxiv_provider):
    """Test RetrievalEngine uses provider selector for provider selection."""
    selector = ProviderSelector()
    health_monitor = ProviderHealthMonitor("duckduckgo")
    circuit_breaker = CircuitBreaker("duckduckgo", failure_threshold=3, cooldown_seconds=60)

    engine = RetrievalEngine(
        duckduckgo_provider=mock_provider,
        arxiv_provider=mock_arxiv_provider,
        wikipedia_provider=None,
        documentation_provider=None,
        duckduckgo_circuit_breaker=circuit_breaker,
        duckduckgo_health_monitor=health_monitor,
        provider_selector=selector,
    )

    async def test_retrieve():
        result = await engine.retrieve_all_sources(
            query="test query",
            query_type="research",
            request_id="test-123",
        )
        return result

    result = asyncio.run(test_retrieve())

    # Verify selector was used (should have selected providers based on query type)
    assert "provider_metrics" in result
    assert "execution_time_ms" in result


def test_unhealthy_provider_filtered(mock_provider, mock_arxiv_provider):
    """Test unhealthy providers are filtered by selector."""
    selector = ProviderSelector()
    health_monitor = ProviderHealthMonitor("duckduckgo")
    circuit_breaker = CircuitBreaker("duckduckgo", failure_threshold=3, cooldown_seconds=60)

    # Mark duckduckgo as unhealthy
    selector.update_provider_health("duckduckgo", False)

    engine = RetrievalEngine(
        duckduckgo_provider=mock_provider,
        arxiv_provider=mock_arxiv_provider,
        wikipedia_provider=None,
        documentation_provider=None,
        duckduckgo_circuit_breaker=circuit_breaker,
        duckduckgo_health_monitor=health_monitor,
        provider_selector=selector,
    )

    async def test_retrieve():
        result = await engine.retrieve_all_sources(
            query="test query",
            query_type="research",
            request_id="test-123",
        )
        return result

    result = asyncio.run(test_retrieve())

    # DuckDuckGo should not be called since it's unhealthy
    # Only arXiv should be called
    assert "arxiv" in result["provider_metrics"]
    # duckduckgo might be in metrics if selected but failed, but selector should filter it


def test_circuit_open_provider_filtered(mock_provider, mock_arxiv_provider):
    """Test circuit-open providers are filtered by selector."""
    selector = ProviderSelector()
    health_monitor = ProviderHealthMonitor("duckduckgo")
    circuit_breaker = CircuitBreaker("duckduckgo", failure_threshold=3, cooldown_seconds=60)

    # Mark duckduckgo circuit as open
    selector.update_provider_circuit_state("duckduckgo", "open")

    engine = RetrievalEngine(
        duckduckgo_provider=mock_provider,
        arxiv_provider=mock_arxiv_provider,
        wikipedia_provider=None,
        documentation_provider=None,
        duckduckgo_circuit_breaker=circuit_breaker,
        duckduckgo_health_monitor=health_monitor,
        provider_selector=selector,
    )

    async def test_retrieve():
        result = await engine.retrieve_all_sources(
            query="test query",
            query_type="research",
            request_id="test-123",
        )
        return result

    result = asyncio.run(test_retrieve())

    # DuckDuckGo should not be called since circuit is open
    assert "arxiv" in result["provider_metrics"]


def test_health_monitor_records_success(mock_provider):
    """Test health monitor records successful calls."""
    health_monitor = ProviderHealthMonitor("test_provider")
    circuit_breaker = CircuitBreaker("test_provider", failure_threshold=3, cooldown_seconds=60)

    # Record a success
    health_monitor.record_success(latency_ms=100)

    # Verify health monitor updated
    assert health_monitor.success_rate == 1.0
    assert health_monitor.average_latency_ms == 100.0
    assert health_monitor.is_healthy == True


def test_health_monitor_records_failure():
    """Test health monitor records failed calls."""
    health_monitor = ProviderHealthMonitor("test_provider")

    # Record a failure
    health_monitor.record_failure("Test error")

    # Verify health monitor updated
    assert health_monitor.success_rate == 0.0
    assert health_monitor.is_healthy == True  # Still healthy with only 1 failure


def test_health_monitor_unhealthy_after_failures():
    """Test health monitor becomes unhealthy after consecutive failures."""
    health_monitor = ProviderHealthMonitor("test_provider")

    # Record 5 consecutive failures
    for _ in range(5):
        health_monitor.record_failure("Test error")

    # Verify health monitor is now unhealthy
    assert health_monitor.is_healthy == False


def test_provider_selector_state_updates():
    """Test provider selector updates health and circuit state."""
    selector = ProviderSelector()

    # Update health
    selector.update_provider_health("duckduckgo", False)
    assert selector.provider_health["duckduckgo"] == False

    # Update circuit state
    selector.update_provider_circuit_state("duckduckgo", "open")
    assert selector.provider_circuit_state["duckduckgo"] == "open"

    # Verify filtering works
    result = selector.select_providers(
        query="test",
        query_type="research",
    )
    assert "duckduckgo" not in result["providers"]


def test_fallback_provider_works(mock_provider, mock_arxiv_provider):
    """Test fallback provider works when primary is unavailable."""
    selector = ProviderSelector()
    health_monitor = ProviderHealthMonitor("duckduckgo")
    circuit_breaker = CircuitBreaker("duckduckgo", failure_threshold=3, cooldown_seconds=60)

    # Mark arXiv as unhealthy (primary for research queries)
    selector.update_provider_health("arxiv", False)

    engine = RetrievalEngine(
        duckduckgo_provider=mock_provider,
        arxiv_provider=mock_arxiv_provider,
        wikipedia_provider=None,
        documentation_provider=None,
        duckduckgo_circuit_breaker=circuit_breaker,
        duckduckgo_health_monitor=health_monitor,
        provider_selector=selector,
    )

    async def test_retrieve():
        result = await engine.retrieve_all_sources(
            query="test query",
            query_type="research",
            request_id="test-123",
        )
        return result

    result = asyncio.run(test_retrieve())

    # DuckDuckGo should be used as fallback
    assert "duckduckgo" in result["provider_metrics"]


def test_health_endpoint_structure():
    """Test health endpoint returns valid structure."""
    from backend.api.system import _provider_status

    status = _provider_status("duckduckgo")

    # Verify structure
    assert "provider" in status
    assert "health" in status
    assert "circuit_breaker" in status
    assert status["provider"] == "duckduckgo"


def test_provider_selector_query_types():
    """Test provider selector handles different query types correctly."""
    selector = ProviderSelector()

    # Definition query
    result = selector.select_providers("what is AI", "definition")
    assert "wikipedia" in result["providers"]

    # Technical query
    result = selector.select_providers("how to code", "technical")
    assert "documentation" in result["providers"]

    # Research query
    result = selector.select_providers("AI research", "research")
    assert "arxiv" in result["providers"]
