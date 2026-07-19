"""arXiv paper provider implementation.

This module implements a provider for searching and retrieving academic
papers from the arXiv database using the official arXiv library.
"""

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
    """

    def __init__(self, timeout: int = 30) -> None:
        """Initialize the arXiv provider.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
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
                "query": query,
                "max_results": max_results,
                "request_id": request_id,
            },
        )

        try:
            # Create arXiv client and search
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
            )

            # Fetch results
            results = []
            for result in arxiv.Client().results(search):
                paper = {
                    "title": result.title,
                    "authors": [author.name for author in result.authors],
                    "abstract": result.summary,
                    "published": result.published.isoformat() if result.published else None,
                    "pdf_url": result.pdf_url,
                    "entry_id": result.entry_id,
                }
                results.append(paper)

            execution_time = time.time() - start_time

            logger.info(
                f"arXiv search completed",
                extra={
                    "query": query,
                    "execution_time": execution_time,
                    "num_results": len(results),
                    "request_id": request_id,
                },
            )

            # Handle empty results
            if not results:
                logger.warning(
                    f"arXiv search returned no results",
                    extra={
                        "query": query,
                        "request_id": request_id,
                    },
                )

            return results

        except arxiv.ArxivError as e:
            execution_time = time.time() - start_time
            logger.error(
                f"arXiv API error: {str(e)}",
                extra={
                    "query": query,
                    "execution_time": execution_time,
                    "request_id": request_id,
                    "error_type": "ArxivError",
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
