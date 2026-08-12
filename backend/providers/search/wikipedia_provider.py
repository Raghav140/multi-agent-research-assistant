"""Wikipedia search provider implementation.

This module implements the SearchProvider interface using the Wikipedia API
for definition and general knowledge queries.
"""

import asyncio
import time
from typing import Any
from urllib.parse import quote

import httpx

from backend.core.exceptions import ExternalServiceException
from backend.core.interfaces import SearchProvider
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"


class WikipediaProvider(SearchProvider):
    """Wikipedia search provider implementation.

    This class implements the SearchProvider interface using Wikipedia's
    free API for definition and general knowledge queries.

    Attributes:
        timeout: Request timeout in seconds
        http_client: Reusable HTTP client with connection pooling
    """

    def __init__(self, timeout: int = 30) -> None:
        """Initialize the Wikipedia provider.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

        # Descriptive User-Agent as required by Wikipedia API policy
        # Format: ApplicationName/Version (ContactURL)
        headers = {
            "User-Agent": "Multi-Agent-Research-Assistant/1.0 (https://github.com/raghav140/multi-agent-research-assistant; research-bot@example.com)"
        }

        # Create reusable HTTP client with connection pooling and keep-alive
        self.http_client = httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        logger.info(
            f"Wikipedia provider initialized",
            extra={"timeout": timeout, "user_agent": headers["User-Agent"]},
        )

    async def search(
        self,
        query: str,
        num_results: int = 10,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Perform a search query using Wikipedia API.

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
            f"Wikipedia search request",
            extra={
                "provider": "Wikipedia",
                "query": query,
                "num_results": num_results,
                "request_id": request_id,
                "url": WIKIPEDIA_API_URL,
                "timeout": self.timeout,
            },
        )

        try:
            # Wikipedia API parameters for search
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": min(num_results, 50),  # Wikipedia max is 50
                "srprop": "snippet|titlesnippet|wordcount|timestamp",
            }

            search_start = time.time()

            logger.info(
                f"Executing Wikipedia search",
                extra={
                    "query": query,
                    "params": params,
                    "request_id": request_id,
                },
            )

            response = await self.http_client.get(
                WIKIPEDIA_API_URL,
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            search_duration = time.time() - search_start
            execution_time = time.time() - start_time

            # Format results to match expected structure
            formatted_results = []

            if "query" in data and "search" in data["query"]:
                for result in data["query"]["search"]:
                    title = result.get("title", "")
                    snippet = result.get("snippet", "").replace('<span class="searchmatch">', "").replace('</span>', "")
                    wordcount = result.get("wordcount", 0)

                    # Construct Wikipedia URL
                    url = f"https://en.wikipedia.org/wiki/{quote(title, safe='')}"

                    # Calculate quality and relevance scores
                    quality_score = self._calculate_quality_score(wordcount)
                    relevance_score = self._calculate_relevance_score(query, title, snippet)

                    formatted_results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                        "content": snippet,  # Wikipedia uses snippet as content
                        "quality_score": quality_score,
                        "relevance_score": relevance_score,
                        "wordcount": wordcount,
                    })

            # Log result titles and URLs for debugging
            result_titles = [r.get("title", "")[:50] for r in formatted_results]
            result_urls = [r.get("url", "")[:50] for r in formatted_results]

            logger.info(
                f"Wikipedia search completed",
                extra={
                    "provider": "Wikipedia",
                    "query": query,
                    "execution_time": execution_time,
                    "search_duration": search_duration,
                    "parsing_duration": execution_time - search_duration,
                    "num_results": len(formatted_results),
                    "result_titles": result_titles,
                    "result_urls": result_urls,
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "response_size": len(response.content),
                },
            )

            # Handle empty results
            if not formatted_results:
                logger.warning(
                    f"Wikipedia search returned no results",
                    extra={
                        "provider": "Wikipedia",
                        "query": query,
                        "request_id": request_id,
                        "raw_results_count": len(data.get("query", {}).get("search", [])),
                        "parsing_status": "empty",
                    },
                )

            return formatted_results

        except httpx.TimeoutException as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Wikipedia search timeout: {str(e)}",
                extra={
                    "provider": "Wikipedia",
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
                f"Wikipedia connection error: {str(e)}",
                extra={
                    "provider": "Wikipedia",
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

        except httpx.HTTPStatusError as e:
            execution_time = time.time() - start_time
            status_code = e.response.status_code

            # Handle specific HTTP status codes
            if status_code == 403:
                # Forbidden - do not retry, return empty results
                logger.error(
                    f"Wikipedia HTTP 403 Forbidden - User-Agent or policy issue",
                    extra={
                        "provider": "Wikipedia",
                        "query": query,
                        "execution_time": execution_time,
                        "request_id": request_id,
                        "status_code": status_code,
                        "error_type": "HTTPStatusError",
                        "parsing_status": "http_error",
                        "retry_count": 0,
                    },
                )
                # Return empty list instead of crashing workflow
                return []

            elif status_code == 429:
                # Rate limit - could retry with backoff, but for now return empty
                logger.warning(
                    f"Wikipedia HTTP 429 Rate Limited",
                    extra={
                        "provider": "Wikipedia",
                        "query": query,
                        "execution_time": execution_time,
                        "request_id": request_id,
                        "status_code": status_code,
                        "error_type": "HTTPStatusError",
                        "parsing_status": "rate_limited",
                        "retry_count": 0,
                    },
                )
                return []

            elif 500 <= status_code < 600:
                # Server error - return empty, could retry in future
                logger.error(
                    f"Wikipedia HTTP 5xx Server Error",
                    extra={
                        "provider": "Wikipedia",
                        "query": query,
                        "execution_time": execution_time,
                        "request_id": request_id,
                        "status_code": status_code,
                        "error_type": "HTTPStatusError",
                        "parsing_status": "server_error",
                        "retry_count": 0,
                    },
                )
                return []

            else:
                # Other HTTP errors
                logger.error(
                    f"Wikipedia HTTP error: {str(e)}",
                    extra={
                        "provider": "Wikipedia",
                        "query": query,
                        "execution_time": execution_time,
                        "request_id": request_id,
                        "status_code": status_code,
                        "error_type": "HTTPStatusError",
                        "parsing_status": "http_error",
                    },
                )
                return []

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Wikipedia search error: {str(e)}",
                extra={
                    "query": query,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": type(e).__name__,
                },
            )
            raise ExternalServiceException(
                message=f"Wikipedia search error: {str(e)}",
                details={"error": str(e), "query": query},
            )

    async def get_content(self, url: str, **kwargs: Any) -> str:
        """Retrieve content from a Wikipedia URL.

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
            f"Wikipedia content retrieval request",
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
                f"Wikipedia content retrieval completed",
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
                f"Wikipedia content retrieval timeout: {str(e)}",
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
                f"Wikipedia content retrieval connection error: {str(e)}",
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
                f"Wikipedia content retrieval HTTP error: {str(e)}",
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
                f"Wikipedia content retrieval error: {str(e)}",
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

    def _calculate_quality_score(self, wordcount: int) -> float:
        """Calculate quality score based on word count.

        Args:
            wordcount: Word count of Wikipedia article

        Returns:
            Quality score between 0 and 1
        """
        if wordcount < 100:
            return 0.3
        elif wordcount < 500:
            return 0.5
        elif wordcount < 1000:
            return 0.7
        elif wordcount < 2000:
            return 0.85
        else:
            return 1.0

    def _calculate_relevance_score(self, query: str, title: str, snippet: str) -> float:
        """Calculate relevance score based on query matching.

        Args:
            query: Search query
            title: Article title
            snippet: Article snippet

        Returns:
            Relevance score between 0 and 1
        """
        query_lower = query.lower()
        title_lower = title.lower()
        snippet_lower = snippet.lower()

        # Exact title match gets highest score
        if query_lower == title_lower:
            return 1.0

        # Query in title
        if query_lower in title_lower:
            return 0.9

        # Query words in title
        query_words = set(query_lower.split())
        title_words = set(title_lower.split())
        overlap = len(query_words & title_words) / max(len(query_words), 1)

        if overlap > 0.5:
            return 0.8
        elif overlap > 0.3:
            return 0.6

        # Query in snippet
        if query_lower in snippet_lower:
            return 0.7

        # Default score
        return 0.5
