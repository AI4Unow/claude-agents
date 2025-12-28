# Phase 01: Execution Tracing Core

## Objective

Create structured execution tracing to capture full execution path with timing, inputs, outputs, and errors.

## New File: `src/core/trace.py`

```python
"""Execution tracing for debugging and analysis.

AgentEx Pattern: Capture full execution path with tool calls, timing, errors.
"""
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from contextvars import ContextVar

from src.utils.logging import get_logger

logger = get_logger()

# Context variable for current trace
_current_trace: ContextVar[Optional["TraceContext"]] = ContextVar("current_trace", default=None)


@dataclass
class ToolTrace:
    """Single tool execution trace."""
    name: str
    input: Dict[str, Any]
    output: str  # Truncated to 500 chars
    duration_ms: int
    is_error: bool
    timestamp: str  # ISO format

    @classmethod
    def create(
        cls,
        name: str,
        input_params: Dict[str, Any],
        output: str,
        duration_ms: int,
        is_error: bool = False
    ) -> "ToolTrace":
        # Truncate output to prevent bloat
        truncated_output = output[:500] + "..." if len(output) > 500 else output
        # Sanitize input (remove sensitive data)
        safe_input = {k: str(v)[:100] for k, v in input_params.items()}

        return cls(
            name=name,
            input=safe_input,
            output=truncated_output,
            duration_ms=duration_ms,
            is_error=is_error,
            timestamp=datetime.now(timezone.utc).isoformat()
        )


@dataclass
class ExecutionTrace:
    """Full execution trace for an agentic run."""
    trace_id: str
    user_id: Optional[int]
    skill: Optional[str]
    started_at: str  # ISO format
    ended_at: Optional[str]
    iterations: int
    tool_traces: List[ToolTrace]
    final_output: str  # Truncated to 1000 chars
    status: str  # success, error, timeout
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to Firebase-compatible dict."""
        return {
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "skill": self.skill,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "iterations": self.iterations,
            "tool_traces": [asdict(t) for t in self.tool_traces],
            "final_output": self.final_output[:1000],
            "status": self.status,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ExecutionTrace":
        """Create from Firebase dict."""
        tool_traces = [
            ToolTrace(**t) for t in data.get("tool_traces", [])
        ]
        return cls(
            trace_id=data["trace_id"],
            user_id=data.get("user_id"),
            skill=data.get("skill"),
            started_at=data["started_at"],
            ended_at=data.get("ended_at"),
            iterations=data.get("iterations", 0),
            tool_traces=tool_traces,
            final_output=data.get("final_output", ""),
            status=data.get("status", "unknown"),
            metadata=data.get("metadata", {}),
        )


class TraceContext:
    """Context manager for execution tracing.

    Usage:
        async with TraceContext(user_id=123, skill="planning") as ctx:
            # Do work
            ctx.add_tool_trace(...)
            ctx.set_output("result")
    """

    def __init__(
        self,
        user_id: Optional[int] = None,
        skill: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        self.trace_id = str(uuid.uuid4())[:8]
        self.user_id = user_id
        self.skill = skill
        self.started_at = datetime.now(timezone.utc)
        self.ended_at: Optional[datetime] = None
        self.iterations = 0
        self.tool_traces: List[ToolTrace] = []
        self.final_output = ""
        self.status = "running"
        self.metadata = metadata or {}
        self._token = None
        self.logger = logger.bind(trace_id=self.trace_id)

    async def __aenter__(self) -> "TraceContext":
        self._token = _current_trace.set(self)
        self.logger.info("trace_started", user_id=self.user_id, skill=self.skill)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.ended_at = datetime.now(timezone.utc)

        if exc_type is not None:
            self.status = "error"
            self.metadata["error"] = str(exc_val)[:200]
        elif self.status == "running":
            self.status = "success"

        # Save trace
        await self._save_trace()

        # Restore context
        if self._token:
            _current_trace.reset(self._token)

        self.logger.info(
            "trace_ended",
            status=self.status,
            iterations=self.iterations,
            tool_count=len(self.tool_traces),
            duration_ms=self._duration_ms()
        )

    def add_tool_trace(self, tool_trace: ToolTrace):
        """Add a tool execution trace."""
        self.tool_traces.append(tool_trace)

    def increment_iteration(self):
        """Increment iteration count."""
        self.iterations += 1

    def set_output(self, output: str):
        """Set final output."""
        self.final_output = output

    def set_status(self, status: str):
        """Set trace status."""
        self.status = status

    def _duration_ms(self) -> int:
        """Calculate total duration in ms."""
        if self.ended_at:
            delta = self.ended_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return 0

    def to_trace(self) -> ExecutionTrace:
        """Convert to ExecutionTrace."""
        return ExecutionTrace(
            trace_id=self.trace_id,
            user_id=self.user_id,
            skill=self.skill,
            started_at=self.started_at.isoformat(),
            ended_at=self.ended_at.isoformat() if self.ended_at else None,
            iterations=self.iterations,
            tool_traces=self.tool_traces,
            final_output=self.final_output,
            status=self.status,
            metadata=self.metadata,
        )

    async def _save_trace(self):
        """Save trace to Firebase via StateManager."""
        try:
            from src.core.state import get_state_manager
            state = get_state_manager()
            trace = self.to_trace()

            # Only save errors or 10% of success (sampling)
            should_save = (
                self.status == "error" or
                self.status == "timeout" or
                hash(self.trace_id) % 10 == 0  # 10% sampling
            )

            if should_save:
                await state.set(
                    "execution_traces",
                    self.trace_id,
                    trace.to_dict(),
                    ttl_seconds=86400 * 7,  # 7 days
                    persist=True
                )
                self.logger.debug("trace_saved", trace_id=self.trace_id)
            else:
                self.logger.debug("trace_sampled_out", trace_id=self.trace_id)

        except Exception as e:
            self.logger.error("trace_save_failed", error=str(e))


def get_current_trace() -> Optional[TraceContext]:
    """Get current trace context."""
    return _current_trace.get()


async def get_trace(trace_id: str) -> Optional[ExecutionTrace]:
    """Retrieve a trace by ID."""
    from src.core.state import get_state_manager
    state = get_state_manager()
    data = await state.get("execution_traces", trace_id)
    if data:
        return ExecutionTrace.from_dict(data)
    return None


async def list_traces(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 20
) -> List[ExecutionTrace]:
    """List traces with optional filters.

    Note: This requires a Firebase query, not cached.
    """
    from src.core.state import get_state_manager
    import asyncio

    state = get_state_manager()
    db = state._get_db()

    try:
        query = db.collection("execution_traces")

        if user_id:
            query = query.where("user_id", "==", user_id)
        if status:
            query = query.where("status", "==", status)

        query = query.order_by("started_at", direction="DESCENDING").limit(limit)

        docs = await asyncio.to_thread(lambda: query.get())

        return [ExecutionTrace.from_dict(doc.to_dict()) for doc in docs]

    except Exception as e:
        logger.error("list_traces_failed", error=str(e))
        return []
```

## Update `src/core/__init__.py`

Add exports:

```python
from src.core.state import get_state_manager, StateManager
from src.core.trace import (
    TraceContext,
    ExecutionTrace,
    ToolTrace,
    get_current_trace,
    get_trace,
    list_traces,
)

__all__ = [
    "get_state_manager",
    "StateManager",
    "TraceContext",
    "ExecutionTrace",
    "ToolTrace",
    "get_current_trace",
    "get_trace",
    "list_traces",
]
```

## Verification

```python
# Test trace creation
async def test_trace():
    async with TraceContext(user_id=123, skill="test") as ctx:
        # Simulate tool call
        tool_trace = ToolTrace.create(
            name="web_search",
            input_params={"query": "test"},
            output="Search results...",
            duration_ms=150,
            is_error=False
        )
        ctx.add_tool_trace(tool_trace)
        ctx.increment_iteration()
        ctx.set_output("Final result")

    # Verify trace was saved
    trace = await get_trace(ctx.trace_id)
    assert trace is not None
    assert trace.status == "success"
    assert len(trace.tool_traces) == 1
```

## Acceptance Criteria

- [ ] TraceContext captures start/end timing
- [ ] ToolTrace captures name, input, output, duration, errors
- [ ] Traces saved to Firebase with 7-day TTL
- [ ] 10% sampling for success, 100% for errors
- [ ] Output/input truncated to prevent bloat
- [ ] get_current_trace() returns active context
