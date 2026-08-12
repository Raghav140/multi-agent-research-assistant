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

# Singleton provider instances - initialized once at module import
_llm_provider: LLMProvider | None = None
_search_provider: SearchProvider | None = None
_arxiv_provider: ArxivProvider | None = None
_wikipedia_provider: WikipediaProvider | None = None


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
