"""Lightweight local cache for retrieval results.

This module provides a simple in-memory cache for query embeddings,
retrieval results, and processed rankings.
"""

import hashlib
import json
import time
from typing import Any, Optional, Dict
from collections import OrderedDict
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


class LRUCache:
    """Simple LRU (Least Recently Used) cache implementation.

    This cache has a maximum size and evicts the least recently used
    items when the limit is exceeded.
    """

    def __init__(self, max_size: int = 100):
        """Initialize the LRU cache.

        Args:
            max_size: Maximum number of items to store
        """
        self.max_size = max_size
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.time_saved = 0.0  # Total time saved by cache hits in seconds

    def _make_key(self, key: str) -> str:
        """Create a hash-based key from the input string.

        Args:
            key: Input string to hash

        Returns:
            Hashed key string
        """
        return hashlib.md5(key.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Get an item from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value if found, None otherwise
        """
        hashed_key = self._make_key(key)

        if hashed_key in self.cache:
            # Move to end (most recently used)
            value, timestamp = self.cache.pop(hashed_key)
            self.cache[hashed_key] = (value, timestamp)
            self.hits += 1
            logger.debug(f"Cache hit for key: {key[:50]}")
            return value
        else:
            self.misses += 1
            logger.debug(f"Cache miss for key: {key[:50]}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set an item in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (optional)
        """
        hashed_key = self._make_key(key)
        timestamp = time.time()

        # Remove if exists (will be re-added at end)
        if hashed_key in self.cache:
            self.cache.pop(hashed_key)

        # Evict if at capacity
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)

        self.cache[hashed_key] = (value, timestamp)
        logger.debug(f"Cache set for key: {key[:50]}")

    def invalidate(self, key: str) -> None:
        """Invalidate a specific cache entry.

        Args:
            key: Cache key to invalidate
        """
        hashed_key = self._make_key(key)
        if hashed_key in self.cache:
            del self.cache[hashed_key]
            logger.debug(f"Cache invalidated for key: {key[:50]}")

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        logger.info("Cache cleared")

    def cleanup_expired(self, ttl: float = 3600) -> int:
        """Remove expired entries based on TTL.

        Args:
            ttl: Time to live in seconds (default 1 hour)

        Returns:
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = []

        for hashed_key, (value, timestamp) in self.cache.items():
            if current_time - timestamp > ttl:
                expired_keys.append(hashed_key)

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics.

        Returns:
            Dictionary with metrics:
            - size: Current cache size
            - max_size: Maximum cache size
            - hits: Number of cache hits
            - misses: Number of cache misses
            - hit_rate: Cache hit rate (0-1)
            - time_saved_ms: Total time saved by cache hits
        """
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0.0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "time_saved_ms": self.time_saved * 1000,
        }


# Global cache instances
_embedding_cache: Optional[LRUCache] = None
_retrieval_cache: Optional[LRUCache] = None
_ranking_cache: Optional[LRUCache] = None
_provider_cache: Optional[LRUCache] = None
_fusion_cache: Optional[LRUCache] = None
_memory_cache: Optional[LRUCache] = None


def get_embedding_cache() -> LRUCache:
    """Get the global embedding cache instance.

    Returns:
        LRUCache instance for embeddings
    """
    global _embedding_cache
    if _embedding_cache is None:
        _embedding_cache = LRUCache(max_size=200)
        logger.info("Embedding cache initialized (max_size=200)")
    return _embedding_cache


def get_retrieval_cache() -> LRUCache:
    """Get the global retrieval cache instance.

    Returns:
        LRUCache instance for retrieval results
    """
    global _retrieval_cache
    if _retrieval_cache is None:
        _retrieval_cache = LRUCache(max_size=100)
        logger.info("Retrieval cache initialized (max_size=100)")
    return _retrieval_cache


def get_ranking_cache() -> LRUCache:
    """Get the global ranking cache instance.

    Returns:
        LRUCache instance for ranking results
    """
    global _ranking_cache
    if _ranking_cache is None:
        _ranking_cache = LRUCache(max_size=100)
        logger.info("Ranking cache initialized (max_size=100)")
    return _ranking_cache


def get_provider_cache() -> LRUCache:
    """Get the global provider cache instance.

    Returns:
        LRUCache instance for provider results
    """
    global _provider_cache
    if _provider_cache is None:
        _provider_cache = LRUCache(max_size=150)
        logger.info("Provider cache initialized (max_size=150)")
    return _provider_cache


def get_fusion_cache() -> LRUCache:
    """Get the global fusion cache instance.

    Returns:
        LRUCache instance for fusion results
    """
    global _fusion_cache
    if _fusion_cache is None:
        _fusion_cache = LRUCache(max_size=100)
        logger.info("Fusion cache initialized (max_size=100)")
    return _fusion_cache


def get_memory_cache() -> LRUCache:
    """Get the global memory cache instance.

    Returns:
        LRUCache instance for memory lookup results
    """
    global _memory_cache
    if _memory_cache is None:
        _memory_cache = LRUCache(max_size=50)
        logger.info("Memory cache initialized (max_size=50)")
    return _memory_cache


def cache_query_embedding(query: str, embedding: Any) -> None:
    """Cache a query embedding.

    Args:
        query: Query string
        embedding: Embedding vector
    """
    cache = get_embedding_cache()
    cache.set(query, embedding)


def get_cached_query_embedding(query: str) -> Optional[Any]:
    """Get a cached query embedding.

    Args:
        query: Query string

    Returns:
        Cached embedding if found, None otherwise
    """
    cache = get_embedding_cache()
    return cache.get(query)


def cache_retrieval_results(query: str, results: list[dict[str, Any]]) -> None:
    """Cache retrieval results.

    Args:
        query: Query string
        results: Retrieval results to cache
    """
    cache = get_retrieval_cache()
    # Create a hashable key from query and result count
    key = f"{query}|{len(results)}"
    cache.set(key, results)


def get_cached_retrieval_results(query: str, expected_count: int) -> Optional[list[dict[str, Any]]]:
    """Get cached retrieval results.

    Args:
        query: Query string
        expected_count: Expected number of results

    Returns:
        Cached results if found, None otherwise
    """
    cache = get_retrieval_cache()
    key = f"{query}|{expected_count}"
    return cache.get(key)


def cache_ranking_results(query: str, ranked_results: tuple) -> None:
    """Cache ranking results.

    Args:
        query: Query string
        ranked_results: Tuple of (web_results, papers, metrics)
    """
    cache = get_ranking_cache()
    # Create a hashable key from query
    cache.set(query, ranked_results)


def get_cached_ranking_results(query: str) -> Optional[tuple]:
    """Get cached ranking results.

    Args:
        query: Query string

    Returns:
        Cached ranking results if found, None otherwise
    """
    cache = get_ranking_cache()
    return cache.get(query)


def get_all_cache_metrics() -> Dict[str, Any]:
    """Get metrics from all cache instances.

    Returns:
        Dictionary with metrics for all caches
    """
    return {
        "embedding_cache": get_embedding_cache().get_metrics(),
        "retrieval_cache": get_retrieval_cache().get_metrics(),
        "ranking_cache": get_ranking_cache().get_metrics(),
        "provider_cache": get_provider_cache().get_metrics(),
        "fusion_cache": get_fusion_cache().get_metrics(),
        "memory_cache": get_memory_cache().get_metrics(),
    }


def clear_all_caches() -> None:
    """Clear all cache instances."""
    get_embedding_cache().clear()
    get_retrieval_cache().clear()
    get_ranking_cache().clear()
    get_provider_cache().clear()
    get_fusion_cache().clear()
    get_memory_cache().clear()
    logger.info("All caches cleared")


def cleanup_expired_caches(ttl: float = 3600) -> Dict[str, int]:
    """Clean up expired entries in all caches.

    Args:
        ttl: Time to live in seconds (default 1 hour)

    Returns:
        Dictionary with cleanup counts for each cache
    """
    return {
        "embedding_cache": get_embedding_cache().cleanup_expired(ttl),
        "retrieval_cache": get_retrieval_cache().cleanup_expired(ttl),
        "ranking_cache": get_ranking_cache().cleanup_expired(ttl),
        "provider_cache": get_provider_cache().cleanup_expired(ttl),
        "fusion_cache": get_fusion_cache().cleanup_expired(ttl),
        "memory_cache": get_memory_cache().cleanup_expired(ttl),
    }


# Helper functions for new cache types
def cache_provider_result(provider: str, query: str, results: list) -> None:
    """Cache provider search results.

    Args:
        provider: Provider name
        query: Search query
        results: Provider results
    """
    cache = get_provider_cache()
    key = f"{provider}:{query}"
    cache.set(key, results)


def get_cached_provider_result(provider: str, query: str) -> Optional[list]:
    """Get cached provider results.

    Args:
        provider: Provider name
        query: Search query

    Returns:
        Cached results if found, None otherwise
    """
    cache = get_provider_cache()
    key = f"{provider}:{query}"
    return cache.get(key)


def cache_fusion_result(query: str, fusion_result: dict) -> None:
    """Cache evidence fusion result.

    Args:
        query: Search query
        fusion_result: Fusion result dictionary
    """
    cache = get_fusion_cache()
    cache.set(query, fusion_result)


def get_cached_fusion_result(query: str) -> Optional[dict]:
    """Get cached fusion result.

    Args:
        query: Search query

    Returns:
        Cached fusion result if found, None otherwise
    """
    cache = get_fusion_cache()
    return cache.get(query)


def cache_memory_lookup(query: str, memory_result: dict) -> None:
    """Cache memory lookup result.

    Args:
        query: Search query
        memory_result: Memory lookup result
    """
    cache = get_memory_cache()
    cache.set(query, memory_result)


def get_cached_memory_lookup(query: str) -> Optional[dict]:
    """Get cached memory lookup result.

    Args:
        query: Search query

    Returns:
        Cached memory result if found, None otherwise
    """
    cache = get_memory_cache()
    return cache.get(query)
