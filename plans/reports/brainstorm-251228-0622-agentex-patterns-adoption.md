# Brainstorm: Scale AgentEx Patterns Adoption

**Date:** 2025-12-28
**Goal:** Production Reliability
**Scope:** Moderate complexity

## Problem Statement

Current Modal.com agents lack:
1. **Execution tracing** - Can't inspect full execution path, tool calls, latency
2. **Process-oriented evaluation** - EvaluatorOptimizer only judges final output, not execution quality
3. **Production resilience** - No circuit breakers, retry logic, or structured error handling
4. **Agent maturity model** - No structured progression from L1 (task-specific) to L5 (autonomous)

## Scale AgentEx Key Patterns

| Pattern | Description | Applicability |
|---------|-------------|---------------|
| Agent-as-a-Judge | Evaluate execution path, not just output | High - enhances self-improvement |
| Execution Tracing | Capture tool calls, latency, decisions | High - critical for debugging |
| Multi-Level Maturity | L1→L5 agent evolution framework | Medium - nice structure |
| Agent Server | Kubernetes-native orchestration | Low - Modal handles this |

## Current Architecture Gaps

### 1. Execution Tracing (Missing)
```
CURRENT: agentic.py logs tool calls but doesn't persist traces
NEEDED: Structured trace capture with timing, inputs, outputs, errors
```

### 2. Evaluation Quality (Partial)
```
CURRENT: evaluator.py uses LLM-as-Judge on final output only
NEEDED: Agent-as-Judge that can:
  - Inspect intermediate tool calls
  - Verify code execution results
  - Analyze decision quality
```

### 3. Production Resilience (Missing)
```
CURRENT: Basic error logging, no recovery
NEEDED:
  - Circuit breakers for external services
  - Retry with exponential backoff
  - Graceful degradation
  - Health metrics
```

## Recommended Solution

### Phase 1: Execution Tracing (src/core/trace.py)

```python
@dataclass
class ToolTrace:
    name: str
    input: Dict
    output: str
    duration_ms: int
    is_error: bool
    timestamp: datetime

@dataclass
class ExecutionTrace:
    trace_id: str
    user_id: Optional[int]
    skill: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    iterations: int
    tool_traces: List[ToolTrace]
    final_output: str
    status: str  # success, error, timeout
    metadata: Dict

class TraceStore:
    """Store traces in Firebase with L1 cache."""

    COLLECTION = "execution_traces"
    TTL_SECONDS = 86400 * 7  # 7 days

    async def save(self, trace: ExecutionTrace)
    async def get(self, trace_id: str) -> Optional[ExecutionTrace]
    async def list_by_user(self, user_id: int, limit: int = 20)
    async def list_by_status(self, status: str, limit: int = 100)
```

### Phase 2: Agent-as-a-Judge (src/core/agent_judge.py)

```python
class AgentJudge:
    """Evaluate execution quality, not just output."""

    CRITERIA = {
        "tool_efficiency": "Were tools used appropriately and efficiently?",
        "decision_quality": "Were reasoning steps logical and grounded?",
        "error_handling": "Were errors detected and handled appropriately?",
        "task_completion": "Was the task fully completed as requested?",
    }

    async def evaluate_trace(self, trace: ExecutionTrace) -> TraceEvaluation:
        """Analyze full execution path."""
        # 1. Check tool call patterns
        # 2. Verify outputs (can re-execute code to check)
        # 3. Analyze iteration count efficiency
        # 4. Score each criterion

    async def generate_improvement(self, trace: ExecutionTrace, eval: TraceEvaluation) -> str:
        """Generate info.md improvement suggestions based on trace analysis."""
```

### Phase 3: Circuit Breakers (src/core/resilience.py)

```python
@dataclass
class CircuitState:
    name: str
    failures: int
    last_failure: Optional[datetime]
    state: str  # closed, open, half_open
    cooldown_seconds: int

class CircuitBreaker:
    """Prevent cascading failures to external services."""

    def __init__(self, name: str, threshold: int = 5, cooldown: int = 60):
        self.threshold = threshold
        self.cooldown = cooldown

    async def call(self, func: Callable, *args, **kwargs):
        if self._is_open():
            raise CircuitOpenError(f"{self.name} circuit is open")
        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise

# Usage in tools:
exa_circuit = CircuitBreaker("exa_api", threshold=3, cooldown=30)
tavily_circuit = CircuitBreaker("tavily_api", threshold=3, cooldown=30)
```

### Phase 4: Agent Maturity Config (src/core/maturity.py)

```python
class AgentLevel(Enum):
    L1_TASK = 1      # Single task execution
    L2_WORKFLOW = 2  # Multi-step workflows
    L3_ADAPTIVE = 3  # Self-adjusts based on feedback
    L4_LEARNING = 4  # Persists improvements to info.md
    L5_AUTONOMOUS = 5  # Full self-improvement loop

@dataclass
class MaturityConfig:
    level: AgentLevel
    max_iterations: int
    tool_access: List[str]
    can_self_improve: bool
    requires_approval: bool

MATURITY_CONFIGS = {
    AgentLevel.L1_TASK: MaturityConfig(
        level=AgentLevel.L1_TASK,
        max_iterations=1,
        tool_access=[],
        can_self_improve=False,
        requires_approval=False,
    ),
    AgentLevel.L4_LEARNING: MaturityConfig(
        level=AgentLevel.L4_LEARNING,
        max_iterations=5,
        tool_access=["web_search", "run_python", "read_webpage"],
        can_self_improve=True,
        requires_approval=False,
    ),
}
```

## Integration Points

| Component | Changes |
|-----------|---------|
| `agentic.py` | Add trace capture, return ExecutionTrace |
| `evaluator.py` | Use AgentJudge for trace-based evaluation |
| `web_search.py` | Wrap in circuit breaker |
| `state.py` | Add TraceStore methods |
| `main.py` | Add /traces endpoint for debugging |

## Implementation Priority

| Phase | Effort | Impact | Priority |
|-------|--------|--------|----------|
| Execution Tracing | 4h | High - foundation for all else | P0 |
| Circuit Breakers | 2h | High - immediate reliability | P0 |
| Agent-as-a-Judge | 4h | Medium - enhances self-improvement | P1 |
| Maturity Config | 2h | Low - organizational structure | P2 |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Trace storage costs | 7-day TTL, limit to error traces only |
| Agent-as-Judge LLM costs | Only run on failures or sampled success |
| Complexity creep | Start with P0, validate before P1 |

## Success Metrics

| Metric | Target |
|--------|--------|
| Tool call visibility | 100% traced |
| Circuit breaker coverage | All external APIs |
| Mean time to debug | Reduce 50% |
| Self-improvement accuracy | Increase 25% |

## Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scope | Moderate | Balances YAGNI with real needs |
| Trace storage | Firebase | Already integrated, fits L1/L2 pattern |
| Evaluation approach | Agent-as-a-Judge | Process-oriented > output-only |
| Resilience pattern | Circuit breakers | Simple, effective, battle-tested |

## Next Steps

1. Create implementation plan with phase files
2. Implement P0 (Tracing + Circuit Breakers) first
3. Validate with production usage
4. Add P1 (Agent-as-a-Judge) after P0 stable

## Unresolved Questions

1. **Trace sampling** - Should we trace 100% or sample to reduce costs?
2. **Judge frequency** - Run Agent-as-a-Judge on every execution or only failures?
3. **Maturity assignment** - How to assign L1-L5 levels to existing skills?
