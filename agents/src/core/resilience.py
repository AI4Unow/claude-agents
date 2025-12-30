"""Resilience patterns for production reliability.

AgentEx Pattern: Circuit breakers prevent cascading failures.
"""
import asyncio
import functools
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, Awaitable

from src.utils.logging import get_logger

logger = get_logger()

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitOpenError(Exception):
    """Raised when circuit is open."""
    def __init__(self, name: str, cooldown_remaining: int):
        self.name = name
        self.cooldown_remaining = cooldown_remaining
        super().__init__(f"Circuit '{name}' is open. Retry in {cooldown_remaining}s")


@dataclass
class CircuitBreaker:
    """Circuit breaker for external service calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service failing, reject requests immediately
    - HALF_OPEN: Testing if service recovered

    Usage:
        exa_circuit = CircuitBreaker("exa_api", threshold=3, cooldown=30)

        try:
            result = await exa_circuit.call(search_exa, query)
        except CircuitOpenError as e:
            # Fallback to alternative
            result = await tavily_circuit.call(search_tavily, query)
    """
    name: str
    threshold: int = 3  # Failures before opening
    cooldown: int = 30  # Seconds before half-open
    half_open_max: int = 1  # Successful calls to close

    # Internal state
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failures: int = field(default=0, init=False)
    _successes: int = field(default=0, init=False)
    _last_failure: Optional[datetime] = field(default=None, init=False)
    _last_success: Optional[datetime] = field(default=None, init=False)

    def __post_init__(self):
        self.logger = logger.bind(circuit=self.name)
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current state, transitioning if needed."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_try_half_open():
                    self._state = CircuitState.HALF_OPEN
                    self.logger.info("circuit_half_open")
            return self._state

    def _should_try_half_open(self) -> bool:
        """Check if cooldown has passed."""
        if self._last_failure is None:
            return True
        elapsed = datetime.now(timezone.utc) - self._last_failure
        return elapsed > timedelta(seconds=self.cooldown)

    def _cooldown_remaining(self) -> int:
        """Seconds remaining in cooldown."""
        if self._last_failure is None:
            return 0
        elapsed = datetime.now(timezone.utc) - self._last_failure
        remaining = self.cooldown - int(elapsed.total_seconds())
        return max(0, remaining)

    def _record_success(self):
        """Record successful call."""
        now = datetime.now(timezone.utc)  # Outside lock to minimize critical section
        should_log_closed = False

        with self._lock:
            self._successes += 1
            self._last_success = now

            if self._state == CircuitState.HALF_OPEN:
                if self._successes >= self.half_open_max:
                    self._state = CircuitState.CLOSED
                    self._failures = 0
                    self._successes = 0
                    should_log_closed = True

        # Log outside lock to reduce contention
        if should_log_closed:
            self.logger.info("circuit_closed", reason="recovery")

    def _record_failure(self, error: Exception):
        """Record failed call."""
        now = datetime.now(timezone.utc)  # Outside lock to minimize critical section
        log_data = None

        with self._lock:
            self._failures += 1
            self._last_failure = now

            if self._state == CircuitState.HALF_OPEN:
                # Immediate open on half-open failure
                self._state = CircuitState.OPEN
                log_data = ("half_open_failure", str(error)[:50], None)
            elif self._failures >= self.threshold:
                self._state = CircuitState.OPEN
                log_data = ("threshold", str(error)[:50], self._failures)

        # Log outside lock to reduce contention
        if log_data:
            reason, error_msg, failures = log_data
            if failures is not None:
                self.logger.warning("circuit_opened", reason=reason, failures=failures)
            else:
                self.logger.warning("circuit_opened", reason=reason, error=error_msg)

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        timeout: Optional[float] = 30.0,
        **kwargs
    ) -> T:
        """Execute function through circuit breaker.

        Args:
            func: Async function to call
            *args: Positional arguments for func
            timeout: Max seconds to wait (None=no timeout)
            **kwargs: Keyword arguments for func

        Returns:
            Function result

        Raises:
            CircuitOpenError: If circuit is open
            asyncio.TimeoutError: If function timed out
            Exception: If function fails
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            remaining = self._cooldown_remaining()
            self.logger.debug("circuit_rejected", cooldown_remaining=remaining)
            raise CircuitOpenError(self.name, remaining)

        start_time = time.monotonic()
        try:
            if timeout:
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            else:
                result = await func(*args, **kwargs)

            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._record_success()
            self.logger.debug("circuit_success", duration_ms=duration_ms)
            return result

        except asyncio.TimeoutError as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._record_failure(e)
            self.logger.warning("circuit_timeout", duration_ms=duration_ms, timeout=timeout)
            raise

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._record_failure(e)
            self.logger.debug("circuit_failure", duration_ms=duration_ms, error=str(e)[:50])
            raise

    def reset(self):
        """Manually reset circuit to closed state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failures = 0
            self._successes = 0
            self._last_failure = None
        self.logger.info("circuit_reset")

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit statistics."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failures": self._failures,
            "successes": self._successes,
            "threshold": self.threshold,
            "cooldown": self.cooldown,
            "cooldown_remaining": self._cooldown_remaining(),
            "last_failure": self._last_failure.isoformat() if self._last_failure else None,
            "last_success": self._last_success.isoformat() if self._last_success else None,
        }


# Pre-configured circuits for external services
exa_circuit = CircuitBreaker("exa_api", threshold=3, cooldown=30)
tavily_circuit = CircuitBreaker("tavily_api", threshold=3, cooldown=30)
firebase_circuit = CircuitBreaker("firebase", threshold=5, cooldown=60)
qdrant_circuit = CircuitBreaker("qdrant", threshold=5, cooldown=60)
claude_circuit = CircuitBreaker("claude_api", threshold=5, cooldown=60)
telegram_circuit = CircuitBreaker("telegram_api", threshold=5, cooldown=30)
gemini_circuit = CircuitBreaker("gemini_api", threshold=3, cooldown=60)
evolution_circuit = CircuitBreaker("evolution_api", threshold=3, cooldown=30)


def get_circuit_stats() -> Dict[str, Dict]:
    """Get stats for all circuits."""
    return {
        "exa_api": exa_circuit.get_stats(),
        "tavily_api": tavily_circuit.get_stats(),
        "firebase": firebase_circuit.get_stats(),
        "qdrant": qdrant_circuit.get_stats(),
        "claude_api": claude_circuit.get_stats(),
        "telegram_api": telegram_circuit.get_stats(),
        "gemini_api": gemini_circuit.get_stats(),
        "evolution_api": evolution_circuit.get_stats(),
    }


def get_circuit_status() -> Dict[str, str]:
    """Get simplified status (state only) for all circuits."""
    return {
        "exa": exa_circuit.state.value,
        "tavily": tavily_circuit.state.value,
        "firebase": firebase_circuit.state.value,
        "qdrant": qdrant_circuit.state.value,
        "claude": claude_circuit.state.value,
        "telegram": telegram_circuit.state.value,
        "gemini": gemini_circuit.state.value,
        "evolution": evolution_circuit.state.value,
    }


def reset_all_circuits():
    """Reset all circuits (for testing/recovery)."""
    exa_circuit.reset()
    tavily_circuit.reset()
    firebase_circuit.reset()
    qdrant_circuit.reset()
    claude_circuit.reset()
    telegram_circuit.reset()
    gemini_circuit.reset()
    evolution_circuit.reset()


def reset_circuit(name: str) -> bool:
    """Reset a specific circuit by name.

    Args:
        name: Circuit name (e.g., "exa_api", "claude_api")

    Returns:
        True if reset successful, False if circuit not found
    """
    circuits = {
        "exa_api": exa_circuit,
        "tavily_api": tavily_circuit,
        "firebase": firebase_circuit,
        "qdrant": qdrant_circuit,
        "claude_api": claude_circuit,
        "telegram_api": telegram_circuit,
        "gemini_api": gemini_circuit,
        "evolution_api": evolution_circuit,
    }

    circuit = circuits.get(name)
    if circuit:
        circuit.reset()
        return True
    return False


def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Decorator for retry with exponential backoff.

    Usage:
        @with_retry(max_attempts=3, delay=1.0)
        async def fetch_data():
            ...
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = delay

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.debug(
                            "retry_attempt",
                            func=func.__name__,
                            attempt=attempt,
                            delay=current_delay,
                            error=str(e)[:50]
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff

            raise last_exception

        return wrapper
    return decorator
