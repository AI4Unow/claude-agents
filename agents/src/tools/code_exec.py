"""Code execution tool - Safe Python execution for calculations."""
from typing import Any, Dict
import io
import contextlib
from src.tools.base import BaseTool, ToolResult

from src.utils.logging import get_logger

logger = get_logger()

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

# Add numpy with safe whitelist only
import numpy
import types

def _create_safe_numpy():
    """Create numpy module with only safe math functions.

    Blocks file I/O functions like np.save(), np.load() that could be used
    to escape the sandbox and access the filesystem.
    """
    safe_np = types.ModuleType('numpy')

    # Set module metadata to prevent import issues
    safe_np.__name__ = 'numpy'
    safe_np.__package__ = 'numpy'

    # Safe math functions only - NO file I/O (np.save, np.load, etc.)
    safe_attrs = [
        'abs', 'add', 'subtract', 'multiply', 'divide',
        'sqrt', 'power', 'exp', 'log', 'log10', 'log2',
        'sin', 'cos', 'tan', 'arcsin', 'arccos', 'arctan',
        'sinh', 'cosh', 'tanh', 'floor', 'ceil', 'round',
        'mean', 'median', 'std', 'var', 'sum', 'prod',
        'min', 'max', 'argmin', 'argmax', 'sort',
        'array', 'zeros', 'ones', 'arange', 'linspace',
        'pi', 'e', 'inf', 'nan', 'dtype', 'float64', 'int64',
    ]

    for attr in safe_attrs:
        if hasattr(numpy, attr):
            setattr(safe_np, attr, getattr(numpy, attr))

    return safe_np

SAFE_BUILTINS['np'] = _create_safe_numpy()
SAFE_BUILTINS['numpy'] = _create_safe_numpy()
SAFE_BUILTINS['array'] = numpy.array
SAFE_BUILTINS['linspace'] = numpy.linspace
SAFE_BUILTINS['arange'] = numpy.arange
SAFE_BUILTINS['zeros'] = numpy.zeros
SAFE_BUILTINS['ones'] = numpy.ones
SAFE_BUILTINS['mean'] = numpy.mean
SAFE_BUILTINS['std'] = numpy.std
SAFE_BUILTINS['median'] = numpy.median


class CodeExecutionTool(BaseTool):
    """Execute Python code safely for calculations."""

    @property
    def name(self) -> str:
        return "run_python"

    @property
    def description(self) -> str:
        return (
            "Execute Python code for calculations. Use for: math, percentages, "
            "unit conversions, data processing, numpy arrays. No file/network access. "
            "Use print() to output results. numpy available as 'np'."
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

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        code = params.get("code", "")
        if not code:
            return ToolResult.fail("No code provided")

        # Capture stdout
        output = io.StringIO()
        try:
            # Create restricted globals with safe builtins
            # Block __import__ to prevent importing dangerous modules
            safe_builtins_no_import = {
                **SAFE_BUILTINS,
                "__import__": lambda *args, **kwargs: (_ for _ in ()).throw(
                    ImportError("Import not allowed in sandbox")
                ),
            }
            restricted_globals = {
                "__builtins__": safe_builtins_no_import,
                "__name__": "__main__",
                "__doc__": None,
            }

            with contextlib.redirect_stdout(output):
                exec(code, restricted_globals, {})
            result = output.getvalue().strip()
            if not result:
                result = "Code executed successfully (no output)"
            if len(result) > 2000:
                result = result[:1997] + "..."
            logger.info("code_exec_success", code_len=len(code))
            return ToolResult.ok(result)
        except Exception as e:
            logger.error("code_exec_error", error=str(e))
            return ToolResult.fail(f"Execution error: {str(e)[:100]}")
