"""Provider circuit breaker implementation.

This module implements a circuit breaker pattern for provider resilience,
preventing cascading failures and repeated calls to unhealthy providers.
"""

import asyncio
import time
from enum import Enum
from typing import Any
from backend.utils.logging_config import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Provider failing, skip calls
    HALF_OPEN = "half_open"  # Testing if provider recovered


class CircuitBreaker:
    """Circuit breaker for provider resilience.

    This class implements the circuit breaker pattern to prevent repeated
    calls to failing providers, allowing the system to remain functional
    even when individual providers are unhealthy.

    Attributes:
        provider_name: Name of the provider being monitored
        failure_threshold: Number of failures before opening circuit
        cooldown_seconds: Seconds to wait before half-open state
        timeout_seconds: Timeout for individual provider calls
    """

    def __init__(
        self,
        provider_name: str,
        failure_threshold: int = 3,
        cooldown_seconds: int = 60,
        timeout_seconds: int = 30,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            provider_name: Name of the provider
            failure_threshold: Failures before opening circuit
            cooldown_seconds: Cooldown period in seconds
            timeout_seconds: Timeout for provider calls
        """
        self.provider_name = provider_name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.timeout_seconds = timeout_seconds

        # State tracking
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._cooldown_until = 0.0
        self._lock = asyncio.Lock()

        logger.info(
            f"Circuit breaker initialized for provider: {provider_name}",
            extra={
                "provider": provider_name,
                "failure_threshold": failure_threshold,
                "cooldown_seconds": cooldown_seconds,
                "timeout_seconds": timeout_seconds,
                "state": self._state.value,
            },
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    @property
    def success_count(self) -> int:
        """Get current success count."""
        return self._success_count

    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self._state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self._state == CircuitState.CLOSED

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        return self._state == CircuitState.HALF_OPEN

    async def call(self, func, *args: Any, **kwargs: Any) -> Any:
        """Execute a provider call with circuit breaker protection.

        Args:
            func: Provider function to call
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result from provider function

        Raises:
            Exception: If provider call fails and circuit is open
        """
        # Acquire lock only to check state and potentially transition
        async with self._lock:
            # Check if circuit is open and cooldown has elapsed
            if self._state == CircuitState.OPEN:
                if time.time() < self._cooldown_until:
                    logger.warning(
                        f"Circuit breaker OPEN for provider: {self.provider_name}, skipping call",
                        extra={
                            "provider": self.provider_name,
                            "state": self._state.value,
                            "cooldown_remaining": self._cooldown_until - time.time(),
                        },
                    )
                    raise Exception(f"Circuit breaker OPEN for {self.provider_name}")
                else:
                    # Cooldown elapsed, transition to half-open
                    self._transition_to_half_open()

        # Release lock before executing provider function
        # Execute call with timeout
        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.timeout_seconds,
            )

            # Re-acquire lock to record success
            await self._record_success()
            return result

        except asyncio.TimeoutError:
            await self._record_failure("timeout")
            raise Exception(f"Provider {self.provider_name} timeout")

        except Exception as e:
            await self._record_failure(str(e))
            raise

    async def _record_success(self) -> None:
        """Record a successful provider call."""
        async with self._lock:
            self._success_count += 1

            if self._state == CircuitState.HALF_OPEN:
                # Successful call in half-open, close circuit
                self._transition_to_closed()
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success in closed state
                self._failure_count = max(0, self._failure_count - 1)

            logger.info(
                f"Recorded success for provider: {self.provider_name}",
                extra={
                    "provider": self.provider_name,
                    "state": self._state.value,
                    "success_count": self._success_count,
                    "failure_count": self._failure_count,
                },
            )

    async def _record_failure(self, error: str) -> None:
        """Record a failed provider call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Failure in half-open, reopen circuit
                self._transition_to_open()
            elif self._state == CircuitState.CLOSED:
                # Check if threshold reached
                if self._failure_count >= self.failure_threshold:
                    self._transition_to_open()

            logger.error(
                f"Recorded failure for provider: {self.provider_name}",
                extra={
                    "provider": self.provider_name,
                    "state": self._state.value,
                    "error": error,
                    "failure_count": self._failure_count,
                    "success_count": self._success_count,
                },
            )

    def _transition_to_open(self) -> None:
        """Transition circuit to open state."""
        self._state = CircuitState.OPEN
        self._cooldown_until = time.time() + self.cooldown_seconds

        logger.warning(
            f"Circuit breaker OPENED for provider: {self.provider_name}",
            extra={
                "provider": self.provider_name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "cooldown_until": self._cooldown_until,
            },
        )

    def _transition_to_half_open(self) -> None:
        """Transition circuit to half-open state."""
        self._state = CircuitState.HALF_OPEN

        logger.info(
            f"Circuit breaker HALF_OPEN for provider: {self.provider_name}",
            extra={
                "provider": self.provider_name,
                "state": self._state.value,
            },
        )

    def _transition_to_closed(self) -> None:
        """Transition circuit to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0

        logger.info(
            f"Circuit breaker CLOSED for provider: {self.provider_name}",
            extra={
                "provider": self.provider_name,
                "state": self._state.value,
            },
        )

    async def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = 0.0
            self._cooldown_until = 0.0

            logger.info(
                f"Circuit breaker reset for provider: {self.provider_name}",
                extra={
                    "provider": self.provider_name,
                    "state": self._state.value,
                },
            )

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status.

        Returns:
            Dictionary with current status
        """
        return {
            "provider": self.provider_name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
            "cooldown_until": self._cooldown_until,
            "is_open": self.is_open,
            "is_closed": self.is_closed,
            "is_half_open": self.is_half_open,
        }
