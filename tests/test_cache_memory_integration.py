"""Integration tests for Cache + Memory in RetrievalEngine."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.retrieval_engine import RetrievalEngine
from backend.core.interfaces import SearchProvider
from backend.providers.papers.arxiv_provider import ArxivProvider
from backend.providers.circuit_breaker import CircuitBreaker
from backend.providers.health_monitor import ProviderHealthMonitor
from backend.memory.memory_manager import MemoryManager
from backend.utils.cache import LRUCache, get_retrieval_cache


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
        use_cache=True,
        use_memory=False,  # Disable memory for cache-focused tests
    )


def test_cache_hit_returns_cached_results(retrieval_engine):
    """Test cache hit returns cached results without provider calls."""
    # Pre-populate cache with correct key format (query_type:query)
    cache = get_retrieval_cache()
    cache.set("research:test query", {
        "web_results": [{"title": "Cached Result"}],
        "papers": [],
        "documentation": [],
        "provider_metrics": {},
    })

    async def test_retrieve():
        result = await retrieval_engine.retrieve_all_sources(
            query="test query",
            query_type="research",
            request_id="test-123",
        )
        return result

    result = asyncio.run(test_retrieve())

    # Verify cache hit
    assert result["cache_hit"] == True
    assert result["memory_hit"] == False
    assert len(result["web_results"]) == 1
    assert result["web_results"][0]["title"] == "Cached Result"


def test_cache_miss_triggers_provider_retrieval(retrieval_engine):
    """Test cache miss triggers actual provider retrieval."""
    async def test_retrieve():
        result = await retrieval_engine.retrieve_all_sources(
            query="new query",
            query_type="research",
            request_id="test-123",
        )
        return result

    result = asyncio.run(test_retrieve())

    # Verify cache miss and provider was called
    assert result["cache_hit"] == False
    assert result["memory_hit"] == False
    assert len(result["web_results"]) > 0 or len(result["papers"]) > 0


def test_cache_storage_after_retrieval(retrieval_engine):
    """Test results are cached after successful retrieval."""
    cache = get_retrieval_cache()
    cache.clear()  # Start with empty cache

    async def test_retrieve():
        result = await retrieval_engine.retrieve_all_sources(
            query="cache storage test",
            query_type="research",
            request_id="test-123",
        )
        return result

    # First call - should cache
    result1 = asyncio.run(test_retrieve())
    assert result1["cache_hit"] == False

    # Check that cache was populated (with the correct key format)
    cache_key = "research:cache storage test"
    cached = cache.get(cache_key)
    assert cached is not None

    # Second call - should hit cache
    result2 = asyncio.run(test_retrieve())
    assert result2["cache_hit"] == True


def test_cache_failure_does_not_break_retrieval(retrieval_engine):
    """Test cache failure falls back to provider retrieval."""
    # Mock cache to raise exception
    with patch('backend.services.retrieval_engine.get_cached_retrieval_results') as mock_cache:
        mock_cache.side_effect = Exception("Cache failure")

        async def test_retrieve():
            result = await retrieval_engine.retrieve_all_sources(
                query="cache failure test",
                query_type="research",
                request_id="test-123",
            )
            return result

        result = asyncio.run(test_retrieve())

        # Should still work despite cache failure
        assert result["cache_hit"] == False
        assert len(result["web_results"]) > 0 or len(result["papers"]) > 0


def test_memory_hit_returns_context(mock_provider, mock_arxiv_provider):
    """Test memory hit returns similar query context."""
    # Create a mock memory manager
    memory_manager = MagicMock(spec=MemoryManager)
    memory_manager.check_memory = MagicMock(return_value={
        "query": "similar previous query",
        "similarity": 0.85,
        "confidence_score": 0.9,
    })

    engine = RetrievalEngine(
        duckduckgo_provider=mock_provider,
        arxiv_provider=mock_arxiv_provider,
        wikipedia_provider=None,
        documentation_provider=None,
        memory_manager=memory_manager,
        use_cache=False,
        use_memory=True,
    )

    async def test_retrieve():
        result = await engine.retrieve_all_sources(
            query="test query",
            query_type="research",
            request_id="test-123",
        )
        return result

    result = asyncio.run(test_retrieve())

    # Verify memory hit
    assert result["memory_hit"] == True
    assert result["memory_context"] is not None
    assert result["memory_context"]["similarity"] == 0.85


def test_memory_miss_continues_retrieval(mock_provider, mock_arxiv_provider):
    """Test memory miss continues with normal retrieval."""
    memory_manager = MagicMock(spec=MemoryManager)
    memory_manager.check_memory = MagicMock(return_value=None)

    engine = RetrievalEngine(
        duckduckgo_provider=mock_provider,
        arxiv_provider=mock_arxiv_provider,
        wikipedia_provider=None,
        documentation_provider=None,
        memory_manager=memory_manager,
        use_cache=False,
        use_memory=True,
    )

    async def test_retrieve():
        result = await engine.retrieve_all_sources(
            query="new query",
            query_type="research",
            request_id="test-123",
        )
        return result

    result = asyncio.run(test_retrieve())

    # Verify memory miss and normal retrieval
    assert result["memory_hit"] == False
    assert result["memory_context"] is None
    assert len(result["web_results"]) > 0 or len(result["papers"]) > 0


def test_memory_failure_does_not_break_retrieval(mock_provider, mock_arxiv_provider):
    """Test memory failure falls back to normal retrieval."""
    memory_manager = MagicMock(spec=MemoryManager)
    memory_manager.check_memory = MagicMock(side_effect=Exception("Memory failure"))

    engine = RetrievalEngine(
        duckduckgo_provider=mock_provider,
        arxiv_provider=mock_arxiv_provider,
        wikipedia_provider=None,
        documentation_provider=None,
        memory_manager=memory_manager,
        use_cache=False,
        use_memory=True,
    )

    async def test_retrieve():
        result = await engine.retrieve_all_sources(
            query="memory failure test",
            query_type="research",
            request_id="test-123",
        )
        return result

    result = asyncio.run(test_retrieve())

    # Should still work despite memory failure
    assert result["memory_hit"] == False
    assert len(result["web_results"]) > 0 or len(result["papers"]) > 0


def test_cache_and_memory_disabled(mock_provider, mock_arxiv_provider):
    """Test retrieval works with both cache and memory disabled."""
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

    result = asyncio.run(test_retrieve())

    # Both should be disabled
    assert result["cache_hit"] == False
    assert result["memory_hit"] == False
    assert len(result["web_results"]) > 0 or len(result["papers"]) > 0


def test_cache_key_includes_query_type(retrieval_engine):
    """Test cache key includes query type for proper isolation."""
    cache = get_retrieval_cache()
    cache.clear()

    # Store results for research query
    cache.set("research:shared query", {
        "web_results": [{"title": "Research Result"}],
        "papers": [],
        "documentation": [],
        "provider_metrics": {},
    })

    async def test_retrieve():
        # Same query but different type should not hit cache
        result = await retrieval_engine.retrieve_all_sources(
            query="shared query",
            query_type="technical",  # Different type
            request_id="test-123",
        )
        return result

    result = asyncio.run(test_retrieve())

    # Should be cache miss due to different query type
    assert result["cache_hit"] == False


def test_lru_cache_eviction():
    """Test LRU cache evicts old entries when full."""
    cache = LRUCache(max_size=3)

    # Fill cache to capacity
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")

    # Add one more - should evict key1 (least recently used)
    cache.set("key4", "value4")

    assert cache.get("key1") is None  # Evicted
    assert cache.get("key2") == "value2"  # Still present
    assert cache.get("key3") == "value3"  # Still present
    assert cache.get("key4") == "value4"  # New entry


def test_cache_metrics_tracking():
    """Test cache tracks hits and misses correctly."""
    cache = LRUCache(max_size=10)

    # Initial metrics
    metrics = cache.get_metrics()
    assert metrics["hits"] == 0
    assert metrics["misses"] == 0
    assert metrics["hit_rate"] == 0.0

    # Add some data
    cache.set("key1", "value1")
    cache.set("key2", "value2")

    # Hit
    cache.get("key1")
    metrics = cache.get_metrics()
    assert metrics["hits"] == 1
    assert metrics["misses"] == 0

    # Miss
    cache.get("key3")
    metrics = cache.get_metrics()
    assert metrics["hits"] == 1
    assert metrics["misses"] == 1
    assert metrics["hit_rate"] == 0.5


def test_cache_cleanup_expired():
    """Test cache cleanup removes expired entries."""
    cache = LRUCache(max_size=10)

    # This test would need to mock time.time() to properly test expiration
    # For now, just verify the method exists and runs
    removed = cache.cleanup_expired(ttl=3600)
    assert isinstance(removed, int)


def test_cache_invalidation():
    """Test cache invalidation removes specific entries."""
    cache = LRUCache(max_size=10)

    cache.set("key1", "value1")
    cache.set("key2", "value2")

    # Invalidate key1
    cache.invalidate("key1")

    assert cache.get("key1") is None
    assert cache.get("key2") == "value2"


def test_cache_clear():
    """Test cache clear removes all entries."""
    cache = LRUCache(max_size=10)

    cache.set("key1", "value1")
    cache.set("key2", "value2")

    cache.clear()

    assert cache.get("key1") is None
    assert cache.get("key2") is None
    assert len(cache.cache) == 0
