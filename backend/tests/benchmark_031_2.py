"""TASK-031.2 Full Pipeline Benchmark

This script runs the 10-query benchmark to verify provider recovery
and fault-tolerant retrieval implementation.
"""

import sys
import os
import time
import asyncio
from typing import Any, Dict
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from backend.providers.search.duckduckgo_provider import DuckDuckGoProvider
from backend.providers.search.wikipedia_provider import WikipediaProvider
from backend.providers.papers.arxiv_provider import ArxivProvider
from backend.utils.query_classifier import classify_query
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


# Benchmark queries from TASK-031.2
BENCHMARK_QUERIES = [
    "What is artificial intelligence?",
    "What is machine learning?",
    "What is Python?",
    "LangGraph tutorial",
    "FastAPI authentication tutorial",
    "Explain quantum computing",
    "Transformer architecture research",
    "Retrieval augmented generation research",
    "FastAPI vs Flask",
    "Current LangGraph documentation",
]


async def run_single_benchmark(
    query: str,
    duckduckgo_provider: DuckDuckGoProvider,
    wikipedia_provider: WikipediaProvider,
    arxiv_provider: ArxivProvider,
) -> Dict[str, Any]:
    """Run benchmark for a single query.

    Args:
        query: Benchmark query
        duckduckgo_provider: DuckDuckGo provider instance
        wikipedia_provider: Wikipedia provider instance
        arxiv_provider: arXiv provider instance

    Returns:
        Benchmark results dictionary
    """
    logger.info(f"=== Benchmark Query: {query} ===")

    result = {
        "query": query,
        "query_type": classify_query(query),
        "start_time": time.time(),
        "total_execution_time": 0,
        "providers": {},
        "sources_found": 0,
        "sources_accepted": 0,
        "sources_rejected": 0,
        "fallback_used": False,
        "cache_hit": False,
        "final_status": "unknown",
    }

    # Test each provider independently
    providers = {
        "duckduckgo": duckduckgo_provider,
        "wikipedia": wikipedia_provider,
        "arxiv": arxiv_provider,
    }

    for provider_name, provider in providers.items():
        provider_result = {
            "success": False,
            "execution_time": 0,
            "result_count": 0,
            "error": None,
            "error_type": None,
        }

        try:
            provider_start = time.time()

            if provider_name == "duckduckgo":
                results = await provider.search(
                    query=query,
                    num_results=5,
                    request_id=f"benchmark_{query[:20]}",
                )
            elif provider_name == "wikipedia":
                results = await provider.search(
                    query=query,
                    num_results=5,
                    request_id=f"benchmark_{query[:20]}",
                )
            elif provider_name == "arxiv":
                results = await provider.search(
                    query=query,
                    max_results=5,
                    request_id=f"benchmark_{query[:20]}",
                )

            provider_time = time.time() - provider_start
            provider_result["success"] = True
            provider_result["execution_time"] = provider_time
            provider_result["result_count"] = len(results)

            result["sources_found"] += len(results)

            logger.info(
                f"{provider_name} provider succeeded",
                extra={
                    "query": query,
                    "provider": provider_name,
                    "execution_time": provider_time,
                    "result_count": len(results),
                },
            )

        except asyncio.TimeoutError as e:
            provider_time = time.time() - provider_start
            provider_result["execution_time"] = provider_time
            provider_result["error"] = "TimeoutError"
            provider_result["error_type"] = "TimeoutError"
            result["fallback_used"] = True

            logger.error(
                f"{provider_name} provider timeout",
                extra={
                    "query": query,
                    "provider": provider_name,
                    "error": "TimeoutError",
                },
            )

        except Exception as e:
            provider_time = time.time() - provider_start
            provider_result["execution_time"] = provider_time
            provider_result["error"] = str(e)
            provider_result["error_type"] = type(e).__name__
            result["fallback_used"] = True

            logger.error(
                f"{provider_name} provider error",
                extra={
                    "query": query,
                    "provider": provider_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

        result["providers"][provider_name] = provider_result

    result["total_execution_time"] = time.time() - result["start_time"]

    # Determine final status
    successful_providers = sum(1 for p in result["providers"].values() if p["success"])
    if successful_providers > 0:
        result["final_status"] = "success"
        result["sources_accepted"] = result["sources_found"]
    else:
        result["final_status"] = "failure"

    logger.info(
        f"Benchmark query completed",
        extra={
            "query": query,
            "total_execution_time": result["total_execution_time"],
            "successful_providers": successful_providers,
            "sources_found": result["sources_found"],
            "final_status": result["final_status"],
        },
    )

    return result


async def run_full_benchmark() -> Dict[str, Any]:
    """Run full 10-query benchmark.

    Returns:
        Complete benchmark results
    """
    logger.info("=" * 60)
    logger.info("TASK-031.2 Full Pipeline Benchmark")
    logger.info("=" * 60)
    logger.info(f"Starting benchmark at {datetime.now().isoformat()}")

    # Initialize providers
    duckduckgo_provider = DuckDuckGoProvider(timeout=30)
    wikipedia_provider = WikipediaProvider(timeout=30)
    arxiv_provider = ArxivProvider(timeout=30)

    benchmark_start = time.time()

    # Run all queries
    results = []
    for query in BENCHMARK_QUERIES:
        try:
            result = await run_single_benchmark(
                query=query,
                duckduckgo_provider=duckduckgo_provider,
                wikipedia_provider=wikipedia_provider,
                arxiv_provider=arxiv_provider,
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Benchmark query failed: {query}, error: {str(e)}")
            results.append({
                "query": query,
                "error": str(e),
                "final_status": "error",
            })

    total_benchmark_time = time.time() - benchmark_start

    # Calculate aggregate statistics
    successful_queries = sum(1 for r in results if r.get("final_status") == "success")
    failed_queries = sum(1 for r in results if r.get("final_status") == "failure")

    provider_stats = {
        "duckduckgo": {"successes": 0, "failures": 0, "avg_time": 0, "total_results": 0},
        "wikipedia": {"successes": 0, "failures": 0, "avg_time": 0, "total_results": 0},
        "arxiv": {"successes": 0, "failures": 0, "avg_time": 0, "total_results": 0},
    }

    execution_times = []

    for result in results:
        if "providers" in result:
            for provider_name, provider_result in result["providers"].items():
                if provider_result["success"]:
                    provider_stats[provider_name]["successes"] += 1
                    provider_stats[provider_name]["total_results"] += provider_result["result_count"]
                    provider_stats[provider_name]["avg_time"] += provider_result["execution_time"]
                else:
                    provider_stats[provider_name]["failures"] += 1

        if result.get("total_execution_time"):
            execution_times.append(result["total_execution_time"])

    # Calculate averages
    for provider_name in provider_stats:
        if provider_stats[provider_name]["successes"] > 0:
            provider_stats[provider_name]["avg_time"] /= provider_stats[provider_name]["successes"]

    avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
    max_execution_time = max(execution_times) if execution_times else 0
    min_execution_time = min(execution_times) if execution_times else 0

    # Compile final results
    benchmark_results = {
        "benchmark_info": {
            "task": "TASK-031.2",
            "timestamp": datetime.now().isoformat(),
            "total_queries": len(BENCHMARK_QUERIES),
            "total_benchmark_time": total_benchmark_time,
        },
        "summary": {
            "successful_queries": successful_queries,
            "failed_queries": failed_queries,
            "success_rate": successful_queries / len(BENCHMARK_QUERIES) if BENCHMARK_QUERIES else 0,
            "avg_execution_time": avg_execution_time,
            "max_execution_time": max_execution_time,
            "min_execution_time": min_execution_time,
        },
        "provider_statistics": provider_stats,
        "individual_results": results,
    }

    # Print summary
    logger.info("=" * 60)
    logger.info("BENCHMARK SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total Queries: {len(BENCHMARK_QUERIES)}")
    logger.info(f"Successful: {successful_queries}")
    logger.info(f"Failed: {failed_queries}")
    logger.info(f"Success Rate: {benchmark_results['summary']['success_rate']:.2%}")
    logger.info(f"Total Benchmark Time: {total_benchmark_time:.2f}s")
    logger.info(f"Avg Execution Time: {avg_execution_time:.2f}s")
    logger.info(f"Max Execution Time: {max_execution_time:.2f}s")
    logger.info(f"Min Execution Time: {min_execution_time:.2f}s")

    logger.info("\nProvider Statistics:")
    for provider_name, stats in provider_stats.items():
        logger.info(f"  {provider_name}:")
        logger.info(f"    Successes: {stats['successes']}")
        logger.info(f"    Failures: {stats['failures']}")
        logger.info(f"    Avg Time: {stats['avg_time']:.2f}s")
        logger.info(f"    Total Results: {stats['total_results']}")

    return benchmark_results


if __name__ == "__main__":
    results = asyncio.run(run_full_benchmark())

    # Save results to file
    output_file = "benchmark_031_2_results.json"
    import json
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Benchmark results saved to {output_file}")
