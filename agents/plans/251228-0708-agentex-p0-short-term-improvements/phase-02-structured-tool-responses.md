# Phase 02: Structured Tool Responses

## Context

- **Parent Plan:** [plan.md](./plan.md)
- **Issue:** Code review #8 - Error detection uses brittle string matching
- **Related:** `src/services/agentic.py:119-124`, `src/tools/*.py`

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-28 |
| Priority | MEDIUM |
| Effort | 2h |
| Implementation | pending |
| Review | pending |

## Problem

Current error detection relies on string prefix matching:

```python
is_error = (
    result.startswith("Search failed") or
    result.startswith("Error") or
    result.startswith("Tool error")
)
```

This is brittle - valid tool output like "Error analysis: no issues found" would be incorrectly marked as error.

## Solution

Create `ToolResult` dataclass and update tools to return it:

```python
@dataclass
class ToolResult:
    success: bool
    data: str
    error: Optional[str] = None
```

## Related Files

| File | Lines | Action |
|------|-------|--------|
| `src/tools/base.py` | - | Add ToolResult dataclass |
| `src/tools/web_search.py` | 87-118 | Return ToolResult |
| `src/tools/datetime_tool.py` | - | Return ToolResult |
| `src/tools/code_exec.py` | - | Return ToolResult |
| `src/tools/web_reader.py` | - | Return ToolResult |
| `src/tools/memory_search.py` | - | Return ToolResult |
| `src/tools/registry.py` | - | Handle ToolResult in execute() |
| `src/services/agentic.py` | 119-124 | Check result.success |

## Implementation Steps

1. Add `ToolResult` dataclass to `src/tools/base.py`
2. Update `BaseTool.execute()` signature to return `ToolResult`
3. Add compatibility helper `ToolResult.to_str()` for backwards compatibility
4. Update each tool to return `ToolResult` instead of string
5. Update `registry.execute()` to handle ToolResult
6. Update `agentic.py` to check `result.success`

## Code Changes

### src/tools/base.py

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ToolResult:
    """Structured tool execution result."""
    success: bool
    data: str
    error: Optional[str] = None

    def to_str(self) -> str:
        """Convert to string for API response."""
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
```

### src/tools/web_search.py (example)

```python
async def execute(self, params: Dict[str, Any]) -> ToolResult:
    query = params.get("query", "")

    if not query:
        return ToolResult.fail("No query provided")

    # ... search logic ...

    if not result.startswith("Search failed"):
        return ToolResult.ok(result)
    else:
        return ToolResult.fail(result)
```

### src/services/agentic.py

```python
# Replace lines 119-124
result = await registry.execute(block.name, block.input)

# Structured error detection
is_error = not result.success

# Add to trace with result data
tool_trace = ToolTrace.create(
    name=block.name,
    input_params=block.input if isinstance(block.input, dict) else {"input": str(block.input)},
    output=result.to_str(),  # Use string representation
    duration_ms=duration_ms,
    is_error=is_error,
)

tool_results.append({
    "type": "tool_result",
    "tool_use_id": block.id,
    "content": result.to_str(),  # API needs string
    "is_error": is_error,
})
```

## Migration Strategy

To avoid breaking changes:

1. Add `ToolResult` without changing existing tools
2. Update `registry.execute()` to handle both str and ToolResult:
   ```python
   async def execute(self, name: str, params: dict) -> ToolResult:
       result = await tool.execute(params)
       # Backwards compatibility
       if isinstance(result, str):
           if result.startswith(("Error", "Search failed", "Tool error")):
               return ToolResult.fail(result)
           return ToolResult.ok(result)
       return result
   ```
3. Gradually update each tool to return ToolResult
4. Remove compatibility layer once all tools updated

## Todo List

- [ ] Add ToolResult dataclass to base.py
- [ ] Update registry.execute() with compatibility layer
- [ ] Update web_search.py
- [ ] Update datetime_tool.py
- [ ] Update code_exec.py
- [ ] Update web_reader.py
- [ ] Update memory_search.py
- [ ] Update agentic.py to use result.success
- [ ] Remove compatibility layer (after all tools updated)

## Success Criteria

- [ ] All tools return ToolResult instead of raw strings
- [ ] Error detection uses `result.success`, not string prefix
- [ ] Backwards compatibility maintained during migration
- [ ] Test: tool returning "Error analysis: ok" not marked as error

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing tool integrations | HIGH | Compatibility layer in registry |
| Increased complexity | LOW | ToolResult is simple dataclass |
| Performance overhead | NEGLIGIBLE | Dataclass instantiation is O(1) |

## Next Steps

After this phase, proceed to [Phase 03](./phase-03-cache-eviction.md).
