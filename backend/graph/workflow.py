"""LangGraph workflow for research assistant.

This module defines the LangGraph workflow structure for the research assistant
pipeline with integrated retrieval orchestration.
"""

import time
from typing import Any

from langgraph.graph import END, StateGraph

from backend.core.interfaces import LLMProvider
from backend.graph.nodes import planner_node, research_node, report_node
from backend.graph.state import ResearchState
from backend.services.retrieval_engine import RetrievalEngine
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


def build_workflow(
    llm_provider: LLMProvider,
    retrieval_engine: RetrievalEngine,
) -> StateGraph:
    """Build and compile the LangGraph workflow.

    This function creates the workflow graph, adds all nodes, and
    establishes the connections between them in the required order:
    START -> Planner -> Research -> Report -> END

    Note: The search_node placeholder has been removed since RetrievalEngine
    now handles all multi-provider retrieval within the research_node.

    Args:
        llm_provider: LLM provider instance for dependency injection
        retrieval_engine: RetrievalEngine instance for centralized provider orchestration

    Returns:
        Compiled StateGraph ready for execution
    """
    # Create wrapper for planner node with dependency injection and timing
    async def planner_wrapper(state: ResearchState) -> ResearchState:
        """Wrapper for planner node with dependency injection."""
        wrapper_start = time.time()
        result = await planner_node(state, llm_provider)
        node_duration = time.time() - wrapper_start

        # Track state copying overhead
        copy_start = time.time()
        if result is state:
            result = state.copy()
        copy_duration = time.time() - copy_start

        execution_time = (time.time() - wrapper_start) * 1000
        # Ensure timing is preserved even if node returned a copy
        result["_timing_planner"] = execution_time
        result["_planner_copy_overhead_ms"] = copy_duration * 1000
        # Log wrapper timing for debugging
        logger.info(
            f"Planner wrapper completed - Duration: {execution_time:.0f}ms",
            extra={
                "request_id": state.get("request_id"),
                "wrapper_execution_time_ms": execution_time,
                "node_execution_time_ms": node_duration * 1000,
                "copy_overhead_ms": copy_duration * 1000,
            },
        )
        return result

    # Create wrapper for research node with dependency injection and timing
    async def research_wrapper(state: ResearchState) -> ResearchState:
        """Wrapper for research node with dependency injection."""
        wrapper_start = time.time()
        result = await research_node(state, retrieval_engine)
        node_duration = time.time() - wrapper_start

        # Track state copying overhead
        copy_start = time.time()
        if result is state:
            result = state.copy()
        copy_duration = time.time() - copy_start

        execution_time = (time.time() - wrapper_start) * 1000
        # Preserve timing from previous nodes and add current timing
        result["_timing_planner"] = state.get("_timing_planner", 0)
        result["_timing_research"] = execution_time
        result["_planner_copy_overhead_ms"] = state.get("_planner_copy_overhead_ms", 0)
        result["_research_copy_overhead_ms"] = copy_duration * 1000
        return result

    # Create wrapper for report node with dependency injection and timing
    async def report_wrapper(state: ResearchState) -> ResearchState:
        """Wrapper for report node with dependency injection."""
        wrapper_start = time.time()
        result = await report_node(state, llm_provider)
        node_duration = time.time() - wrapper_start

        # Track state copying overhead
        copy_start = time.time()
        if result is state:
            result = state.copy()
        copy_duration = time.time() - copy_start

        execution_time = (time.time() - wrapper_start) * 1000
        # Preserve timing from previous nodes and add current timing
        result["_timing_planner"] = state.get("_timing_planner", 0)
        result["_timing_research"] = state.get("_timing_research", 0)
        result["_timing_report"] = execution_time
        result["_planner_copy_overhead_ms"] = state.get("_planner_copy_overhead_ms", 0)
        result["_research_copy_overhead_ms"] = state.get("_research_copy_overhead_ms", 0)
        result["_report_copy_overhead_ms"] = copy_duration * 1000
        return result

    # Create the workflow graph
    workflow = StateGraph(ResearchState)

    # Add nodes to the workflow
    workflow.add_node("planner", planner_wrapper)
    workflow.add_node("research", research_wrapper)
    workflow.add_node("report", report_wrapper)

    # Define the workflow edges (removed search_node)
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "research")
    workflow.add_edge("research", "report")
    workflow.add_edge("report", END)

    # Compile the workflow
    compiled_workflow = workflow.compile()

    return compiled_workflow
