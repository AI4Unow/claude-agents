"""Live tests for circuit breaker behavior.

Tests real circuit breaker patterns:
- Circuit opens after threshold failures
- Recovery after cooldown period
- All circuits start in expected state
"""
import pytest
from datetime import datetime, timezone, timedelta


@pytest.mark.live
@pytest.mark.asyncio
async def test_circuit_opens_on_failures(reset_circuits):
    """Circuit opens after threshold failures.

    Tests basic circuit breaker open behavior with intentional failures.
    """
    from src.core.resilience import (
        CircuitBreaker, CircuitState, CircuitOpenError
    )

    circuit = CircuitBreaker("test_live", threshold=2, cooldown=5)

    async def failing_func():
        raise ValueError("Intentional failure")

    # Two failures should open circuit
    for i in range(2):
        with pytest.raises(ValueError):
            await circuit.call(failing_func)

    assert circuit.state == CircuitState.OPEN, f"Circuit not open after 2 failures: {circuit.state}"

    # Next call should raise CircuitOpenError
    with pytest.raises(CircuitOpenError) as exc:
        await circuit.call(failing_func)

    assert exc.value.name == "test_live"
    assert exc.value.cooldown_remaining <= 5, f"Cooldown {exc.value.cooldown_remaining}s exceeds limit"

    print(f"\nCircuit opened correctly. Cooldown: {exc.value.cooldown_remaining}s")


@pytest.mark.live
@pytest.mark.asyncio
async def test_circuit_recovery_after_cooldown(reset_circuits):
    """Circuit recovers after cooldown period.

    Tests complete circuit lifecycle: CLOSED → OPEN → HALF_OPEN → CLOSED
    """
    from src.core.resilience import CircuitBreaker, CircuitState

    circuit = CircuitBreaker("test_recovery", threshold=2, cooldown=1)

    async def failing_func():
        raise ValueError("Fail")

    async def success_func():
        return "success"

    # Open circuit with 2 failures
    for i in range(2):
        with pytest.raises(ValueError):
            await circuit.call(failing_func)

    assert circuit.state == CircuitState.OPEN, "Circuit not open after failures"
    print("\nCircuit opened, waiting for cooldown...")

    # Wait for cooldown (1 second + buffer)
    import asyncio
    await asyncio.sleep(1.5)

    # Should transition to HALF_OPEN
    assert circuit.state == CircuitState.HALF_OPEN, f"Circuit not half-open after cooldown: {circuit.state}"
    print("Circuit transitioned to half-open")

    # Successful call should close
    result = await circuit.call(success_func)
    assert result == "success", f"Success function failed: {result}"
    assert circuit.state == CircuitState.CLOSED, f"Circuit not closed after success: {circuit.state}"

    print("Circuit recovered and closed")


@pytest.mark.live
@pytest.mark.asyncio
async def test_all_circuits_status(reset_circuits):
    """All circuits are in expected initial state.

    Verifies all production circuits exist and start closed with no failures.
    """
    from src.core.resilience import get_circuit_stats, CircuitState

    stats = get_circuit_stats()

    expected_circuits = [
        "exa_api", "tavily_api", "firebase", "qdrant",
        "claude_api", "telegram_api", "gemini_api", "evolution_api"
    ]

    print(f"\nFound circuits: {list(stats.keys())}")

    for name in expected_circuits:
        assert name in stats, f"Missing circuit: {name}"
        assert stats[name]["state"] == "closed", f"{name} not closed: {stats[name]['state']}"
        assert stats[name]["failures"] == 0, f"{name} has failures: {stats[name]['failures']}"

    print(f"All {len(expected_circuits)} circuits verified in closed state with 0 failures")
