"""Tools package - Tool registry and tool implementations."""
from src.tools.registry import ToolRegistry, get_registry
from src.tools.base import BaseTool
from src.tools.web_search import WebSearchTool


def init_default_tools():
    """Register default tools."""
    registry = get_registry()
    registry.register(WebSearchTool())


__all__ = ["ToolRegistry", "get_registry", "BaseTool", "WebSearchTool", "init_default_tools"]
