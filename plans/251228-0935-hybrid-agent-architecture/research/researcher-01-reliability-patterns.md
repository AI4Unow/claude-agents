# Research: Reliability Patterns for Hybrid Agent Architecture

**Date:** 2025-12-28
**Topic:** Circuit breakers, retries, and fault tolerance for Python async services

## Circuit Breaker Pattern

Acts as safety switch that "trips" to stop requests to failing service.

**States:**
- **Closed:** Normal operation, requests pass through
- **Open:** Requests fail immediately (return fallback)
- **Half-Open:** Periodic trial requests to check recovery

**Recommended Libraries:**
- `aiobreaker` - Standard for asyncio, fork of pybreaker
- `purgatory` - Supports Redis for distributed state
- `circuitbreaker` - Simple decorator-based

## Retry Pattern

Handles "self-correcting" errors (503, timeouts).

**Best Practices:**
- Exponential backoff (1s, 2s, 4s)
- Jitter to avoid thundering herd
- Only retry idempotent operations

**Libraries:**
- `tenacity` - Industry standard, robust asyncio support
- `opnieuw` - Clean async code, jitter + backoff

## Integration Strategy

```
Retry (inner) → Circuit Breaker (outer)
```

1. Attempt 3 retries for quick fix
2. If all fail, increment breaker failure count
3. Once threshold hit, stop all calls for cooldown

**Key Principles:**
- Target specific exceptions (`aiohttp.ClientError`, `asyncio.TimeoutError`)
- Define fallback for Open state (cached data, default message)
- Use shared state (Redis) for distributed circuit breakers

## Application to Agents Project

| Service | Strategy |
|---------|----------|
| Claude API | Retry 3x + breaker (5 failures/min) |
| Firebase | Retry 2x + graceful fallback to L1 cache |
| Qdrant | Retry 2x + fallback to keyword match |
| Telegram | Retry 2x (webhook ack critical) |
| Exa/Tavily | Exa primary → Tavily fallback (already implemented) |

## Citations

- [Tenacity Docs](https://tenacity.readthedocs.io/en/latest/#async-and-tenacity)
- [Aiobreaker](https://github.com/danielfm/aiobreaker)
