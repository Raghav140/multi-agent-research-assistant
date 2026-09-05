"""Tests for CircuitBreaker."""

import pytest
import asyncio
from unittest.mock import AsyncMock

from backend.providers.circuit_breaker import CircuitBreaker, CircuitState


@pytest.fixture
def circuit_breaker():
    """Create a circuit breaker with short timeouts for testing."""
    return CircuitBreaker("test_provider", failure_threshold=3, cooldown_seconds=1, timeout_seconds=1)


def test_circuit_breaker_initial_state(circuit_breaker):
    """Test circuit breaker starts in CLOSED state."""
    assert circuit_breaker.state == CircuitState.CLOSED
    assert circuit_breaker.failure_count == 0


def test_circuit_breaker_success(circuit_breaker):
    """Test successful call doesn't open circuit."""
    async def test_func():
        return "success"

    result = asyncio.run(circuit_breaker.call(test_func))
    assert result == "success"
    assert circuit_breaker.state == CircuitState.CLOSED
    assert circuit_breaker.failure_count == 0


def test_circuit_breaker_failure_counting(circuit_breaker):
    """Test failures are counted correctly."""
    async def failing_func():
        raise Exception("Test error")

    # First failure
    try:
        asyncio.run(circuit_breaker.call(failing_func))
    except:
        pass
    assert circuit_breaker.failure_count == 1
    assert circuit_breaker.state == CircuitState.CLOSED

    # Second failure
    try:
        asyncio.run(circuit_breaker.call(failing_func))
    except:
        pass
    assert circuit_breaker.failure_count == 2
    assert circuit_breaker.state == CircuitState.CLOSED

    # Third failure - should open circuit
    try:
        asyncio.run(circuit_breaker.call(failing_func))
    except:
        pass
    assert circuit_breaker.failure_count == 3
    assert circuit_breaker.state == CircuitState.OPEN


def test_circuit_breaker_blocks_when_open(circuit_breaker):
    """Test calls are blocked when circuit is open."""
    async def failing_func():
        raise Exception("Test error")

    # Open the circuit
    for _ in range(3):
        try:
            asyncio.run(circuit_breaker.call(failing_func))
        except:
            pass

    assert circuit_breaker.state == CircuitState.OPEN

    # Next call should be blocked immediately
    async def test_func():
        return "success"

    try:
        asyncio.run(circuit_breaker.call(test_func))
        assert False, "Should have raised CircuitBreakerError"
    except Exception as e:
        assert "Circuit breaker OPEN" in str(e)


def test_circuit_breaker_timeout(circuit_breaker):
    """Test timeout triggers failure."""
    async def slow_func():
        await asyncio.sleep(2)
        return "success"

    try:
        asyncio.run(circuit_breaker.call(slow_func))
        assert False, "Should have timed out"
    except Exception as e:
        # Timeout should count as failure
        assert circuit_breaker.failure_count >= 1


def test_circuit_breaker_half_open_after_cooldown(circuit_breaker):
    """Test circuit transitions to HALF_OPEN after cooldown and then to CLOSED on success."""
    async def failing_func():
        raise Exception("Test error")

    # Open the circuit
    for _ in range(3):
        try:
            asyncio.run(circuit_breaker.call(failing_func))
        except:
            pass

    assert circuit_breaker.state == CircuitState.OPEN

    # Wait for cooldown
    asyncio.run(asyncio.sleep(1.1))

    # Next call should transition to HALF_OPEN and then to CLOSED on success
    async def test_func():
        return "success"

    result = asyncio.run(circuit_breaker.call(test_func))
    assert result == "success"

    # Should be in CLOSED state after successful HALF_OPEN call
    assert circuit_breaker.state == CircuitState.CLOSED
    assert circuit_breaker.failure_count == 0


def test_circuit_breaker_reset_on_success(circuit_breaker):
    """Test circuit resets to CLOSED on successful call in HALF_OPEN."""
    async def failing_func():
        raise Exception("Test error")

    # Open the circuit
    for _ in range(3):
        try:
            asyncio.run(circuit_breaker.call(failing_func))
        except:
            pass

    assert circuit_breaker.state == CircuitState.OPEN

    # Wait for cooldown
    asyncio.run(asyncio.sleep(1.1))

    # Successful call should reset
    async def test_func():
        return "success"

    result = asyncio.run(circuit_breaker.call(test_func))
    assert result == "success"
    assert circuit_breaker.state == CircuitState.CLOSED
    assert circuit_breaker.failure_count == 0


def test_circuit_breaker_get_status(circuit_breaker):
    """Test get_status returns correct information."""
    status = circuit_breaker.get_status()
    assert status["provider"] == "test_provider"
    assert status["state"] == CircuitState.CLOSED.value
    assert status["failure_count"] == 0
    assert "last_failure_time" in status


def test_circuit_breaker_reset(circuit_breaker):
    """Test reset function."""
    async def failing_func():
        raise Exception("Test error")

    # Open the circuit
    for _ in range(3):
        try:
            asyncio.run(circuit_breaker.call(failing_func))
        except:
            pass

    assert circuit_breaker.state == CircuitState.OPEN
    assert circuit_breaker.failure_count == 3

    # Reset should be async now
    asyncio.run(circuit_breaker.reset())

    assert circuit_breaker.state == CircuitState.CLOSED
    assert circuit_breaker.failure_count == 0
    assert circuit_breaker.success_count == 0


def test_circuit_breaker_concurrent_calls_no_deadlock(circuit_breaker):
    """Test concurrent calls do not cause deadlock."""
    async def test_func():
        await asyncio.sleep(0.1)
        return "success"

    async def run_concurrent():
        tasks = [circuit_breaker.call(test_func) for _ in range(5)]
        results = await asyncio.gather(*tasks)
        return results

    results = asyncio.run(run_concurrent())
    assert len(results) == 5
    assert all(r == "success" for r in results)
    assert circuit_breaker.state == CircuitState.CLOSED
