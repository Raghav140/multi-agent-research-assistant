"""Research node for LangGraph workflow.

This module implements the research node that coordinates information retrieval
from web search and academic paper sources using dependency injection.
"""

import asyncio
import time
from typing import Any

from backend.core.interfaces import SearchProvider
from backend.graph.state import ResearchState
from backend.providers.papers.arxiv_provider import ArxivProvider
from backend.providers.search.wikipedia_provider import WikipediaProvider
from backend.utils.logging_config import get_logger
from backend.utils.source_ranking import rank_sources
from backend.utils.query_classifier import classify_query
from backend.utils.evidence_fusion import fuse_evidence
from backend.memory.memory_manager import get_memory_manager
from backend.utils.evaluation import get_evaluator
from backend.utils.provider_selector import get_provider_selector
from backend.utils.cache import (
    get_cached_provider_result,
    cache_provider_result,
    get_cached_fusion_result,
    cache_fusion_result,
    get_cached_memory_lookup,
    cache_memory_lookup,
)

logger = get_logger(__name__)


async def research_node(
    state: ResearchState,
    search_provider: SearchProvider,
    arxiv_provider: ArxivProvider,
    wikipedia_provider: WikipediaProvider = None,
) -> ResearchState:
    """Research node - coordinates information retrieval from multiple sources.

    This node executes web search and arXiv search concurrently using
    dependency injection. For definition queries, Wikipedia is prioritized.
    Results are stored separately in the state.

    Args:
        state: Current workflow state containing research plan
        search_provider: Search provider instance (dependency injection)
        arxiv_provider: arXiv provider instance (dependency injection)
        wikipedia_provider: Wikipedia provider instance (optional, for definition queries)

    Returns:
        Updated state with search_results and research_papers
    """
    request_id = state.get("request_id")
    research_plan = state.get("metadata", {}).get("research_plan", {})
    user_query = state.get("user_query", "")

    logger.info(
        f"Research node started",
        extra={
            "request_id": request_id,
            "user_query": user_query,
            "has_research_plan": bool(research_plan),
            "wikipedia_provider_available": wikipedia_provider is not None,
        },
    )

    # Extract tasks from research plan or use user query directly
    if research_plan and "tasks" in research_plan:
        search_query = research_plan["tasks"][0] if research_plan["tasks"] else user_query
    else:
        search_query = user_query

    # Classify query type for adaptive validation and scoring
    query_type = classify_query(search_query)

    # Use intelligent provider selection
    provider_selector = get_provider_selector()
    provider_selection = provider_selector.select_providers(
        query=search_query,
        query_type=query_type,
    )

    logger.info(
        "Provider selection completed",
        extra={
            "request_id": request_id,
            "query": search_query,
            "query_type": query_type,
            "selected_providers": provider_selection["providers"],
            "selection_reason": provider_selection["reason"],
            "selection_confidence": provider_selection["confidence"],
        },
    )

    # Check research memory for similar queries before retrieval
    memory_manager = get_memory_manager()
    evaluator = get_evaluator()

    # Check memory cache first
    cached_memory = get_cached_memory_lookup(search_query)
    if cached_memory:
        memory_hit = cached_memory
        logger.info(
            "Memory cache hit",
            extra={
                "request_id": request_id,
                "query": search_query,
            },
        )
    else:
        memory_hit = memory_manager.check_memory(
            query=search_query,
            query_type=query_type,
            similarity_threshold=0.75,
        )
        # Cache memory lookup result
        if memory_hit:
            cache_memory_lookup(search_query, memory_hit)

    if memory_hit and memory_hit.get("confidence_score", 0) >= 0.70:
        # Return cached research if confidence is high enough
        logger.info(
            "Using cached research from memory",
            extra={
                "request_id": request_id,
                "query": search_query,
                "similar_query": memory_hit["query"],
                "similarity": memory_hit["similarity"],
                "cached_confidence": memory_hit["confidence_score"],
            },
        )

        updated_state = state.copy()
        updated_state["search_results"] = memory_hit["sources_used"]
        updated_state["research_papers"] = []
        updated_state["memory_hit"] = True
        updated_state["memory_similarity"] = memory_hit["similarity"]

        return updated_state

    start_time = time.time()

    # Intelligent query expansion - generate multiple variations
    def generate_query_variations(original_query: str) -> list[str]:
        """Generate multiple search query variations for comprehensive retrieval."""
        query_lower = original_query.lower()
        words = original_query.split()
        variations = [original_query]  # Always include original

        # Variation 1: Definition/Overview
        if "what is" in query_lower or "define" in query_lower or "explain" in query_lower:
            if "what is" in query_lower:
                topic = original_query.replace("What is", "").replace("what is", "").strip()
                if topic:
                    variations.append(f"{topic} definition")
                    variations.append(f"{topic} overview")
                    variations.append(f"{topic} explained")
                    variations.append(f"{topic} basics")
            else:
                variations.append(f"{original_query} definition")
                variations.append(f"{original_query} overview")
        elif "how to" in query_lower or "tutorial" in query_lower or "guide" in query_lower:
            variations.append(f"{original_query} tutorial")
            variations.append(f"{original_query} guide")
            variations.append(f"{original_query} step by step")
        else:
            variations.append(f"{original_query} overview")
            variations.append(f"{original_query} explained")

        # Variation 2: Domain-specific expansions
        if "ai" in query_lower or "artificial intelligence" in query_lower:
            variations.append("artificial intelligence machine learning")
            variations.append("AI neural networks")
            variations.append("artificial intelligence deep learning")
        elif "quantum" in query_lower:
            variations.append("quantum computing physics")
            variations.append("quantum mechanics computing")
        elif "python" in query_lower:
            variations.append("python programming language")
            variations.append("python code tutorial")
            variations.append("python development")
        elif "langgraph" in query_lower:
            variations.append("langgraph framework tutorial")
            variations.append("langgraph guide examples")

        # Variation 3: Alternative phrasings
        if "what is" in query_lower:
            topic = original_query.replace("What is", "").replace("what is", "").strip()
            if topic:
                variations.append(f"Explain {topic}")
                variations.append(f"Describe {topic}")
                variations.append(f"Introduction to {topic}")
        elif "explain" in query_lower:
            variations.append(original_query.replace("explain", "describe").replace("Explain", "Describe"))
            variations.append(original_query.replace("explain", "introduction to").replace("Explain", "Introduction to"))

        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for var in variations:
            if var.lower() not in seen:
                seen.add(var.lower())
                unique_variations.append(var)

        return unique_variations

    # Generate all query variations
    query_variations = generate_query_variations(search_query)

    logger.info(
        f"Generated {len(query_variations)} query variations",
        extra={
            "request_id": request_id,
            "original_query": search_query,
            "query_variations": query_variations,
            "num_variations": len(query_variations),
        },
    )

    # Execute searches for all variations in parallel
    all_search_results = []
    all_research_papers = []
    errors = []

    logger.info(
        f"Starting parallel searches for query variations",
        extra={
            "request_id": request_id,
            "num_variations": len(query_variations),
            "query_type": query_type,
            "wikipedia_provider_available": wikipedia_provider is not None,
        },
    )

    # For definition queries, prioritize Wikipedia search with fallback
    if query_type == "definition" and wikipedia_provider:
        try:
            # Check provider cache first
            cached_wikipedia = get_cached_provider_result("wikipedia", search_query)
            if cached_wikipedia:
                wikipedia_results = cached_wikipedia
                logger.info(
                    "Wikipedia provider cache hit",
                    extra={
                        "request_id": request_id,
                        "query": search_query,
                    },
                )
            else:
                logger.info(
                    f"Executing Wikipedia search for definition query",
                    extra={
                        "request_id": request_id,
                        "query": search_query,
                    },
                )
                # Add individual timeout for Wikipedia
                wikipedia_results = await asyncio.wait_for(
                    wikipedia_provider.search(
                        query=search_query,
                        num_results=5,
                        request_id=request_id,
                    ),
                    timeout=30.0,  # Individual provider timeout
                )
                # Cache Wikipedia results
                cache_provider_result("wikipedia", search_query, wikipedia_results)

            if wikipedia_results:
                all_search_results.extend(wikipedia_results)
                logger.info(
                    f"Wikipedia search completed",
                    extra={
                        "request_id": request_id,
                        "results_count": len(wikipedia_results),
                    },
                )
            else:
                logger.warning(
                    f"Wikipedia search returned no results, falling back to web search",
                    extra={
                        "request_id": request_id,
                        "query": search_query,
                    },
                )
                # Fallback to web search if Wikipedia returns empty
                errors.append({
                    "source": "wikipedia",
                    "query": search_query,
                    "error": "No results returned",
                    "error_type": "EmptyResults",
                    "fallback_triggered": True,
                })
        except asyncio.TimeoutError:
            logger.error(
                f"Wikipedia search timeout, falling back to web search",
                extra={
                    "request_id": request_id,
                    "query": search_query,
                    "timeout": 30.0,
                },
            )
            errors.append({
                "source": "wikipedia",
                "query": search_query,
                "error": "TimeoutError",
                "error_type": "TimeoutError",
                "fallback_triggered": True,
            })
        except Exception as e:
            logger.error(
                f"Wikipedia search failed, falling back to web search: {str(e)}",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            errors.append({
                "source": "wikipedia",
                "query": search_query,
                "error": str(e),
                "error_type": type(e).__name__,
                "fallback_triggered": True,
            })

    # Create search tasks for all variations with individual timeouts
    search_tasks = []
    for variation in query_variations:
        try:
            # Wrap web search with individual timeout
            web_task = asyncio.wait_for(
                search_provider.search(
                    query=variation,
                    num_results=5,
                    request_id=request_id,
                ),
                timeout=30.0,  # Individual provider timeout
            )
            search_tasks.append(("web", variation, web_task))
        except Exception as e:
            logger.error(
                f"Web search task creation failed for variation '{variation}': {str(e)}",
                extra={
                    "request_id": request_id,
                    "variation": variation,
                    "error": str(e),
                },
            )
            errors.append({
                "source": "web",
                "variation": variation,
                "error": str(e),
                "error_type": type(e).__name__,
            })

        try:
            # Wrap arXiv search with individual timeout
            arxiv_task = asyncio.wait_for(
                arxiv_provider.search(
                    query=variation,
                    max_results=3,
                    request_id=request_id,
                ),
                timeout=30.0,  # Individual provider timeout
            )
            search_tasks.append(("arxiv", variation, arxiv_task))
        except Exception as e:
            logger.error(
                f"arXiv search task creation failed for variation '{variation}': {str(e)}",
                extra={
                    "request_id": request_id,
                    "variation": variation,
                    "error": str(e),
                },
            )
            errors.append({
                "source": "arxiv",
                "variation": variation,
                "error": str(e),
                "error_type": type(e).__name__,
            })

    # Execute all search tasks concurrently with overall timeout
    if search_tasks:
        try:
            logger.info(
                f"Executing {len(search_tasks)} search tasks concurrently",
                extra={
                    "request_id": request_id,
                    "num_tasks": len(search_tasks),
                },
            )

            results = await asyncio.wait_for(
                asyncio.gather(
                    *[task for _, _, task in search_tasks],
                    return_exceptions=True,
                ),
                timeout=90.0,  # Overall timeout for all providers
            )

            for (source, variation, _), result in zip(search_tasks, results):
                if isinstance(result, Exception):
                    logger.error(
                        f"{source} search failed for variation '{variation}': {str(result)}",
                        extra={
                            "request_id": request_id,
                            "source": source,
                            "variation": variation,
                            "error": str(result),
                            "error_type": type(result).__name__,
                        },
                    )
                    errors.append({
                        "source": source,
                        "variation": variation,
                        "error": str(result),
                        "error_type": type(result).__name__,
                    })
                else:
                    if source == "web":
                        all_search_results.extend(result)
                    elif source == "arxiv":
                        all_research_papers.extend(result)

            logger.info(
                f"Collected results from all variations",
                extra={
                    "request_id": request_id,
                    "total_web_results": len(all_search_results),
                    "total_papers": len(all_research_papers),
                },
            )

        except asyncio.TimeoutError:
            logger.error(
                f"Search execution timeout after 90s",
                extra={
                    "request_id": request_id,
                    "timeout": 90.0,
                },
            )
            errors.append({
                "source": "concurrent_execution",
                "error": "TimeoutError",
                "error_type": "TimeoutError",
            })
        except Exception as e:
            logger.error(
                f"Concurrent search execution failed: {str(e)}",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                },
            )
            errors.append({
                "source": "concurrent_execution",
                "error": str(e),
                "error_type": type(e).__name__,
            })

    # Apply evidence fusion to remove duplicates and calculate diversity
    documentation_results = []  # Placeholder for future documentation integration

    # Initialize fusion variables
    agreement_score = 0.0
    diversity_score = 0.0
    fusion_metrics = {}

    # Check fusion cache first
    fusion_cache_key = f"{search_query}:{len(all_search_results)}:{len(all_research_papers)}"
    cached_fusion = get_cached_fusion_result(fusion_cache_key)

    if cached_fusion:
        fusion_result = cached_fusion
        logger.info(
            "Fusion cache hit",
            extra={
                "request_id": request_id,
                "query": search_query,
            },
        )
    else:
        fusion_result = fuse_evidence(
            web_results=all_search_results,
            papers=all_research_papers,
            documentation=documentation_results,
            query=search_query,
        )
        # Cache fusion result
        cache_fusion_result(fusion_cache_key, fusion_result)

    fused_sources = fusion_result["combined_sources"]
    agreement_score = fusion_result["agreement_score"]
    diversity_score = fusion_result["diversity_score"]
    fusion_metrics = fusion_result["metrics"]

    # Separate fused sources back into web and papers for ranking
    fused_web = [s for s in fused_sources if s.get("source_type") in ["web", "documentation"]]
    fused_papers = [s for s in fused_sources if s.get("source_type") == "academic"]

    logger.info(
        f"Evidence fusion completed",
        extra={
            "request_id": request_id,
            "original_count": fusion_metrics["original_count"],
            "deduplicated_count": fusion_metrics["deduplicated_count"],
            "duplicates_removed": fusion_metrics["duplicates_removed"],
            "agreement_score": agreement_score,
            "diversity_score": diversity_score,
            "fusion_time_ms": fusion_metrics["fusion_time_ms"],
        },
    )

    # Merge and globally rank all results
    if fused_web or fused_papers:
        ranked_web, ranked_papers, ranking_metrics = rank_sources(
            fused_web,
            fused_papers,
            search_query,  # Use original query for ranking
            query_type,  # Pass query type for adaptive scoring
        )

        final_search_results = ranked_web
        final_research_papers = ranked_papers

        logger.info(
            f"Global ranking completed",
            extra={
                "request_id": request_id,
                "original_query": search_query,
                "num_variations": len(query_variations),
                "web_before_filtering": len(all_search_results),
                "papers_before_filtering": len(all_research_papers),
                "web_after_filtering": len(ranked_web),
                "papers_after_filtering": len(ranked_papers),
                "ranking_metrics": ranking_metrics,
            },
        )
        # Add fusion metrics to ranking metrics
        ranking_metrics["fusion_metrics"] = fusion_metrics
        ranking_metrics["agreement_score"] = agreement_score
        ranking_metrics["diversity_score"] = diversity_score
    else:
        final_search_results = []
        final_research_papers = []
        ranking_metrics = {}
        fusion_metrics = {}
        agreement_score = 0.0
        diversity_score = 0.0

    # Log final retrieval outcome with structured metrics
    logger.info(
        f"Retrieval completed with query expansion",
        extra={
            "request_id": request_id,
            "original_query": search_query,
            "num_variations": len(query_variations),
            "retrieved_web": len(final_search_results),
            "retrieved_papers": len(final_research_papers),
            "accepted_web": len(final_search_results),
            "accepted_papers": len(final_research_papers),
            "rejected_web": ranking_metrics.get("web_rejected", 0),
            "rejected_papers": ranking_metrics.get("papers_rejected", 0),
            "ranking_metrics": ranking_metrics,
            "raw_web_results": len(all_search_results),
            "raw_papers": len(all_research_papers),
            "fused_web": len(fused_web) if 'fused_web' in locals() else 0,
            "fused_papers": len(fused_papers) if 'fused_papers' in locals() else 0,
        },
    )

    execution_time = time.time() - start_time

    # Store research in memory if confidence is high enough
    all_sources = final_search_results + final_research_papers
    if all_sources and ranking_metrics:
        avg_quality = ranking_metrics.get("average_quality", 0.5)
        if avg_quality >= 0.50:
            try:
                memory_manager.store_research(
                    query=search_query,
                    query_type=query_type,
                    sources_used=all_sources,
                    final_summary="",  # Will be filled by report node
                    confidence_score=ranking_metrics.get("average_confidence", 0.5),
                )
            except Exception as e:
                logger.warning(
                    f"Failed to store research in memory: {str(e)}",
                    extra={
                        "request_id": request_id,
                        "error": str(e),
                    },
                )

        # Track retrieval metrics for evaluation
        providers_used = ["duckduckgo"]
        if wikipedia_provider and query_type == "definition":
            providers_used.append("wikipedia")
        if query_type == "research":
            providers_used.append("arxiv")

        evaluator.track_retrieval_metrics(
            query=search_query,
            query_type=query_type,
            providers_used=providers_used,
            sources_found=len(all_search_results) + len(all_research_papers),
            sources_selected=len(final_search_results) + len(final_research_papers),
            source_quality_score=avg_quality,
            evidence_diversity=diversity_score,
            confidence_score=ranking_metrics.get("average_confidence", 0.5),
            execution_time_ms=execution_time * 1000,
            request_id=request_id,
        )

    logger.info(
        f"Research node completed - Duration: {execution_time:.0f}ms",
        extra={
            "request_id": request_id,
            "execution_time_ms": execution_time * 1000,
            "num_web_results_received": len(final_search_results),
            "num_papers_received": len(final_research_papers),
            "num_errors": len(errors),
            "memory_hit": False,
        },
    )

    # Update state with ranked results
    updated_state = state.copy()
    updated_state["search_results"] = final_search_results
    updated_state["research_papers"] = final_research_papers
    updated_state["intermediate_steps"] = state.get("intermediate_steps", [])
    updated_state["intermediate_steps"].append({
        "node": "research",
        "action": "retrieved_research_data",
        "status": "completed" if (final_search_results or final_research_papers) else "no_results",
        "num_web_results": len(final_search_results),
        "num_papers": len(final_research_papers),
        "num_errors": len(errors),
        "num_variations": len(query_variations),
        "ranking_metrics": ranking_metrics,
    })

    # Append errors if any
    if errors:
        updated_state["errors"] = state.get("errors", [])
        updated_state["errors"].extend(errors)

    return updated_state
