"""SDK hooks package."""

from typing import List, Optional
from claude_agents import Hook

from .circuits import CircuitBreakerHook
from .trust_rules import TrustRulesHook
from .tracing import TracingHook
from .improvement import ImprovementHook

from src.core.trace import get_current_trace


def get_all_hooks(
    user_id: int,
    config,
    circuit_manager=None,
    skill_name: Optional[str] = None,
) -> List[Hook]:
    """Get all hooks for SDK agent.

    Args:
        user_id: User ID for trust rules
        config: Agent config
        circuit_manager: Circuit breaker manager
        skill_name: Skill name for improvement tracking

    Returns:
        List of hooks in execution order
    """
    hooks = []

    # PreToolUse hooks (executed before tool call)
    if circuit_manager:
        hooks.append(CircuitBreakerHook(circuit_manager))

    hooks.append(TrustRulesHook(user_id=user_id))

    # PostToolUse hooks (executed after tool call)
    trace = get_current_trace()
    if trace:
        hooks.append(TracingHook(trace_context=trace))

    hooks.append(ImprovementHook(skill_name=skill_name))

    return hooks


__all__ = [
    "CircuitBreakerHook",
    "TrustRulesHook",
    "TracingHook",
    "ImprovementHook",
    "get_all_hooks",
]
