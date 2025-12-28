"""Core framework modules."""
from src.core.state import get_state_manager, StateManager
from src.core.trace import (
    TraceContext,
    ExecutionTrace,
    ToolTrace,
    get_current_trace,
    get_trace,
    list_traces,
)
from src.core.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    exa_circuit,
    tavily_circuit,
    firebase_circuit,
    qdrant_circuit,
    claude_circuit,
    telegram_circuit,
    get_circuit_stats,
    reset_all_circuits,
    with_retry,
)
from src.core.improvement import (
    ImprovementProposal,
    ImprovementService,
    get_improvement_service,
)

__all__ = [
    # State
    "get_state_manager",
    "StateManager",
    # Tracing
    "TraceContext",
    "ExecutionTrace",
    "ToolTrace",
    "get_current_trace",
    "get_trace",
    "list_traces",
    # Resilience
    "CircuitBreaker",
    "CircuitOpenError",
    "CircuitState",
    "exa_circuit",
    "tavily_circuit",
    "firebase_circuit",
    "qdrant_circuit",
    "claude_circuit",
    "telegram_circuit",
    "get_circuit_stats",
    "reset_all_circuits",
    "with_retry",
    # Improvement
    "ImprovementProposal",
    "ImprovementService",
    "get_improvement_service",
]
