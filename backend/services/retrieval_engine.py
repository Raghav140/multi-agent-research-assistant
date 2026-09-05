"""Multi-provider retrieval engine.

This module coordinates retrieval from multiple sources (DuckDuckGo, Wikipedia, arXiv, Documentation)
and provides unified results with provider metrics tracking, caching, and memory integration.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional
from backend.core.interfaces import SearchProvider
from backend.providers.papers.arxiv_provider import ArxivProvider
from backend.providers.search.wikipedia_provider import WikipediaProvider
from backend.providers.circuit_breaker import CircuitBreaker
from backend.providers.health_monitor import ProviderHealthMonitor
from backend.utils.provider_selector import ProviderSelector
from backend.utils.cache import (
    get_cached_provider_result,
    cache_provider_result,
    get_cached_retrieval_results,
    cache_retrieval_results,
    get_retrieval_cache,
)
from backend.memory.memory_manager import MemoryManager
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)

# Provider result limits (enforced at retrieval engine level)
DDG_NUM_RESULTS = 2
ARXIV_MAX_RESULTS = 1
WIKIPEDIA_NUM_RESULTS = 3
DOCUMENTATION_NUM_RESULTS = 3


class RetrievalEngine:
    """Multi-provider retrieval engine.

    This class coordinates retrieval from multiple providers and provides
    unified results with performance metrics for each provider.
    """

    def __init__(
        self,
        duckduckgo_provider: SearchProvider,
        arxiv_provider: ArxivProvider,
        wikipedia_provider: Optional[WikipediaProvider] = None,
        documentation_provider: Optional[SearchProvider] = None,
        duckduckgo_circuit_breaker: Optional[CircuitBreaker] = None,
        wikipedia_circuit_breaker: Optional[CircuitBreaker] = None,
        arxiv_circuit_breaker: Optional[CircuitBreaker] = None,
        documentation_circuit_breaker: Optional[CircuitBreaker] = None,
        duckduckgo_health_monitor: Optional[ProviderHealthMonitor] = None,
        wikipedia_health_monitor: Optional[ProviderHealthMonitor] = None,
        arxiv_health_monitor: Optional[ProviderHealthMonitor] = None,
        documentation_health_monitor: Optional[ProviderHealthMonitor] = None,
        provider_selector: Optional[ProviderSelector] = None,
        memory_manager: Optional[MemoryManager] = None,
        use_cache: bool = True,
        use_memory: bool = True,
    ):
        """Initialize the retrieval engine.

        Args:
            duckduckgo_provider: DuckDuckGo search provider
            arxiv_provider: arXiv paper provider
            wikipedia_provider: Wikipedia provider (optional)
            documentation_provider: Documentation provider (optional)
            duckduckgo_circuit_breaker: Circuit breaker for DuckDuckGo (optional)
            wikipedia_circuit_breaker: Circuit breaker for Wikipedia (optional)
            arxiv_circuit_breaker: Circuit breaker for arXiv (optional)
            documentation_circuit_breaker: Circuit breaker for Documentation (optional)
            duckduckgo_health_monitor: Health monitor for DuckDuckGo (optional)
            wikipedia_health_monitor: Health monitor for Wikipedia (optional)
            arxiv_health_monitor: Health monitor for arXiv (optional)
            documentation_health_monitor: Health monitor for Documentation (optional)
            provider_selector: Provider selector for adaptive provider selection (optional)
            memory_manager: Memory manager for research memory (optional)
            use_cache: Whether to use caching (default True)
            use_memory: Whether to use memory lookup (default True)
        """
        self.duckduckgo_provider = duckduckgo_provider
        self.arxiv_provider = arxiv_provider
        self.wikipedia_provider = wikipedia_provider
        self.documentation_provider = documentation_provider
        self.duckduckgo_circuit_breaker = duckduckgo_circuit_breaker
        self.wikipedia_circuit_breaker = wikipedia_circuit_breaker
        self.arxiv_circuit_breaker = arxiv_circuit_breaker
        self.documentation_circuit_breaker = documentation_circuit_breaker
        self.duckduckgo_health_monitor = duckduckgo_health_monitor
        self.wikipedia_health_monitor = wikipedia_health_monitor
        self.arxiv_health_monitor = arxiv_health_monitor
        self.documentation_health_monitor = documentation_health_monitor
        self.provider_selector = provider_selector
        self.memory_manager = memory_manager
        self.use_cache = use_cache
        self.use_memory = use_memory

        logger.info(
            "Retrieval engine initialized",
            extra={
                "has_wikipedia": wikipedia_provider is not None,
                "has_documentation": documentation_provider is not None,
                "has_circuit_breakers": all([
                    duckduckgo_circuit_breaker is not None,
                    wikipedia_circuit_breaker is not None,
                    arxiv_circuit_breaker is not None,
                    documentation_circuit_breaker is not None,
                ]),
                "has_health_monitors": all([
                    duckduckgo_health_monitor is not None,
                    wikipedia_health_monitor is not None,
                    arxiv_health_monitor is not None,
                    documentation_health_monitor is not None,
                ]),
                "has_provider_selector": provider_selector is not None,
                "has_memory_manager": memory_manager is not None,
                "use_cache": use_cache,
                "use_memory": use_memory,
            },
        )

    async def retrieve_all_sources(
        self,
        query: str,
        query_type: str = "research",
        request_id: Optional[str] = None,
        selected_providers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retrieve sources from all available providers with caching and memory.

        Args:
            query: Search query
            query_type: Query category (definition, technical, research)
            request_id: Request identifier for logging
            selected_providers: Optional provider selection override

        Returns:
            Dictionary with:
            - web_results: Combined web search results
            - papers: Academic papers from arXiv
            - documentation: Official documentation results
            - provider_metrics: Performance metrics per provider
            - cache_hit: Whether cache was hit
            - memory_hit: Whether memory was hit
        """
        start_time = time.time()
        cache_hit = False
        memory_hit = False

        logger.info(
            "Multi-provider retrieval started",
            extra={
                "request_id": request_id,
                "query": query,
                "query_type": query_type,
                "use_cache": self.use_cache,
                "use_memory": self.use_memory,
            },
        )

        # Check cache first if enabled
        if self.use_cache:
            cached_results = self._check_cache(query, query_type)
            if cached_results is not None:
                cache_hit = True
                logger.info(
                    "Cache hit - returning cached results",
                    extra={
                        "request_id": request_id,
                        "query": query,
                        "query_type": query_type,
                    },
                )
                return {
                    **cached_results,
                    "cache_hit": True,
                    "memory_hit": False,
                    "execution_time_ms": (time.time() - start_time) * 1000,
                }

        # Check memory for similar queries if enabled
        memory_context = None
        if self.use_memory and self.memory_manager:
            memory_context = self._check_memory(query, query_type)
            if memory_context is not None:
                memory_hit = True
                logger.info(
                    "Memory hit - found similar query",
                    extra={
                        "request_id": request_id,
                        "query": query,
                        "query_type": query_type,
                        "similar_query": memory_context.get("query"),
                        "similarity": memory_context.get("similarity"),
                    },
                )

        # Use caller-provided selection or run provider selector
        if selected_providers is None:
            if self.provider_selector:
                # Update provider selector with current health and circuit states
                self._update_provider_selector_state()

                provider_selection = self.provider_selector.select_providers(
                    query=query,
                    query_type=query_type,
                )
                selected_providers = provider_selection["providers"]
                selection_confidence = provider_selection["confidence"]
                selection_reason = provider_selection["reason"]

                logger.info(
                    "Provider selector used",
                    extra={
                        "request_id": request_id,
                        "selected_providers": selected_providers,
                        "selection_confidence": selection_confidence,
                        "selection_reason": selection_reason,
                    },
                )
            else:
                selected_providers = self._get_provider_priority(query_type)
                logger.info(
                    "Using default provider priority (no selector)",
                    extra={
                        "request_id": request_id,
                        "default_providers": selected_providers,
                    },
                )
        else:
            logger.info(
                "Using caller-provided provider selection",
                extra={
                    "request_id": request_id,
                    "selected_providers": selected_providers,
                },
            )

        # Execute provider retrievals in parallel
        provider_execution_start = time.time()
        tasks = []
        provider_names = []

        # DuckDuckGo (if selected)
        if "duckduckgo" in selected_providers:
            tasks.append(("duckduckgo", self._retrieve_duckduckgo(query, request_id)))
            provider_names.append("duckduckgo")

        # Wikipedia (if selected and available)
        if "wikipedia" in selected_providers and self.wikipedia_provider:
            tasks.append(("wikipedia", self._retrieve_wikipedia(query, request_id)))
            provider_names.append("wikipedia")

        # Documentation (if selected and available)
        if "documentation" in selected_providers and self.documentation_provider:
            tasks.append(("documentation", self._retrieve_documentation(query, request_id)))
            provider_names.append("documentation")

        # arXiv (if selected)
        if "arxiv" in selected_providers:
            tasks.append(("arxiv", self._retrieve_arxiv(query, request_id)))
            provider_names.append("arxiv")

        # Execute all tasks concurrently
        results = {}
        provider_metrics = {}

        if tasks:
            try:
                task_results = await asyncio.gather(
                    *[task for _, task in tasks],
                    return_exceptions=True,
                )

                for (provider_name, _), result in zip(tasks, task_results):
                    if isinstance(result, Exception):
                        logger.error(
                            f"{provider_name} retrieval failed: {str(result)}",
                            extra={
                                "request_id": request_id,
                                "provider": provider_name,
                                "error": str(result),
                            },
                        )
                        provider_metrics[provider_name] = {
                            "success": False,
                            "error": str(result),
                            "execution_time_ms": 0,
                            "results_count": 0,
                            "accepted_count": 0,
                        }
                    else:
                        results[provider_name] = result["results"]
                        provider_metrics[provider_name] = result["metrics"]
                        if self.provider_selector:
                            self.provider_selector.record_provider_result(
                                provider=provider_name,
                                success=result["metrics"].get("success", False),
                                sources_found=result["metrics"].get("results_count", 0),
                                execution_time_ms=result["metrics"].get("execution_time_ms", 0),
                            )

            except Exception as e:
                logger.error(
                    f"Concurrent retrieval failed: {str(e)}",
                    extra={
                        "request_id": request_id,
                        "error": str(e),
                    },
                )

        # Combine results by category
        web_results = []
        papers = []
        documentation = []

        # Add DuckDuckGo results to web
        if "duckduckgo" in results:
            web_results.extend(results["duckduckgo"])

        # Add Wikipedia results to web (for definition queries)
        if "wikipedia" in results:
            web_results.extend(results["wikipedia"])

        # Add Documentation results
        if "documentation" in results:
            documentation.extend(results["documentation"])

        # Add arXiv results to papers
        if "arxiv" in results:
            papers.extend(results["arxiv"])

        provider_execution_ms = (time.time() - provider_execution_start) * 1000
        execution_time = time.time() - start_time

        # Store results in cache if enabled and retrieval was successful
        if self.use_cache and web_results or papers or documentation:
            self._store_cache(query, query_type, {
                "web_results": web_results,
                "papers": papers,
                "documentation": documentation,
                "provider_metrics": provider_metrics,
            })

        logger.info(
            "Multi-provider retrieval completed",
            extra={
                "request_id": request_id,
                "query": query,
                "query_type": query_type,
                "provider_execution_ms": provider_execution_ms,
                "execution_time_ms": execution_time * 1000,
                "web_results_count": len(web_results),
                "papers_count": len(papers),
                "documentation_count": len(documentation),
                "providers_used": list(provider_metrics.keys()),
                "provider_metrics": provider_metrics,
                "cache_hit": cache_hit,
                "memory_hit": memory_hit,
            },
        )

        # Calculate provider statistics
        provider_count = len(provider_metrics)
        successful_provider_count = sum(1 for m in provider_metrics.values() if m.get("success", False))
        failed_provider_count = sum(1 for m in provider_metrics.values() if not m.get("success", False))
        provider_timeouts = sum(1 for m in provider_metrics.values() if "timeout" in m.get("error", "").lower())

        return {
            "web_results": web_results,
            "papers": papers,
            "documentation": documentation,
            "provider_metrics": provider_metrics,
            "cache_hit": cache_hit,
            "memory_hit": memory_hit,
            "memory_context": memory_context,
            "execution_time_ms": execution_time * 1000,
            "provider_execution_ms": provider_execution_ms,
            "cache_metrics": get_retrieval_cache().get_metrics() if self.use_cache else {},
            "memory_stats": self.memory_manager.get_memory_stats() if self.memory_manager and self.use_memory else {},
            "provider_count": provider_count,
            "successful_provider_count": successful_provider_count,
            "failed_provider_count": failed_provider_count,
            "provider_timeouts": provider_timeouts,
        }

    def _get_provider_priority(self, query_type: str) -> List[str]:
        """Get provider priority based on query type.

        Args:
            query_type: Query category

        Returns:
            List of provider names in priority order
        """
        if query_type == "definition":
            # Definition: Wikipedia first, then web (skip arXiv for faster response)
            priority = ["wikipedia", "duckduckgo"]
        elif query_type == "technical":
            # Technical: Documentation first, then web, then arXiv
            priority = ["documentation", "duckduckgo", "arxiv"]
        else:  # research
            # Research: arXiv first, then web, then documentation
            priority = ["arxiv", "duckduckgo", "documentation"]

        # Filter to available providers
        available = []
        if self.duckduckgo_provider:
            available.append("duckduckgo")
        if self.arxiv_provider:
            available.append("arxiv")
        if self.wikipedia_provider:
            available.append("wikipedia")
        if self.documentation_provider:
            available.append("documentation")

        # Return prioritized available providers
        return [p for p in priority if p in available]

    def _update_provider_selector_state(self) -> None:
        """Update provider selector with current health and circuit states."""
        if not self.provider_selector:
            return

        # Update health status from health monitors
        if self.duckduckgo_health_monitor:
            self.provider_selector.update_provider_health(
                "duckduckgo", self.duckduckgo_health_monitor.is_healthy
            )
        if self.wikipedia_health_monitor:
            self.provider_selector.update_provider_health(
                "wikipedia", self.wikipedia_health_monitor.is_healthy
            )
        if self.arxiv_health_monitor:
            self.provider_selector.update_provider_health(
                "arxiv", self.arxiv_health_monitor.is_healthy
            )
        if self.documentation_health_monitor:
            self.provider_selector.update_provider_health(
                "documentation", self.documentation_health_monitor.is_healthy
            )

        # Update circuit breaker states
        if self.duckduckgo_circuit_breaker:
            self.provider_selector.update_provider_circuit_state(
                "duckduckgo", self.duckduckgo_circuit_breaker.state.value
            )
        if self.wikipedia_circuit_breaker:
            self.provider_selector.update_provider_circuit_state(
                "wikipedia", self.wikipedia_circuit_breaker.state.value
            )
        if self.arxiv_circuit_breaker:
            self.provider_selector.update_provider_circuit_state(
                "arxiv", self.arxiv_circuit_breaker.state.value
            )
        if self.documentation_circuit_breaker:
            self.provider_selector.update_provider_circuit_state(
                "documentation", self.documentation_circuit_breaker.state.value
            )

    def _check_cache(self, query: str, query_type: str) -> Optional[Dict[str, Any]]:
        """Check cache for existing retrieval results.

        Args:
            query: Search query
            query_type: Query category

        Returns:
            Cached results if found, None otherwise
        """
        try:
            # Direct cache access with query_type prefix for better isolation
            cache = get_retrieval_cache()
            cache_key = f"{query_type}:{query}"
            cached = cache.get(cache_key)
            return cached
        except Exception as e:
            logger.error(
                f"Cache lookup failed: {str(e)}",
                extra={"query": query, "query_type": query_type, "error": str(e)},
            )
            return None

    def _store_cache(self, query: str, query_type: str, results: Dict[str, Any]) -> None:
        """Store retrieval results in cache.

        Args:
            query: Search query
            query_type: Query category
            results: Retrieval results to cache
        """
        try:
            # Direct cache access with query_type prefix for better isolation
            cache = get_retrieval_cache()
            cache_key = f"{query_type}:{query}"
            cache.set(cache_key, results)
        except Exception as e:
            logger.error(
                f"Cache storage failed: {str(e)}",
                extra={"query": query, "query_type": query_type, "error": str(e)},
            )

    def _check_memory(self, query: str, query_type: str) -> Optional[Dict[str, Any]]:
        """Check memory for similar queries.

        Args:
            query: Search query
            query_type: Query category

        Returns:
            Similar research record if found, None otherwise
        """
        try:
            if not self.memory_manager:
                return None
            return self.memory_manager.check_memory(query, query_type)
        except Exception as e:
            logger.error(
                f"Memory lookup failed: {str(e)}",
                extra={"query": query, "query_type": query_type, "error": str(e)},
            )
            return None

    async def _retrieve_duckduckgo(
        self,
        query: str,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve results from DuckDuckGo.

        Args:
            query: Search query
            request_id: Request identifier

        Returns:
            Dictionary with results and metrics
        """
        start_time = time.time()

        cached = get_cached_provider_result("duckduckgo", query)
        if cached is not None:
            execution_time = time.time() - start_time
            return {
                "results": cached,
                "metrics": {
                    "success": True,
                    "execution_time_ms": execution_time * 1000,
                    "results_count": len(cached),
                    "accepted_count": len(cached),
                    "cached": True,
                    "circuit_protected": self.duckduckgo_circuit_breaker is not None,
                    "health_monitored": self.duckduckgo_health_monitor is not None,
                },
            }

        try:
            provider_call_start = time.time()
            if self.duckduckgo_circuit_breaker:
                results = await self.duckduckgo_circuit_breaker.call(
                    self.duckduckgo_provider.search,
                    query=query,
                    num_results=DDG_NUM_RESULTS,
                    request_id=request_id,
                )
            else:
                results = await self.duckduckgo_provider.search(
                    query=query,
                    num_results=DDG_NUM_RESULTS,
                    request_id=request_id,
                )
            provider_call_ms = (time.time() - provider_call_start) * 1000

            cache_provider_result("duckduckgo", query, results)

            execution_time = time.time() - start_time

            # Record success to health monitor
            if self.duckduckgo_health_monitor:
                self.duckduckgo_health_monitor.record_success(execution_time * 1000)

            # Update provider selector state
            if self.provider_selector:
                self.provider_selector.update_provider_health(
                    "duckduckgo", self.duckduckgo_health_monitor.is_healthy
                )
                if self.duckduckgo_circuit_breaker:
                    self.provider_selector.update_provider_circuit_state(
                        "duckduckgo", self.duckduckgo_circuit_breaker.state.value
                    )

            return {
                "results": results,
                "metrics": {
                    "success": True,
                    "execution_time_ms": execution_time * 1000,
                    "results_count": len(results),
                    "accepted_count": len(results),
                    "circuit_protected": self.duckduckgo_circuit_breaker is not None,
                    "health_monitored": self.duckduckgo_health_monitor is not None,
                },
            }
        except Exception as e:
            execution_time = time.time() - start_time

            # Record failure to health monitor
            if self.duckduckgo_health_monitor:
                self.duckduckgo_health_monitor.record_failure(str(e))

            # Update provider selector state
            if self.provider_selector:
                self.provider_selector.update_provider_health(
                    "duckduckgo", self.duckduckgo_health_monitor.is_healthy
                )
                if self.duckduckgo_circuit_breaker:
                    self.provider_selector.update_provider_circuit_state(
                        "duckduckgo", self.duckduckgo_circuit_breaker.state.value
                    )

            return {
                "results": [],
                "metrics": {
                    "success": False,
                    "error": str(e),
                    "execution_time_ms": execution_time * 1000,
                    "results_count": 0,
                    "accepted_count": 0,
                    "circuit_protected": self.duckduckgo_circuit_breaker is not None,
                    "health_monitored": self.duckduckgo_health_monitor is not None,
                },
            }

    async def _retrieve_wikipedia(
        self,
        query: str,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve results from Wikipedia.

        Args:
            query: Search query
            request_id: Request identifier

        Returns:
            Dictionary with results and metrics
        """
        start_time = time.time()

        if not self.wikipedia_provider:
            return {
                "results": [],
                "metrics": {
                    "success": False,
                    "error": "Wikipedia provider not available",
                    "execution_time_ms": 0,
                    "results_count": 0,
                    "accepted_count": 0,
                    "circuit_protected": False,
                    "health_monitored": False,
                },
            }

        try:
            provider_call_start = time.time()
            if self.wikipedia_circuit_breaker:
                # Use circuit breaker if available
                results = await self.wikipedia_circuit_breaker.call(
                    self.wikipedia_provider.search,
                    query=query,
                    num_results=WIKIPEDIA_NUM_RESULTS,
                    request_id=request_id,
                )
            else:
                results = await self.wikipedia_provider.search(
                    query=query,
                    num_results=WIKIPEDIA_NUM_RESULTS,
                    request_id=request_id,
                )
            provider_call_ms = (time.time() - provider_call_start) * 1000

            execution_time = time.time() - start_time

            # Record success to health monitor
            if self.wikipedia_health_monitor:
                self.wikipedia_health_monitor.record_success(execution_time * 1000)

            # Update provider selector state
            if self.provider_selector:
                self.provider_selector.update_provider_health(
                    "wikipedia", self.wikipedia_health_monitor.is_healthy
                )
                if self.wikipedia_circuit_breaker:
                    self.provider_selector.update_provider_circuit_state(
                        "wikipedia", self.wikipedia_circuit_breaker.state.value
                    )

            return {
                "results": results,
                "metrics": {
                    "success": True,
                    "execution_time_ms": execution_time * 1000,
                    "results_count": len(results),
                    "accepted_count": len(results),
                    "circuit_protected": self.wikipedia_circuit_breaker is not None,
                    "health_monitored": self.wikipedia_health_monitor is not None,
                },
            }
        except Exception as e:
            execution_time = time.time() - start_time

            # Record failure to health monitor
            if self.wikipedia_health_monitor:
                self.wikipedia_health_monitor.record_failure(str(e))

            # Update provider selector state
            if self.provider_selector:
                self.provider_selector.update_provider_health(
                    "wikipedia", self.wikipedia_health_monitor.is_healthy
                )
                if self.wikipedia_circuit_breaker:
                    self.provider_selector.update_provider_circuit_state(
                        "wikipedia", self.wikipedia_circuit_breaker.state.value
                    )

            return {
                "results": [],
                "metrics": {
                    "success": False,
                    "error": str(e),
                    "execution_time_ms": execution_time * 1000,
                    "results_count": 0,
                    "accepted_count": 0,
                    "circuit_protected": self.wikipedia_circuit_breaker is not None,
                    "health_monitored": self.wikipedia_health_monitor is not None,
                },
            }

    async def _retrieve_documentation(
        self,
        query: str,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve results from documentation provider.

        Args:
            query: Search query
            request_id: Request identifier

        Returns:
            Dictionary with results and metrics
        """
        start_time = time.time()

        if not self.documentation_provider:
            return {
                "results": [],
                "metrics": {
                    "success": False,
                    "error": "Documentation provider not available",
                    "execution_time_ms": 0,
                    "results_count": 0,
                    "accepted_count": 0,
                    "circuit_protected": False,
                    "health_monitored": False,
                },
            }

        try:
            provider_call_start = time.time()
            if self.documentation_circuit_breaker:
                # Use circuit breaker if available
                results = await self.documentation_circuit_breaker.call(
                    self.documentation_provider.search,
                    query=query,
                    num_results=DOCUMENTATION_NUM_RESULTS,
                    request_id=request_id,
                )
            else:
                results = await self.documentation_provider.search(
                    query=query,
                    num_results=DOCUMENTATION_NUM_RESULTS,
                    request_id=request_id,
                )
            provider_call_ms = (time.time() - provider_call_start) * 1000

            execution_time = time.time() - start_time

            # Record success to health monitor
            if self.documentation_health_monitor:
                self.documentation_health_monitor.record_success(execution_time * 1000)

            # Update provider selector state
            if self.provider_selector:
                self.provider_selector.update_provider_health(
                    "documentation", self.documentation_health_monitor.is_healthy
                )
                if self.documentation_circuit_breaker:
                    self.provider_selector.update_provider_circuit_state(
                        "documentation", self.documentation_circuit_breaker.state.value
                    )

            return {
                "results": results,
                "metrics": {
                    "success": True,
                    "execution_time_ms": execution_time * 1000,
                    "results_count": len(results),
                    "accepted_count": len(results),
                    "circuit_protected": self.documentation_circuit_breaker is not None,
                    "health_monitored": self.documentation_health_monitor is not None,
                },
            }
        except Exception as e:
            execution_time = time.time() - start_time

            # Record failure to health monitor
            if self.documentation_health_monitor:
                self.documentation_health_monitor.record_failure(str(e))

            # Update provider selector state
            if self.provider_selector:
                self.provider_selector.update_provider_health(
                    "documentation", self.documentation_health_monitor.is_healthy
                )
                if self.documentation_circuit_breaker:
                    self.provider_selector.update_provider_circuit_state(
                        "documentation", self.documentation_circuit_breaker.state.value
                    )

            return {
                "results": [],
                "metrics": {
                    "success": False,
                    "error": str(e),
                    "execution_time_ms": execution_time * 1000,
                    "results_count": 0,
                    "accepted_count": 0,
                    "circuit_protected": self.documentation_circuit_breaker is not None,
                    "health_monitored": self.documentation_health_monitor is not None,
                },
            }

    async def _retrieve_arxiv(
        self,
        query: str,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve results from arXiv.

        Args:
            query: Search query
            request_id: Request identifier

        Returns:
            Dictionary with results and metrics
        """
        start_time = time.time()

        try:
            provider_call_start = time.time()
            if self.arxiv_circuit_breaker:
                # Use circuit breaker if available
                results = await self.arxiv_circuit_breaker.call(
                    self.arxiv_provider.search,
                    query=query,
                    max_results=ARXIV_MAX_RESULTS,
                    request_id=request_id,
                )
            else:
                results = await self.arxiv_provider.search(
                    query=query,
                    max_results=ARXIV_MAX_RESULTS,
                    request_id=request_id,
                )
            provider_call_ms = (time.time() - provider_call_start) * 1000

            execution_time = time.time() - start_time

            # Record success to health monitor
            if self.arxiv_health_monitor:
                self.arxiv_health_monitor.record_success(execution_time * 1000)

            # Update provider selector state
            if self.provider_selector:
                self.provider_selector.update_provider_health(
                    "arxiv", self.arxiv_health_monitor.is_healthy
                )
                if self.arxiv_circuit_breaker:
                    self.provider_selector.update_provider_circuit_state(
                        "arxiv", self.arxiv_circuit_breaker.state.value
                    )

            return {
                "results": results,
                "metrics": {
                    "success": True,
                    "execution_time_ms": execution_time * 1000,
                    "results_count": len(results),
                    "accepted_count": len(results),
                    "circuit_protected": self.arxiv_circuit_breaker is not None,
                    "health_monitored": self.arxiv_health_monitor is not None,
                },
            }
        except Exception as e:
            execution_time = time.time() - start_time

            # Record failure to health monitor
            if self.arxiv_health_monitor:
                self.arxiv_health_monitor.record_failure(str(e))

            # Update provider selector state
            if self.provider_selector:
                self.provider_selector.update_provider_health(
                    "arxiv", self.arxiv_health_monitor.is_healthy
                )
                if self.arxiv_circuit_breaker:
                    self.provider_selector.update_provider_circuit_state(
                        "arxiv", self.arxiv_circuit_breaker.state.value
                    )

            return {
                "results": [],
                "metrics": {
                    "success": False,
                    "error": str(e),
                    "execution_time_ms": execution_time * 1000,
                    "results_count": 0,
                    "accepted_count": 0,
                    "circuit_protected": self.arxiv_circuit_breaker is not None,
                    "health_monitored": self.arxiv_health_monitor is not None,
                },
            }
