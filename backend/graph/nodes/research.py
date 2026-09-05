"""Research node for LangGraph workflow.

This module implements the research node that coordinates information retrieval
from web search and academic paper sources using the centralized RetrievalEngine.
"""

import asyncio
import time
from typing import Any

from backend.graph.state import ResearchState
from backend.services.retrieval_engine import RetrievalEngine
from backend.utils.logging_config import get_logger
from backend.utils.source_ranking import rank_sources
from backend.utils.query_classifier import classify_query
from backend.utils.evidence_fusion import fuse_evidence
from backend.memory.memory_manager import get_memory_manager
from backend.utils.evaluation import get_evaluator
from backend.utils.cache import (
    get_cached_fusion_result,
    cache_fusion_result,
    get_cached_memory_lookup,
    cache_memory_lookup,
)

logger = get_logger(__name__)

MAX_QUERY_VARIATIONS = 3


def generate_query_variations(original_query: str, research_plan: dict[str, Any] | None = None) -> list[str]:
    """Generate search query variations for retrieval.

    Optimized for definition queries to reduce unnecessary variations.
    """
    query_lower = original_query.lower()
    variations = [original_query]

    # Use query_type from research plan if available
    query_type = research_plan.get("query_type", "research") if research_plan else "research"

    # For definition queries, minimize variations to reduce latency
    if query_type == "definition":
        # Definition queries: use original query + 1 variation max
        if "what is" in query_lower or "define" in query_lower or "explain" in query_lower:
            topic = original_query
            for prefix in ("What is", "what is", "Define", "define", "Explain", "explain"):
                topic = topic.replace(prefix, "").strip()
            if topic:
                variations.append(f"{topic} definition")
        # Limit to 2 variations for definition queries
        max_variations = 2
    elif query_type == "technical":
        # Technical queries: original + tutorial variation
        if "how to" in query_lower or "tutorial" in query_lower:
            variations.append(f"{original_query} tutorial")
        max_variations = 2
    else:
        # Research queries: use research plan tasks or standard variations
        if research_plan and research_plan.get("tasks"):
            for task in research_plan["tasks"][:2]:
                if task and task.lower() != original_query.lower():
                    variations.append(task)
        else:
            if "what is" in query_lower or "define" in query_lower or "explain" in query_lower:
                topic = original_query
                for prefix in ("What is", "what is", "Define", "define", "Explain", "explain"):
                    topic = topic.replace(prefix, "").strip()
                if topic:
                    variations.append(f"{topic} definition")
                    variations.append(f"{topic} overview")
            elif "how to" in query_lower or "tutorial" in query_lower:
                variations.append(f"{original_query} tutorial")
            else:
                variations.append(f"{original_query} research")
                variations.append(f"{original_query} analysis")
        max_variations = MAX_QUERY_VARIATIONS

    seen: set[str] = set()
    unique: list[str] = []
    for var in variations:
        key = var.lower()
        if key not in seen:
            seen.add(key)
            unique.append(var)
    return unique[:max_variations], query_type


async def research_node(
    state: ResearchState,
    retrieval_engine: RetrievalEngine,
) -> ResearchState:
    """Research node - coordinates information retrieval from multiple sources."""
    request_id = state.get("request_id")
    research_plan = state.get("metadata", {}).get("research_plan", {})
    user_query = state.get("user_query", "")

    logger.info(
        "Research node started",
        extra={
            "request_id": request_id,
            "user_query": user_query,
            "has_research_plan": bool(research_plan),
        },
    )

    if research_plan and research_plan.get("tasks"):
        search_query = research_plan["tasks"][0]
    else:
        search_query = user_query

    # Use query_type from research plan if available, otherwise classify
    query_type = research_plan.get("query_type") if research_plan else None
    if not query_type:
        query_type = classify_query(search_query)

    memory_manager = get_memory_manager()
    evaluator = get_evaluator()

    cached_memory = get_cached_memory_lookup(search_query)
    if cached_memory:
        memory_hit = cached_memory
    else:
        memory_hit = memory_manager.check_memory(
            query=search_query,
            query_type=query_type,
            similarity_threshold=0.75,
        )
        if memory_hit:
            cache_memory_lookup(search_query, memory_hit)

    if memory_hit and memory_hit.get("confidence_score", 0) >= 0.70:
        logger.info(
            "Using cached research from memory",
            extra={
                "request_id": request_id,
                "query": search_query,
                "similar_query": memory_hit["query"],
                "similarity": memory_hit["similarity"],
            },
        )
        updated_state = state.copy()
        updated_state["search_results"] = memory_hit["sources_used"]
        updated_state["research_papers"] = []
        updated_state["memory_hit"] = True
        updated_state["memory_similarity"] = memory_hit["similarity"]
        return updated_state

    start_time = time.time()
    query_expansion_start = time.time()
    query_variations, _ = generate_query_variations(search_query, research_plan)
    query_expansion_ms = (time.time() - query_expansion_start) * 1000
    errors: list[dict[str, Any]] = []
    all_search_results: list[dict[str, Any]] = []
    all_research_papers: list[dict[str, Any]] = []
    all_documentation: list[dict[str, Any]] = []

    logger.info(
        "Starting RetrievalEngine retrieval",
        extra={
            "request_id": request_id,
            "num_variations": len(query_variations),
            "query_type": query_type,
            "query_expansion_ms": query_expansion_ms,
            "has_wikipedia": retrieval_engine.wikipedia_provider is not None,
            "has_documentation": retrieval_engine.documentation_provider is not None,
        },
    )

    retrieval_tasks = [
        retrieval_engine.retrieve_all_sources(
            query=variation,
            query_type=query_type,
            request_id=request_id,
        )
        for variation in query_variations
    ]

    # Track cache and memory hits from RetrievalEngine
    cache_hits = 0
    memory_hits = 0
    provider_count = 0
    successful_provider_count = 0
    failed_provider_count = 0
    provider_timeouts = 0

    if retrieval_tasks:
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*retrieval_tasks, return_exceptions=True),
                timeout=90.0,
            )
            for variation, result in zip(query_variations, results):
                if isinstance(result, Exception):
                    logger.error(
                        f"RetrievalEngine failed for '{variation}': {result}",
                        extra={"request_id": request_id, "variation": variation},
                    )
                    errors.append({
                        "source": "retrieval_engine",
                        "variation": variation,
                        "error": str(result),
                        "error_type": type(result).__name__,
                    })
                else:
                    all_search_results.extend(result.get("web_results", []))
                    all_research_papers.extend(result.get("papers", []))
                    all_documentation.extend(result.get("documentation", []))
                    # Track cache and memory hits
                    if result.get("cache_hit"):
                        cache_hits += 1
                    if result.get("memory_hit"):
                        memory_hits += 1
                    # Track provider statistics from this variation
                    provider_count += result.get("provider_count", 0)
                    successful_provider_count += result.get("successful_provider_count", 0)
                    failed_provider_count += result.get("failed_provider_count", 0)
                    provider_timeouts += result.get("provider_timeouts", 0)
        except asyncio.TimeoutError:
            errors.append({
                "source": "concurrent_execution",
                "error": "TimeoutError",
                "error_type": "TimeoutError",
            })

    agreement_score = 0.0
    diversity_score = 0.0
    fusion_metrics: dict[str, Any] = {}
    fusion_cache_key = f"{search_query}:{len(all_search_results)}:{len(all_research_papers)}:{len(all_documentation)}"
    cached_fusion = get_cached_fusion_result(fusion_cache_key)

    fusion_start = time.time()
    if cached_fusion:
        fusion_result = cached_fusion
    else:
        fusion_result = fuse_evidence(
            web_results=all_search_results,
            papers=all_research_papers,
            documentation=all_documentation,
            query=search_query,
        )
        cache_fusion_result(fusion_cache_key, fusion_result)
    fusion_ms = (time.time() - fusion_start) * 1000

    fused_sources = fusion_result["combined_sources"]
    agreement_score = fusion_result["agreement_score"]
    diversity_score = fusion_result["diversity_score"]
    fusion_metrics = fusion_result["metrics"]
    fusion_metrics["fusion_time_ms"] = fusion_ms

    fused_web = [s for s in fused_sources if s.get("source_type") in ["web", "documentation"]]
    fused_papers = [s for s in fused_sources if s.get("source_type") == "academic"]

    ranking_start = time.time()
    if fused_web or fused_papers:
        ranked_web, ranked_papers, ranking_metrics = rank_sources(
            fused_web,
            fused_papers,
            search_query,
            query_type,
        )
        final_search_results = ranked_web
        final_research_papers = ranked_papers
        ranking_metrics["fusion_metrics"] = fusion_metrics
        ranking_metrics["agreement_score"] = agreement_score
        ranking_metrics["diversity_score"] = diversity_score
    else:
        final_search_results = []
        final_research_papers = []
        ranking_metrics = {}
    ranking_ms = (time.time() - ranking_start) * 1000
    if ranking_metrics:
        ranking_metrics["ranking_time_ms"] = ranking_ms

    execution_time_raw = time.time() - start_time
    execution_time_ms = execution_time_raw * 1000
    all_sources = final_search_results + final_research_papers

    if all_sources and ranking_metrics:
        avg_quality = ranking_metrics.get("average_quality", 0.5)
        if avg_quality >= 0.50:
            try:
                memory_manager.store_research(
                    query=search_query,
                    query_type=query_type,
                    sources_used=all_sources,
                    final_summary="",
                    confidence_score=ranking_metrics.get("average_confidence", 0.5),
                )
            except Exception as e:
                logger.warning(f"Failed to store research in memory: {e}")

        providers_used = list({
            s.get("provider", "unknown") for s in all_sources if s.get("provider")
        }) or (["duckduckgo"] if final_search_results else []) + (["arxiv"] if final_research_papers else [])

        try:
            evaluator.track_retrieval_metrics(
                query=search_query,
                query_type=query_type,
                providers_used=providers_used,
                sources_found=len(all_search_results) + len(all_research_papers) + len(all_documentation),
                sources_selected=len(final_search_results) + len(final_research_papers),
                source_quality_score=avg_quality,
                evidence_diversity=diversity_score,
                confidence_score=ranking_metrics.get("average_confidence", 0.5),
                execution_time_ms=execution_time_ms,
                request_id=request_id,
                cache_hit=cache_hits > 0,
                memory_hit=memory_hits > 0,
                provider_count=provider_count,
                successful_provider_count=successful_provider_count,
                failed_provider_count=failed_provider_count,
                provider_timeouts=provider_timeouts,
            )
        except Exception as e:
            logger.warning(f"Failed to track retrieval metrics: {e}")

    updated_state = state.copy()
    updated_state["search_results"] = final_search_results
    updated_state["research_papers"] = final_research_papers
    updated_state["metadata"] = state.get("metadata", {})
    updated_state["metadata"]["research_metrics"] = {
        "diversity_score": diversity_score,
        "agreement_score": agreement_score,
        "ranking_metrics": ranking_metrics,
        "query_type": query_type,
        "execution_time_ms": execution_time_ms,
        "query_expansion_ms": query_expansion_ms,
        "fusion_time_ms": fusion_ms,
        "ranking_time_ms": ranking_ms,
        "cache_hits": cache_hits,
        "memory_hits": memory_hits,
        "total_variations": len(query_variations),
    }
    updated_state["intermediate_steps"] = state.get("intermediate_steps", [])
    updated_state["intermediate_steps"].append({
        "node": "research",
        "action": "retrieved_research_data",
        "status": "completed" if all_sources else "no_results",
        "num_web_results": len(final_search_results),
        "num_papers": len(final_research_papers),
        "num_errors": len(errors),
        "num_variations": len(query_variations),
        "ranking_metrics": ranking_metrics,
    })
    if errors:
        updated_state["errors"] = state.get("errors", [])
        updated_state["errors"].extend(errors)

    logger.info(
        "Research node completed",
        extra={
            "request_id": request_id,
            "execution_time_ms": execution_time_ms,
            "num_web_results": len(final_search_results),
            "num_papers": len(final_research_papers),
        },
    )
    return updated_state
