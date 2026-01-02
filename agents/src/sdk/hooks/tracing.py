"""Tracing integration as PostToolUse hook."""

from claude_agents import Hook, PostToolUseResult
from typing import Dict, Any
import time
import structlog

from src.core.trace import TraceContext

logger = structlog.get_logger()


class TracingHook(Hook):
    """Log tool calls to TraceContext."""

    def __init__(self, trace_context: TraceContext):
        self.trace = trace_context
        self._start_times: Dict[str, float] = {}

    async def pre_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
    ):
        self._start_times[tool_name] = time.time()

    async def post_tool_use(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
    ) -> PostToolUseResult:
        duration = time.time() - self._start_times.pop(tool_name, time.time())

        self.trace.add_tool_call(
            name=tool_name,
            input_summary=str(tool_input)[:200],
            duration_ms=int(duration * 1000),
            success=not isinstance(tool_output, Exception),
        )

        return PostToolUseResult()
