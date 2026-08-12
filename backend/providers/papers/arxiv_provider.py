"""arXiv paper provider implementation.

This module implements a provider for searching and retrieving academic
papers from the arXiv database using the official arXiv library.
"""

import asyncio
import time
from typing import Any

import arxiv

from backend.core.exceptions import ExternalServiceException
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


class ArxivProvider:
    """arXiv paper provider implementation.

    This class provides functionality to search and retrieve academic
    papers from the arXiv database.

    Attributes:
        timeout: Request timeout in seconds
        client: Reusable arXiv client
    """

    def __init__(self, timeout: int = 30) -> None:
        """Initialize the arXiv provider.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        # Create reusable arXiv client
        self.client = arxiv.Client()
        logger.info(
            f"arXiv provider initialized",
            extra={"timeout": timeout},
        )

    async def search(
        self,
        query: str,
        max_results: int = 5,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Search for academic papers on arXiv.

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            **kwargs: Additional provider-specific parameters

        Returns:
            List of paper dictionaries with title, authors, abstract, published, pdf_url, entry_id

        Raises:
            ExternalServiceException: If search fails
        """
        start_time = time.time()
        request_id = kwargs.get("request_id")

        logger.info(
            f"arXiv search request",
            extra={
                "provider": "arXiv",
                "query": query,
                "max_results": max_results,
                "request_id": request_id,
                "url": "export.arxiv.org (via arxiv library)",
                "timeout": self.timeout,
            },
        )

        try:
            # Create arXiv search
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
            )

            # Fetch results with timeout using reusable client
            results = []
            search_start = time.time()

            logger.info(
                f"Executing arXiv search",
                extra={
                    "query": query,
                    "max_results": max_results,
                    "sort_by": "Relevance",
                    "request_id": request_id,
                },
            )

            async def fetch_results():
                for result in self.client.results(search):
                    paper = {
                        "title": result.title,
                        "authors": [author.name for author in result.authors],
                        "abstract": result.summary,
                        "published": result.published.isoformat() if result.published else None,
                        "pdf_url": result.pdf_url,
                        "entry_id": result.entry_id,
                    }
                    results.append(paper)

            await asyncio.wait_for(fetch_results(), timeout=self.timeout)
            search_duration = time.time() - search_start

            execution_time = time.time() - start_time

            # Log paper titles for debugging
            paper_titles = [r.get("title", "")[:50] for r in results]
            paper_ids = [r.get("entry_id", "")[:30] for r in results]

            logger.info(
                f"arXiv search completed",
                extra={
                    "provider": "arXiv",
                    "query": query,
                    "execution_time": execution_time,
                    "search_duration": search_duration,
                    "parsing_duration": execution_time - search_duration,
                    "num_results": len(results),
                    "paper_titles": paper_titles,
                    "paper_ids": paper_ids,
                    "request_id": request_id,
                    "status_code": "N/A (arxiv library)",
                    "response_size": len(str(results)),
                },
            )

            # Handle empty results
            if not results:
                logger.warning(
                    f"arXiv search returned no results",
                    extra={
                        "provider": "arXiv",
                        "query": query,
                        "request_id": request_id,
                        "parsing_status": "empty",
                    },
                )

            return results

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(
                f"arXiv search timeout after {execution_time:.2f}s",
                extra={
                    "provider": "arXiv",
                    "query": query,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "timeout": self.timeout,
                    "error_type": "TimeoutError",
                    "parsing_status": "timeout",
                },
            )
            raise ExternalServiceException(
                message=f"arXiv search timeout after {self.timeout}s",
                details={"error": "TimeoutError", "query": query},
            )

        except arxiv.ArxivError as e:
            execution_time = time.time() - start_time
            logger.error(
                f"arXiv API error: {str(e)}",
                extra={
                    "provider": "arXiv",
                    "query": query,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "ArxivError",
                    "parsing_status": "api_error",
                },
            )
            raise ExternalServiceException(
                message=f"arXiv API error: {str(e)}",
                details={"error": str(e), "query": query},
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"arXiv search error: {str(e)}",
                extra={
                    "query": query,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": type(e).__name__,
                },
            )
            raise ExternalServiceException(
                message=f"arXiv search error: {str(e)}",
                details={"error": str(e), "query": query},
            )
