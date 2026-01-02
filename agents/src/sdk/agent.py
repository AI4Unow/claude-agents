"""Main SDK agent configuration."""

from anthropic import Anthropic
from claude_agents import Agent
from typing import List, Optional, Callable
import structlog

from .config import AgentConfig, TierLimits
from .hooks import get_all_hooks
from .tools import get_all_tools
from src.core.resilience import CircuitBreakerManager

logger = structlog.get_logger()


def create_agent(
    user_id: int,
    tier: str = "user",
    config: Optional[AgentConfig] = None,
    tools: Optional[List[Callable]] = None,
    circuit_manager: Optional[CircuitBreakerManager] = None,
) -> Agent:
    """Create SDK agent for user with tier-appropriate limits.

    Args:
        user_id: Telegram user ID
        tier: User tier (guest, user, developer, admin)
        config: Optional agent config override
        tools: Optional tool list override
        circuit_manager: Circuit breaker manager for PreToolUse

    Returns:
        Configured Agent instance
    """
    config = config or AgentConfig.for_tier(tier)

    # Get tier-appropriate iteration limits
    limits = TierLimits.for_tier(tier)

    # Collect all hooks
    hooks = get_all_hooks(
        user_id=user_id,
        config=config,
        circuit_manager=circuit_manager,
    )

    # Get tools (existing + new)
    all_tools = tools or get_all_tools()

    agent = Agent(
        model=config.model,
        tools=all_tools,
        hooks=hooks,
        max_iterations=limits.max_iterations,
        system_prompt=_build_system_prompt(user_id, tier),
    )

    return agent


async def run_agent(
    agent: Agent,
    message: str,
    context: Optional[dict] = None,
) -> str:
    """Run agent with message.

    Args:
        agent: Configured Agent
        message: User message
        context: Optional context (tasks, calendar, etc.)

    Returns:
        Agent response
    """
    prompt = message
    if context:
        prompt = f"Context: {context}\n\nUser: {message}"

    try:
        result = await agent.run(prompt)
        return result.content
    except Exception as e:
        logger.error("agent_run_failed", error=str(e))
        raise


def _build_system_prompt(user_id: int, tier: str) -> str:
    """Build system prompt with user context."""
    return f"""You are ai4u.now, a smart personal assistant.
User ID: {user_id} | Tier: {tier}

Capabilities: Task management, calendar sync, web search, memory, code execution.
Trust rules enforce permission checks before tool execution."""
