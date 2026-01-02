"""Code execution tool (migrated from src/tools/code_exec.py)."""

from claude_agents import tool
from typing import Dict
import structlog

logger = structlog.get_logger()


@tool
async def run_python(
    code: str,
    timeout: int = 30,
) -> Dict:
    """Execute Python code safely in sandboxed environment.

    Args:
        code: Python code to execute
        timeout: Execution timeout in seconds (default: 30)

    Returns:
        Execution result with stdout, stderr, return_value, success
    """
    from src.tools.code_exec import CodeExecutionTool

    # Use existing implementation
    exec_tool = CodeExecutionTool()
    result = await exec_tool.execute({"code": code, "timeout": timeout})

    if result.success:
        return {
            "stdout": result.data,
            "stderr": "",
            "success": True,
            "return_value": None
        }
    else:
        return {
            "stdout": "",
            "stderr": result.error or "Execution failed",
            "success": False,
            "return_value": None
        }
