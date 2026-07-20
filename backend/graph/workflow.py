"""LangGraph workflow skeleton for research assistant.

This module defines the LangGraph workflow structure with placeholder nodes
for the research assistant pipeline. No AI logic is implemented - only the
workflow structure and node connections.
"""

import time
from typing import Any

from langgraph.graph import END, StateGraph

from backend.core.interfaces import LLMProvider, SearchProvider
from backend.graph.nodes import planner_node, research_node, report_node
from backend.graph.state import ResearchState
from backend.providers.papers.arxiv_provider import ArxivProvider
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


async def search_node(state: ResearchState) -> ResearchState:
    """Search node - performs web search for additional information.

    This is a placeholder node that will eventually perform web searches
    to gather additional context and information.

    Args:
        state: Current workflow state

    Returns:
        Updated state with search results
    """
    # Placeholder logic - no web search, return state unchanged
    # No copy needed since we're not modifying the state
    return state


def build_workflow(
    llm_provider: LLMProvider,
    search_provider: SearchProvider,
    arxiv_provider: ArxivProvider,
) -> StateGraph:
    """Build and compile the LangGraph workflow.

    This function creates the workflow graph, adds all nodes, and
    establishes the connections between them in the required order:
    START -> Planner -> Research -> Search -> Report -> END

    Args:
        llm_provider: LLM provider instance for dependency injection
        search_provider: Search provider instance for dependency injection
        arxiv_provider: arXiv provider instance for dependency injection

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
        result["_timing_planner"] = execution_time
        result["_planner_copy_overhead_ms"] = copy_duration * 1000
        return result

    # Create wrapper for research node with dependency injection and timing
    async def research_wrapper(state: ResearchState) -> ResearchState:
        """Wrapper for research node with dependency injection."""
        wrapper_start = time.time()
        result = await research_node(state, search_provider, arxiv_provider)
        node_duration = time.time() - wrapper_start
        
        # Track state copying overhead
        copy_start = time.time()
        if result is state:
            result = state.copy()
        copy_duration = time.time() - copy_start
        
        execution_time = (time.time() - wrapper_start) * 1000
        result["_timing_planner"] = state.get("_timing_planner", 0)
        result["_timing_research"] = execution_time
        result["_research_copy_overhead_ms"] = copy_duration * 1000
        return result

    # Create wrapper for search node with timing
    async def search_wrapper(state: ResearchState) -> ResearchState:
        """Wrapper for search node with timing."""
        wrapper_start = time.time()
        result = await search_node(state)
        node_duration = time.time() - wrapper_start
        
        # Track state copying overhead
        copy_start = time.time()
        if result is state:
            result = state.copy()
        copy_duration = time.time() - copy_start
        
        execution_time = (time.time() - wrapper_start) * 1000
        result["_timing_planner"] = state.get("_timing_planner", 0)
        result["_timing_research"] = state.get("_timing_research", 0)
        result["_timing_search"] = execution_time
        result["_search_copy_overhead_ms"] = copy_duration * 1000
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
        result["_timing_planner"] = state.get("_timing_planner", 0)
        result["_timing_research"] = state.get("_timing_research", 0)
        result["_timing_search"] = state.get("_timing_search", 0)
        result["_timing_report"] = execution_time
        result["_report_copy_overhead_ms"] = copy_duration * 1000
        return result

    # Create the workflow graph
    workflow = StateGraph(ResearchState)

    # Add nodes to the workflow
    workflow.add_node("planner", planner_wrapper)
    workflow.add_node("research", research_wrapper)
    workflow.add_node("search", search_wrapper)
    workflow.add_node("report", report_wrapper)

    # Define the workflow edges
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "research")
    workflow.add_edge("research", "search")
    workflow.add_edge("search", "report")
    workflow.add_edge("report", END)

    # Compile the workflow
    compiled_workflow = workflow.compile()

    return compiled_workflow
