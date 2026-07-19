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
            num_results=5,
            request_id=request_id,
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
            max_results=3,
            request_id=request_id,
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

    execution_time = time.time() - start_time

    logger.info(
        f"Research node completed",
        extra={
            "request_id": request_id,
            "execution_time": execution_time,
            "num_web_results": len(search_results),
            "num_papers": len(research_papers),
            "num_errors": len(errors),
        },
    )

    # Update state with results
    updated_state = state.copy()
    updated_state["search_results"] = search_results
    updated_state["research_papers"] = research_papers
    updated_state["intermediate_steps"] = state.get("intermediate_steps", [])
    updated_state["intermediate_steps"].append({
        "node": "research",
        "action": "retrieved_research_data",
        "status": "completed" if not errors else "partial",
        "num_web_results": len(search_results),
        "num_papers": len(research_papers),
        "num_errors": len(errors),
    })

    # Append errors if any
    if errors:
        updated_state["errors"] = state.get("errors", [])
        updated_state["errors"].extend(errors)

    return updated_state
