"""Planner node for LangGraph workflow.

This module implements the planner node that analyzes the user query
and creates a structured research plan using the LLM provider.
"""

import time
from typing import Any

from backend.core.interfaces import LLMProvider
from backend.graph.state import ResearchState
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


async def planner_node(
    state: ResearchState,
    llm_provider: LLMProvider,
) -> ResearchState:
    """Planner node - analyzes user query and creates research plan.

    This node uses the LLM provider to analyze the user query and generate
    a structured research plan with goals and tasks.

    Args:
        state: Current workflow state containing user_query
        llm_provider: LLM provider instance (dependency injection)

    Returns:
        Updated state with research plan in metadata
    """
    start_time = time.time()
    
    user_query = state.get("user_query", "")
    request_id = state.get("request_id")

    logger.info(
        f"Planner node started",
        extra={
            "request_id": request_id,
            "user_query": user_query,
        },
    )

    # Create planning prompt
    prompt = f"""You are a research planning assistant. Analyze the user's query and create a structured research plan.

User Query: {user_query}

Your task is to:
1. Understand the research goal
2. Break it down into specific, actionable tasks
3. Output a JSON response with this exact structure:
{{
  "goal": "Clear statement of the research objective",
  "tasks": [
    "Specific task 1",
    "Specific task 2",
    "Specific task 3"
  ]
}}

Be specific and practical. Focus on what information needs to be gathered."""

    try:
        # Call LLM provider to generate research plan
        response = await llm_provider.generate(
            prompt=prompt,
            temperature=0.3,  # Lower temperature for more structured output
            max_tokens=256,  # Optimized for planning tasks
            request_id=request_id,
            function_name="planner",
        )

        # Parse the response (in production, add proper JSON parsing with error handling)
        # For now, we'll store the raw response and structure it
        research_plan = {
            "goal": f"Research and analyze: {user_query}",
            "tasks": [
                "Gather background information on the topic",
                "Search for relevant academic papers and research",
                "Analyze findings and synthesize information",
                "Prepare comprehensive report",
            ],
            "raw_response": response,
        }

        # Update state with research plan
        updated_state = state.copy()
        updated_state["metadata"] = state.get("metadata", {})
        updated_state["metadata"]["research_plan"] = research_plan
        updated_state["intermediate_steps"] = state.get("intermediate_steps", [])
        updated_state["intermediate_steps"].append({
            "node": "planner",
            "action": "created_research_plan",
            "status": "completed",
            "plan": research_plan,
        })

        execution_time = time.time() - start_time

        logger.info(
            f"Planner node completed successfully - Duration: {execution_time:.0f}ms",
            extra={
                "request_id": request_id,
                "plan_goal": research_plan["goal"],
                "num_tasks": len(research_plan["tasks"]),
                "execution_time_ms": execution_time * 1000,
            },
        )

        return updated_state

    except Exception as e:
        execution_time = time.time() - start_time

        logger.error(
            f"Planner node failed: {str(e)}",
            extra={
                "request_id": request_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time_ms": execution_time * 1000,
            },
        )

        # Continue gracefully - append error to state and continue
        updated_state = state.copy()
        updated_state["errors"] = state.get("errors", [])
        updated_state["errors"].append({
            "node": "planner",
            "error": str(e),
            "error_type": type(e).__name__,
        })
        updated_state["intermediate_steps"] = state.get("intermediate_steps", [])
        updated_state["intermediate_steps"].append({
            "node": "planner",
            "action": "created_research_plan",
            "status": "failed",
            "error": str(e),
        })

        # Set a fallback plan
        updated_state["metadata"] = state.get("metadata", {})
        updated_state["metadata"]["research_plan"] = {
            "goal": f"Research and analyze: {user_query}",
            "tasks": [
                "Gather background information",
                "Search for relevant research",
                "Analyze findings",
                "Prepare report",
            ],
            "fallback": True,
        }

        return updated_state
