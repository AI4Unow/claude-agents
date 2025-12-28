"""Base tool class for Anthropic tool_use integration."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    """Structured tool execution result.

    Replaces string-based error detection with explicit success/failure.
    """
    success: bool
    data: str
    error: Optional[str] = None

    def to_str(self) -> str:
        """Convert to string for LLM consumption."""
        if self.success:
            return self.data
        return f"Error: {self.error}" if self.error else "Unknown error"

    @classmethod
    def ok(cls, data: str) -> "ToolResult":
        """Create successful result."""
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str) -> "ToolResult":
        """Create failed result."""
        return cls(success=False, data="", error=error)


class BaseTool(ABC):
    """Abstract base for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for Anthropic API."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description - helps Claude decide when to use it."""
        ...

    @property
    @abstractmethod
    def input_schema(self) -> dict:
        """JSON Schema for tool inputs."""
        ...

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute tool with given parameters. Returns ToolResult."""
        ...

    def to_anthropic_format(self) -> dict:
        """Convert to Anthropic tool definition format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema
        }
