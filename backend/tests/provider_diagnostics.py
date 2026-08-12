"""Independent provider diagnostic tests for TASK-031.2

This script directly tests each provider (DuckDuckGo, Wikipedia, arXiv)
without running the LangGraph workflow to verify provider fixes.
"""

import sys
import os
# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import asyncio
import time
from typing import Any, Dict
from backend.providers.search.duckduckgo_provider import DuckDuckGoProvider
from backend.providers.search.wikipedia_provider import WikipediaProvider
from backend.providers.papers.arxiv_provider import ArxivProvider
from backend.providers.circuit_breaker import CircuitBreaker
from backend.providers.health_monitor import ProviderHealthMonitor
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


async def test_duckduckgo(query: str) -> Dict[str, Any]:
    """Test DuckDuckGo provider independently.

    Args:
        query: Search query

    Returns:
        Diagnostic results dictionary
    """
    logger.info(f"=== Testing DuckDuckGo Provider ===")
    logger.info(f"Query: {query}")

    result = {
        "provider": "DuckDuckGo",
        "query": query,
        "request_start": time.time(),
        "request_duration": 0,
        "http_status_code": None,
        "response_content_type": None,
        "response_size": 0,
        "parsed_results": 0,
        "exception_type": None,
        "exception_message": None,
        "timeout_status": False,
        "parsing_status": "unknown",
        "error": None,
        "retry_count": 0,
        "circuit_breaker_state": None,
    }

    try:
        provider = DuckDuckGoProvider(timeout=30)

        logger.info(f"PROVIDER_REQUEST: provider=DuckDuckGo, query={query}, timeout=30")

        search_start = time.time()
        results = await provider.search(query=query, num_results=5, request_id="diag_test")
        search_duration = time.time() - search_start

        result["request_duration"] = search_duration
        result["parsed_results"] = len(results)
        result["parsing_status"] = "success" if results else "empty"
        result["circuit_breaker_state"] = "N/A (direct test)"

        logger.info(f"PROVIDER_RESULT: provider=DuckDuckGo, query={query}, result_count={len(results)}")
        logger.info(f"DuckDuckGo test completed: {len(results)} results in {search_duration:.2f}s")

        # Log sample results
        if results:
            for i, r in enumerate(results[:3]):
                logger.info(f"  Result {i+1}: {r.get('title', 'N/A')[:50]}")

    except Exception as e:
        result["exception_type"] = type(e).__name__
        result["exception_message"] = str(e)
        result["error"] = str(e)
        result["request_duration"] = time.time() - result["request_start"]
        result["circuit_breaker_state"] = "N/A (direct test)"

        if "timeout" in str(e).lower():
            result["timeout_status"] = True
            result["parsing_status"] = "timeout"
            logger.error(f"PROVIDER_ERROR: provider=DuckDuckGo, error_type=TimeoutError, error_message={str(e)}")
        elif "connection" in str(e).lower():
            result["parsing_status"] = "connection_error"
            logger.error(f"PROVIDER_ERROR: provider=DuckDuckGo, error_type=ConnectionError, error_message={str(e)}")
        else:
            result["parsing_status"] = "error"
            logger.error(f"PROVIDER_ERROR: provider=DuckDuckGo, error_type={type(e).__name__}, error_message={str(e)}")

    return result


async def test_wikipedia(query: str) -> Dict[str, Any]:
    """Test Wikipedia provider independently.

    Args:
        query: Search query

    Returns:
        Diagnostic results dictionary
    """
    logger.info(f"=== Testing Wikipedia Provider ===")
    logger.info(f"Query: {query}")

    result = {
        "provider": "Wikipedia",
        "query": query,
        "request_start": time.time(),
        "request_duration": 0,
        "http_status_code": None,
        "response_content_type": None,
        "response_size": 0,
        "parsed_results": 0,
        "exception_type": None,
        "exception_message": None,
        "timeout_status": False,
        "parsing_status": "unknown",
        "error": None,
        "retry_count": 0,
        "circuit_breaker_state": None,
    }

    try:
        provider = WikipediaProvider(timeout=30)

        logger.info(f"PROVIDER_REQUEST: provider=Wikipedia, query={query}, timeout=30")

        search_start = time.time()
        results = await provider.search(query=query, num_results=5, request_id="diag_test")
        search_duration = time.time() - search_start

        result["request_duration"] = search_duration
        result["parsed_results"] = len(results)
        result["parsing_status"] = "success" if results else "empty"
        result["circuit_breaker_state"] = "N/A (direct test)"

        logger.info(f"PROVIDER_RESULT: provider=Wikipedia, query={query}, result_count={len(results)}")
        logger.info(f"Wikipedia test completed: {len(results)} results in {search_duration:.2f}s")

        # Log sample results
        if results:
            for i, r in enumerate(results[:3]):
                logger.info(f"  Result {i+1}: {r.get('title', 'N/A')[:50]}")

    except Exception as e:
        result["exception_type"] = type(e).__name__
        result["exception_message"] = str(e)
        result["error"] = str(e)
        result["request_duration"] = time.time() - result["request_start"]
        result["circuit_breaker_state"] = "N/A (direct test)"

        if "timeout" in str(e).lower():
            result["timeout_status"] = True
            result["parsing_status"] = "timeout"
            logger.error(f"PROVIDER_ERROR: provider=Wikipedia, error_type=TimeoutError, error_message={str(e)}")
        elif "403" in str(e) or "forbidden" in str(e).lower():
            result["parsing_status"] = "http_403"
            logger.error(f"PROVIDER_ERROR: provider=Wikipedia, error_type=HTTP403, error_message={str(e)}")
        elif "429" in str(e) or "rate" in str(e).lower():
            result["parsing_status"] = "http_429"
            logger.error(f"PROVIDER_ERROR: provider=Wikipedia, error_type=HTTP429, error_message={str(e)}")
        else:
            result["parsing_status"] = "error"
            logger.error(f"PROVIDER_ERROR: provider=Wikipedia, error_type={type(e).__name__}, error_message={str(e)}")

    return result


async def test_arxiv(query: str) -> Dict[str, Any]:
    """Test arXiv provider independently.

    Args:
        query: Search query

    Returns:
        Diagnostic results dictionary
    """
    logger.info(f"=== Testing arXiv Provider ===")
    logger.info(f"Query: {query}")

    result = {
        "provider": "arXiv",
        "query": query,
        "request_start": time.time(),
        "request_duration": 0,
        "http_status_code": None,
        "response_content_type": None,
        "response_size": 0,
        "parsed_results": 0,
        "exception_type": None,
        "exception_message": None,
        "timeout_status": False,
        "parsing_status": "unknown",
        "error": None,
        "retry_count": 0,
        "circuit_breaker_state": None,
    }

    try:
        provider = ArxivProvider(timeout=30)

        logger.info(f"PROVIDER_REQUEST: provider=arXiv, query={query}, timeout=30")

        search_start = time.time()
        results = await provider.search(query=query, max_results=5, request_id="diag_test")
        search_duration = time.time() - search_start

        result["request_duration"] = search_duration
        result["parsed_results"] = len(results)
        result["parsing_status"] = "success" if results else "empty"
        result["circuit_breaker_state"] = "N/A (direct test)"

        logger.info(f"PROVIDER_RESULT: provider=arXiv, query={query}, result_count={len(results)}")
        logger.info(f"arXiv test completed: {len(results)} results in {search_duration:.2f}s")

        # Log sample results
        if results:
            for i, r in enumerate(results[:3]):
                logger.info(f"  Result {i+1}: {r.get('title', 'N/A')[:50]}")

    except Exception as e:
        result["exception_type"] = type(e).__name__
        result["exception_message"] = str(e)
        result["error"] = str(e)
        result["request_duration"] = time.time() - result["request_start"]
        result["circuit_breaker_state"] = "N/A (direct test)"

        if "timeout" in str(e).lower():
            result["timeout_status"] = True
            result["parsing_status"] = "timeout"
            logger.error(f"PROVIDER_ERROR: provider=arXiv, error_type=TimeoutError, error_message={str(e)}")
        elif "arxiv" in str(e).lower():
            result["parsing_status"] = "arxiv_error"
            logger.error(f"PROVIDER_ERROR: provider=arXiv, error_type=ArxivError, error_message={str(e)}")
        else:
            result["parsing_status"] = "error"
            logger.error(f"PROVIDER_ERROR: provider=arXiv, error_type={type(e).__name__}, error_message={str(e)}")

    return result


async def main():
    """Run all provider diagnostic tests."""
    logger.info("=" * 60)
    logger.info("TASK-031.2 Provider Diagnostics")
    logger.info("=" * 60)

    # Test DuckDuckGo
    ddg_result = await test_duckduckgo("What is artificial intelligence?")

    # Test Wikipedia
    wiki_result = await test_wikipedia("What is artificial intelligence?")

    # Test arXiv
    arxiv_result = await test_arxiv("quantum computing")

    # Print summary
    logger.info("=" * 60)
    logger.info("DIAGNOSTIC SUMMARY")
    logger.info("=" * 60)

    for result in [ddg_result, wiki_result, arxiv_result]:
        logger.info(f"\nProvider: {result['provider']}")
        logger.info(f"  Query: {result['query']}")
        logger.info(f"  Duration: {result['request_duration']:.2f}s")
        logger.info(f"  Parsed Results: {result['parsed_results']}")
        logger.info(f"  Parsing Status: {result['parsing_status']}")
        logger.info(f"  Timeout: {result['timeout_status']}")
        logger.info(f"  Circuit Breaker State: {result.get('circuit_breaker_state', 'N/A')}")
        if result.get('health_status'):
            logger.info(f"  Health Status: {result['health_status']}")
        if result['error']:
            logger.info(f"  Error: {result['error']}")

    # Return results for further analysis
    return {
        "duckduckgo": ddg_result,
        "wikipedia": wiki_result,
        "arxiv": arxiv_result,
    }


if __name__ == "__main__":
    asyncio.run(main())
