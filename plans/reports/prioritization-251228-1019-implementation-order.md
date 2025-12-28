# Implementation Order for Active Plans

**Date:** 2025-12-28
**Type:** Prioritization Analysis

## Active Plans Inventory

| # | Plan | Priority | Effort | Status |
|---|------|----------|--------|--------|
| 1 | `251228-0622-agentex-p0-tracing-resilience` | **P0** | 6h | Pending |
| 2 | `251228-0736-agents-enhancement` | P1 | 16h | Pending |
| 3 | `251227-2251-telegram-skills-terminal` | P1 | 6h | Code-review (fixes needed) |
| 4 | `251227-0629-agent-reliability-improvements` | P1 | 8h | Pending (overlaps P0) |
| 5 | `251228-0935-hybrid-agent-architecture` | P1 | 8h | Pending (docs only) |

## Recommended Order

### 1️⃣ FIRST: AgentEx P0 - Tracing + Circuit Breakers (6h)

**Plan:** `251228-0622-agentex-p0-tracing-resilience`

**Rationale:**
- **P0 priority** - Production reliability foundation
- **No dependencies** - StateManager already implemented
- **Enables other plans** - TraceContext and CircuitBreaker reused by agents-enhancement
- **Immediate value** - Debugging and failure prevention

**Deliverables:**
- `src/core/trace.py` - ExecutionTrace, TraceContext, TraceStore
- `src/core/resilience.py` - CircuitBreaker, retry decorator
- `/api/traces` endpoint
- Circuit breakers on Exa, Tavily, Firebase, Qdrant

---

### 2️⃣ SECOND: Telegram Skills Terminal Fixes (2-3h fixes)

**Plan:** `251227-2251-telegram-skills-terminal`

**Rationale:**
- **Already implemented** - Just needs critical fixes
- **Prerequisite for agents-enhancement** - Self-improvement notifications use Telegram
- **Quick wins** - Fix 3 critical issues, deploy

**Critical Fixes (from code review):**
1. Add error handling to Firebase session functions
2. Validate user_id before Firebase operations
3. Escape HTML in message formatting

---

### 3️⃣ THIRD: Agents Enhancement - Skill Categorization + Self-Improvement (16h)

**Plan:** `251228-0736-agents-enhancement`

**Rationale:**
- **Depends on #1** - Uses TraceContext for error detection
- **Depends on #2** - Uses Telegram for admin notifications
- **Highest value** - Self-improving agents

**Phases:**
1. Skill Categorization Schema (2h)
2. Skill Sync Filter (2h)
3. ImprovementService Core (4h)
4. Telegram Admin Notifications (3h)
5. Integration & Testing (3h)
6. Deploy & Monitor (2h)

---

### 4️⃣ DEFER: Agent Reliability Improvements

**Plan:** `251227-0629-agent-reliability-improvements`

**Recommendation:** **Mark as superseded or merge with AgentEx P0**

**Overlap Analysis:**
| Feature | AgentEx P0 | Agent Reliability |
|---------|------------|-------------------|
| Circuit breakers | ✅ | ✅ |
| Retries | ✅ | ✅ |
| Health checks | ✅ | ✅ |
| Execution tracing | ✅ | ❌ |
| Model fallback | ❌ | ✅ |
| Checkpointing | ❌ | ✅ |
| DLQ | ❌ | ✅ |

**Action:** Cherry-pick model fallback + checkpointing into AgentEx P0 or Phase 4

---

### 5️⃣ REFERENCE: Hybrid Agent Architecture

**Plan:** `251228-0935-hybrid-agent-architecture`

**Rationale:**
- **Documentation only** - Already validated as reference document
- **No implementation** - Guides other plans
- Keep updated as implementation progresses

---

## Timeline Summary

| Week | Plan | Effort |
|------|------|--------|
| Now | AgentEx P0 Tracing | 6h |
| Next | Telegram Fixes | 2-3h |
| After | Agents Enhancement | 16h |
| Later | Agent Coordination (Phase 2) | TBD |

## Dependencies Diagram

```
AgentEx P0 (6h)
    │
    ├──► Telegram Fixes (3h)
    │         │
    └─────────┴──► Agents Enhancement (16h)
                         │
                         └──► Local Agent Coordination (later)
```

## Unresolved Questions

1. Should `251227-0629-agent-reliability` be merged into AgentEx P0?
2. When to implement model fallback (Claude → Gemini)?
3. Should checkpointing be added to AgentEx P0 or deferred?
