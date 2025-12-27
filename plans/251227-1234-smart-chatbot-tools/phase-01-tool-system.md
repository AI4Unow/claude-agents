# Phase 1: Tool System Architecture

## Context

- [Plan Overview](./plan.md)
- [Anthropic Tool Use Research](./research/researcher-01-anthropic-tool-use.md)
- Current LLM service: `agents/src/services/llm.py`

## Overview

Create extensible tool registry and update LLM service to support Anthropic's tool_use feature.

## Requirements

1. Tool definitions follow Anthropic schema (name, description, input_schema)
2. Registry pattern for easy tool addition
3. Type-safe tool execution with validation
4. Error handling returns structured messages

## Architecture

```
src/tools/
├── __init__.py          # Export registry
├── registry.py          # Tool registration/lookup
├── base.py              # BaseTool abstract class
└── web_search.py        # (Phase 2)
```

### Tool Definition Interface

```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], Awaitable[str]]
```

### Registry API

```python
registry = ToolRegistry()
registry.register(tool_def)
registry.get_definitions()  # → List[dict] for Anthropic API
registry.execute(name, input)  # → str result
```

## Implementation Steps

### 1.1 Create BaseTool abstract class

**File:** `agents/src/tools/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class BaseTool(ABC):
    """Abstract base for all tools."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def input_schema(self) -> dict: ...

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> str: ...

    def to_anthropic_format(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema
        }
```

### 1.2 Create ToolRegistry

**File:** `agents/src/tools/registry.py`

```python
from typing import Dict, List, Optional
from src.tools.base import BaseTool
import structlog

logger = structlog.get_logger()

class ToolRegistry:
    """Registry for managing tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool
        logger.info("tool_registered", name=tool.name)

    def get_definitions(self) -> List[dict]:
        return [t.to_anthropic_format() for t in self._tools.values()]

    async def execute(self, name: str, params: dict) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Unknown tool '{name}'"
        try:
            return await tool.execute(params)
        except Exception as e:
            logger.error("tool_execution_error", tool=name, error=str(e))
            return f"Error executing {name}: {e}"

# Global registry
_registry: Optional[ToolRegistry] = None

def get_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
```

### 1.3 Update LLM Service

**File:** `agents/src/services/llm.py` - Add tools parameter

```python
def chat(
    self,
    messages: List[Dict[str, str]],
    system: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    tools: Optional[List[dict]] = None,  # NEW
) -> Message:  # Return full Message for tool inspection
    kwargs = {
        "model": self.model,
        "max_tokens": max_tokens,
        "system": system or "You are a helpful assistant.",
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools

    return self.client.messages.create(**kwargs)
```

### 1.4 Create package exports

**File:** `agents/src/tools/__init__.py`

```python
from src.tools.registry import ToolRegistry, get_registry
from src.tools.base import BaseTool

__all__ = ["ToolRegistry", "get_registry", "BaseTool"]
```

## Todo

- [ ] Create `src/tools/` directory structure
- [ ] Implement `base.py` with BaseTool
- [ ] Implement `registry.py` with ToolRegistry
- [ ] Update `llm.py` to accept tools param
- [ ] Add tools to `requirements.txt` if needed
- [ ] Unit test registry with mock tool

## Success Criteria

1. `get_registry().get_definitions()` returns valid Anthropic tool format
2. `await registry.execute("test_tool", {})` executes handler
3. LLM service accepts tools parameter without breaking existing calls
4. Error handling captures and formats tool execution failures
