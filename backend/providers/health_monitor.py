"""Provider health monitoring implementation.

This module tracks provider health metrics including success/failure rates,
latency, and consecutive failures for diagnostic purposes.
"""

import time
from typing import Any
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


class ProviderHealthMonitor:
    """Health monitor for provider metrics.

    This class tracks health metrics for providers including success/failure
    counts, latency, and consecutive failures. It provides diagnostic information
    without changing public API contracts.

    Attributes:
        provider_name: Name of the provider being monitored
    """

    def __init__(self, provider_name: str) -> None:
        """Initialize health monitor.

        Args:
            provider_name: Name of the provider
        """
        self.provider_name = provider_name

        # Health metrics
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._consecutive_failures = 0
        self._consecutive_successes = 0

        # Timing metrics
        self._total_latency = 0.0
        self._latencies = []
        self._last_successful_request = 0.0
        self._last_failure = 0.0

        logger.info(
            f"Health monitor initialized for provider: {provider_name}",
            extra={"provider": provider_name},
        )

    def record_success(self, latency_ms: float) -> None:
        """Record a successful provider request.

        Args:
            latency_ms: Request latency in milliseconds
        """
        self._total_requests += 1
        self._successful_requests += 1
        self._consecutive_successes += 1
        self._consecutive_failures = 0
        self._total_latency += latency_ms
        self._latencies.append(latency_ms)
        self._last_successful_request = time.time()

        # Keep only last 100 latencies
        if len(self._latencies) > 100:
            self._latencies.pop(0)

        logger.debug(
            f"Recorded success for provider: {self.provider_name}",
            extra={
                "provider": self.provider_name,
                "latency_ms": latency_ms,
                "total_requests": self._total_requests,
                "successful_requests": self._successful_requests,
                "consecutive_successes": self._consecutive_successes,
            },
        )

    def record_failure(self, error: str) -> None:
        """Record a failed provider request.

        Args:
            error: Error message
        """
        self._total_requests += 1
        self._failed_requests += 1
        self._consecutive_failures += 1
        self._consecutive_successes = 0
        self._last_failure = time.time()

        logger.debug(
            f"Recorded failure for provider: {self.provider_name}",
            extra={
                "provider": self.provider_name,
                "error": error,
                "total_requests": self._total_requests,
                "failed_requests": self._failed_requests,
                "consecutive_failures": self._consecutive_failures,
            },
        )

    @property
    def is_healthy(self) -> bool:
        """Check if provider is considered healthy."""
        # Provider is healthy if:
        # - Has at least 1 successful request
        # - Consecutive failures < 5
        # - Success rate > 50% (if enough requests)
        if self._total_requests == 0:
            return True  # Unknown, assume healthy

        if self._consecutive_failures >= 5:
            return False

        if self._total_requests >= 10:
            success_rate = self._successful_requests / self._total_requests
            return success_rate > 0.5

        return True

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self._total_requests == 0:
            return 1.0
        return self._successful_requests / self._total_requests

    @property
    def average_latency_ms(self) -> float:
        """Calculate average latency in milliseconds."""
        if self._successful_requests == 0:
            return 0.0
        return self._total_latency / self._successful_requests

    @property
    def p50_latency_ms(self) -> float:
        """Calculate median latency (p50)."""
        if not self._latencies:
            return 0.0
        sorted_latencies = sorted(self._latencies)
        mid = len(sorted_latencies) // 2
        return sorted_latencies[mid]

    @property
    def p95_latency_ms(self) -> float:
        """Calculate 95th percentile latency."""
        if not self._latencies:
            return 0.0
        sorted_latencies = sorted(self._latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    def get_status(self) -> dict[str, Any]:
        """Get health status.

        Returns:
            Dictionary with health metrics
        """
        return {
            "provider": self.provider_name,
            "is_healthy": self.is_healthy,
            "total_requests": self._total_requests,
            "successful_requests": self._successful_requests,
            "failed_requests": self._failed_requests,
            "consecutive_failures": self._consecutive_failures,
            "consecutive_successes": self._consecutive_successes,
            "success_rate": self.success_rate,
            "average_latency_ms": self.average_latency_ms,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "last_successful_request": self._last_successful_request,
            "last_failure": self._last_failure,
        }

    def reset(self) -> None:
        """Reset health metrics."""
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._total_latency = 0.0
        self._latencies = []
        self._last_successful_request = 0.0
        self._last_failure = 0.0

        logger.info(
            f"Health monitor reset for provider: {self.provider_name}",
            extra={"provider": self.provider_name},
        )
