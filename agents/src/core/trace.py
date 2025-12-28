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

# Constants
MAX_TOOL_TRACES = 100  # Prevent memory exhaustion
SENSITIVE_KEYS = {"api_key", "token", "password", "secret", "authorization", "auth", "key"}

# Context variable for current trace
_current_trace: ContextVar[Optional["TraceContext"]] = ContextVar("current_trace", default=None)


def _sanitize_input(params: Dict[str, Any]) -> Dict[str, str]:
    """Remove sensitive data from input params."""
    safe = {}
    for k, v in params.items():
        key_lower = k.lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
            safe[k] = "***REDACTED***"
        else:
            safe[k] = str(v)[:100]
    return safe


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
        safe_input = _sanitize_input(input_params)

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

        try:
            if exc_type is not None:
                self.status = "error"
                self.metadata["error"] = str(exc_val)[:200]
            elif self.status == "running":
                self.status = "success"

            # Save trace
            await self._save_trace()
        finally:
            # Always restore context, even if save fails
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
        if len(self.tool_traces) >= MAX_TOOL_TRACES:
            self.logger.warning("max_tool_traces_reached", limit=MAX_TOOL_TRACES)
            return
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


VALID_STATUSES = {"success", "error", "timeout", "running"}


async def get_trace(trace_id: str) -> Optional[ExecutionTrace]:
    """Retrieve a trace by ID."""
    import re
    # Validate trace_id format
    if not trace_id or not re.match(r'^[a-f0-9-]{8,36}$', trace_id):
        logger.warning("invalid_trace_id", trace_id=str(trace_id)[:20])
        return None

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

    # Validate inputs
    if limit < 1 or limit > 100:
        limit = 20
    if status and status not in VALID_STATUSES:
        logger.warning("invalid_status_filter", status=status)
        status = None

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
