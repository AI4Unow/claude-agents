# Critical Fixes Plan - Parallel Execution

**Date:** 2025-12-28
**Priority:** P0-P1
**Status:** ✅ COMPLETED

## Summary

All 14 critical/high issues fixed across 11 files in 6 parallel phases.

```
Group 1 (Tools)     Group 2 (Core)     Group 3 (Services)
     │                   │                    │
     ├── code_exec       ├── state.py        ├── llm.py
     ├── web_search      ├── resilience.py   ├── firebase.py
     ├── web_reader      ├── orchestrator    └── qdrant.py
     └── memory_search   │
                         │
     ────────────────────┴───────────────────
                         │
                    Group 4 (Main)
                         │
                    └── main.py
```

## Execution Strategy

| Phase | Files | Parallel | Depends On |
|-------|-------|----------|------------|
| 1A | code_exec.py, web_search.py | Yes | None |
| 1B | web_reader.py, memory_search.py | Yes | None |
| 2A | state.py, resilience.py | Yes | None |
| 2B | orchestrator.py | Yes | None |
| 3 | llm.py, firebase.py, qdrant.py | Yes | 2A (resilience) |
| 4 | main.py (refactor) | No | 3 |

## File Ownership Matrix

| File | Phase | Owner | Fixes |
|------|-------|-------|-------|
| code_exec.py | 1A | Agent-1A | Sandbox escape |
| web_search.py | 1A | Agent-1A | Cache limit |
| web_reader.py | 1B | Agent-1B | DoS fix |
| memory_search.py | 1B | Agent-1B | Timeout add |
| state.py | 2A | Agent-2A | Cache limit, race fix |
| resilience.py | 2A | Agent-2A | Lock contention |
| orchestrator.py | 2B | Agent-2B | DAG validation |
| llm.py | 3 | Agent-3 | Circuit breaker, timeout |
| firebase.py | 3 | Agent-3 | Circuit breaker |
| qdrant.py | 3 | Agent-3 | Circuit breaker |
| main.py | 4 | Agent-4 | Rate limit, webhook verify |

## Phases

- [phase-01a-tools-security.md](./phase-01a-tools-security.md)
- [phase-01b-tools-stability.md](./phase-01b-tools-stability.md)
- [phase-02a-core-caching.md](./phase-02a-core-caching.md)
- [phase-02b-core-orchestrator.md](./phase-02b-core-orchestrator.md)
- [phase-03-services-resilience.md](./phase-03-services-resilience.md)
- [phase-04-main-security.md](./phase-04-main-security.md)
