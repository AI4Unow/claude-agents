"""Tool registry for managing and executing tools."""
from typing import Dict, List, Optional
from src.tools.base import BaseTool
import structlog

logger = structlog.get_logger()


class ToolRegistry:
    """Registry for managing tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.info("tool_registered", name=tool.name)

    def get_definitions(self) -> List[dict]:
        """Get all tool definitions in Anthropic format."""
        return [t.to_anthropic_format() for t in self._tools.values()]

    async def execute(self, name: str, params: dict) -> str:
        """Execute a tool by name."""
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Unknown tool '{name}'"
        try:
            return await tool.execute(params)
        except Exception as e:
            logger.error("tool_execution_error", tool=name, error=str(e))
            return f"Tool error: {str(e)[:100]}"


# Global registry singleton
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get or create global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
