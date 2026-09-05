"""Intelligent provider selection based on query type and historical performance.

This module provides adaptive provider selection considering query complexity,
historical success rates, and required evidence types.
"""

from typing import Any, Dict, List, Optional
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


class ProviderSelector:
    """Intelligent provider selector for adaptive retrieval.

    This class selects providers based on query type, historical performance,
    health status, circuit breaker state, and evidence requirements.
    """

    def __init__(self):
        """Initialize the provider selector."""
        # Historical provider performance tracking
        self.provider_performance: Dict[str, Dict[str, Any]] = {
            "duckduckgo": {"success_rate": 0.85, "avg_sources": 8, "avg_latency_ms": 2000},
            "wikipedia": {"success_rate": 0.90, "avg_sources": 3, "avg_latency_ms": 1500},
            "arxiv": {"success_rate": 0.80, "avg_sources": 5, "avg_latency_ms": 3000},
            "documentation": {"success_rate": 0.75, "avg_sources": 4, "avg_latency_ms": 2500},
        }

        # Health status cache (updated externally)
        self.provider_health: Dict[str, bool] = {
            "duckduckgo": True,
            "wikipedia": True,
            "arxiv": True,
            "documentation": True,
        }

        # Circuit breaker state cache (updated externally)
        self.provider_circuit_state: Dict[str, str] = {
            "duckduckgo": "closed",
            "wikipedia": "closed",
            "arxiv": "closed",
            "documentation": "closed",
        }

        logger.info("Provider selector initialized")

    def select_providers(
        self,
        query: str,
        query_type: str,
        historical_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Select providers based on query type, health, and historical performance.

        Args:
            query: Search query
            query_type: Query category (definition, technical, research)
            historical_metrics: Optional historical performance metrics

        Returns:
            Dictionary with providers, reason, and confidence
        """
        # Update performance from historical metrics if provided
        if historical_metrics:
            self._update_performance_from_metrics(historical_metrics)

        # Get base provider priority based on query type
        base_providers = self._get_base_providers(query_type)

        # Filter out unhealthy and circuit-open providers
        available_providers = self._filter_available_providers(base_providers)

        # Adjust priority based on historical performance
        adjusted_providers = self._adjust_by_performance(available_providers)

        # Select providers based on adjusted priority
        selected_providers = self._select_top_providers(adjusted_providers, max_providers=3)

        # Generate reason for selection
        reason = self._generate_reason(query_type, selected_providers, base_providers)

        # Calculate selection confidence
        confidence = self._calculate_selection_confidence(selected_providers)

        logger.info(
            "Provider selection completed",
            extra={
                "query": query,
                "query_type": query_type,
                "base_providers": base_providers,
                "available_providers": available_providers,
                "selected_providers": selected_providers,
                "reason": reason,
                "confidence": confidence,
            },
        )

        return {
            "providers": selected_providers,
            "reason": reason,
            "confidence": confidence,
        }

    def _get_base_providers(self, query_type: str) -> List[str]:
        """Get base provider priority based on query type.

        Args:
            query_type: Query category

        Returns:
            List of providers in priority order
        """
        if query_type == "definition":
            # Definition: Wikipedia first, then documentation, then web
            return ["wikipedia", "documentation", "duckduckgo"]
        elif query_type == "technical":
            # Technical: Documentation first, then web, then arXiv
            return ["documentation", "duckduckgo", "arxiv"]
        else:  # research
            # Research: arXiv first, then web, then documentation
            return ["arxiv", "duckduckgo", "documentation"]

    def _filter_available_providers(self, providers: List[str]) -> List[str]:
        """Filter out unhealthy and circuit-open providers.

        Args:
            providers: List of provider names

        Returns:
            List of available provider names
        """
        available = []
        for provider in providers:
            is_healthy = self.provider_health.get(provider, True)
            circuit_state = self.provider_circuit_state.get(provider, "closed")

            # Provider is available if healthy and circuit is not open
            if is_healthy and circuit_state != "open":
                available.append(provider)
            else:
                logger.debug(
                    f"Provider filtered out",
                    extra={
                        "provider": provider,
                        "is_healthy": is_healthy,
                        "circuit_state": circuit_state,
                    },
                )

        return available

    def _adjust_by_performance(self, providers: List[str]) -> List[tuple[str, float]]:
        """Adjust provider priority based on historical performance.

        Args:
            providers: List of providers in base priority order

        Returns:
            List of (provider, adjusted_score) tuples sorted by score
        """
        adjusted = []

        for i, provider in enumerate(providers):
            performance = self.provider_performance.get(provider, {})
            success_rate = performance.get("success_rate", 0.5)

            # Base score decreases with position (higher priority = higher base score)
            base_score = 1.0 - (i * 0.2)

            # Adjust by success rate
            adjusted_score = base_score * success_rate

            adjusted.append((provider, adjusted_score))

        # Sort by adjusted score
        adjusted.sort(key=lambda x: x[1], reverse=True)

        return adjusted

    def _select_top_providers(
        self,
        adjusted_providers: List[tuple[str, float]],
        max_providers: int = 3,
    ) -> List[str]:
        """Select top providers from adjusted list.

        Args:
            adjusted_providers: List of (provider, score) tuples
            max_providers: Maximum number of providers to select

        Returns:
            List of selected provider names
        """
        return [p[0] for p in adjusted_providers[:max_providers]]

    def _generate_reason(self, query_type: str, providers: List[str], base_providers: List[str]) -> str:
        """Generate reason for provider selection.

        Args:
            query_type: Query category
            providers: Selected providers
            base_providers: Original provider priority list

        Returns:
            Reason string
        """
        filtered_out = set(base_providers) - set(providers)

        base_reason = ""
        if query_type == "definition":
            base_reason = "Definition query prioritizes authoritative sources"
        elif query_type == "technical":
            base_reason = "Technical query prioritizes official documentation"
        else:  # research
            base_reason = "Research query prioritizes academic sources"

        if filtered_out:
            return f"{base_reason}. Selected: {', '.join(providers)}. Filtered out: {', '.join(filtered_out)}"
        else:
            return f"{base_reason}: {', '.join(providers)}"

    def _calculate_selection_confidence(self, providers: List[str]) -> float:
        """Calculate confidence in provider selection.

        Args:
            providers: Selected providers

        Returns:
            Confidence score between 0 and 1
        """
        if not providers:
            return 0.0

        # Average success rate of selected providers
        success_rates = []
        for provider in providers:
            performance = self.provider_performance.get(provider, {})
            success_rates.append(performance.get("success_rate", 0.5))

        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0.0

        return avg_success_rate

    def _update_performance_from_metrics(self, metrics: Dict[str, Any]) -> None:
        """Update provider performance from historical metrics.

        Args:
            metrics: Historical performance metrics
        """
        provider_performance = metrics.get("provider_performance", {})

        for provider, perf in provider_performance.items():
            if provider in self.provider_performance:
                self.provider_performance[provider].update(perf)

    def update_provider_health(self, provider: str, is_healthy: bool) -> None:
        """Update provider health status.

        Args:
            provider: Provider name
            is_healthy: Whether the provider is healthy
        """
        self.provider_health[provider] = is_healthy
        logger.debug(
            f"Provider health updated",
            extra={"provider": provider, "is_healthy": is_healthy},
        )

    def update_provider_circuit_state(self, provider: str, circuit_state: str) -> None:
        """Update provider circuit breaker state.

        Args:
            provider: Provider name
            circuit_state: Circuit state (closed, open, half_open)
        """
        self.provider_circuit_state[provider] = circuit_state
        logger.debug(
            f"Provider circuit state updated",
            extra={"provider": provider, "circuit_state": circuit_state},
        )

    def record_provider_result(
        self,
        provider: str,
        success: bool,
        sources_found: int,
        execution_time_ms: float,
    ) -> None:
        """Record provider result for adaptive learning.

        Args:
            provider: Provider name
            success: Whether the provider succeeded
            sources_found: Number of sources found
            execution_time_ms: Execution time in milliseconds
        """
        if provider not in self.provider_performance:
            self.provider_performance[provider] = {
                "success_rate": 0.5,
                "avg_sources": 0,
                "avg_latency_ms": 0,
            }

        perf = self.provider_performance[provider]

        # Update success rate with exponential moving average
        current_rate = perf["success_rate"]
        new_rate = 0.9 * current_rate + 0.1 * (1.0 if success else 0.0)
        perf["success_rate"] = new_rate

        # Update average sources
        current_sources = perf["avg_sources"]
        new_sources = 0.9 * current_sources + 0.1 * sources_found
        perf["avg_sources"] = new_sources

        # Update average latency
        current_latency = perf["avg_latency_ms"]
        new_latency = 0.9 * current_latency + 0.1 * execution_time_ms
        perf["avg_latency_ms"] = new_latency

        logger.debug(
            f"Provider performance updated",
            extra={
                "provider": provider,
                "success_rate": perf["success_rate"],
                "avg_sources": perf["avg_sources"],
                "avg_latency_ms": perf["avg_latency_ms"],
            },
        )


# Global singleton instance
_provider_selector: Optional[ProviderSelector] = None


def get_provider_selector() -> ProviderSelector:
    """Get the global provider selector singleton.

    Returns:
        ProviderSelector instance
    """
    global _provider_selector
    if _provider_selector is None:
        _provider_selector = ProviderSelector()
    return _provider_selector
