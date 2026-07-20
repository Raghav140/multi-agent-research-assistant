"""Research node for LangGraph workflow.

This module implements the research node that coordinates information retrieval
from web search and academic paper sources using dependency injection.
"""

import asyncio
import time
from typing import Any

from backend.core.interfaces import SearchProvider
from backend.graph.state import ResearchState
from backend.providers.papers.arxiv_provider import ArxivProvider
from backend.utils.logging_config import get_logger
from backend.utils.source_ranking import rank_sources

logger = get_logger(__name__)


async def research_node(
    state: ResearchState,
    search_provider: SearchProvider,
    arxiv_provider: ArxivProvider,
) -> ResearchState:
    """Research node - coordinates information retrieval from multiple sources.

    This node executes web search and arXiv search concurrently using
    dependency injection. Results are stored separately in the state.

    Args:
        state: Current workflow state containing research plan
        search_provider: Search provider instance (dependency injection)
        arxiv_provider: arXiv provider instance (dependency injection)

    Returns:
        Updated state with search_results and research_papers
    """
    request_id = state.get("request_id")
    research_plan = state.get("metadata", {}).get("research_plan", {})
    user_query = state.get("user_query", "")

    logger.info(
        f"Research node started",
        extra={
            "request_id": request_id,
            "user_query": user_query,
            "has_research_plan": bool(research_plan),
        },
    )

    # Extract tasks from research plan or use user query directly
    if research_plan and "tasks" in research_plan:
        search_query = research_plan["tasks"][0] if research_plan["tasks"] else user_query
    else:
        search_query = user_query

    start_time = time.time()

    # Execute searches concurrently
    try:
        web_search_task = search_provider.search(
            query=search_query,
            num_results=2,  # Reduced from 5 - report only uses 2 results
            request_id=request_id,
        )
        logger.info(
            "Web search task created",
            extra={
                "request_id": request_id,
                "query": search_query,
                "num_results_requested": 2,
            },
        )
    except Exception as e:
        logger.error(
            f"Web search task creation failed: {str(e)}",
            extra={
                "request_id": request_id,
                "error": str(e),
            },
        )
        web_search_task = None

    try:
        arxiv_search_task = arxiv_provider.search(
            query=search_query,
            max_results=1,  # Reduced from 3 - report only uses 1 paper
            request_id=request_id,
        )
        logger.info(
            "arXiv search task created",
            extra={
                "request_id": request_id,
                "query": search_query,
                "max_results_requested": 1,
            },
        )
    except Exception as e:
        logger.error(
            f"arXiv search task creation failed: {str(e)}",
            extra={
                "request_id": request_id,
                "error": str(e),
            },
        )
        arxiv_search_task = None

    # Execute available tasks concurrently
    search_results = []
    research_papers = []
    errors = []

    tasks_to_execute = []
    if web_search_task:
        tasks_to_execute.append(("web", web_search_task))
    if arxiv_search_task:
        tasks_to_execute.append(("arxiv", arxiv_search_task))

    if tasks_to_execute:
        try:
            results = await asyncio.gather(
                *[task for _, task in tasks_to_execute],
                return_exceptions=True,
            )

            for (source, _), result in zip(tasks_to_execute, results):
                if isinstance(result, Exception):
                    logger.error(
                        f"{source} search failed: {str(result)}",
                        extra={
                            "request_id": request_id,
                            "source": source,
                            "error": str(result),
                        },
                    )
                    errors.append({
                        "source": source,
                        "error": str(result),
                        "error_type": type(result).__name__,
                    })
                else:
                    if source == "web":
                        search_results = result
                    elif source == "arxiv":
                        research_papers = result

        except Exception as e:
            logger.error(
                f"Concurrent search execution failed: {str(e)}",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                },
            )
            errors.append({
                "source": "concurrent_execution",
                "error": str(e),
                "error_type": type(e).__name__,
            })

    # Rank and score sources
    ranking_start = time.time()
    ranked_web_results, ranked_papers, ranking_metrics = rank_sources(
        web_results=search_results,
        papers=research_papers,
        query=user_query,
    )
    ranking_time = (time.time() - ranking_start) * 1000

    logger.info(
        "Source ranking completed",
        extra={
            "request_id": request_id,
            "ranking_time_ms": ranking_metrics["ranking_time_ms"],
            "normalization_ms": ranking_metrics["normalization_ms"],
            "scoring_ms": ranking_metrics["scoring_ms"],
            "sorting_ms": ranking_metrics["sorting_ms"],
            "duplicate_detection_ms": ranking_metrics["duplicate_detection_ms"],
            "duplicates_removed": ranking_metrics["duplicates_removed"],
            "sources_before": ranking_metrics["sources_before"],
            "sources_after": ranking_metrics["sources_after"],
            "academic_query": ranking_metrics["academic_query"],
            "academic_sources_selected": ranking_metrics["academic_sources_selected"],
            "final_sources_used": ranking_metrics["final_sources_used"],
            "average_source_score": ranking_metrics["average_source_score"],
            "highest_source_score": ranking_metrics["highest_source_score"],
            "lowest_source_score": ranking_metrics["lowest_source_score"],
        },
    )

    execution_time = time.time() - start_time

    logger.info(
        f"Research node completed - Duration: {execution_time:.0f}ms",
        extra={
            "request_id": request_id,
            "execution_time_ms": execution_time * 1000,
            "num_web_results_received": len(search_results),
            "num_papers_received": len(research_papers),
            "num_errors": len(errors),
            "web_search_percent": 0,  # Will be calculated after total known
            "arxiv_search_percent": 0,  # Will be calculated after total known
        },
    )

    # Update state with ranked results
    updated_state = state.copy()
    updated_state["search_results"] = ranked_web_results
    updated_state["research_papers"] = ranked_papers
    updated_state["ranking_metrics"] = ranking_metrics
    updated_state["intermediate_steps"] = state.get("intermediate_steps", [])
    updated_state["intermediate_steps"].append({
        "node": "research",
        "action": "retrieved_research_data",
        "status": "completed" if not errors else "partial",
        "num_web_results": len(ranked_web_results),
        "num_papers": len(ranked_papers),
        "num_errors": len(errors),
        "ranking_time_ms": ranking_time,
        "duplicates_removed": ranking_metrics["duplicates_removed"],
    })

    # Append errors if any
    if errors:
        updated_state["errors"] = state.get("errors", [])
        updated_state["errors"].extend(errors)

    return updated_state
