---
title: "AgentEx P0: Execution Tracing + Circuit Breakers"
description: "Production reliability via structured tracing and resilience patterns"
status: needs-review
review_date: 2025-12-28
review_report: plans/reports/code-reviewer-251228-1311-critical-fixes.md
priority: P0
effort: 6h
branch: main
tags: [agentex, tracing, resilience, circuit-breaker, production]
created: 2025-12-28
---

# AgentEx P0: Execution Tracing + Circuit Breakers

## Problem Summary

Current agents lack production reliability:
1. **No execution tracing** - Can't debug failures, no visibility into tool calls
2. **No resilience** - External service failures cascade, no circuit breakers
3. **No metrics** - Can't measure latency, success rates, or error patterns

## Solution Overview

Implement Scale AgentEx P0 patterns:
- **Execution Tracing** - Capture full execution path with timing/errors
- **Circuit Breakers** - Prevent cascading failures to external APIs
- **Trace Storage** - Persist to Firebase with 7-day TTL

## Phases

| Phase | Focus | Effort | File |
|-------|-------|--------|------|
| 01 | Execution Tracing Core | 2h | phase-01-execution-tracing.md |
| 02 | Circuit Breakers | 2h | phase-02-circuit-breakers.md |
| 03 | Integration & API | 2h | phase-03-integration.md |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        EXECUTION TRACING FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User Request                                                                │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ TraceContext.start()                                                    ││
│  │   trace_id = uuid                                                       ││
│  │   started_at = now()                                                    ││
│  └───────────────────────────────────┬─────────────────────────────────────┘│
│                                      │                                       │
│       ┌──────────────────────────────┼──────────────────────────────┐       │
│       ▼                              ▼                              ▼       │
│  ┌──────────┐                  ┌──────────┐                  ┌──────────┐   │
│  │ Tool Call│                  │ Tool Call│                  │ Tool Call│   │
│  │ web_search                  │ run_python                  │ read_url │   │
│  └─────┬────┘                  └─────┬────┘                  └─────┬────┘   │
│        │                             │                             │        │
│        ▼                             ▼                             ▼        │
│  ┌──────────┐                  ┌──────────┐                  ┌──────────┐   │
│  │ Circuit  │                  │ No circuit                 │ Circuit  │   │
│  │ Breaker  │                  │ (local)  │                  │ Breaker  │   │
│  └─────┬────┘                  └─────┬────┘                  └─────┬────┘   │
│        │                             │                             │        │
│        └─────────────────────────────┼─────────────────────────────┘        │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ TraceContext.end()                                                      ││
│  │   ended_at = now()                                                      ││
│  │   status = success|error|timeout                                        ││
│  │   → TraceStore.save(trace)                                              ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                      │                                       │
│                                      ▼                                       │
│                             ┌─────────────────┐                              │
│                             │    Firebase     │                              │
│                             │ execution_traces│                              │
│                             │   (7-day TTL)   │                              │
│                             └─────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## New Files

| File | Purpose |
|------|---------|
| `src/core/trace.py` | ExecutionTrace, ToolTrace, TraceContext, TraceStore |
| `src/core/resilience.py` | CircuitBreaker, CircuitOpenError, retry decorator |

## Modified Files

| File | Changes |
|------|---------|
| `src/services/agentic.py` | Wrap in TraceContext, capture tool traces |
| `src/tools/web_search.py` | Add circuit breaker for Exa/Tavily |
| `src/tools/registry.py` | Add trace capture to execute() |
| `main.py` | Add /api/traces endpoint |

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Trace storage | Firebase | Already integrated, fits L1/L2 pattern |
| Trace TTL | 7 days | Balance storage cost vs debugging utility |
| Circuit threshold | 3 failures | Quick failover without flapping |
| Circuit cooldown | 30 seconds | Fast recovery for transient errors |
| Trace sampling | 100% errors, 10% success | Reduce costs, keep error visibility |

## Success Criteria

- [x] All tool calls have timing captured
- [x] Circuit breakers on all external APIs (Exa, Tavily, Firebase, Qdrant, Claude, Telegram)
- [x] Traces viewable via /api/traces endpoint
- [x] Mean time to debug reduced (can see exact failure point)
- [x] No cascading failures when external API down
- [ ] **Security fixes applied** (code sandbox, webhook verification)
- [ ] **Performance optimizations** (cache eviction, TTL cleanup)
- [ ] **Tests added** for critical tools and state management

## Risks

| Risk | Mitigation |
|------|------------|
| Firebase write costs | 7-day TTL + sampling |
| Circuit breaker false positives | Low threshold (3), short cooldown (30s) |
| Trace size bloat | Truncate outputs to 500 chars |

## Dependencies

- StateManager (already implemented)
- Firebase (already integrated)
- structlog (already used)
