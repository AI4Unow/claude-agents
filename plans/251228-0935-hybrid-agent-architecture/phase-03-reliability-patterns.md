# Phase 3: Reliability Patterns

## Context

Implement production-grade reliability: circuit breakers, retries, health checks, graceful degradation. Based on research in `research/researcher-01-reliability-patterns.md`.

## Overview

Custom CircuitBreaker already implemented in `src/core/resilience.py`. This phase documents the pattern and extends to all services.

## Key Insights

- Circuit breakers prevent cascading failures
- Retries handle transient errors (503, timeouts)
- Fallback chains provide degraded service
- Health checks enable monitoring

## Current Implementation (resilience.py)

Already implemented:

```python
# Pre-configured circuits
exa_circuit = CircuitBreaker("exa_api", threshold=3, cooldown=30)
tavily_circuit = CircuitBreaker("tavily_api", threshold=3, cooldown=30)
firebase_circuit = CircuitBreaker("firebase", threshold=5, cooldown=60)
qdrant_circuit = CircuitBreaker("qdrant", threshold=5, cooldown=60)

# Retry decorator
@with_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def fetch_data(): ...
```

## Circuit Breaker States

```
┌─────────────────────────────────────────────────────────────────┐
│                    CIRCUIT BREAKER STATES                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CLOSED (Normal)                                                 │
│  ───────────────                                                 │
│  • Requests pass through                                         │
│  • Track failure count                                           │
│  • On threshold hit → OPEN                                       │
│                                                                  │
│       │ failures >= threshold                                    │
│       ▼                                                          │
│                                                                  │
│  OPEN (Failing)                                                  │
│  ──────────────                                                  │
│  • Reject requests immediately (CircuitOpenError)                │
│  • Return fallback if available                                  │
│  • After cooldown → HALF_OPEN                                    │
│                                                                  │
│       │ cooldown elapsed                                         │
│       ▼                                                          │
│                                                                  │
│  HALF_OPEN (Testing)                                             │
│  ───────────────────                                             │
│  • Allow single trial request                                    │
│  • On success → CLOSED                                           │
│  • On failure → OPEN (immediate)                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Service Strategy Matrix

| Service | Circuit | Retries | Fallback | Priority |
|---------|---------|---------|----------|----------|
| Claude API | claude_circuit (new) | 3x, exp backoff | Error message | Critical |
| Firebase | firebase_circuit | 2x | L1 cache only | High |
| Qdrant | qdrant_circuit | 2x | Keyword match | High |
| Exa | exa_circuit | 2x | Tavily | Medium |
| Tavily | tavily_circuit | 2x | "Search unavailable" | Medium |
| Telegram | telegram_circuit (new) | 2x | Queue for retry | Critical |

## Extended Resilience Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    RESILIENCE STACK                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Request                                                         │
│     │                                                            │
│     ▼                                                            │
│  ┌─────────────────────────────────────────────┐                │
│  │ 1. CIRCUIT BREAKER (outer)                  │                │
│  │    • Check state                            │                │
│  │    • If OPEN → fallback immediately         │                │
│  └─────────────────────┬───────────────────────┘                │
│                        │ CLOSED or HALF_OPEN                    │
│                        ▼                                         │
│  ┌─────────────────────────────────────────────┐                │
│  │ 2. RETRY WRAPPER (inner)                    │                │
│  │    • Attempt 1-3                            │                │
│  │    • Exponential backoff + jitter           │                │
│  └─────────────────────┬───────────────────────┘                │
│                        │                                         │
│                        ▼                                         │
│  ┌─────────────────────────────────────────────┐                │
│  │ 3. TIMEOUT                                  │                │
│  │    • asyncio.wait_for(func, timeout)        │                │
│  │    • Default 30s for API calls              │                │
│  └─────────────────────┬───────────────────────┘                │
│                        │                                         │
│                        ▼                                         │
│  ┌─────────────────────────────────────────────┐                │
│  │ 4. ACTUAL SERVICE CALL                      │                │
│  │    • Claude, Firebase, Qdrant, etc.         │                │
│  └─────────────────────────────────────────────┘                │
│                        │                                         │
│                        ▼                                         │
│  Success → Record in circuit → Return                           │
│  Failure → Record in circuit → Retry or Fallback                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Fallback Chains

### Web Search Fallback

```python
async def web_search_with_fallback(query: str) -> str:
    try:
        return await exa_circuit.call(search_exa, query)
    except CircuitOpenError:
        pass
    except Exception:
        pass  # Recorded by circuit

    try:
        return await tavily_circuit.call(search_tavily, query)
    except CircuitOpenError:
        return "Web search temporarily unavailable. Please try again."
    except Exception:
        return "Web search failed. Please try again later."
```

### State Fallback

```python
async def get_session(user_id: str) -> dict:
    # L1 cache first
    cached = l1_cache.get(f"session:{user_id}")
    if cached:
        return cached

    # L2 Firebase with circuit
    try:
        session = await firebase_circuit.call(
            firebase_get, "sessions", user_id
        )
        l1_cache.set(f"session:{user_id}", session)
        return session
    except CircuitOpenError:
        # Degraded mode: empty session
        return {"user_id": user_id, "degraded": True}
```

## Health Check Enhancement

Current endpoint returns circuit status:

```python
@web_app.get("/health")
async def health():
    circuits = get_circuit_stats()
    any_open = any(c["state"] == "open" for c in circuits.values())

    return {
        "status": "degraded" if any_open else "healthy",
        "agent": "claude-agents",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "circuits": circuits,
    }
```

**Response:**
```json
{
  "status": "healthy",
  "circuits": {
    "exa_api": {"state": "closed", "failures": 0},
    "firebase": {"state": "closed", "failures": 2},
    "qdrant": {"state": "half_open", "failures": 5}
  }
}
```

## Graceful Degradation Levels

| Level | Condition | Behavior |
|-------|-----------|----------|
| 0 - Normal | All circuits closed | Full functionality |
| 1 - Search degraded | Exa+Tavily open | Return cached or "unavailable" |
| 2 - Memory degraded | Qdrant open | Keyword routing, no vector search |
| 3 - State degraded | Firebase open | L1 cache only, no persistence |
| 4 - Critical | Claude API open | Error message, log for retry |

## New Circuits to Add

```python
# In resilience.py

# Claude API circuit (most critical)
claude_circuit = CircuitBreaker(
    "claude_api",
    threshold=3,
    cooldown=60,  # Longer cooldown for rate limits
)

# Telegram API circuit
telegram_circuit = CircuitBreaker(
    "telegram_api",
    threshold=5,
    cooldown=30,
)

# Update get_circuit_stats()
def get_circuit_stats() -> Dict[str, Dict]:
    return {
        "claude_api": claude_circuit.get_stats(),
        "telegram_api": telegram_circuit.get_stats(),
        "exa_api": exa_circuit.get_stats(),
        "tavily_api": tavily_circuit.get_stats(),
        "firebase": firebase_circuit.get_stats(),
        "qdrant": qdrant_circuit.get_stats(),
    }
```

## Implementation Steps

1. [ ] Add claude_circuit and telegram_circuit
2. [ ] Wrap LLM calls in claude_circuit
3. [ ] Wrap Telegram send in telegram_circuit
4. [ ] Implement fallback chains for each service
5. [ ] Add degradation level to health endpoint
6. [ ] Create circuit status Telegram command (/circuits)
7. [ ] Add admin circuit reset endpoint (already exists)

## Todo List

- [ ] Add jitter to retry decorator
- [ ] Implement request queue for Telegram when circuit open
- [ ] Add metrics/alerting for circuit trips
- [ ] Create runbook for circuit failures

## Success Criteria

- [ ] All external services wrapped in circuits
- [ ] Fallback chains work for search, state, routing
- [ ] Health endpoint reflects actual service status
- [ ] Graceful degradation prevents total outage
- [ ] Circuits auto-recover after cooldown
