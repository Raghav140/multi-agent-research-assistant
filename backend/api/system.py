"""System API endpoints for health, metrics, memory, and cache."""

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.config.dependencies import (
    get_arxiv_circuit_breaker,
    get_arxiv_health_monitor,
    get_documentation_circuit_breaker,
    get_documentation_health_monitor,
    get_duckduckgo_circuit_breaker,
    get_duckduckgo_health_monitor,
    get_wikipedia_circuit_breaker,
    get_wikipedia_health_monitor,
)
from backend.memory.memory_manager import get_memory_manager
from backend.utils.cache import get_all_cache_metrics
from backend.utils.evaluation import get_evaluator
from backend.utils.metrics_storage import get_metrics_storage
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)

system_router = APIRouter(prefix="/api/v1/system", tags=["system"])


def _provider_status(provider: str) -> dict[str, Any]:
    """Collect health and circuit breaker status for a provider."""
    monitors = {
        "duckduckgo": get_duckduckgo_health_monitor(),
        "wikipedia": get_wikipedia_health_monitor(),
        "arxiv": get_arxiv_health_monitor(),
        "documentation": get_documentation_health_monitor(),
    }
    breakers = {
        "duckduckgo": get_duckduckgo_circuit_breaker(),
        "wikipedia": get_wikipedia_circuit_breaker(),
        "arxiv": get_arxiv_circuit_breaker(),
        "documentation": get_documentation_circuit_breaker(),
    }
    monitor = monitors.get(provider)
    breaker = breakers.get(provider)
    return {
        "provider": provider,
        "health": monitor.get_status() if monitor else {},
        "circuit_breaker": breaker.get_status() if breaker else {},
    }


@system_router.get("/providers/health")
async def providers_health() -> dict[str, Any]:
    """Return health and circuit breaker status for all providers."""
    providers = ["duckduckgo", "wikipedia", "arxiv", "documentation", "ollama"]
    provider_data = [_provider_status(p) for p in providers[:4]]
    return {
        "providers": provider_data,
        "ollama": {"provider": "ollama", "note": "Health tracked via LLM requests"},
    }


@system_router.get("/metrics")
async def system_metrics() -> dict[str, Any]:
    """Return aggregated evaluation metrics."""
    evaluator = get_evaluator()
    metrics_storage = get_metrics_storage()
    return {
        "averages": evaluator.calculate_average_metrics(),
        "by_provider": evaluator.get_provider_performance(),
        "by_query_type": evaluator.get_query_type_performance(),
        "aggregated": metrics_storage.get_aggregated_metrics(days=7),
    }


@system_router.get("/metrics/summary")
async def metrics_summary() -> dict[str, Any]:
    """Return high-level metrics summary."""
    evaluator = get_evaluator()
    metrics_storage = get_metrics_storage()

    # Get aggregated metrics
    agg_metrics = metrics_storage.get_aggregated_metrics(days=7)

    # Get cache metrics
    cache_metrics = get_all_cache_metrics()

    # Get memory stats
    memory_manager = get_memory_manager()
    memory_stats = memory_manager.get_memory_stats()

    # Calculate cache hit rate
    total_cache_hits = sum(c.get("hits", 0) for c in cache_metrics.values())
    total_cache_misses = sum(c.get("misses", 0) for c in cache_metrics.values())
    cache_hit_rate = total_cache_hits / (total_cache_hits + total_cache_misses) if (total_cache_hits + total_cache_misses) > 0 else 0.0

    # Calculate actual success rate from metrics
    total_requests = agg_metrics.get("count", 0)
    successful_requests = agg_metrics.get("successful_count", total_requests)  # Default to all successful if not tracked
    actual_success_rate = successful_requests / total_requests if total_requests > 0 else 1.0

    return {
        "request_count": total_requests,
        "success_rate": actual_success_rate,
        "average_latency_ms": agg_metrics.get("avg_execution_time_ms", 0),
        "provider_performance": evaluator.get_provider_performance(),
        "cache_hit_rate": cache_hit_rate,
        "cache_hits": total_cache_hits,
        "cache_misses": total_cache_misses,
        "memory_reuse": memory_stats.get("total_records", 0),
        "average_confidence": agg_metrics.get("avg_confidence", 0),
        "average_source_quality": agg_metrics.get("avg_source_quality", 0),
        "average_evidence_diversity": agg_metrics.get("avg_evidence_diversity", 0),
    }


@system_router.get("/memory/history")
async def memory_history(limit: int = 20) -> dict[str, Any]:
    """Return recent research history from memory."""
    memory = get_memory_manager()
    records = memory.memory.get_recent_research(limit=min(limit, 100))
    return {
        "records": records,
        "stats": memory.get_memory_stats(),
    }


@system_router.get("/memory/{record_id}")
async def memory_record(record_id: int) -> dict[str, Any]:
    """Return a single research memory record."""
    memory = get_memory_manager()
    record = memory.memory.get_research_by_id(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@system_router.delete("/memory/{record_id}")
async def delete_memory_record(record_id: int) -> dict[str, Any]:
    """Delete a research memory record."""
    memory = get_memory_manager()
    deleted = memory.memory.delete_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"deleted": True, "record_id": record_id}


@system_router.get("/cache/stats")
async def cache_stats() -> dict[str, Any]:
    """Return cache hit/miss statistics."""
    return get_all_cache_metrics()


@system_router.get("/health")
async def health_check() -> dict[str, Any]:
    """Return overall system health status."""
    evaluator = get_evaluator()
    metrics_storage = get_metrics_storage()

    # Get provider health
    providers = ["duckduckgo", "wikipedia", "arxiv", "documentation"]
    provider_data = [_provider_status(p) for p in providers]

    # Check if any providers are unhealthy
    unhealthy_providers = [p for p in provider_data if p.get("health", {}).get("is_healthy") == False]
    open_circuits = [p for p in provider_data if p.get("circuit_breaker", {}).get("state") == "OPEN"]

    # Overall health status
    overall_status = "healthy"
    if len(unhealthy_providers) > 0:
        overall_status = "degraded"
    if len(open_circuits) > 0:
        overall_status = "degraded"
    if len(unhealthy_providers) > 2 or len(open_circuits) > 2:
        overall_status = "unhealthy"

    return {
        "status": overall_status,
        "providers": {
            "total": len(providers),
            "healthy": len([p for p in provider_data if p.get("health", {}).get("is_healthy") == True]),
            "unhealthy": len(unhealthy_providers),
            "open_circuits": len(open_circuits),
        },
        "metrics": {
            "database_connected": True,  # SQLite always connected
            "recent_requests": metrics_storage.get_aggregated_metrics(days=1).get("count", 0),
        },
        "cache": {
            "enabled": True,
            "total_hits": sum(c.get("hits", 0) for c in get_all_cache_metrics().values()),
            "total_misses": sum(c.get("misses", 0) for c in get_all_cache_metrics().values()),
        },
        "memory": {
            "enabled": True,
            "total_records": get_memory_manager().get_memory_stats().get("total_records", 0),
        },
    }
