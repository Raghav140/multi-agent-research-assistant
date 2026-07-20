"""LangGraph workflow state definition.

This module defines the shared application state for the LangGraph workflow
using TypedDict for strong typing. The state is provider-agnostic and
contains all necessary fields for the research assistant workflow.
"""

from typing import Any, TypedDict


class ResearchState(TypedDict, total=False):
    """Shared application state for the LangGraph research workflow.

    This TypedDict defines the structure of the state object that flows
    through the LangGraph workflow nodes. All fields are optional to allow
    gradual population of the state as the workflow progresses.

    Attributes:
        user_query: The original user query or research question
        conversation_id: Unique identifier for the conversation session
        request_id: Unique identifier for the current request
        search_results: Results from web search operations
        research_papers: Academic papers retrieved from research databases
        retrieved_documents: Documents retrieved from vector store
        context: Accumulated context from various sources
        intermediate_steps: List of intermediate processing steps
        final_answer: The final answer generated for the user query
        report: Structured research report
        errors: List of errors encountered during processing
        metadata: Additional metadata about the workflow execution
        _timing_planner: Execution time for planner node (ms)
        _timing_research: Execution time for research node (ms)
        _timing_search: Execution time for search node (ms)
        _timing_report: Execution time for report node (ms)
        _planner_copy_overhead_ms: State copy overhead for planner (ms)
        _research_copy_overhead_ms: State copy overhead for research (ms)
        _search_copy_overhead_ms: State copy overhead for search (ms)
        _report_copy_overhead_ms: State copy overhead for report (ms)
    """

    user_query: str
    conversation_id: str
    request_id: str
    search_results: list[dict[str, Any]]
    research_papers: list[dict[str, Any]]
    retrieved_documents: list[dict[str, Any]]
    context: str
    intermediate_steps: list[dict[str, Any]]
    final_answer: str
    report: dict[str, Any]
    errors: list[dict[str, Any]]
    metadata: dict[str, Any]
    _timing_planner: float
    _timing_research: float
    _timing_search: float
    _timing_report: float
    _planner_copy_overhead_ms: float
    _research_copy_overhead_ms: float
    _search_copy_overhead_ms: float
    _report_copy_overhead_ms: float


def create_initial_state(
    user_query: str,
    conversation_id: str | None = None,
    request_id: str | None = None,
) -> ResearchState:
    """Create an initial state object with required fields.

    Args:
        user_query: The user's research query
        conversation_id: Optional conversation identifier
        request_id: Optional request identifier

    Returns:
        Initial ResearchState with populated required fields
    """
    import uuid

    return ResearchState(
        user_query=user_query,
        conversation_id=conversation_id or str(uuid.uuid4()),
        request_id=request_id or str(uuid.uuid4()),
        search_results=[],
        research_papers=[],
        retrieved_documents=[],
        context="",
        intermediate_steps=[],
        final_answer="",
        report={},
        errors=[],
        metadata={},
    )
