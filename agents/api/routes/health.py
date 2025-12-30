"""Health check endpoint with circuit breaker status."""
from fastapi import APIRouter
from datetime import datetime, timezone


router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Health check endpoint with circuit status and platform availability.

    Returns:
        Service health status including circuit breaker states and platform status
    """
    from src.core.resilience import get_circuit_stats
    from src.services.evolution import get_connection_state

    circuits = get_circuit_stats()
    wa_state = await get_connection_state()

    any_open = any(c["state"] == "open" for c in circuits.values())
    wa_connected = wa_state == "open"

    return {
        "status": "degraded" if (any_open or not wa_connected) else "healthy",
        "agent": "claude-agents",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.2.0",
        "circuits": circuits,
        "platforms": {
            "telegram": "active",
            "whatsapp": wa_state or "disconnected"
        }
    }


@router.get("/health/whatsapp")
async def whatsapp_health():
    """Check WhatsApp connection via Evolution API.

    Returns:
        WhatsApp platform connection status
    """
    from src.services.evolution import get_connection_state

    state = await get_connection_state()

    return {
        "platform": "whatsapp",
        "connection": state or "unknown",
        "healthy": state == "open"
    }
