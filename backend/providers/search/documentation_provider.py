"""Official documentation search provider implementation.

This module implements the SearchProvider interface for retrieving
trusted technical documentation from official sources.
"""

import asyncio
import time
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from backend.core.exceptions import ExternalServiceException
from backend.core.interfaces import SearchProvider
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)

# Trusted documentation domains
DOCUMENTATION_DOMAINS = {
    # Python
    "python.org",
    "docs.python.org",
    "pypi.org",
    # FastAPI
    "fastapi.tiangolo.com",
    "tiangolo.com",
    # LangGraph/LangChain
    "langchain-ai.github.io",
    "python.langchain.com",
    "langchain.com",
    # JavaScript/Node
    "developer.mozilla.org",
    "nodejs.org",
    "docs.nodejs.org",
    # React
    "react.dev",
    "reactjs.org",
    # Django
    "docs.djangoproject.com",
    "djangoproject.com",
    # Flask
    "flask.palletsprojects.com",
    "palletsprojects.com",
    # General documentation indicators
    "docs.",
    "documentation",
    "readthedocs.io",
}


class DocumentationProvider(SearchProvider):
    """Official documentation search provider implementation.

    This class implements the SearchProvider interface for retrieving
    trusted technical documentation from official sources.

    Attributes:
        timeout: Request timeout in seconds
        http_client: Reusable HTTP client with connection pooling
    """

    def __init__(self, timeout: int = 30) -> None:
        """Initialize the documentation provider.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        # Create reusable HTTP client with connection pooling and keep-alive
        self.http_client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        logger.info(
            f"Documentation provider initialized",
            extra={"timeout": timeout},
        )

    async def search(
        self,
        query: str,
        num_results: int = 10,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Perform a search query using DuckDuckGo with domain filtering.

        Since there's no official documentation search API, we use DuckDuckGo
        with site-specific searches for trusted documentation domains.

        Args:
            query: Search query string
            num_results: Number of results to return
            **kwargs: Additional provider-specific parameters

        Returns:
            List of search result dictionaries with title, url, and snippet

        Raises:
            ExternalServiceException: If search fails
        """
        start_time = time.time()
        request_id = kwargs.get("request_id")

        logger.info(
            f"Documentation search request",
            extra={
                "query": query,
                "num_results": num_results,
                "request_id": request_id,
            },
        )

        try:
            # Build site-specific search queries for trusted domains
            search_queries = self._build_site_queries(query)

            all_results = []

            # Execute searches for each documentation domain
            for site_query in search_queries:
                try:
                    results = await self._search_duckduckgo_site(site_query, num_results // len(search_queries), request_id)
                    all_results.extend(results)
                except Exception as e:
                    logger.warning(
                        f"Documentation search failed for query '{site_query}': {str(e)}",
                        extra={
                            "request_id": request_id,
                            "query": site_query,
                            "error": str(e),
                        },
                    )

            # Filter and score results
            filtered_results = self._filter_and_score_results(all_results, query)

            # Limit to requested number
            filtered_results = filtered_results[:num_results]

            execution_time = time.time() - start_time

            logger.info(
                f"Documentation search completed",
                extra={
                    "query": query,
                    "execution_time": execution_time,
                    "num_results": len(filtered_results),
                    "request_id": request_id,
                },
            )

            return filtered_results

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Documentation search error: {str(e)}",
                extra={
                    "query": query,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": type(e).__name__,
                },
            )
            raise ExternalServiceException(
                message=f"Documentation search error: {str(e)}",
                details={"error": str(e), "query": query},
            )

    def _build_site_queries(self, query: str) -> list[str]:
        """Build site-specific search queries for trusted domains.

        Args:
            query: Original search query

        Returns:
            List of site-specific search queries
        """
        # Extract potential technology keywords from query
        query_lower = query.lower()

        # Determine which domains to search based on query content
        domains_to_search = []

        if "python" in query_lower or "django" in query_lower or "flask" in query_lower:
            domains_to_search.extend(["site:python.org", "site:docs.python.org"])
        elif "fastapi" in query_lower:
            domains_to_search.append("site:fastapi.tiangolo.com")
        elif "langgraph" in query_lower or "langchain" in query_lower:
            domains_to_search.extend(["site:langchain-ai.github.io", "site:python.langchain.com"])
        elif "javascript" in query_lower or "js" in query_lower or "node" in query_lower:
            domains_to_search.extend(["site:developer.mozilla.org", "site:nodejs.org"])
        elif "react" in query_lower:
            domains_to_search.append("site:react.dev")
        else:
            # Default: search general documentation sites
            domains_to_search.extend(["site:docs.python.org", "site:developer.mozilla.org"])

        # Build queries
        queries = []
        for domain in domains_to_search:
            queries.append(f"{query} {domain}")

        return queries

    async def _search_duckduckgo_site(
        self,
        query: str,
        num_results: int,
        request_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Search DuckDuckGo with site-specific query.

        Args:
            query: Site-specific search query
            num_results: Number of results to return
            request_id: Request identifier

        Returns:
            List of search results
        """
        from duckduckgo_search import DDGS

        ddgs = DDGS()

        try:
            raw_results = await asyncio.wait_for(
                asyncio.to_thread(list, ddgs.text(query, max_results=num_results)),
                timeout=self.timeout,
            )

            formatted_results = []
            for result in raw_results:
                formatted_results.append({
                    "title": result.get("title", ""),
                    "url": result.get("href", ""),
                    "snippet": result.get("body", ""),
                })

            return formatted_results
        except Exception as e:
            logger.error(
                f"DuckDuckGo site search failed: {str(e)}",
                extra={
                    "request_id": request_id,
                    "query": query,
                    "error": str(e),
                },
            )
            return []

    def _filter_and_score_results(self, results: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
        """Filter and score documentation results.

        Args:
            results: Raw search results
            query: Original query

        Returns:
            Filtered and scored results
        """
        filtered = []

        for result in results:
            url = result.get("url", "")

            # Check if URL is from trusted documentation domain
            if not self._is_documentation_domain(url):
                continue

            # Calculate quality score
            quality_score = self._calculate_quality_score(result)

            # Calculate relevance score
            relevance_score = self._calculate_relevance_score(query, result)

            # Add scores to result
            result["quality_score"] = quality_score
            result["relevance_score"] = relevance_score

            filtered.append(result)

        # Sort by combined score
        filtered.sort(key=lambda x: (x.get("quality_score", 0) + x.get("relevance_score", 0)) / 2, reverse=True)

        return filtered

    def _is_documentation_domain(self, url: str) -> bool:
        """Check if URL is from a trusted documentation domain.

        Args:
            url: URL to check

        Returns:
            True if from trusted documentation domain
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Check exact match
            if domain in DOCUMENTATION_DOMAINS:
                return True

            # Check subdomain match
            for doc_domain in DOCUMENTATION_DOMAINS:
                if domain == doc_domain or domain.endswith(f".{doc_domain}"):
                    return True

            # Check for documentation indicators
            if "docs." in domain or "documentation" in domain:
                return True

            return False
        except Exception:
            return False

    def _calculate_quality_score(self, result: dict[str, Any]) -> float:
        """Calculate quality score for a documentation result.

        Args:
            result: Search result

        Returns:
            Quality score between 0 and 1
        """
        url = result.get("url", "")
        title = result.get("title", "")
        snippet = result.get("snippet", "")

        score = 0.5  # Base score

        # Boost for official documentation domains
        if "docs." in url or "documentation" in url:
            score += 0.3

        # Boost for specific trusted domains
        if any(domain in url for domain in ["python.org", "fastapi.tiangolo.com", "langchain-ai.github.io"]):
            score += 0.2

        # Boost for clear documentation indicators in title
        if any(indicator in title.lower() for indicator in ["documentation", "guide", "tutorial", "api", "reference"]):
            score += 0.1

        # Boost for substantial content
        if len(snippet) > 100:
            score += 0.1

        return min(score, 1.0)

    def _calculate_relevance_score(self, query: str, result: dict[str, Any]) -> float:
        """Calculate relevance score for a documentation result.

        Args:
            query: Search query
            result: Search result

        Returns:
            Relevance score between 0 and 1
        """
        query_lower = query.lower()
        title_lower = result.get("title", "").lower()
        snippet_lower = result.get("snippet", "").lower()

        score = 0.0

        # Exact query match in title
        if query_lower in title_lower:
            score += 0.5

        # Query words in title
        query_words = set(query_lower.split())
        title_words = set(title_lower.split())
        overlap = len(query_words & title_words) / max(len(query_words), 1)
        score += overlap * 0.3

        # Query in snippet
        if query_lower in snippet_lower:
            score += 0.2

        return min(score, 1.0)

    async def get_content(self, url: str, **kwargs: Any) -> str:
        """Retrieve content from a documentation URL.

        Args:
            url: URL to retrieve content from
            **kwargs: Additional provider-specific parameters

        Returns:
            Retrieved content as string

        Raises:
            ExternalServiceException: If content retrieval fails
        """
        start_time = time.time()
        request_id = kwargs.get("request_id")

        logger.info(
            f"Documentation content retrieval request",
            extra={
                "url": url,
                "request_id": request_id,
            },
        )

        try:
            # Use reusable HTTP client to fetch content
            response = await self.http_client.get(url)
            response.raise_for_status()
            content = response.text

            execution_time = time.time() - start_time

            logger.info(
                f"Documentation content retrieval completed",
                extra={
                    "url": url,
                    "execution_time": execution_time,
                    "content_length": len(content),
                    "request_id": request_id,
                },
            )

            return content

        except httpx.TimeoutException as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Documentation content retrieval timeout: {str(e)}",
                extra={
                    "url": url,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "TimeoutException",
                },
            )
            raise ExternalServiceException(
                message=f"Content retrieval timeout: {str(e)}",
                details={"error": str(e), "url": url},
            )

        except httpx.ConnectError as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Documentation content retrieval connection error: {str(e)}",
                extra={
                    "url": url,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "ConnectError",
                },
            )
            raise ExternalServiceException(
                message=f"Content retrieval connection failed: {str(e)}",
                details={"error": str(e), "url": url},
            )

        except httpx.HTTPStatusError as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Documentation content retrieval HTTP error: {str(e)}",
                extra={
                    "url": url,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "status_code": e.response.status_code,
                    "error_type": "HTTPStatusError",
                },
            )
            raise ExternalServiceException(
                message=f"Content retrieval HTTP error: {str(e)}",
                details={"error": str(e), "url": url, "status_code": e.response.status_code},
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Documentation content retrieval error: {str(e)}",
                extra={
                    "url": url,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": type(e).__name__,
                },
            )
            raise ExternalServiceException(
                message=f"Content retrieval error: {str(e)}",
                details={"error": str(e), "url": url},
            )
