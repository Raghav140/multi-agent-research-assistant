"""Multi-provider retrieval engine.

This module coordinates retrieval from multiple sources (DuckDuckGo, Wikipedia, arXiv, Documentation)
and provides unified results with provider metrics tracking.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional
from backend.core.interfaces import SearchProvider
from backend.providers.papers.arxiv_provider import ArxivProvider
from backend.providers.search.wikipedia_provider import WikipediaProvider
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


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
    ):
        """Initialize the retrieval engine.

        Args:
            duckduckgo_provider: DuckDuckGo search provider
            arxiv_provider: arXiv paper provider
            wikipedia_provider: Wikipedia provider (optional)
            documentation_provider: Documentation provider (optional)
        """
        self.duckduckgo_provider = duckduckgo_provider
        self.arxiv_provider = arxiv_provider
        self.wikipedia_provider = wikipedia_provider
        self.documentation_provider = documentation_provider

        logger.info(
            "Retrieval engine initialized",
            extra={
                "has_wikipedia": wikipedia_provider is not None,
                "has_documentation": documentation_provider is not None,
            },
        )

    async def retrieve_all_sources(
        self,
        query: str,
        query_type: str = "research",
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve sources from all available providers.

        Args:
            query: Search query
            query_type: Query category (definition, technical, research)
            request_id: Request identifier for logging

        Returns:
            Dictionary with:
            - web_results: Combined web search results
            - papers: Academic papers from arXiv
            - documentation: Official documentation results
            - provider_metrics: Performance metrics per provider
        """
        start_time = time.time()

        logger.info(
            "Multi-provider retrieval started",
            extra={
                "request_id": request_id,
                "query": query,
                "query_type": query_type,
            },
        )

        # Determine provider priority based on query type
        provider_priority = self._get_provider_priority(query_type)

        # Execute provider retrievals in parallel
        tasks = []
        provider_names = []

        # DuckDuckGo (always included)
        tasks.append(("duckduckgo", self._retrieve_duckduckgo(query, request_id)))
        provider_names.append("duckduckgo")

        # Wikipedia (for definition queries)
        if self.wikipedia_provider and query_type == "definition":
            tasks.append(("wikipedia", self._retrieve_wikipedia(query, request_id)))
            provider_names.append("wikipedia")

        # Documentation (for technical queries)
        if self.documentation_provider and query_type == "technical":
            tasks.append(("documentation", self._retrieve_documentation(query, request_id)))
            provider_names.append("documentation")

        # arXiv (for research queries)
        if query_type == "research":
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

        execution_time = time.time() - start_time

        logger.info(
            "Multi-provider retrieval completed",
            extra={
                "request_id": request_id,
                "query": query,
                "query_type": query_type,
                "execution_time_ms": execution_time * 1000,
                "web_results_count": len(web_results),
                "papers_count": len(papers),
                "documentation_count": len(documentation),
                "providers_used": list(provider_metrics.keys()),
                "provider_metrics": provider_metrics,
            },
        )

        return {
            "web_results": web_results,
            "papers": papers,
            "documentation": documentation,
            "provider_metrics": provider_metrics,
            "execution_time_ms": execution_time * 1000,
        }

    def _get_provider_priority(self, query_type: str) -> List[str]:
        """Get provider priority based on query type.

        Args:
            query_type: Query category

        Returns:
            List of provider names in priority order
        """
        if query_type == "definition":
            # Definition: Wikipedia first, then documentation, then web
            priority = ["wikipedia", "documentation", "duckduckgo"]
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

        try:
            results = await self.duckduckgo_provider.search(
                query=query,
                num_results=10,
                request_id=request_id,
            )

            execution_time = time.time() - start_time

            return {
                "results": results,
                "metrics": {
                    "success": True,
                    "execution_time_ms": execution_time * 1000,
                    "results_count": len(results),
                    "accepted_count": len(results),
                },
            }
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "results": [],
                "metrics": {
                    "success": False,
                    "error": str(e),
                    "execution_time_ms": execution_time * 1000,
                    "results_count": 0,
                    "accepted_count": 0,
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
                },
            }

        try:
            results = await self.wikipedia_provider.search(
                query=query,
                num_results=5,
                request_id=request_id,
            )

            execution_time = time.time() - start_time

            return {
                "results": results,
                "metrics": {
                    "success": True,
                    "execution_time_ms": execution_time * 1000,
                    "results_count": len(results),
                    "accepted_count": len(results),
                },
            }
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "results": [],
                "metrics": {
                    "success": False,
                    "error": str(e),
                    "execution_time_ms": execution_time * 1000,
                    "results_count": 0,
                    "accepted_count": 0,
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
                },
            }

        try:
            results = await self.documentation_provider.search(
                query=query,
                num_results=5,
                request_id=request_id,
            )

            execution_time = time.time() - start_time

            return {
                "results": results,
                "metrics": {
                    "success": True,
                    "execution_time_ms": execution_time * 1000,
                    "results_count": len(results),
                    "accepted_count": len(results),
                },
            }
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "results": [],
                "metrics": {
                    "success": False,
                    "error": str(e),
                    "execution_time_ms": execution_time * 1000,
                    "results_count": 0,
                    "accepted_count": 0,
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
            results = await self.arxiv_provider.search(
                query=query,
                max_results=5,
                request_id=request_id,
            )

            execution_time = time.time() - start_time

            return {
                "results": results,
                "metrics": {
                    "success": True,
                    "execution_time_ms": execution_time * 1000,
                    "results_count": len(results),
                    "accepted_count": len(results),
                },
            }
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "results": [],
                "metrics": {
                    "success": False,
                    "error": str(e),
                    "execution_time_ms": execution_time * 1000,
                    "results_count": 0,
                    "accepted_count": 0,
                },
            }
