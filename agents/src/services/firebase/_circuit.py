"""Circuit breaker decorator for Firebase operations.

Eliminates repeated circuit breaker boilerplate across 24+ operations.
"""
from functools import wraps
from typing import TypeVar, Callable, Any

from src.core.resilience import firebase_circuit, CircuitState, CircuitOpenError
from src.utils.logging import get_logger

logger = get_logger()
T = TypeVar('T')

# Sentinel for circuit open state
CIRCUIT_OPEN = object()


def with_firebase_circuit(
    operation: str = None,
    open_return: Any = None,
    raise_on_open: bool = False
):
    """Decorator for Firebase operations with circuit breaker.

    Args:
        operation: Operation name for logging (auto-detected from func name)
        open_return: Value to return when circuit open (None, [], False, CIRCUIT_OPEN)
        raise_on_open: Raise CircuitOpenError instead of returning

    Usage:
        @with_firebase_circuit(open_return=None)
        async def get_user(user_id: int):
            db = get_db()
            ...

        @with_firebase_circuit(raise_on_open=True)
        async def create_user(user_id: int, data: dict):
            db = get_db()
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            op_name = operation or func.__name__

            # Check circuit state
            if firebase_circuit.state == CircuitState.OPEN:
                logger.warning("firebase_circuit_open", operation=op_name)
                if raise_on_open:
                    raise CircuitOpenError("firebase", firebase_circuit._cooldown_remaining())
                return open_return

            # Execute with circuit tracking
            try:
                result = await func(*args, **kwargs)
                firebase_circuit._record_success()
                return result
            except Exception as e:
                firebase_circuit._record_failure(e)
                logger.error(
                    f"firebase_{op_name}_error",
                    error=str(e)[:100],
                    error_type=type(e).__name__
                )
                raise

        return wrapper
    return decorator
