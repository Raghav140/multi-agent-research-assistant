"""DuckDuckGo search provider implementation.

This module implements the SearchProvider interface using the DuckDuckGo
search library for web search functionality.
"""

import asyncio
import time
from typing import Any

import httpx
from ddgs import DDGS

from backend.core.exceptions import ExternalServiceException
from backend.core.interfaces import SearchProvider
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


class DuckDuckGoProvider(SearchProvider):
    """DuckDuckGo search provider implementation.

    This class implements the SearchProvider interface using DuckDuckGo's
    free search API for web search and content retrieval.

    Attributes:
        timeout: Request timeout in seconds
        http_client: Reusable HTTP client with connection pooling
    """

    def __init__(self, timeout: int = 30) -> None:
        """Initialize the DuckDuckGo provider.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        # Create reusable HTTP client with connection pooling and keep-alive
        self.http_client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            http2=True,  # Enable HTTP/2 for better performance
        )
        logger.info(
            f"DuckDuckGo provider initialized",
            extra={"timeout": timeout},
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
                "query": query,
                "num_results": num_results,
                "request_id": request_id,
            },
        )

        try:
            # Perform search using DuckDuckGo with timeout
            ddgs = DDGS()
            search_start = time.time()
            results = await asyncio.wait_for(
                asyncio.to_thread(list, ddgs.text(query, max_results=num_results)),
                timeout=self.timeout,
            )
            search_duration = time.time() - search_start

            execution_time = time.time() - start_time

            # Format results to match expected structure
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "title": result.get("title", ""),
                    "url": result.get("href", ""),
                    "snippet": result.get("body", ""),
                })

            logger.info(
                f"DuckDuckGo search completed",
                extra={
                    "query": query,
                    "execution_time": execution_time,
                    "search_duration": search_duration,
                    "parsing_duration": execution_time - search_duration,
                    "num_results": len(formatted_results),
                    "request_id": request_id,
                },
            )

            # Handle empty results
            if not formatted_results:
                logger.warning(
                    f"DuckDuckGo search returned no results",
                    extra={
                        "query": query,
                        "request_id": request_id,
                    },
                )

            return formatted_results

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(
                f"DuckDuckGo search timeout after {execution_time:.2f}s",
                extra={
                    "query": query,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "timeout": self.timeout,
                },
            )
            raise ExternalServiceException(
                message=f"DuckDuckGo search timeout after {self.timeout}s",
                details={"error": "TimeoutError", "query": query},
            )

        except httpx.TimeoutException as e:
            execution_time = time.time() - start_time
            logger.error(
                f"DuckDuckGo search timeout: {str(e)}",
                extra={
                    "query": query,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "TimeoutException",
                },
            )
            raise ExternalServiceException(
                message=f"DuckDuckGo search timeout: {str(e)}",
                details={"error": str(e), "query": query},
            )

        except httpx.ConnectError as e:
            execution_time = time.time() - start_time
            logger.error(
                f"DuckDuckGo connection error: {str(e)}",
                extra={
                    "query": query,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "ConnectError",
                },
            )
            raise ExternalServiceException(
                message=f"DuckDuckGo connection failed: {str(e)}",
                details={"error": str(e), "query": query},
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"DuckDuckGo search error: {str(e)}",
                extra={
                    "query": query,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": type(e).__name__,
                },
            )
            raise ExternalServiceException(
                message=f"DuckDuckGo search error: {str(e)}",
                details={"error": str(e), "query": query},
            )

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
