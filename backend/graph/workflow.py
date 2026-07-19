"""LangGraph workflow skeleton for research assistant.

This module defines the LangGraph workflow structure with placeholder nodes
for the research assistant pipeline. No AI logic is implemented - only the
workflow structure and node connections.
"""

from typing import Any

from langgraph.graph import END, StateGraph

from backend.core.interfaces import LLMProvider
from backend.graph.nodes import planner_node
from backend.graph.state import ResearchState


async def research_node(state: ResearchState) -> ResearchState:
    """Research node - performs academic research and paper retrieval.

    This is a placeholder node that will eventually search academic databases
    and retrieve relevant research papers.

    Args:
        state: Current workflow state

    Returns:
        Updated state with research papers
    """
    # Placeholder logic - no actual research
    updated_state = state.copy()
    updated_state["research_papers"] = state.get("research_papers", [])
    updated_state["intermediate_steps"] = state.get("intermediate_steps", [])
    updated_state["intermediate_steps"].append({
        "node": "research",
        "action": "retrieved_research_papers",
        "status": "completed"
    })
    return updated_state


async def search_node(state: ResearchState) -> ResearchState:
    """Search node - performs web search for additional information.

    This is a placeholder node that will eventually perform web searches
    to gather additional context and information.

    Args:
        state: Current workflow state

    Returns:
        Updated state with search results
    """
    # Placeholder logic - no web search
    updated_state = state.copy()
    updated_state["search_results"] = state.get("search_results", [])
    updated_state["intermediate_steps"] = state.get("intermediate_steps", [])
    updated_state["intermediate_steps"].append({
        "node": "search",
        "action": "performed_web_search",
        "status": "completed"
    })
    return updated_state


async def report_node(state: ResearchState) -> ResearchState:
    """Report node - synthesizes findings into a final report.

    This is a placeholder node that will eventually use an LLM to synthesize
    all gathered information into a comprehensive research report.

    Args:
        state: Current workflow state

    Returns:
        Updated state with final report and answer
    """
    # Placeholder logic - no LLM calls
    updated_state = state.copy()
    updated_state["report"] = state.get("report", {})
    updated_state["final_answer"] = state.get("final_answer", "")
    updated_state["intermediate_steps"] = state.get("intermediate_steps", [])
    updated_state["intermediate_steps"].append({
        "node": "report",
        "action": "synthesized_final_report",
        "status": "completed"
    })
    return updated_state


def build_workflow(llm_provider: LLMProvider) -> StateGraph:
    """Build and compile the LangGraph workflow.

    This function creates the workflow graph, adds all nodes, and
    establishes the connections between them in the required order:
    START -> Planner -> Research -> Search -> Report -> END

    Args:
        llm_provider: LLM provider instance for dependency injection

    Returns:
        Compiled StateGraph ready for execution
    """
    # Create wrapper for planner node with dependency injection
    async def planner_wrapper(state: ResearchState) -> ResearchState:
        """Wrapper for planner node with dependency injection."""
        return await planner_node(state, llm_provider)

    # Create the workflow graph
    workflow = StateGraph(ResearchState)

    # Add nodes to the workflow
    workflow.add_node("planner", planner_wrapper)
    workflow.add_node("research", research_node)
    workflow.add_node("search", search_node)
    workflow.add_node("report", report_node)

    # Define the workflow edges
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "research")
    workflow.add_edge("research", "search")
    workflow.add_edge("search", "report")
    workflow.add_edge("report", END)

    # Compile the workflow
    compiled_workflow = workflow.compile()

    return compiled_workflow
