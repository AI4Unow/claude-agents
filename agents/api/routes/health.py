"""Health check endpoint with circuit breaker status."""
from fastapi import APIRouter
from datetime import datetime, timezone


router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Health check endpoint with circuit status.

    Returns:
        Service health status including circuit breaker states
    """
    from src.core.resilience import get_circuit_stats

    circuits = get_circuit_stats()
    any_open = any(c["state"] == "open" for c in circuits.values())

    return {
        "status": "degraded" if any_open else "healthy",
        "agent": "claude-agents",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "circuits": circuits,
    }
