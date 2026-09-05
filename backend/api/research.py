"""Research API endpoint for LangGraph workflow execution."""

import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.config.dependencies import (
    get_arxiv_provider,
    get_llm_provider,
    get_retrieval_engine,
    get_search_provider,
    get_wikipedia_provider,
)
from backend.core.interfaces import LLMProvider, SearchProvider
from backend.graph.state import create_initial_state
from backend.graph.workflow import build_workflow
from backend.providers.papers.arxiv_provider import ArxivProvider
from backend.providers.search.wikipedia_provider import WikipediaProvider
from backend.services.retrieval_engine import RetrievalEngine
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)

research_router = APIRouter(prefix="/api/v1", tags=["research"])


class ResearchRequest(BaseModel):
    """Request model for research endpoint."""

    query: str = Field(..., description="Research query", min_length=1)


class ResearchResponse(BaseModel):
    """Response model for research endpoint."""

    success: bool = Field(..., description="Whether the research completed successfully")
    degraded: bool = Field(default=False, description="Whether the result was degraded (fallback/cached)")
    answer: str = Field(..., description="Final answer to the research query")
    report: str = Field(..., description="Detailed research report")
    search_results: list[dict[str, Any]] = Field(default_factory=list, description="Web search results")
    papers: list[dict[str, Any]] = Field(default_factory=list, description="Academic research papers")
    execution_time_ms: float = Field(..., description="Total execution time in milliseconds")
    request_id: str = Field(..., description="Unique request identifier")
    cache_hit: bool | None = Field(default=None, description="Whether the result was served from cache")
    cache_metrics: dict[str, Any] | None = Field(default=None, description="Cache performance metrics")
    error_code: str | None = Field(default=None, description="Error code for failed requests")
    error_message: str | None = Field(default=None, description="User-facing error message")


@research_router.post("/research", response_model=ResearchResponse)
async def research(
    request: ResearchRequest,
    llm_provider: LLMProvider = Depends(get_llm_provider),
    retrieval_engine: RetrievalEngine = Depends(get_retrieval_engine),
) -> ResearchResponse:
    """Execute research workflow using LangGraph.

    This endpoint runs the complete research pipeline including planning,
    information retrieval from web and academic sources, and report generation.

    Args:
        request: Research request with query
        llm_provider: LLM provider for planning and report generation
        retrieval_engine: Centralized retrieval engine for multi-provider orchestration

    Returns:
        Research response with answer, report, and sources
    """
    request_id = str(uuid.uuid4())
    request_received_time = time.time()

    logger.info(
        f"Research request received",
        extra={
            "request_id": request_id,
            "query": request.query,
            "request_received_timestamp": request_received_time,
        },
    )

    # Track dependency injection timing
    di_start = time.time()
    # DI happens via FastAPI Depends before this point
    di_time = (time.time() - di_start) * 1000

    start_time = time.time()

    # Build initial state
    state = create_initial_state(
        user_query=request.query,
        request_id=request_id,
    )

    # Build workflow with dependency injection
    workflow_build_start = time.time()
    workflow = build_workflow(llm_provider, retrieval_engine)
    workflow_build_time = (time.time() - workflow_build_start) * 1000

    logger.info(
        "Workflow built",
        extra={
            "request_id": request_id,
            "workflow_build_time_ms": workflow_build_time,
        },
    )

    try:
        # Execute workflow
        workflow_invoke_start = time.time()
        result_state = await workflow.ainvoke(state)
        workflow_invoke_time = (time.time() - workflow_invoke_start) * 1000

        execution_time = (time.time() - start_time) * 1000

        # Extract node timings from state
        planner_time = result_state.get("_timing_planner", 0)
        research_time = result_state.get("_timing_research", 0)
        search_time = result_state.get("_timing_search", 0)
        report_time = result_state.get("_timing_report", 0)

        # Extract cache information from state
        research_metrics = result_state.get("metadata", {}).get("research_metrics", {})
        cache_hit = research_metrics.get("cache_hits", 0) > 0 or result_state.get("memory_hit", False)
        cache_metrics = {
            "hits": research_metrics.get("cache_hits", 0),
            "memory_hits": research_metrics.get("memory_hits", 0),
            "total_variations": research_metrics.get("total_variations", 0),
        }

        # Set degraded flag if cache or memory was hit
        degraded = cache_hit or result_state.get("memory_hit", False)

        # Track response serialization timing
        serialization_start = time.time()
        response = ResearchResponse(
            success=True,
            degraded=degraded,
            answer=result_state.get("final_answer", ""),
            report=result_state.get("report", {}).get("content", ""),
            search_results=result_state.get("search_results", []),
            papers=result_state.get("research_papers", []),
            execution_time_ms=execution_time,
            request_id=request_id,
            cache_hit=cache_hit,
            cache_metrics=cache_metrics,
        )
        serialization_time = (time.time() - serialization_start) * 1000

        logger.info(
            f"Research request completed successfully - Total: {execution_time:.0f}ms, Planner: {planner_time:.0f}ms, Research: {research_time:.0f}ms, Search: {search_time:.0f}ms, Report: {report_time:.0f}ms",
            extra={
                "request_id": request_id,
                "execution_time_ms": execution_time,
                "di_time_ms": di_time,
                "workflow_build_time_ms": workflow_build_time,
                "workflow_invoke_time_ms": workflow_invoke_time,
                "serialization_time_ms": serialization_time,
                "num_search_results": len(result_state.get("search_results", [])),
                "num_papers": len(result_state.get("research_papers", [])),
                "timing_planner_ms": planner_time,
                "timing_research_ms": research_time,
                "timing_search_ms": search_time,
                "timing_report_ms": report_time,
                "timing_sum_ms": planner_time + research_time + search_time + report_time,
                "timing_gap_ms": execution_time - (planner_time + research_time + search_time + report_time),
                "planner_copy_overhead_ms": result_state.get("_planner_copy_overhead_ms", 0),
                "research_copy_overhead_ms": result_state.get("_research_copy_overhead_ms", 0),
                "search_copy_overhead_ms": result_state.get("_search_copy_overhead_ms", 0),
                "report_copy_overhead_ms": result_state.get("_report_copy_overhead_ms", 0),
                "total_copy_overhead_ms": (
                    result_state.get("_planner_copy_overhead_ms", 0) +
                    result_state.get("_research_copy_overhead_ms", 0) +
                    result_state.get("_search_copy_overhead_ms", 0) +
                    result_state.get("_report_copy_overhead_ms", 0)
                ),
                "planner_percent": (planner_time / execution_time * 100) if execution_time > 0 else 0,
                "research_percent": (research_time / execution_time * 100) if execution_time > 0 else 0,
                "search_percent": (search_time / execution_time * 100) if execution_time > 0 else 0,
                "report_percent": (report_time / execution_time * 100) if execution_time > 0 else 0,
                "gap_percent": ((execution_time - (planner_time + research_time + search_time + report_time)) / execution_time * 100) if execution_time > 0 else 0,
            },
        )

        logger.info(
            f"Research workflow timing summary - Total: {execution_time:.0f}ms, Planner: {planner_time:.0f}ms, Research: {research_time:.0f}ms, Search: {search_time:.0f}ms, Report: {report_time:.0f}ms",
            extra={
                "request_id": request_id,
                "total_time_ms": execution_time,
                "planner_ms": planner_time,
                "research_ms": research_time,
                "search_ms": search_time,
                "report_ms": report_time,
            },
        )

        return response

    except Exception as e:
        execution_time = (time.time() - start_time) * 1000

        logger.error(
            f"Research request failed",
            extra={
                "request_id": request_id,
                "execution_time_ms": execution_time,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )

        # Return error response (do not expose internal exception details to user)
        return ResearchResponse(
            success=False,
            degraded=False,
            answer="Research failed. Please try again.",
            report="# Research Report\n\n## Error\n\nThe research workflow encountered an error. Please try again.",
            search_results=[],
            papers=[],
            execution_time_ms=execution_time,
            request_id=request_id,
            cache_hit=None,
            cache_metrics=None,
            error_code="WORKFLOW_ERROR",
            error_message="The research workflow encountered an error. Please try again.",
        )
