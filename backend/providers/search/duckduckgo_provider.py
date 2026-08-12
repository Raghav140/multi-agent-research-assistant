"""DuckDuckGo search provider implementation.

This module implements the SearchProvider interface using the DuckDuckGo
search library for web search functionality.
"""

import asyncio
import time
from typing import Any, Optional

import httpx
from ddgs import DDGS

from backend.core.exceptions import ExternalServiceException
from backend.core.interfaces import SearchProvider
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


# Preferred domains for different query types
PREFERRED_DOMAINS = {
    "definition": ["wikipedia.org", ".edu", ".gov", "docs.", "official"],
    "technical": ["github.com", "docs.", "stackoverflow.com", "dev.to", "medium.com", "official"],
    "research": ["arxiv.org", ".edu", "researchgate.net", "scholar.google.com", "nature.com", "ieee.org", "acm.org"],
}

# Rejected domain patterns
REJECTED_DOMAINS = [
    "ads.",
    "ad.",
    "advertisement",
    "login.",
    "signin.",
    "auth.",
    "download.",
    "downloads.",
    "install.",
    "pricing.",
    "checkout.",
    "cart.",
    "shop.",
    "store.",
]


class DuckDuckGoProvider(SearchProvider):
    """DuckDuckGo search provider implementation.

    This class implements the SearchProvider interface using DuckDuckGo's
    free search API for web search and content retrieval.

    Attributes:
        timeout: Request timeout in seconds
        http_client: Reusable HTTP client with connection pooling
    """

    def __init__(self, timeout: int = 30, query_type: Optional[str] = None) -> None:
        """Initialize the DuckDuckGo provider.

        Args:
            timeout: Request timeout in seconds
            query_type: Query type for domain preference (definition, technical, research)
        """
        self.timeout = timeout
        self.query_type = query_type or "research"
        # Create reusable HTTP client with connection pooling and keep-alive
        self.http_client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        logger.info(
            f"DuckDuckGo provider initialized",
            extra={"timeout": timeout, "query_type": self.query_type},
        )

    async def search(
        self,
        query: str,
        num_results: int = 10,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Perform a search query.

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
            f"DuckDuckGo search request",
            extra={
                "provider": "DuckDuckGo",
                "query": query,
                "num_results": num_results,
                "request_id": request_id,
                "url": "duckduckgo.com (via DDGS library)",
                "timeout": self.timeout,
            },
        )

        try:
            # Perform search using DuckDuckGo with timeout
            ddgs = DDGS()
            search_start = time.time()

            logger.info(
                f"Executing DuckDuckGo search",
                extra={
                    "query": query,
                    "max_results": num_results,
                    "request_id": request_id,
                },
            )

            # DDGS text() returns a generator, convert to list in thread
            ddgs_generator = ddgs.text(query, max_results=num_results)
            raw_results = await asyncio.wait_for(
                asyncio.to_thread(list, ddgs_generator),
                timeout=self.timeout,
            )
            search_duration = time.time() - search_start

            # DIAGNOSTIC: Log raw result count
            logger.info(
                f"DDGS raw results received",
                extra={
                    "DDG_RAW_RESULT_COUNT": len(raw_results),
                    "DDG_SEARCH_DURATION": search_duration,
                },
            )

            execution_time = time.time() - start_time

            # Format results to match expected structure
            formatted_results = []
            filtered_count = 0
            for result in raw_results:
                url = result.get("href", "")

                # Filter out rejected domains
                if self._is_rejected_domain(url):
                    filtered_count += 1
                    logger.debug(
                        f"Filtered result from rejected domain: {url[:50]}",
                        extra={"url": url[:50], "reason": "rejected_domain"},
                    )
                    continue

                # Add domain preference score
                domain_score = self._calculate_domain_score(url)

                formatted_results.append({
                    "title": result.get("title", ""),
                    "url": url,
                    "snippet": result.get("body", ""),
                    "domain_score": domain_score,
                })

            # DIAGNOSTIC: Log parsing and filtering counts
            logger.info(
                f"DDGS result parsing completed",
                extra={
                    "DDG_PARSED_RESULT_COUNT": len(raw_results),
                    "DDG_FILTERED_RESULT_COUNT": filtered_count,
                    "DDG_RETURN_RESULT_COUNT": len(formatted_results),
                },
            )

            # Sort by domain preference (preferred domains first)
            formatted_results.sort(key=lambda x: x.get("domain_score", 0), reverse=True)

            # Log result titles and URLs for debugging
            result_titles = [r.get("title", "")[:50] for r in formatted_results]
            result_urls = [r.get("url", "")[:50] for r in formatted_results]

            logger.info(
                f"DuckDuckGo search completed",
                extra={
                    "provider": "DuckDuckGo",
                    "query": query,
                    "execution_time": execution_time,
                    "search_duration": search_duration,
                    "parsing_duration": execution_time - search_duration,
                    "num_results": len(formatted_results),
                    "result_titles": result_titles,
                    "result_urls": result_urls,
                    "request_id": request_id,
                    "status_code": "N/A (DDGS library)",
                    "response_size": len(str(raw_results)) if 'raw_results' in locals() else 0,
                },
            )

            # Handle empty results
            if not formatted_results:
                logger.warning(
                    f"DuckDuckGo search returned no results",
                    extra={
                        "provider": "DuckDuckGo",
                        "query": query,
                        "request_id": request_id,
                        "raw_results_count": len(raw_results) if 'raw_results' in locals() else 0,
                        "parsing_status": "empty",
                    },
                )

            return formatted_results

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(
                f"DuckDuckGo search timeout after {execution_time:.2f}s",
                extra={
                    "provider": "DuckDuckGo",
                    "query": query,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "timeout": self.timeout,
                    "error_type": "TimeoutError",
                    "parsing_status": "timeout",
                    "retry_count": 0,
                },
            )
            # Return empty list instead of crashing workflow
            return []

        except httpx.TimeoutException as e:
            execution_time = time.time() - start_time
            logger.error(
                f"DuckDuckGo search timeout: {str(e)}",
                extra={
                    "provider": "DuckDuckGo",
                    "query": query,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "TimeoutException",
                    "parsing_status": "timeout",
                    "retry_count": 0,
                },
            )
            # Return empty list instead of crashing workflow
            return []

        except httpx.ConnectError as e:
            execution_time = time.time() - start_time
            logger.error(
                f"DuckDuckGo connection error: {str(e)}",
                extra={
                    "provider": "DuckDuckGo",
                    "query": query,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "ConnectError",
                    "parsing_status": "connection_error",
                    "retry_count": 0,
                },
            )
            # Return empty list instead of crashing workflow
            return []

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"DuckDuckGo search error: {str(e)}",
                extra={
                    "provider": "DuckDuckGo",
                    "query": query,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": type(e).__name__,
                    "retry_count": 0,
                },
            )
            # Return empty list instead of crashing workflow
            return []

    async def get_content(self, url: str, **kwargs: Any) -> str:
        """Retrieve content from a URL.

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
            f"DuckDuckGo content retrieval request",
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
                f"DuckDuckGo content retrieval completed",
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
                f"DuckDuckGo content retrieval timeout: {str(e)}",
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
                f"DuckDuckGo content retrieval connection error: {str(e)}",
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
                f"DuckDuckGo content retrieval HTTP error: {str(e)}",
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
                f"DuckDuckGo content retrieval error: {str(e)}",
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

    def _is_rejected_domain(self, url: str) -> bool:
        """Check if URL is from a rejected domain pattern.

        Args:
            url: URL to check

        Returns:
            True if domain should be rejected
        """
        url_lower = url.lower()
        for pattern in REJECTED_DOMAINS:
            if pattern in url_lower:
                return True
        return False

    def _calculate_domain_score(self, url: str) -> float:
        """Calculate domain preference score based on query type.

        Args:
            url: URL to score

        Returns:
            Domain score between 0 and 1
        """
        url_lower = url.lower()
        preferred = PREFERRED_DOMAINS.get(self.query_type, [])

        # Check if URL matches any preferred domain
        for pattern in preferred:
            if pattern in url_lower:
                return 1.0

        # Check for general good domains
        if ".edu" in url_lower or ".gov" in url_lower:
            return 0.8
        elif "wikipedia.org" in url_lower:
            return 0.8
        elif "github.com" in url_lower:
            return 0.7

        # Default score
        return 0.5
