"""Retrieval quality feedback loop and evaluation metrics.

This module provides tracking and evaluation of retrieval quality,
answer quality, and overall system performance with persistent storage.
"""

import time
from typing import Any, Dict, List, Optional
from backend.utils.logging_config import get_logger
from backend.utils.metrics_storage import get_metrics_storage

logger = get_logger(__name__)


class RetrievalEvaluator:
    """Evaluator for tracking retrieval and answer quality metrics."""

    def __init__(self):
        """Initialize the retrieval evaluator."""
        self.metrics_history: List[Dict[str, Any]] = []
        self.metrics_storage = get_metrics_storage()
        logger.info("Retrieval evaluator initialized with persistent storage")

    def track_retrieval_metrics(
        self,
        query: str,
        query_type: str,
        providers_used: List[str],
        sources_found: int,
        sources_selected: int,
        source_quality_score: float,
        evidence_diversity: float,
        confidence_score: float,
        execution_time_ms: float,
        request_id: Optional[str] = None,
    ) -> None:
        """Track retrieval quality metrics.

        Args:
            query: Search query
            query_type: Query category
            providers_used: List of providers used
            sources_found: Total sources found
            sources_selected: Sources selected after filtering
            source_quality_score: Average source quality score
            evidence_diversity: Source diversity score
            confidence_score: Overall confidence score
            execution_time_ms: Execution time in milliseconds
            request_id: Request identifier
        """
        metrics = {
            "timestamp": time.time(),
            "request_id": request_id,
            "query": query,
            "query_type": query_type,
            "providers_used": providers_used,
            "sources_found": sources_found,
            "sources_selected": sources_selected,
            "selection_rate": sources_selected / sources_found if sources_found > 0 else 0.0,
            "source_quality_score": source_quality_score,
            "evidence_diversity": evidence_diversity,
            "confidence_score": confidence_score,
            "execution_time_ms": execution_time_ms,
        }

        self.metrics_history.append(metrics)

        # Store in persistent database
        try:
            self.metrics_storage.store_metrics(
                query=query,
                query_type=query_type,
                request_id=request_id,
                retrieval_metrics=metrics,
            )
        except Exception as e:
            logger.warning(f"Failed to store metrics in database: {str(e)}")

        logger.info(
            "Retrieval metrics tracked",
            extra=metrics,
        )

    def track_answer_metrics(
        self,
        structure_score: float,
        leakage_score: float,
        hallucination_risk: float,
        citation_score: float,
        request_id: Optional[str] = None,
    ) -> None:
        """Track answer quality metrics.

        Args:
            structure_score: Report structure compliance score
            leakage_score: Prompt leakage detection score
            hallucination_risk: Estimated hallucination risk
            citation_score: Citation quality score
            request_id: Request identifier
        """
        metrics = {
            "timestamp": time.time(),
            "request_id": request_id,
            "structure_score": structure_score,
            "leakage_score": leakage_score,
            "hallucination_risk": hallucination_risk,
            "citation_score": citation_score,
        }

        # Add to most recent retrieval metrics if available
        if self.metrics_history:
            self.metrics_history[-1].update(metrics)

            # Update persistent database with answer metrics
            try:
                # Get the most recent query and query_type from metrics history
                if self.metrics_history:
                    recent = self.metrics_history[-1]
                    self.metrics_storage.store_metrics(
                        query=recent.get("query", ""),
                        query_type=recent.get("query_type", ""),
                        request_id=recent.get("request_id"),
                        retrieval_metrics=recent,
                        answer_metrics=metrics,
                    )
            except Exception as e:
                logger.warning(f"Failed to update metrics in database: {str(e)}")

        logger.info(
            "Answer metrics tracked",
            extra=metrics,
        )

    def calculate_average_metrics(
        self,
        query_type: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Calculate average metrics for evaluation.

        Args:
            query_type: Optional query type filter
            limit: Maximum number of recent metrics to consider

        Returns:
            Dictionary with average metrics
        """
        recent_metrics = self.metrics_history[-limit:] if self.metrics_history else []

        if query_type:
            recent_metrics = [m for m in recent_metrics if m.get("query_type") == query_type]

        if not recent_metrics:
            return {}

        # Calculate averages
        avg_metrics = {
            "count": len(recent_metrics),
            "avg_sources_found": sum(m.get("sources_found", 0) for m in recent_metrics) / len(recent_metrics),
            "avg_sources_selected": sum(m.get("sources_selected", 0) for m in recent_metrics) / len(recent_metrics),
            "avg_selection_rate": sum(m.get("selection_rate", 0) for m in recent_metrics) / len(recent_metrics),
            "avg_source_quality": sum(m.get("source_quality_score", 0) for m in recent_metrics) / len(recent_metrics),
            "avg_evidence_diversity": sum(m.get("evidence_diversity", 0) for m in recent_metrics) / len(recent_metrics),
            "avg_confidence": sum(m.get("confidence_score", 0) for m in recent_metrics) / len(recent_metrics),
            "avg_execution_time_ms": sum(m.get("execution_time_ms", 0) for m in recent_metrics) / len(recent_metrics),
        }

        # Add answer metrics if available
        if any("structure_score" in m for m in recent_metrics):
            with_structure = [m for m in recent_metrics if "structure_score" in m]
            avg_metrics["avg_structure_score"] = sum(m.get("structure_score", 0) for m in with_structure) / len(with_structure)
            avg_metrics["avg_leakage_score"] = sum(m.get("leakage_score", 0) for m in with_structure) / len(with_structure)
            avg_metrics["avg_hallucination_risk"] = sum(m.get("hallucination_risk", 0) for m in with_structure) / len(with_structure)
            avg_metrics["avg_citation_score"] = sum(m.get("citation_score", 0) for m in with_structure) / len(with_structure)

        return avg_metrics

    def get_provider_performance(self) -> Dict[str, Any]:
        """Get performance metrics by provider.

        Returns:
            Dictionary with provider-specific metrics
        """
        provider_stats: Dict[str, Dict[str, Any]] = {}

        for metrics in self.metrics_history:
            providers = metrics.get("providers_used", [])
            for provider in providers:
                if provider not in provider_stats:
                    provider_stats[provider] = {
                        "count": 0,
                        "total_sources": 0,
                        "total_execution_time": 0.0,
                    }

                provider_stats[provider]["count"] += 1
                provider_stats[provider]["total_sources"] += metrics.get("sources_found", 0)
                provider_stats[provider]["total_execution_time"] += metrics.get("execution_time_ms", 0)

        # Calculate averages per provider
        for provider, stats in provider_stats.items():
            stats["avg_sources"] = stats["total_sources"] / stats["count"] if stats["count"] > 0 else 0
            stats["avg_execution_time_ms"] = stats["total_execution_time"] / stats["count"] if stats["count"] > 0 else 0

        return provider_stats

    def get_query_type_performance(self) -> Dict[str, Any]:
        """Get performance metrics by query type.

        Returns:
            Dictionary with query-type-specific metrics
        """
        type_stats: Dict[str, Dict[str, Any]] = {}

        for metrics in self.metrics_history:
            query_type = metrics.get("query_type", "unknown")
            if query_type not in type_stats:
                type_stats[query_type] = {
                    "count": 0,
                    "total_confidence": 0.0,
                    "total_sources": 0.0,
                    "total_diversity": 0.0,
                }

            type_stats[query_type]["count"] += 1
            type_stats[query_type]["total_confidence"] += metrics.get("confidence_score", 0)
            type_stats[query_type]["total_sources"] += metrics.get("sources_selected", 0)
            type_stats[query_type]["total_diversity"] += metrics.get("evidence_diversity", 0)

        # Calculate averages per query type
        for query_type, stats in type_stats.items():
            stats["avg_confidence"] = stats["total_confidence"] / stats["count"] if stats["count"] > 0 else 0
            stats["avg_sources"] = stats["total_sources"] / stats["count"] if stats["count"] > 0 else 0
            stats["avg_diversity"] = stats["total_diversity"] / stats["count"] if stats["count"] > 0 else 0

        return type_stats

    def clear_metrics(self) -> None:
        """Clear all stored metrics."""
        self.metrics_history.clear()
        logger.info("All evaluation metrics cleared")


# Global singleton instance
_evaluator: Optional[RetrievalEvaluator] = None


def get_evaluator() -> RetrievalEvaluator:
    """Get the global retrieval evaluator singleton.

    Returns:
        RetrievalEvaluator instance
    """
    global _evaluator
    if _evaluator is None:
        _evaluator = RetrievalEvaluator()
    return _evaluator
