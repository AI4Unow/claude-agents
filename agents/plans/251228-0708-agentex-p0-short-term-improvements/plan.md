---
title: "AgentEx P0 Short-Term Improvements"
description: "Address high-priority issues from code review: timeout protection, structured responses, cache eviction, authentication, unit tests"
status: completed
priority: P1
effort: 8h
branch: main
tags: [agentex, resilience, testing, security]
created: 2025-12-28
completed: 2025-12-28
---

# AgentEx P0 Short-Term Improvements

## Context

Based on code review report: `plans/reports/code-reviewer-251228-0659-agentex-p0-review.md`

**Critical issues (#1-4) already fixed:**
- Thread safety in CircuitBreaker (threading.Lock added)
- Async cleanup guarantee in TraceContext (try-finally)
- Memory exhaustion protection (MAX_TOOL_TRACES = 100)
- Sensitive data sanitization (_sanitize_input function)

**This plan covers short-term improvements (issues #5-10):**

| Issue | Severity | Description |
|-------|----------|-------------|
| #6 | HIGH | Circuit breaker missing timeout protection |
| #8 | MEDIUM | Error detection uses brittle string matching |
| #9 | MEDIUM | Cache eviction never runs automatically |
| #11 | MEDIUM | Admin endpoints lack authentication |
| #12 | MEDIUM | with_retry retries all exceptions |
| - | HIGH | No unit tests for core modules |

## Implementation Phases

| Phase | Description | Status | Effort |
|-------|-------------|--------|--------|
| [Phase 01](./phase-01-circuit-timeout-protection.md) | Add timeout to circuit breaker calls | completed | 1h |
| [Phase 02](./phase-02-structured-tool-responses.md) | Replace string matching with ToolResult | completed | 2h |
| [Phase 03](./phase-03-cache-eviction.md) | Periodic cache cleanup in StateManager | completed | 1h |
| [Phase 04](./phase-04-admin-authentication.md) | Add auth to /api/circuits endpoints | completed | 1h |
| [Phase 05](./phase-05-unit-tests.md) | Unit tests for trace.py, resilience.py | completed | 3h |

## Success Criteria

- [x] Circuit breaker calls timeout after 30s (configurable)
- [x] Tool errors detected via structured response, not string prefix
- [x] L1 cache cleaned every 5 minutes
- [x] Admin endpoints require X-Admin-Token header
- [x] 100% test coverage for src/core/trace.py and src/core/resilience.py

## Validation Summary

**Validated:** 2025-12-28
**Questions asked:** 6

### Confirmed Decisions

| Decision | User Choice |
|----------|-------------|
| Default circuit timeout | 30 seconds |
| ToolResult migration strategy | All at once (no compatibility layer) |
| Cache eviction interval | 5 minutes |
| Auth scope | Admin endpoints only (/api/circuits, /api/traces) |
| Test coverage target | 100% for core modules |
| Implementation order | 01 → 02 → 03 → 04 → 05 |

### Action Items

- [ ] Update phase-05: Change target from 80% to 100% coverage
- [ ] Update phase-02: Remove compatibility layer, update all tools at once

## Files to Modify

| File | Changes |
|------|---------|
| `src/core/resilience.py` | Add timeout param to call(), update with_retry defaults |
| `src/tools/base.py` | Add ToolResult dataclass |
| `src/tools/*.py` | Return ToolResult instead of str |
| `src/services/agentic.py` | Check result.success instead of string prefix |
| `src/core/state.py` | Add periodic cleanup task |
| `main.py` | Add verify_admin_token dependency |
| `tests/test_trace.py` | NEW - TraceContext tests |
| `tests/test_resilience.py` | NEW - CircuitBreaker tests |

## Dependencies

- No external dependencies required
- All changes are backwards-compatible

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| ToolResult breaking change | HIGH | Add compatibility wrapper, deprecate old signature |
| Async cleanup task fails silently | LOW | Add error logging in cleanup task |
| Token header conflicts with existing | LOW | Use X-Admin-Token (non-standard prefix) |
