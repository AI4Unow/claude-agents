# Phase 05: Unit Tests

## Context

- **Parent Plan:** [plan.md](./plan.md)
- **Issue:** Code review - No unit tests for core modules
- **Related:** `src/core/trace.py`, `src/core/resilience.py`

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-28 |
| Priority | HIGH |
| Effort | 3h |
| Implementation | pending |
| Review | pending |

## Problem

Zero test coverage for critical path modules. Makes refactoring risky.

## Solution

Add pytest unit tests targeting 80% coverage for:
- `src/core/trace.py` - TraceContext, ToolTrace, ExecutionTrace
- `src/core/resilience.py` - CircuitBreaker, with_retry

## Related Files

| File | Action |
|------|--------|
| `tests/test_trace.py` | NEW - TraceContext tests |
| `tests/test_resilience.py` | NEW - CircuitBreaker tests |
| `tests/conftest.py` | NEW - Shared fixtures |
| `requirements.txt` | Add pytest, pytest-asyncio |

## Implementation Steps

1. Add pytest dependencies
2. Create conftest.py with shared fixtures
3. Write test_trace.py
4. Write test_resilience.py
5. Run tests and verify coverage

## Test Plan

### test_trace.py

```python
# TraceContext tests
async def test_trace_context_sets_status_success():
    """Normal exit sets status to success."""

async def test_trace_context_sets_status_error_on_exception():
    """Exception sets status to error."""

async def test_trace_context_cleanup_on_save_failure():
    """Context restored even if _save_trace fails."""

async def test_trace_sampling_errors_always_saved():
    """Error traces always saved (100%)."""

async def test_trace_sampling_success_10_percent():
    """Success traces sampled at 10%."""

async def test_max_tool_traces_limit():
    """Exceeding MAX_TOOL_TRACES stops adding."""

# ToolTrace tests
def test_tool_trace_truncates_output():
    """Output truncated to 500 chars."""

def test_tool_trace_sanitizes_sensitive_keys():
    """api_key, token, password redacted."""

# Input validation tests
async def test_get_trace_validates_trace_id():
    """Invalid trace_id returns None."""

async def test_list_traces_validates_status():
    """Invalid status ignored."""

async def test_list_traces_clamps_limit():
    """limit < 1 or > 100 reset to 20."""
```

### test_resilience.py

```python
# CircuitBreaker state tests
def test_circuit_starts_closed():
    """New circuit is CLOSED."""

async def test_circuit_opens_after_threshold_failures():
    """Circuit opens after N failures."""

async def test_circuit_half_open_after_cooldown():
    """OPEN transitions to HALF_OPEN after cooldown."""

async def test_circuit_closes_on_half_open_success():
    """HALF_OPEN success closes circuit."""

async def test_circuit_opens_on_half_open_failure():
    """HALF_OPEN failure reopens circuit."""

# Thread safety tests
async def test_circuit_thread_safe_state_transitions():
    """Concurrent calls don't corrupt state."""

# CircuitOpenError tests
async def test_circuit_open_raises_error():
    """OPEN circuit raises CircuitOpenError."""

def test_circuit_open_error_includes_cooldown():
    """Error includes cooldown_remaining."""

# Timeout tests (Phase 01 dependent)
async def test_circuit_call_times_out():
    """Slow function times out."""

async def test_timeout_recorded_as_failure():
    """Timeout counts as failure."""

# with_retry tests
async def test_with_retry_retries_on_failure():
    """Decorator retries N times."""

async def test_with_retry_exponential_backoff():
    """Delay increases exponentially."""

async def test_with_retry_only_retries_specified_exceptions():
    """Only retries matching exception types."""

# Reset tests
def test_reset_clears_state():
    """reset() restores to CLOSED with 0 counters."""
```

### conftest.py

```python
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_state_manager():
    """Mock StateManager to avoid Firebase calls."""
    with patch("src.core.trace.get_state_manager") as mock:
        manager = AsyncMock()
        manager.set = AsyncMock()
        manager.get = AsyncMock(return_value=None)
        mock.return_value = manager
        yield manager

@pytest.fixture
def circuit():
    """Fresh circuit breaker for each test."""
    from src.core.resilience import CircuitBreaker
    return CircuitBreaker("test", threshold=3, cooldown=1)
```

## Dependencies

Add to requirements.txt:
```
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
```

## Commands

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/core --cov-report=term-missing

# Run specific test file
pytest tests/test_trace.py -v
```

## Todo List

- [ ] Add pytest dependencies to requirements.txt
- [ ] Create tests/conftest.py with fixtures
- [ ] Write tests/test_trace.py (10+ tests)
- [ ] Write tests/test_resilience.py (12+ tests)
- [ ] Run tests and verify 80% coverage
- [ ] Fix any bugs found during testing

## Success Criteria

- [ ] `pytest tests/` passes all tests
- [ ] 80%+ coverage for src/core/trace.py
- [ ] 80%+ coverage for src/core/resilience.py
- [ ] All critical paths tested (error handling, state transitions)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Mocking too much | MEDIUM | Integration tests later |
| Flaky async tests | LOW | Use pytest-asyncio fixtures |
| Tests take too long | LOW | Mock external calls |

## Test Coverage Goals

| File | Target | Critical Paths |
|------|--------|----------------|
| trace.py | 80% | TraceContext enter/exit, sampling, max limits |
| resilience.py | 80% | State transitions, thread safety, timeout |

## Next Steps

After tests pass, all short-term improvements are complete. Update plan.md status to `completed`.
