# Phase 01: Circuit Breaker Timeout Protection

## Context

- **Parent Plan:** [plan.md](./plan.md)
- **Issue:** Code review #6 - CircuitBreaker.call() has no timeout
- **Related:** `src/core/resilience.py:122-160`

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-28 |
| Priority | HIGH |
| Effort | 1h |
| Implementation | completed |
| Review | pending |

## Problem

Current `CircuitBreaker.call()` awaits wrapped function indefinitely. Slow external services can hang the circuit, blocking resources.

```python
# Current (no timeout)
result = await func(*args, **kwargs)  # Hangs forever if slow
```

## Solution

Add optional timeout parameter with `asyncio.wait_for()`:

```python
async def call(
    self,
    func: Callable[..., Awaitable[T]],
    *args,
    timeout: Optional[float] = 30.0,  # NEW
    **kwargs
) -> T:
    # ... state checks ...

    start_time = time.monotonic()
    try:
        if timeout:
            result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
        else:
            result = await func(*args, **kwargs)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        self._record_success()
        return result

    except asyncio.TimeoutError as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        self._record_failure(e)
        self.logger.warning("circuit_timeout", duration_ms=duration_ms, timeout=timeout)
        raise
```

## Related Files

| File | Lines | Action |
|------|-------|--------|
| `src/core/resilience.py` | 122-160 | Update call() method |
| `src/tools/web_search.py` | 98-112 | Pass timeout to circuit.call() |

## Implementation Steps

1. Add `import asyncio` at top (if not present)
2. Add `timeout: Optional[float] = 30.0` parameter to `call()` method
3. Wrap `func(*args, **kwargs)` with `asyncio.wait_for()` when timeout set
4. Add `asyncio.TimeoutError` handling that records failure and logs
5. Update callers in `web_search.py` to pass explicit timeout if needed

## Code Changes

### src/core/resilience.py

```python
# Add after line 121 (call method signature)
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

    Raises:
        CircuitOpenError: Circuit is open
        asyncio.TimeoutError: Function timed out
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
```

## Success Criteria

- [x] `call()` accepts optional `timeout` parameter (default 30s)
- [x] TimeoutError recorded as failure and triggers circuit open
- [x] Existing callers work without changes (default timeout)
- [ ] Test: slow function times out after configured duration

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking change for callers | LOW | Default timeout=30s maintains behavior |
| Timeout too short for valid ops | MEDIUM | Make configurable per-call |

## Next Steps

After this phase, proceed to [Phase 02](./phase-02-structured-tool-responses.md).
