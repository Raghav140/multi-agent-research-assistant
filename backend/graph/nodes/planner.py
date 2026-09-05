"""Planner node for LangGraph workflow."""

import json
import re
import time
from typing import Any

from backend.core.interfaces import LLMProvider
from backend.graph.state import ResearchState
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


def _fallback_plan(user_query: str, raw_response: str = "", fallback: bool = False) -> dict[str, Any]:
    """Build a safe fallback research plan."""
    return {
        "goal": f"Research and analyze: {user_query}",
        "tasks": [
            user_query,
            f"{user_query} overview",
            "Search for relevant academic papers",
            "Synthesize findings into a report",
        ],
        "query_type": "research",  # Default query type
        "preferred_providers": ["duckduckgo", "arxiv"],  # Default providers
        "research_depth": "moderate",  # Default research depth
        "raw_response": raw_response,
        "fallback": fallback,
    }


def _parse_research_plan(response: str, user_query: str) -> dict[str, Any]:
    """Parse LLM JSON plan response with fallback."""
    try:
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if match:
            data = json.loads(match.group())
            goal = data.get("goal") or f"Research and analyze: {user_query}"
            tasks = data.get("tasks") or []

            # Extract optional fields with defaults
            query_type = data.get("query_type", "research")
            preferred_providers = data.get("preferred_providers", ["duckduckgo", "arxiv"])
            research_depth = data.get("research_depth", "moderate")

            # Validate and normalize fields
            if isinstance(tasks, list) and tasks:
                cleaned_tasks = [str(t).strip() for t in tasks if str(t).strip()]
                if cleaned_tasks:
                    return {
                        "goal": str(goal).strip(),
                        "tasks": cleaned_tasks[:5],
                        "query_type": str(query_type).strip() if isinstance(query_type, str) else "research",
                        "preferred_providers": list(preferred_providers) if isinstance(preferred_providers, list) else ["duckduckgo", "arxiv"],
                        "research_depth": str(research_depth).strip() if isinstance(research_depth, str) else "moderate",
                        "raw_response": response,
                        "fallback": False,
                    }
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning(f"Failed to parse planner JSON: {e}")

    return _fallback_plan(user_query, raw_response=response, fallback=True)


async def planner_node(
    state: ResearchState,
    llm_provider: LLMProvider,
) -> ResearchState:
    """Planner node - analyzes user query and creates research plan."""
    start_time = time.time()
    user_query = state.get("user_query", "")
    request_id = state.get("request_id")

    logger.info(
        "Planner node started",
        extra={"request_id": request_id, "user_query": user_query},
    )

    prompt = (
        f'Query: "{user_query}"\n\n'
        'Return ONLY valid JSON: {"goal": "...", "tasks": ["search task 1", "search task 2"]}\n'
        "Tasks should be specific searchable queries related to the user question."
    )

    try:
        llm_start = time.time()
        response = await llm_provider.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=256,
            request_id=request_id,
            function_name="planner",
        )
        llm_ms = (time.time() - llm_start) * 1000
        research_plan = _parse_research_plan(response, user_query)

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

        logger.info(
            "Planner node completed",
            extra={
                "request_id": request_id,
                "plan_goal": research_plan["goal"],
                "num_tasks": len(research_plan["tasks"]),
                "used_fallback": research_plan.get("fallback", False),
                "llm_time_ms": llm_ms,
                "execution_time_ms": (time.time() - start_time) * 1000,
            },
        )
        return updated_state

    except Exception as e:
        logger.error(
            f"Planner node failed: {e}",
            extra={"request_id": request_id, "error_type": type(e).__name__},
        )
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
        updated_state["metadata"] = state.get("metadata", {})
        updated_state["metadata"]["research_plan"] = _fallback_plan(user_query, fallback=True)
        return updated_state
