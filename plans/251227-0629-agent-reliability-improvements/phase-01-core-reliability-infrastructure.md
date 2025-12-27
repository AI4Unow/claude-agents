# Phase 1: Core Reliability Infrastructure

## Context

- Plan: [plan.md](./plan.md)
- Research: [reliability-patterns.md](./research/researcher-01-reliability-patterns.md)
- Research: [modal-reliability.md](./research/researcher-02-modal-reliability.md)
- Parent plan: `../251226-1500-modal-claude-agents/phase-01-project-setup-modal-config.md`

## Overview

**Priority:** P1 - Foundation
**Status:** Pending
**Effort:** 2h

Implement core reliability patterns: Modal retry configuration, error classification, idempotency, and model fallback.

## Key Insights

1. Modal supports `Retries` class with exponential backoff
2. Distinguish transient errors (network) from logic errors (bad LLM output)
3. Idempotency critical for retry safety
4. Model fallback prevents single-provider dependency

## Requirements

### Functional
- All Modal functions use retry configuration ✓ USER VALIDATED: 3 retries, 2x backoff
- Error classification in BaseAgent
- Idempotent task processing
- Model fallback chain (Claude → Gemini) ✓ USER VALIDATED: Multi-provider

### Non-Functional
- <5% increase in latency from retries
- Zero duplicate side effects from retries

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ERROR HANDLING FLOW                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Exception ──► classify_error()                                  │
│                     │                                            │
│         ┌───────────┼───────────┐                               │
│         ▼           ▼           ▼                               │
│    TRANSIENT     LOGIC      FATAL                               │
│    (network,     (invalid   (auth,                              │
│     rate limit)   output)    config)                            │
│         │           │           │                               │
│         ▼           ▼           ▼                               │
│    Wait+Retry   Self-fix    Dead Letter                         │
│    (Modal)      + Retry     + Alert                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Related Code Files

| Path | Action | Description |
|------|--------|-------------|
| `agents/main.py` | Modify | Add retry config to all functions |
| `agents/src/agents/base.py` | Modify | Add error classification, model fallback |
| `agents/src/utils/errors.py` | Create | Error types and classification |
| `agents/src/utils/retry.py` | Create | Retry utilities and decorators |
| `agents/src/services/llm.py` | Create | LLM wrapper with fallback |

## Implementation Steps

### 1. Create Error Types (`src/utils/errors.py`)

```python
from enum import Enum, auto

class ErrorType(Enum):
    TRANSIENT = auto()  # Network, rate limit - Modal retries
    LOGIC = auto()      # Invalid output - self-correct
    FATAL = auto()      # Auth, config - dead letter

class AgentError(Exception):
    def __init__(self, message: str, error_type: ErrorType, cause: Exception = None):
        super().__init__(message)
        self.error_type = error_type
        self.cause = cause

def classify_error(e: Exception) -> ErrorType:
    """Classify exception for retry strategy."""
    transient_codes = [429, 500, 502, 503, 504]

    if hasattr(e, 'status_code') and e.status_code in transient_codes:
        return ErrorType.TRANSIENT
    if 'rate' in str(e).lower() or 'timeout' in str(e).lower():
        return ErrorType.TRANSIENT
    if 'auth' in str(e).lower() or 'credential' in str(e).lower():
        return ErrorType.FATAL
    return ErrorType.LOGIC
```

### 2. Create LLM Wrapper with Fallback (`src/services/llm.py`)

```python
import anthropic
from typing import List, Dict, Optional
import structlog

logger = structlog.get_logger()

class LLMService:
    """LLM wrapper with model fallback."""

    # USER VALIDATED: Multi-provider fallback (Claude → Gemini)
    FALLBACK_CHAIN = [
        ("anthropic", "claude-sonnet-4-20250514"),
        ("anthropic", "claude-haiku-4-20250514"),
        ("google", "gemini-2.0-flash"),  # Multi-provider fallback
    ]

    def __init__(self):
        self.anthropic = anthropic.Anthropic()

    async def complete(
        self,
        messages: List[Dict],
        system: str = "",
        max_tokens: int = 2048,
    ) -> str:
        """Complete with automatic fallback."""
        last_error = None

        for provider, model in self.FALLBACK_CHAIN:
            try:
                return await self._call_provider(
                    provider, model, messages, system, max_tokens
                )
            except Exception as e:
                logger.warning("model_fallback",
                    model=model, error=str(e)
                )
                last_error = e
                continue

        raise AgentError(
            f"All models failed: {last_error}",
            ErrorType.FATAL,
            last_error
        )

    async def _call_provider(
        self, provider: str, model: str,
        messages: List[Dict], system: str, max_tokens: int
    ) -> str:
        if provider == "anthropic":
            response = self.anthropic.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
            return response.content[0].text
        raise ValueError(f"Unknown provider: {provider}")
```

### 3. Update main.py with Retry Config

```python
from modal import Retries

# Standard retry config for all agents
AGENT_RETRIES = Retries(
    max_retries=3,
    backoff_coefficient=2.0,
    initial_delay=1.0,
)

@app.function(
    image=image,
    secrets=secrets,
    volumes={"/skills": skills_volume},
    retries=AGENT_RETRIES,
    timeout=300,
)
async def agent_function():
    ...
```

### 4. Add Idempotency to Firebase Operations

```python
async def process_task(task_id: str, payload: dict) -> dict:
    """Idempotent task processing."""
    # Check if already processed
    existing = await firebase.get_task_result(task_id)
    if existing:
        logger.info("task_already_processed", task_id=task_id)
        return existing

    # Process and store result atomically
    result = await execute_task(payload)
    await firebase.store_task_result(task_id, result)
    return result
```

### 5. Update BaseAgent with Error Handling

```python
async def execute_with_llm(self, user_message: str, ...) -> str:
    try:
        return await self.llm.complete(
            messages=[{"role": "user", "content": user_message}],
            system=self.read_instructions(),
        )
    except AgentError as e:
        if e.error_type == ErrorType.LOGIC:
            # Self-correct
            improved = await self.self_improve(str(e.cause))
            return await self.execute_with_llm(user_message, ...)
        raise  # TRANSIENT handled by Modal, FATAL propagates
```

## Todo List

- [ ] Create `src/utils/errors.py` with error types
- [ ] Create `src/services/llm.py` with fallback
- [ ] Update `main.py` with retry config
- [ ] Add idempotency to Firebase operations
- [ ] Update BaseAgent error handling
- [ ] Write unit tests for error classification

## Success Criteria

- [ ] All functions have retry config
- [ ] Errors correctly classified in logs
- [ ] Model fallback triggers on primary failure
- [ ] Duplicate task processing prevented

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Fallback model worse quality | User experience | Use capable fallback |
| Retry amplifies costs | Budget | Add budget checks (Phase 2) |

## Security Considerations

- Error messages shouldn't leak sensitive info
- Fallback chain shouldn't expose API keys

## Next Steps

→ Phase 2: Circuit Breakers & Guardrails
