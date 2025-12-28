# Phase 02: Circuit Breakers

## Objective

Implement circuit breakers for external services to prevent cascading failures and enable graceful degradation.

## New File: `src/core/resilience.py`

```python
"""Resilience patterns for production reliability.

AgentEx Pattern: Circuit breakers prevent cascading failures.
"""
import asyncio
import functools
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

    @property
    def state(self) -> CircuitState:
        """Get current state, transitioning if needed."""
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
        self._successes += 1
        self._last_success = datetime.now(timezone.utc)

        if self._state == CircuitState.HALF_OPEN:
            if self._successes >= self.half_open_max:
                self._state = CircuitState.CLOSED
                self._failures = 0
                self._successes = 0
                self.logger.info("circuit_closed", reason="recovery")

    def _record_failure(self, error: Exception):
        """Record failed call."""
        self._failures += 1
        self._last_failure = datetime.now(timezone.utc)

        if self._state == CircuitState.HALF_OPEN:
            # Immediate open on half-open failure
            self._state = CircuitState.OPEN
            self.logger.warning("circuit_opened", reason="half_open_failure", error=str(error)[:50])
        elif self._failures >= self.threshold:
            self._state = CircuitState.OPEN
            self.logger.warning("circuit_opened", reason="threshold", failures=self._failures)

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        **kwargs
    ) -> T:
        """Execute function through circuit breaker.

        Args:
            func: Async function to call
            *args, **kwargs: Arguments for func

        Returns:
            Function result

        Raises:
            CircuitOpenError: If circuit is open
            Exception: If function fails
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            remaining = self._cooldown_remaining()
            self.logger.debug("circuit_rejected", cooldown_remaining=remaining)
            raise CircuitOpenError(self.name, remaining)

        start_time = time.monotonic()
        try:
            result = await func(*args, **kwargs)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._record_success()
            self.logger.debug("circuit_success", duration_ms=duration_ms)
            return result

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            self._record_failure(e)
            self.logger.debug("circuit_failure", duration_ms=duration_ms, error=str(e)[:50])
            raise

    def reset(self):
        """Manually reset circuit to closed state."""
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


def get_circuit_stats() -> Dict[str, Dict]:
    """Get stats for all circuits."""
    return {
        "exa_api": exa_circuit.get_stats(),
        "tavily_api": tavily_circuit.get_stats(),
        "firebase": firebase_circuit.get_stats(),
        "qdrant": qdrant_circuit.get_stats(),
    }


def reset_all_circuits():
    """Reset all circuits (for testing/recovery)."""
    exa_circuit.reset()
    tavily_circuit.reset()
    firebase_circuit.reset()
    qdrant_circuit.reset()


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
```

## Update `src/tools/web_search.py`

Wrap Exa/Tavily calls with circuit breakers:

```python
# Add import at top
from src.core.resilience import exa_circuit, tavily_circuit, CircuitOpenError

# Update execute() method
async def execute(self, params: Dict[str, Any]) -> str:
    query = params.get("query", "")

    if not query:
        return "Search failed: No query provided"

    # Check cache first
    cached = self._get_cached(query)
    if cached:
        return cached

    result = None

    # Try Exa with circuit breaker
    try:
        result = await exa_circuit.call(self._search_exa, query)
    except CircuitOpenError as e:
        logger.warning("exa_circuit_open", cooldown=e.cooldown_remaining)
        result = f"Search failed: Exa circuit open"
    except Exception as e:
        logger.warning("exa_failed", error=str(e)[:50])
        result = f"Search failed: {str(e)[:50]}"

    # Fallback to Tavily if Exa failed
    if result and result.startswith("Search failed") and self.tavily_client:
        logger.info("fallback_to_tavily", query=query[:30])
        try:
            result = await tavily_circuit.call(self._search_tavily, query)
        except CircuitOpenError as e:
            logger.warning("tavily_circuit_open", cooldown=e.cooldown_remaining)
            result = f"Search failed: All search services unavailable"
        except Exception as e:
            result = f"Search failed: {str(e)[:50]}"

    # Cache successful results
    if result and not result.startswith("Search failed"):
        self._set_cache(query, result)

    return result or "Search failed: Unknown error"
```

## Update `src/core/__init__.py`

Add resilience exports:

```python
from src.core.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    exa_circuit,
    tavily_circuit,
    firebase_circuit,
    qdrant_circuit,
    get_circuit_stats,
    reset_all_circuits,
    with_retry,
)
```

## Verification

```bash
# Test circuit breaker
python3 -c "
import asyncio
from src.core.resilience import CircuitBreaker, CircuitOpenError

async def test():
    circuit = CircuitBreaker('test', threshold=2, cooldown=5)

    # Simulate failures
    async def failing_call():
        raise Exception('Service down')

    for i in range(3):
        try:
            await circuit.call(failing_call)
        except CircuitOpenError as e:
            print(f'Circuit open after {i+1} attempts: {e}')
            break
        except Exception:
            print(f'Attempt {i+1} failed')

asyncio.run(test())
"
```

## Acceptance Criteria

- [ ] CircuitBreaker tracks failures and opens at threshold
- [ ] OPEN state rejects requests immediately
- [ ] HALF_OPEN allows test request after cooldown
- [ ] Successful test closes circuit
- [ ] Pre-configured circuits for Exa, Tavily, Firebase, Qdrant
- [ ] web_search.py uses circuit breakers
- [ ] get_circuit_stats() returns all circuit states
- [ ] with_retry decorator works with exponential backoff
