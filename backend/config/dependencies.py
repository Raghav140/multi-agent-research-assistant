"""Dependency injection for FastAPI.

This module provides centralized dependency injection for all providers,
ensuring singleton behavior during application lifetime.
"""

from typing import AsyncGenerator

from backend.core.interfaces import LLMProvider, SearchProvider
from backend.providers.llm.ollama_provider import OllamaProvider
from backend.providers.papers.arxiv_provider import ArxivProvider
from backend.providers.search.duckduckgo_provider import DuckDuckGoProvider
from backend.providers.search.wikipedia_provider import WikipediaProvider
from backend.providers.search.documentation_provider import DocumentationProvider
from backend.providers.circuit_breaker import CircuitBreaker
from backend.providers.health_monitor import ProviderHealthMonitor
from backend.services.retrieval_engine import RetrievalEngine
from backend.utils.provider_selector import ProviderSelector
from backend.memory.memory_manager import MemoryManager

# Singleton provider instances - initialized once at module import
_llm_provider: LLMProvider | None = None
_search_provider: SearchProvider | None = None
_arxiv_provider: ArxivProvider | None = None
_wikipedia_provider: WikipediaProvider | None = None
_documentation_provider: DocumentationProvider | None = None
_retrieval_engine: RetrievalEngine | None = None

# Circuit breaker instances
_duckduckgo_circuit_breaker: CircuitBreaker | None = None
_wikipedia_circuit_breaker: CircuitBreaker | None = None
_arxiv_circuit_breaker: CircuitBreaker | None = None
_documentation_circuit_breaker: CircuitBreaker | None = None

# Health monitor instances
_duckduckgo_health_monitor: ProviderHealthMonitor | None = None
_wikipedia_health_monitor: ProviderHealthMonitor | None = None
_arxiv_health_monitor: ProviderHealthMonitor | None = None
_documentation_health_monitor: ProviderHealthMonitor | None = None

# Provider selector instance
_provider_selector: ProviderSelector | None = None

# Memory manager instance
_memory_manager: MemoryManager | None = None


def get_llm_provider() -> LLMProvider:
    """Get singleton LLM provider instance.

    Returns:
        LLM provider instance (OllamaProvider)
    """
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = OllamaProvider()
    return _llm_provider


def get_search_provider() -> SearchProvider:
    """Get singleton search provider instance.

    Returns:
        Search provider instance (DuckDuckGoProvider)
    """
    global _search_provider
    if _search_provider is None:
        _search_provider = DuckDuckGoProvider()
    return _search_provider


def get_arxiv_provider() -> ArxivProvider:
    """Get singleton arXiv provider instance.

    Returns:
        arXiv provider instance (ArxivProvider)
    """
    global _arxiv_provider
    if _arxiv_provider is None:
        _arxiv_provider = ArxivProvider()
    return _arxiv_provider


def get_wikipedia_provider() -> WikipediaProvider:
    """Get singleton Wikipedia provider instance.

    Returns:
        Wikipedia provider instance (WikipediaProvider)
    """
    global _wikipedia_provider
    if _wikipedia_provider is None:
        _wikipedia_provider = WikipediaProvider()
    return _wikipedia_provider


def get_documentation_provider() -> DocumentationProvider:
    """Get singleton Documentation provider instance.

    Returns:
        Documentation provider instance (DocumentationProvider)
    """
    global _documentation_provider
    if _documentation_provider is None:
        _documentation_provider = DocumentationProvider()
    return _documentation_provider


def get_retrieval_engine() -> RetrievalEngine:
    """Get singleton RetrievalEngine instance.

    Returns:
        RetrievalEngine instance with all providers
    """
    global _retrieval_engine
    if _retrieval_engine is None:
        _retrieval_engine = RetrievalEngine(
            duckduckgo_provider=get_search_provider(),
            arxiv_provider=get_arxiv_provider(),
            wikipedia_provider=get_wikipedia_provider(),
            documentation_provider=get_documentation_provider(),
            duckduckgo_circuit_breaker=get_duckduckgo_circuit_breaker(),
            wikipedia_circuit_breaker=get_wikipedia_circuit_breaker(),
            arxiv_circuit_breaker=get_arxiv_circuit_breaker(),
            documentation_circuit_breaker=get_documentation_circuit_breaker(),
            duckduckgo_health_monitor=get_duckduckgo_health_monitor(),
            wikipedia_health_monitor=get_wikipedia_health_monitor(),
            arxiv_health_monitor=get_arxiv_health_monitor(),
            documentation_health_monitor=get_documentation_health_monitor(),
            provider_selector=get_provider_selector(),
            memory_manager=get_memory_manager(),
            use_cache=True,
            use_memory=True,
        )
    return _retrieval_engine


def get_duckduckgo_circuit_breaker() -> CircuitBreaker:
    """Get singleton DuckDuckGo circuit breaker instance.

    Returns:
        CircuitBreaker instance for DuckDuckGo provider
    """
    global _duckduckgo_circuit_breaker
    if _duckduckgo_circuit_breaker is None:
        _duckduckgo_circuit_breaker = CircuitBreaker(
            provider_name="duckduckgo",
            failure_threshold=3,
            cooldown_seconds=60,
            timeout_seconds=30,
        )
    return _duckduckgo_circuit_breaker


def get_wikipedia_circuit_breaker() -> CircuitBreaker:
    """Get singleton Wikipedia circuit breaker instance.

    Returns:
        CircuitBreaker instance for Wikipedia provider
    """
    global _wikipedia_circuit_breaker
    if _wikipedia_circuit_breaker is None:
        _wikipedia_circuit_breaker = CircuitBreaker(
            provider_name="wikipedia",
            failure_threshold=3,
            cooldown_seconds=60,
            timeout_seconds=30,
        )
    return _wikipedia_circuit_breaker


def get_arxiv_circuit_breaker() -> CircuitBreaker:
    """Get singleton arXiv circuit breaker instance.

    Returns:
        CircuitBreaker instance for arXiv provider
    """
    global _arxiv_circuit_breaker
    if _arxiv_circuit_breaker is None:
        _arxiv_circuit_breaker = CircuitBreaker(
            provider_name="arxiv",
            failure_threshold=3,
            cooldown_seconds=60,
            timeout_seconds=30,
        )
    return _arxiv_circuit_breaker


def get_documentation_circuit_breaker() -> CircuitBreaker:
    """Get singleton Documentation circuit breaker instance.

    Returns:
        CircuitBreaker instance for Documentation provider
    """
    global _documentation_circuit_breaker
    if _documentation_circuit_breaker is None:
        _documentation_circuit_breaker = CircuitBreaker(
            provider_name="documentation",
            failure_threshold=3,
            cooldown_seconds=60,
            timeout_seconds=30,
        )
    return _documentation_circuit_breaker


def get_duckduckgo_health_monitor() -> ProviderHealthMonitor:
    """Get singleton DuckDuckGo health monitor instance.

    Returns:
        ProviderHealthMonitor instance for DuckDuckGo provider
    """
    global _duckduckgo_health_monitor
    if _duckduckgo_health_monitor is None:
        _duckduckgo_health_monitor = ProviderHealthMonitor(provider_name="duckduckgo")
    return _duckduckgo_health_monitor


def get_wikipedia_health_monitor() -> ProviderHealthMonitor:
    """Get singleton Wikipedia health monitor instance.

    Returns:
        ProviderHealthMonitor instance for Wikipedia provider
    """
    global _wikipedia_health_monitor
    if _wikipedia_health_monitor is None:
        _wikipedia_health_monitor = ProviderHealthMonitor(provider_name="wikipedia")
    return _wikipedia_health_monitor


def get_arxiv_health_monitor() -> ProviderHealthMonitor:
    """Get singleton arXiv health monitor instance.

    Returns:
        ProviderHealthMonitor instance for arXiv provider
    """
    global _arxiv_health_monitor
    if _arxiv_health_monitor is None:
        _arxiv_health_monitor = ProviderHealthMonitor(provider_name="arxiv")
    return _arxiv_health_monitor


def get_documentation_health_monitor() -> ProviderHealthMonitor:
    """Get singleton Documentation health monitor instance.

    Returns:
        ProviderHealthMonitor instance for Documentation provider
    """
    global _documentation_health_monitor
    if _documentation_health_monitor is None:
        _documentation_health_monitor = ProviderHealthMonitor(provider_name="documentation")
    return _documentation_health_monitor


def get_provider_selector() -> ProviderSelector:
    """Get singleton ProviderSelector instance.

    Returns:
        ProviderSelector instance for adaptive provider selection
    """
    global _provider_selector
    if _provider_selector is None:
        _provider_selector = ProviderSelector()
    return _provider_selector


def get_memory_manager() -> MemoryManager:
    """Get singleton MemoryManager instance.

    Returns:
        MemoryManager instance for research memory
    """
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


async def get_db() -> AsyncGenerator:
    """
    Get database session.

    Yields:
        Database session
    """
    # TODO: Implement database session management
    yield None


async def get_redis() -> AsyncGenerator:
    """
    Get Redis client.

    Yields:
        Redis client
    """
    # TODO: Implement Redis client management
    yield None
