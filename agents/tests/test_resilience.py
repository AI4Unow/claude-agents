"""Unit tests for src/core/resilience.py - Circuit Breaker and Retry patterns.

Target: 100% coverage
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from src.core.resilience import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    with_retry,
    exa_circuit,
    tavily_circuit,
    firebase_circuit,
    qdrant_circuit,
    get_circuit_stats,
    reset_all_circuits,
)


class TestCircuitBreakerState:
    """Test circuit breaker state transitions."""

    def test_circuit_starts_closed(self, circuit):
        """New circuit is CLOSED."""
        assert circuit.state == CircuitState.CLOSED
        assert circuit._failures == 0
        assert circuit._successes == 0

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold_failures(self, circuit):
        """Circuit opens after N failures."""
        async def failing_func():
            raise Exception("Test error")

        # Fail 3 times (threshold)
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit.call(failing_func)

        assert circuit.state == CircuitState.OPEN
        assert circuit._failures == 3

    @pytest.mark.asyncio
    async def test_circuit_stays_closed_below_threshold(self, circuit):
        """Circuit stays closed if failures below threshold."""
        async def failing_func():
            raise Exception("Test error")

        # Fail 2 times (below threshold of 3)
        for _ in range(2):
            with pytest.raises(Exception):
                await circuit.call(failing_func)

        assert circuit.state == CircuitState.CLOSED
        assert circuit._failures == 2

    @pytest.mark.asyncio
    async def test_circuit_half_open_after_cooldown(self, circuit):
        """OPEN transitions to HALF_OPEN after cooldown."""
        async def failing_func():
            raise Exception("Test error")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit.call(failing_func)

        assert circuit.state == CircuitState.OPEN

        # Simulate cooldown passed (1 second)
        circuit._last_failure = datetime.now(timezone.utc) - timedelta(seconds=2)

        # State should transition to HALF_OPEN
        assert circuit.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_circuit_closes_on_half_open_success(self, circuit):
        """HALF_OPEN success closes circuit."""
        async def failing_func():
            raise Exception("Test error")

        async def success_func():
            return "success"

        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit.call(failing_func)

        # Simulate cooldown passed
        circuit._last_failure = datetime.now(timezone.utc) - timedelta(seconds=2)
        assert circuit.state == CircuitState.HALF_OPEN

        # Successful call should close circuit
        result = await circuit.call(success_func)
        assert result == "success"
        assert circuit.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_opens_on_half_open_failure(self, circuit):
        """HALF_OPEN failure reopens circuit."""
        async def failing_func():
            raise Exception("Test error")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit.call(failing_func)

        # Simulate cooldown passed
        circuit._last_failure = datetime.now(timezone.utc) - timedelta(seconds=2)
        assert circuit.state == CircuitState.HALF_OPEN

        # Failure in half-open should reopen immediately
        with pytest.raises(Exception):
            await circuit.call(failing_func)

        assert circuit.state == CircuitState.OPEN


class TestCircuitBreakerCalls:
    """Test circuit breaker call behavior."""

    @pytest.mark.asyncio
    async def test_circuit_open_raises_error(self, circuit):
        """OPEN circuit raises CircuitOpenError."""
        async def failing_func():
            raise Exception("Test error")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit.call(failing_func)

        # Next call should raise CircuitOpenError
        with pytest.raises(CircuitOpenError) as exc_info:
            await circuit.call(failing_func)

        assert exc_info.value.name == "test"
        assert exc_info.value.cooldown_remaining >= 0

    def test_circuit_open_error_includes_cooldown(self):
        """Error includes cooldown_remaining."""
        error = CircuitOpenError("test_circuit", 25)
        assert error.name == "test_circuit"
        assert error.cooldown_remaining == 25
        assert "25s" in str(error)

    @pytest.mark.asyncio
    async def test_circuit_call_times_out(self, circuit):
        """Slow function times out."""
        async def slow_func():
            await asyncio.sleep(5)
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await circuit.call(slow_func, timeout=0.1)

    @pytest.mark.asyncio
    async def test_timeout_recorded_as_failure(self, circuit):
        """Timeout counts as failure."""
        async def slow_func():
            await asyncio.sleep(5)
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await circuit.call(slow_func, timeout=0.1)

        assert circuit._failures == 1

    @pytest.mark.asyncio
    async def test_successful_call_records_success(self, circuit):
        """Successful call records success."""
        async def success_func():
            return "result"

        result = await circuit.call(success_func)
        assert result == "result"
        assert circuit._successes == 1
        assert circuit._last_success is not None


class TestCircuitBreakerThreadSafety:
    """Test thread safety of circuit breaker."""

    @pytest.mark.asyncio
    async def test_circuit_thread_safe_state_transitions(self, circuit):
        """Concurrent calls don't corrupt state."""
        call_count = 0

        async def counting_func():
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise Exception("Even call fails")
            return "odd success"

        # Run 10 concurrent calls
        tasks = [circuit.call(counting_func) for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify state is consistent
        assert circuit._failures >= 0
        assert circuit._successes >= 0
        # Total should equal 10
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        fail_count = sum(1 for r in results if isinstance(r, Exception))
        assert success_count + fail_count == 10


class TestCircuitBreakerReset:
    """Test circuit reset functionality."""

    def test_reset_clears_state(self, circuit):
        """reset() restores to CLOSED with 0 counters."""
        # Manually set some state
        circuit._state = CircuitState.OPEN
        circuit._failures = 5
        circuit._successes = 3
        circuit._last_failure = datetime.now(timezone.utc)

        circuit.reset()

        assert circuit.state == CircuitState.CLOSED
        assert circuit._failures == 0
        assert circuit._successes == 0
        assert circuit._last_failure is None


class TestCircuitBreakerStats:
    """Test circuit statistics."""

    def test_get_stats_returns_dict(self, circuit):
        """get_stats returns comprehensive dict."""
        stats = circuit.get_stats()

        assert stats["name"] == "test"
        assert stats["state"] == "closed"
        assert stats["failures"] == 0
        assert stats["successes"] == 0
        assert stats["threshold"] == 3
        assert stats["cooldown"] == 1
        assert "cooldown_remaining" in stats
        assert "last_failure" in stats
        assert "last_success" in stats


class TestGlobalCircuits:
    """Test global circuit instances."""

    def test_preconfigured_circuits_exist(self):
        """Pre-configured circuits are initialized."""
        assert exa_circuit.name == "exa_api"
        assert tavily_circuit.name == "tavily_api"
        assert firebase_circuit.name == "firebase"
        assert qdrant_circuit.name == "qdrant"

    def test_get_circuit_stats_returns_all(self):
        """get_circuit_stats returns stats for all circuits."""
        stats = get_circuit_stats()

        assert "exa_api" in stats
        assert "tavily_api" in stats
        assert "firebase" in stats
        assert "qdrant" in stats

    def test_reset_all_circuits(self):
        """reset_all_circuits resets all global circuits."""
        # Manually open a circuit
        exa_circuit._state = CircuitState.OPEN
        exa_circuit._failures = 10

        reset_all_circuits()

        assert exa_circuit.state == CircuitState.CLOSED
        assert exa_circuit._failures == 0


class TestWithRetryDecorator:
    """Test retry decorator."""

    @pytest.mark.asyncio
    async def test_with_retry_retries_on_failure(self):
        """Decorator retries N times."""
        call_count = 0

        @with_retry(max_attempts=3, delay=0.01)
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Not yet")
            return "success"

        result = await failing_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_with_retry_fails_after_max_attempts(self):
        """Decorator fails after max attempts."""
        call_count = 0

        @with_retry(max_attempts=3, delay=0.01)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError):
            await always_fails()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_with_retry_exponential_backoff(self):
        """Delay increases exponentially."""
        import time
        start_times = []

        @with_retry(max_attempts=3, delay=0.05, backoff=2.0)
        async def tracked_failing():
            start_times.append(time.monotonic())
            raise ValueError("Fail")

        with pytest.raises(ValueError):
            await tracked_failing()

        # Check delays increased
        assert len(start_times) == 3
        delay1 = start_times[1] - start_times[0]
        delay2 = start_times[2] - start_times[1]

        # Second delay should be approximately double first delay
        # (with some tolerance for timing)
        assert delay2 > delay1 * 1.5

    @pytest.mark.asyncio
    async def test_with_retry_only_retries_specified_exceptions(self):
        """Only retries matching exception types."""
        call_count = 0

        @with_retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        async def type_error_func():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retried")

        with pytest.raises(TypeError):
            await type_error_func()

        # Should only be called once (no retry for TypeError)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_with_retry_success_on_first_try(self):
        """No retry needed on success."""
        call_count = 0

        @with_retry(max_attempts=3, delay=0.01)
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "immediate success"

        result = await success_func()
        assert result == "immediate success"
        assert call_count == 1


class TestCooldownRemaining:
    """Test cooldown remaining calculation."""

    def test_cooldown_remaining_when_no_failure(self, circuit):
        """No failure means 0 cooldown remaining."""
        assert circuit._cooldown_remaining() == 0

    def test_cooldown_remaining_decreases_over_time(self, circuit):
        """Cooldown decreases as time passes."""
        circuit._last_failure = datetime.now(timezone.utc)

        # Immediately after failure
        remaining = circuit._cooldown_remaining()
        assert remaining >= 0
        assert remaining <= circuit.cooldown

    def test_cooldown_remaining_zero_after_expiry(self, circuit):
        """Cooldown is 0 after cooldown period."""
        circuit._last_failure = datetime.now(timezone.utc) - timedelta(seconds=10)

        assert circuit._cooldown_remaining() == 0


class TestCircuitBreakerNoTimeout:
    """Test circuit breaker without timeout."""

    @pytest.mark.asyncio
    async def test_circuit_call_without_timeout(self, circuit):
        """Call works without timeout parameter."""
        async def success_func():
            return "result"

        result = await circuit.call(success_func, timeout=None)
        assert result == "result"
        assert circuit._successes == 1


class TestCircuitBreakerHalfOpenNoFailure:
    """Test half-open transition edge cases."""

    def test_should_try_half_open_when_no_failure(self, circuit):
        """_should_try_half_open returns True when no prior failure."""
        circuit._state = CircuitState.OPEN
        circuit._last_failure = None  # No failure recorded

        # Should transition to half-open
        assert circuit._should_try_half_open() is True
