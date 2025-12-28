---
title: "Hybrid Local + Modal Agent Architecture"
description: "Comprehensive architecture overview for hybrid agent system with reliability patterns"
status: completed
priority: P1
effort: 8h
branch: main
tags: [architecture, hybrid, modal, local, reliability, ii-framework]
created: 2025-12-28
---

# Hybrid Local + Modal Agent Architecture

## Overview

Complete architecture documentation for hybrid agent system: Local Claude Code agents + Modal.com remote agents, unified by II Framework with reliability patterns.

## Context

- **Current State:** Deployed MVP on Modal with Telegram, GitHub, Data, Content agents
- **Gap:** No local agent coordination, channel adapters tightly coupled
- **Target:** Unified hybrid system with reliability, multi-channel support

## Phases

| # | Phase | Effort | Link |
|---|-------|--------|------|
| 1 | System Overview | 1h | [phase-01](./phase-01-system-overview.md) |
| 2 | Agent Coordination | 1.5h | [phase-02-agent-coordination.md](./phase-02-agent-coordination.md) |
| 3 | Reliability Patterns | 1.5h | [phase-03-reliability-patterns.md](./phase-03-reliability-patterns.md) |
| 4 | Skill System | 1.5h | [phase-04-skill-system.md](./phase-04-skill-system.md) |
| 5 | Channel Adapters | 1.5h | [phase-05-channel-adapters.md](./phase-05-channel-adapters.md) |
| 6 | Configuration | 1h | [phase-06-configuration.md](./phase-06-configuration.md) |

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Local browser | chrome-dev/chrome skills | Consumer IP needed |
| Coordination | Async queue via Firebase | Decoupled, resilient |
| Reliability | tenacity + custom CircuitBreaker | Already implemented |
| Channel abstraction | BaseChannelAdapter | Add channels without core changes |
| Skill sync | CC → GitHub → Modal one-way | Single source of truth |

## Architecture Summary

```
LOCAL (Claude Code)              MODAL CLOUD                    EXTERNAL
─────────────────               ────────────                   ────────
┌─────────────────┐            ┌─────────────────────┐        ┌────────┐
│ Claude Code     │◄──────────►│ FastAPI App         │◄──────►│Telegram│
│ + chrome skills │            │ + Telegram Agent    │        │Discord │
│ + TikTok/FB/YT  │            │ + GitHub Agent      │        │Slack   │
└────────┬────────┘            │ + Data Agent        │        └────────┘
         │                     │ + Content Agent     │
         │                     └─────────┬───────────┘
         │                               │
         ▼                               ▼
    ┌─────────────────────────────────────────────┐
    │        Firebase (State + Queue)              │
    ├─────────────────────────────────────────────┤
    │ telegram_sessions | conversations | tasks    │
    └─────────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │  Qdrant (Memory) │
              └──────────────────┘
```

## Success Criteria

- [ ] Master architecture diagram complete
- [ ] Local/remote skill categorization documented
- [ ] Reliability patterns applied to all services
- [ ] Channel adapter interface defined
- [ ] Configuration catalog complete

---

## Validation Summary

**Validated:** 2025-12-28
**Questions asked:** 5

### Confirmed Decisions

| Decision | User Choice |
|----------|-------------|
| Local agent task polling | Polling first (start simple, add real-time later) |
| Next channel after Telegram | Telegram only for now (defer other channels) |
| Circuit breaker scope | Add missing only (Claude + Telegram circuits) |
| Adapter refactor approach | Full refactor (extract all Telegram logic now) |
| Plan purpose | Documentation only (reference document) |

### Action Items

- [x] No implementation needed - this is architecture documentation
- [ ] When implementing, create separate implementation plans per feature
- [ ] Reference existing plan: `plans/251228-0736-agents-enhancement/` for skill categorization + self-improvement

---

## Related Plans (Consolidated)

This architecture document consolidates and supersedes multiple prior plans.

### ✅ Superseded Plans (Historical Reference Only)

| Plan | Status | Notes |
|------|--------|-------|
| `251226-1500-modal-claude-agents` | Superseded | Original II Framework design, now part of Phase 1 |
| `251227-1528-unified-ii-framework` | Completed | Core patterns implemented, now Phase 4 |
| `251227-1234-smart-chatbot-tools` | Completed | Tools exist in codebase |
| `251227-1308-additional-bot-tools` | Completed | Tools exist in codebase |
| `251227-1355-skills-deployment-audit` | Completed | Agents deployed |
| `251228-0523-improve-state-management` | Completed | StateManager implemented in src/core/state.py |

### 🔄 Active Implementation Plans (Reference These)

| Plan | Status | Maps To |
|------|--------|---------|
| `251228-0736-agents-enhancement` | **Pending** | Phase 4 (Skill System): skill categorization + self-improvement loop |
| `251228-0622-agentex-p0-tracing-resilience` | **Pending** | Phase 3 (Reliability): execution tracing + circuit breakers |
| `251227-0629-agent-reliability-improvements` | Pending | Phase 3 (Reliability): retries, health checks, fallbacks |
| `251227-2251-telegram-skills-terminal` | Code-review-feedback | Phase 5 (Channel Adapters): Telegram refactor pending fixes |

### Implementation Order

When ready to implement, follow this order:

1. **Phase 3 First** → `251228-0622-agentex-p0-tracing-resilience` (reliability foundation)
2. **Phase 4 Second** → `251228-0736-agents-enhancement` (skill categorization + self-improvement)
3. **Phase 5 Third** → `251227-2251-telegram-skills-terminal` (fix critical issues first)
4. **Phase 2 Later** → Agent coordination (task queue) when local skills needed
