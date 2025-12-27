"""Tools package - Tool registry and tool implementations."""
from src.tools.registry import ToolRegistry, get_registry
from src.tools.base import BaseTool
from src.tools.web_search import WebSearchTool
from src.tools.datetime_tool import DateTimeTool
from src.tools.code_exec import CodeExecutionTool
from src.tools.web_reader import WebReaderTool
from src.tools.memory_search import MemorySearchTool


def init_default_tools():
    """Register default tools."""
    registry = get_registry()
    registry.register(WebSearchTool())
    registry.register(DateTimeTool())
    registry.register(CodeExecutionTool())
    registry.register(WebReaderTool())
    registry.register(MemorySearchTool())


__all__ = [
    "ToolRegistry", "get_registry", "BaseTool", "init_default_tools",
    "WebSearchTool", "DateTimeTool", "CodeExecutionTool", "WebReaderTool", "MemorySearchTool"
]
