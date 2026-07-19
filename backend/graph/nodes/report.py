"""Report node for LangGraph workflow.

This module implements the report node that synthesizes retrieved information
into a final research report using the LLM provider.
"""

import time
from typing import Any

from backend.core.interfaces import LLMProvider
from backend.graph.state import ResearchState
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


async def report_node(
    state: ResearchState,
    llm_provider: LLMProvider,
) -> ResearchState:
    """Report node - synthesizes findings into a final research report.

    This node uses the LLM provider to generate a comprehensive research report
    based on the user query, research plan, search results, and academic papers.

    Args:
        state: Current workflow state containing research data
        llm_provider: LLM provider instance (dependency injection)

    Returns:
        Updated state with report and final_answer
    """
    request_id = state.get("request_id")
    user_query = state.get("user_query", "")
    research_plan = state.get("metadata", {}).get("research_plan", {})
    search_results = state.get("search_results", [])
    research_papers = state.get("research_papers", [])

    logger.info(
        f"Report node started",
        extra={
            "request_id": request_id,
            "user_query": user_query,
            "num_search_results": len(search_results),
            "num_papers": len(research_papers),
        },
    )

    start_time = time.time()

    # Build the prompt
    prompt_parts = [
        "You are a research assistant. Your task is to synthesize information from multiple sources to answer the user's question.",
        "",
        f"User Question: {user_query}",
        "",
    ]

    # Add research plan if available
    if research_plan:
        prompt_parts.append(f"Research Plan: {research_plan.get('goal', 'N/A')}")
        prompt_parts.append("Tasks:")
        for task in research_plan.get("tasks", []):
            prompt_parts.append(f"  - {task}")
        prompt_parts.append("")

    # Add web search results
    if search_results:
        prompt_parts.append("Web Search Results:")
        for i, result in enumerate(search_results[:5], 1):
            prompt_parts.append(f"{i}. {result.get('title', 'N/A')}")
            prompt_parts.append(f"   URL: {result.get('url', 'N/A')}")
            prompt_parts.append(f"   Snippet: {result.get('snippet', 'N/A')[:200]}...")
        prompt_parts.append("")

    # Add research papers
    if research_papers:
        prompt_parts.append("Academic Papers:")
        for i, paper in enumerate(research_papers[:3], 1):
            prompt_parts.append(f"{i}. {paper.get('title', 'N/A')}")
            prompt_parts.append(f"   Authors: {', '.join(paper.get('authors', []))}")
            prompt_parts.append(f"   Published: {paper.get('published', 'N/A')}")
            prompt_parts.append(f"   Abstract: {paper.get('abstract', 'N/A')[:300]}...")
        prompt_parts.append("")

    prompt_parts.extend([
        "Instructions:",
        "- Answer the user's question based on the provided information",
        "- Combine insights from both web search and academic papers",
        "- When citing information from research papers, explicitly mention 'According to research papers...' or 'Academic research indicates...'",
        "- Produce a clear, well-structured Markdown report",
        "- If information is insufficient, acknowledge limitations",
        "- Be thorough but concise",
        "",
        "Generate the report now:"
    ])

    prompt = "\n".join(prompt_parts)

    try:
        # Generate report using LLM provider
        report = await llm_provider.generate(
            prompt=prompt,
            temperature=0.5,  # Moderate temperature for balanced creativity
            max_tokens=3000,
            request_id=request_id,
        )

        execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        logger.info(
            f"Report node completed successfully",
            extra={
                "request_id": request_id,
                "execution_time_ms": execution_time,
                "report_length": len(report),
            },
        )

        # Update state with results
        updated_state = state.copy()
        updated_state["report"] = {
            "content": report,
            "sources": {
                "web_results": len(search_results),
                "papers": len(research_papers),
            },
            "generated_at": time.time(),
        }
        updated_state["final_answer"] = report
        updated_state["intermediate_steps"] = state.get("intermediate_steps", [])
        updated_state["intermediate_steps"].append({
            "node": "report",
            "action": "synthesized_final_report",
            "status": "completed",
            "execution_time_ms": execution_time,
            "report_length": len(report),
        })

        return updated_state

    except Exception as e:
        execution_time = (time.time() - start_time) * 1000

        logger.error(
            f"Report node failed: {str(e)}",
            extra={
                "request_id": request_id,
                "execution_time_ms": execution_time,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )

        # Create fallback report
        fallback_report = f"""# Research Report

## Question
{user_query}

## Findings
Based on the available information:

### Web Sources
- Found {len(search_results)} web search results
- Key sources include: {', '.join([r.get('title', 'N/A') for r in search_results[:3]])}

### Academic Sources
- Found {len(research_papers)} relevant research papers
- Recent research includes: {', '.join([p.get('title', 'N/A') for p in research_papers[:2]])}

## Note
The automated report generation encountered an error. Please review the raw search results and papers above for detailed information.

Error: {str(e)}
"""

        # Update state with fallback
        updated_state = state.copy()
        updated_state["report"] = {
            "content": fallback_report,
            "sources": {
                "web_results": len(search_results),
                "papers": len(research_papers),
            },
            "generated_at": time.time(),
            "fallback": True,
        }
        updated_state["final_answer"] = fallback_report
        updated_state["errors"] = state.get("errors", [])
        updated_state["errors"].append({
            "node": "report",
            "error": str(e),
            "error_type": type(e).__name__,
        })
        updated_state["intermediate_steps"] = state.get("intermediate_steps", [])
        updated_state["intermediate_steps"].append({
            "node": "report",
            "action": "synthesized_final_report",
            "status": "failed",
            "execution_time_ms": execution_time,
            "report_length": len(fallback_report),
        })

        return updated_state
