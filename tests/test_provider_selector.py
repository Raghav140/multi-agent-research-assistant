"""Tests for ProviderSelector integration with health and circuit breaker."""

import pytest
from backend.utils.provider_selector import ProviderSelector


def test_provider_selector_filters_unhealthy_provider():
    """Test provider selector filters out unhealthy providers."""
    selector = ProviderSelector()

    # Mark duckduckgo as unhealthy
    selector.update_provider_health("duckduckgo", False)

    # Select providers for technical query (should prefer documentation, duckduckgo, arxiv)
    result = selector.select_providers(
        query="how to use python",
        query_type="technical",
    )

    # duckduckgo should be filtered out
    assert "duckduckgo" not in result["providers"]
    assert "documentation" in result["providers"]


def test_provider_selector_filters_circuit_open_provider():
    """Test provider selector filters out providers with open circuit."""
    selector = ProviderSelector()

    # Mark wikipedia circuit as open
    selector.update_provider_circuit_state("wikipedia", "open")

    # Select providers for definition query (should prefer wikipedia, documentation, duckduckgo)
    result = selector.select_providers(
        query="what is machine learning",
        query_type="definition",
    )

    # wikipedia should be filtered out
    assert "wikipedia" not in result["providers"]
    assert "documentation" in result["providers"] or "duckduckgo" in result["providers"]


def test_provider_selector_definition_query():
    """Test provider selector for definition queries."""
    selector = ProviderSelector()

    result = selector.select_providers(
        query="what is quantum computing",
        query_type="definition",
    )

    # Should prefer wikipedia, documentation, duckduckgo
    assert "wikipedia" in result["providers"]
    assert len(result["providers"]) > 0
    assert "definition" in result["reason"].lower()


def test_provider_selector_technical_query():
    """Test provider selector for technical queries."""
    selector = ProviderSelector()

    result = selector.select_providers(
        query="how to implement REST API",
        query_type="technical",
    )

    # Should prefer documentation, duckduckgo, arxiv
    assert "documentation" in result["providers"]
    assert len(result["providers"]) > 0
    assert "technical" in result["reason"].lower()


def test_provider_selector_research_query():
    """Test provider selector for research queries."""
    selector = ProviderSelector()

    result = selector.select_providers(
        query="latest advances in transformer models",
        query_type="research",
    )

    # Should prefer arxiv, duckduckgo, documentation
    assert "arxiv" in result["providers"]
    assert len(result["providers"]) > 0
    assert "research" in result["reason"].lower()


def test_provider_selector_fallback_when_all_filtered():
    """Test provider selector returns empty list when all providers filtered."""
    selector = ProviderSelector()

    # Mark all providers as unhealthy
    selector.update_provider_health("duckduckgo", False)
    selector.update_provider_health("wikipedia", False)
    selector.update_provider_health("arxiv", False)
    selector.update_provider_health("documentation", False)

    result = selector.select_providers(
        query="test query",
        query_type="research",
    )

    # Should return empty list
    assert len(result["providers"]) == 0


def test_provider_selector_records_result():
    """Test provider selector records provider results."""
    selector = ProviderSelector()

    # Record a successful result
    selector.record_provider_result(
        provider="duckduckgo",
        success=True,
        sources_found=5,
        execution_time_ms=200,
    )

    # Check performance was updated
    perf = selector.provider_performance["duckduckgo"]
    assert perf["success_rate"] > 0.85  # Should be updated from baseline
    assert perf["avg_sources"] > 0


def test_provider_selector_updates_health():
    """Test provider selector health status updates."""
    selector = ProviderSelector()

    # Initially healthy
    assert selector.provider_health["duckduckgo"] == True

    # Mark as unhealthy
    selector.update_provider_health("duckduckgo", False)
    assert selector.provider_health["duckduckgo"] == False

    # Mark as healthy again
    selector.update_provider_health("duckduckgo", True)
    assert selector.provider_health["duckduckgo"] == True


def test_provider_selector_updates_circuit_state():
    """Test provider selector circuit state updates."""
    selector = ProviderSelector()

    # Initially closed
    assert selector.provider_circuit_state["wikipedia"] == "closed"

    # Mark as open
    selector.update_provider_circuit_state("wikipedia", "open")
    assert selector.provider_circuit_state["wikipedia"] == "open"

    # Mark as half_open
    selector.update_provider_circuit_state("wikipedia", "half_open")
    assert selector.provider_circuit_state["wikipedia"] == "half_open"
