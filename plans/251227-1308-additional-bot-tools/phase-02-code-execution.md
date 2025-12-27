# Phase 2: Code Execution Tool

## Context
- [Plan Overview](./plan.md)
- Security-critical - must be sandboxed

## Overview
Safe Python code execution for calculations and data processing.

## Security Model
- **Timeout**: 5 seconds max
- **No imports**: Restricted builtins only
- **No file/network**: Remove dangerous functions
- **Output limit**: 2000 chars

## Implementation

**File:** `agents/src/tools/code_exec.py`

```python
from typing import Any, Dict
import io
import contextlib
from src.tools.base import BaseTool
import structlog

logger = structlog.get_logger()

# Safe builtins - math and basics only
SAFE_BUILTINS = {
    'abs': abs, 'all': all, 'any': any, 'bin': bin, 'bool': bool,
    'chr': chr, 'dict': dict, 'divmod': divmod, 'enumerate': enumerate,
    'filter': filter, 'float': float, 'format': format, 'hex': hex,
    'int': int, 'isinstance': isinstance, 'len': len, 'list': list,
    'map': map, 'max': max, 'min': min, 'oct': oct, 'ord': ord,
    'pow': pow, 'print': print, 'range': range, 'repr': repr,
    'reversed': reversed, 'round': round, 'set': set, 'slice': slice,
    'sorted': sorted, 'str': str, 'sum': sum, 'tuple': tuple, 'zip': zip,
    'True': True, 'False': False, 'None': None,
}

# Add math functions
import math
SAFE_BUILTINS.update({
    'sqrt': math.sqrt, 'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
    'log': math.log, 'log10': math.log10, 'exp': math.exp, 'pi': math.pi,
    'ceil': math.ceil, 'floor': math.floor,
})


class CodeExecutionTool(BaseTool):
    """Execute Python code safely for calculations."""

    @property
    def name(self) -> str:
        return "run_python"

    @property
    def description(self) -> str:
        return (
            "Execute Python code for calculations. Use for: math, percentages, "
            "unit conversions, data processing. No file/network access. "
            "Use print() to output results."
        )

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute. Use print() for output."
                }
            },
            "required": ["code"]
        }

    async def execute(self, params: Dict[str, Any]) -> str:
        code = params.get("code", "")
        if not code:
            return "Error: No code provided"

        # Capture stdout
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                exec(code, {"__builtins__": SAFE_BUILTINS}, {})
            result = output.getvalue().strip()
            if not result:
                result = "Code executed successfully (no output)"
            if len(result) > 2000:
                result = result[:1997] + "..."
            logger.info("code_exec_success", code_len=len(code))
            return result
        except Exception as e:
            logger.error("code_exec_error", error=str(e))
            return f"Execution error: {str(e)[:100]}"
```

## Todo
- [ ] Create `code_exec.py`
- [ ] Register in `__init__.py`
- [ ] Test with "Calculate 15% of 847"

## Success Criteria
1. Executes basic Python math
2. Blocks dangerous operations
3. Returns output via print()
