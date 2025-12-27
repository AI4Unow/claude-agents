"""Base tool class for Anthropic tool_use integration."""
from abc import ABC, abstractmethod
from typing import Any, Dict


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
    async def execute(self, params: Dict[str, Any]) -> str:
        """Execute tool with given parameters. Returns result string."""
        ...

    def to_anthropic_format(self) -> dict:
        """Convert to Anthropic tool definition format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema
        }
