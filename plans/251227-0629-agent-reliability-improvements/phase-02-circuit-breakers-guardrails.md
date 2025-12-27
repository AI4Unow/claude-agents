# Phase 2: Circuit Breakers & Guardrails

## Context

- Plan: [plan.md](./plan.md)
- Previous: [Phase 1](./phase-01-core-reliability-infrastructure.md)
- Research: [reliability-patterns.md](./research/researcher-01-reliability-patterns.md)

## Overview

**Priority:** P1 - Critical Safety
**Status:** Pending
**Effort:** 2h

Implement circuit breakers to prevent runaway costs and infinite loops, plus output guardrails for LLM validation.

## Key Insights

1. Token/budget caps prevent expensive runaway agents
2. Max iteration limits stop infinite loops
3. Pydantic validates LLM output schemas
4. HITL escalation when circuit trips

## Requirements

### Functional
- Token cap per execution ($10 default) ✓ USER VALIDATED
- Max iterations per task (10 default) ✓ USER VALIDATED
- Output schema validation
- Escalation to Firebase alerts ✓ USER VALIDATED

### Non-Functional
- Circuit check overhead <10ms
- No false positives blocking valid work

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CIRCUIT BREAKER FLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Before LLM Call:                                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ check_circuit_breaker()                                   │   │
│  │   ├── tokens_used > TOKEN_CAP? ──► TRIP                  │   │
│  │   ├── iterations > MAX_ITERATIONS? ──► TRIP              │   │
│  │   ├── cost_estimate > BUDGET_CAP? ──► TRIP               │   │
│  │   └── confidence_drift? ──► TRIP                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│         ┌─────────────────┼─────────────────┐                   │
│         ▼                 ▼                 ▼                   │
│      CLOSED            TRIPPED           HALF-OPEN              │
│    (continue)    (stop + escalate)    (test one call)           │
│                                                                  │
│  After LLM Call:                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ validate_output(response, schema)                         │   │
│  │   ├── Valid ──► Continue                                 │   │
│  │   └── Invalid ──► ErrorType.LOGIC ──► Self-correct       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Related Code Files

| Path | Action | Description |
|------|--------|-------------|
| `agents/src/utils/circuit_breaker.py` | Create | Circuit breaker implementation |
| `agents/src/utils/guardrails.py` | Create | Output validation |
| `agents/src/agents/base.py` | Modify | Integrate circuit breaker |
| `agents/src/services/firebase.py` | Modify | Add alert functions |

## Implementation Steps

### 1. Create Circuit Breaker (`src/utils/circuit_breaker.py`)

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import structlog

logger = structlog.get_logger()

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Tripped, blocking calls
    HALF_OPEN = "half_open"  # Testing if recovered

@dataclass
class CircuitBreaker:
    """Agent circuit breaker for cost/loop protection."""

    # Limits (USER VALIDATED)
    max_tokens: int = 200_000  # ~$10 worth
    max_iterations: int = 10
    max_cost_usd: float = 10.0

    # State
    tokens_used: int = 0
    iterations: int = 0
    cost_usd: float = 0.0
    state: CircuitState = CircuitState.CLOSED
    trip_reason: str = ""

    def check(self) -> bool:
        """Check if circuit allows execution. Returns False if tripped."""
        if self.state == CircuitState.OPEN:
            return False

        if self.tokens_used > self.max_tokens:
            self._trip(f"Token limit exceeded: {self.tokens_used}")
            return False

        if self.iterations > self.max_iterations:
            self._trip(f"Iteration limit exceeded: {self.iterations}")
            return False

        if self.cost_usd > self.max_cost_usd:
            self._trip(f"Cost limit exceeded: ${self.cost_usd:.2f}")
            return False

        return True

    def record_usage(self, tokens: int, cost: float):
        """Record LLM usage for tracking."""
        self.tokens_used += tokens
        self.cost_usd += cost
        self.iterations += 1

    def _trip(self, reason: str):
        """Trip the circuit breaker."""
        self.state = CircuitState.OPEN
        self.trip_reason = reason
        logger.error("circuit_breaker_tripped", reason=reason)

    def reset(self):
        """Reset for new task."""
        self.tokens_used = 0
        self.iterations = 0
        self.cost_usd = 0.0
        self.state = CircuitState.CLOSED
        self.trip_reason = ""

class CircuitBreakerTripped(Exception):
    """Raised when circuit breaker trips."""
    def __init__(self, reason: str):
        super().__init__(f"Circuit breaker tripped: {reason}")
        self.reason = reason
```

### 2. Create Output Guardrails (`src/utils/guardrails.py`)

```python
from pydantic import BaseModel, ValidationError
from typing import Type, TypeVar, Optional
import json
import structlog

logger = structlog.get_logger()

T = TypeVar('T', bound=BaseModel)

def validate_output(
    response: str,
    schema: Type[T],
    strict: bool = False
) -> Optional[T]:
    """Validate LLM output against Pydantic schema."""
    try:
        # Try to parse as JSON first
        if response.strip().startswith('{'):
            data = json.loads(response)
            return schema.model_validate(data)

        # Try to extract JSON from markdown code block
        if '```json' in response:
            json_str = response.split('```json')[1].split('```')[0]
            data = json.loads(json_str)
            return schema.model_validate(data)

        if strict:
            raise ValueError("Response is not valid JSON")
        return None

    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning("output_validation_failed", error=str(e))
        if strict:
            raise
        return None

# Common output schemas
class TaskResult(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

class AgentDecision(BaseModel):
    action: str
    reasoning: str
    confidence: float  # 0.0 - 1.0
```

### 3. Integrate into BaseAgent

```python
from src.utils.circuit_breaker import CircuitBreaker, CircuitBreakerTripped
from src.utils.guardrails import validate_output

class BaseAgent:
    def __init__(self, agent_id: str):
        ...
        self.circuit = CircuitBreaker()

    async def execute_with_llm(self, user_message: str, ...) -> str:
        # Check circuit before call
        if not self.circuit.check():
            await self._escalate_to_human(self.circuit.trip_reason)
            raise CircuitBreakerTripped(self.circuit.trip_reason)

        # Make LLM call
        response = await self.llm.complete(...)

        # Record usage
        tokens = response.usage.total_tokens if hasattr(response, 'usage') else 1000
        cost = tokens * 0.00003  # Estimate
        self.circuit.record_usage(tokens, cost)

        return response

    async def _escalate_to_human(self, reason: str):
        """Create HITL alert in Firebase."""
        await self.log_activity(
            action="circuit_breaker_alert",
            details={"reason": reason, "agent": self.agent_id},
            level="error"
        )
```

### 4. Add HITL Alert to Firebase

```python
# In src/services/firebase.py

async def create_alert(
    agent_id: str,
    alert_type: str,
    message: str,
    severity: str = "error"
):
    """Create human-in-the-loop alert."""
    db.collection("alerts").add({
        "agent_id": agent_id,
        "type": alert_type,
        "message": message,
        "severity": severity,
        "status": "pending",
        "created_at": firestore.SERVER_TIMESTAMP,
    })
```

## Todo List

- [ ] Create `src/utils/circuit_breaker.py`
- [ ] Create `src/utils/guardrails.py`
- [ ] Integrate circuit breaker into BaseAgent
- [ ] Add HITL alert function to Firebase
- [ ] Write tests for circuit breaker
- [ ] Write tests for output validation

## Success Criteria

- [ ] Circuit trips at token limit
- [ ] Circuit trips at iteration limit
- [ ] Invalid outputs detected and logged
- [ ] HITL alerts created on trip

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| False positives | Blocked valid work | Tune limits carefully |
| Limits too high | Runaway costs | Start conservative |

## Security Considerations

- Don't expose limits in error messages
- Rate limit alert creation

## Next Steps

→ Phase 3: Health Monitoring & Observability
