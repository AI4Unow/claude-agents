"""Telegram message handler using SDK agent."""

from typing import Dict, Any
import structlog

from src.sdk import create_agent, run_agent
from src.core.state import StateManager
from src.core.trace import TraceContext
from src.core.resilience import get_circuit_manager

logger = structlog.get_logger()


async def handle_telegram_message(
    user_id: int,
    message: str,
    tier: str = "user",
    context: Dict[str, Any] = None
) -> str:
    """Handle Telegram message with SDK agent.

    Args:
        user_id: Telegram user ID
        message: User message
        tier: User tier (guest, user, developer, admin)
        context: Optional additional context

    Returns:
        Agent response
    """
    # Initialize tracing
    trace = TraceContext(user_id=user_id, source="telegram")

    try:
        # Create SDK agent with all hooks
        agent = create_agent(
            user_id=user_id,
            tier=tier,
            circuit_manager=get_circuit_manager(),
        )

        # Load user context (tasks, preferences, etc.)
        state = StateManager()
        user_context = await state.get_user_context(user_id)

        # Merge with provided context
        if context:
            user_context.update(context)

        # Run agent
        response = await run_agent(agent, message, user_context)

        trace.complete(success=True)
        logger.info("telegram_agent_success", user_id=user_id, msg_len=len(message))

        return response

    except Exception as e:
        trace.complete(success=False, error=str(e))
        logger.error("telegram_agent_failed", error=str(e)[:100], user_id=user_id)
        raise
