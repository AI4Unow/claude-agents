"""Circuit breaker PreToolUse hook."""

from claude_agents import Hook, PreToolUseResult
from typing import Dict, Any, Optional
import structlog

logger = structlog.get_logger()

# Tool → Circuit breaker mapping
TOOL_CIRCUITS = {
    "web_search": ["exa", "tavily"],
    "search_memory": ["qdrant"],
    "gemini_vision": ["gemini"],
    "gemini_grounding": ["gemini"],
}


class CircuitBreakerHook(Hook):
    """Block tool execution if circuit is open."""

    def __init__(self, circuit_manager):
        self.circuit_manager = circuit_manager

    async def pre_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> PreToolUseResult:
        circuits = TOOL_CIRCUITS.get(tool_name, [])

        for circuit_name in circuits:
            if not self.circuit_manager.is_closed(circuit_name):
                logger.warning("circuit_open", tool=tool_name, circuit=circuit_name)
                return PreToolUseResult(
                    allow=False,
                    message=f"Service {circuit_name} temporarily unavailable",
                )

        return PreToolUseResult(allow=True)
