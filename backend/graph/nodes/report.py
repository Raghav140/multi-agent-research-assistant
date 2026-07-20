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
    start_time = time.time()
    
    request_id = state.get("request_id")
    user_query = state.get("user_query", "")
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

    # Build the prompt
    prompt_parts = [
        "You are a fast research report generator.",
        "Do not explain your reasoning.",
        "Do not analyze your process.",
        "Only output the final answer.",
        "Start directly with the report.",
        "",
        f"User Question: {user_query}",
        "",
    ]


    # Add web search results (deduplicated and limited)
    if search_results:
        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for result in search_results:
            url = result.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
        
        prompt_parts.append("Web Search Results:")
        for i, result in enumerate(unique_results[:2], 1):  # Reduced from 3 to 2
            prompt_parts.append(f"{i}. {result.get('title', 'N/A')}")
            prompt_parts.append(f"   Snippet: {result.get('snippet', 'N/A')[:80]}...")  # Reduced from 100 to 80
        prompt_parts.append("")

    # Add research papers (limited)
    if research_papers:
        prompt_parts.append("Academic Papers:")
        for i, paper in enumerate(research_papers[:1], 1):  # Reduced from 2 to 1
            prompt_parts.append(f"{i}. {paper.get('title', 'N/A')}")
            prompt_parts.append(f"   Abstract: {paper.get('abstract', 'N/A')[:120]}...")  # Reduced from 150 to 120
        prompt_parts.append("")

    prompt_parts.extend([
        "Write a concise research report.",
        "",
        "Use only the provided sources.",
        "",
        "Structure:",
        "- Summary",
        "- Key findings",
        "- Important evidence",
        "- Sources",
        "",
        "Rules:",
        "- Do not show reasoning steps.",
        "- Do not explain your thought process.",
        "- Only provide the final answer.",
        "",
        "Generate the report now:"
    ])

    prompt = "\n".join(prompt_parts)

    # Log detailed prompt construction for debugging
    logger.info(
        "Report prompt construction details",
        extra={
            "request_id": request_id,
            "system_instructions_chars": len("\n".join(prompt_parts[:6])),
            "user_query_chars": len(user_query),
            "num_web_results_in_prompt": len([p for p in prompt_parts if "Web Search Results" in p or p.startswith(("1.", "2."))]),
            "num_papers_in_prompt": len([p for p in prompt_parts if "Academic Papers" in p or p.startswith(("1.", "2."))]),
            "structure_rules_chars": len("\n".join(prompt_parts[-9:])),
            "total_prompt_chars": len(prompt),
            "total_prompt_words": len(prompt.split()),
            "max_tokens": 512,
        },
    )

    try:
        # Generate report using LLM provider
        report = await llm_provider.generate(
            prompt=prompt,
            temperature=0.5,  # Moderate temperature for balanced creativity
            max_tokens=512,  # Further optimized for faster report generation
            request_id=request_id,
            function_name="report",
        )

        execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        logger.info(
            f"Report node completed successfully",
            extra={
                "request_id": request_id,
                "execution_time_ms": execution_time,
                "prompt_length": len(prompt),
                "report_length": len(report),
                "sources_received": len(search_results),
                "sources_used_in_prompt": len(unique_results[:2]) if search_results else 0,
                "papers_received": len(research_papers),
                "papers_used_in_prompt": len(research_papers[:1]) if research_papers else 0,
            },
        )

        # Update state with results (avoid duplicate storage)
        updated_state = state.copy()
        updated_state["report"] = {
            "content": report,
            "sources": {
                "web_results": len(search_results),
                "papers": len(research_papers),
            },
            "generated_at": time.time(),
        }
        # Reference the same content instead of duplicating
        updated_state["final_answer"] = updated_state["report"]["content"]
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

        # Update state with fallback (avoid duplicate storage)
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
        # Reference the same content instead of duplicating
        updated_state["final_answer"] = updated_state["report"]["content"]
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
