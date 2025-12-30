"""Admin API endpoints.

Protected endpoints for debugging and system management.
Requires X-Admin-Token header.
"""
from fastapi import APIRouter, Depends, Header
from typing import Optional
import structlog


router = APIRouter(prefix="/api", tags=["admin"])
logger = structlog.get_logger()


async def verify_admin_token_dep(x_admin_token: str = Header(None)):
    """Dependency to verify admin token."""
    from api.dependencies import verify_admin_token
    return await verify_admin_token(x_admin_token)


@router.get("/traces")
async def list_traces_endpoint(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 20,
    _: bool = Depends(verify_admin_token_dep)
):
    """List execution traces for debugging.

    Admin only. Requires X-Admin-Token header.

    Args:
        user_id: Filter by user ID
        status: Filter by status (success, error, pending)
        limit: Max number of traces to return

    Returns:
        List of execution traces
    """
    from src.core.trace import list_traces

    try:
        traces = await list_traces(user_id=user_id, status=status, limit=limit)
        return {
            "traces": [t.to_dict() for t in traces],
            "count": len(traces),
        }
    except Exception as e:
        return {"error": str(e)}, 500


@router.get("/traces/{trace_id}")
async def get_trace_endpoint(trace_id: str, _: bool = Depends(verify_admin_token_dep)):
    """Get single trace by ID.

    Admin only. Requires X-Admin-Token header.

    Args:
        trace_id: Trace identifier

    Returns:
        Trace details
    """
    from src.core.trace import get_trace

    trace = await get_trace(trace_id)
    if trace:
        return trace.to_dict()
    return {"error": "Trace not found"}, 404


@router.get("/circuits")
async def get_circuits_endpoint(_: bool = Depends(verify_admin_token_dep)):
    """Get circuit breaker status for all services.

    Admin only. Requires X-Admin-Token header.

    Returns:
        Circuit breaker states for all services
    """
    from src.core.resilience import get_circuit_stats

    return get_circuit_stats()


@router.post("/circuits/reset")
async def reset_circuits_endpoint(_: bool = Depends(verify_admin_token_dep)):
    """Reset all circuit breakers (admin only).

    Admin only. Requires X-Admin-Token header.

    Returns:
        Success message
    """
    from src.core.resilience import reset_all_circuits

    reset_all_circuits()
    return {"message": "All circuits reset"}
