---
title: "Telegram Parity Architecture"
description: "API parity via Telegram with semantic orchestration and tier-based auth"
status: pending
priority: P1
effort: 10-15d
branch: main
tags: [telegram, auth, orchestration, api-parity]
created: 2025-12-29
---

# Telegram Parity Architecture

**Goal:** Full API parity via Telegram - skill execution, orchestration, monitoring via Telegram commands.

## Context

- Brainstorm: [brainstorm-251229-0712-telegram-parity-architecture.md](../reports/brainstorm-251229-0712-telegram-parity-architecture.md)
- Codebase: Modal.com agents with existing Telegram webhook

## Phases

| Phase | Description | Status | Effort | Link |
|-------|-------------|--------|--------|------|
| 1 | Auth System | pending | 1-2d | [phase-01](phase-01-auth-system.md) |
| 2 | Admin Commands | pending | 1-2d | [phase-02](phase-02-admin-commands.md) |
| 3 | Complexity Detector | pending | 2-3d | [phase-03](phase-03-complexity-detector.md) |
| 4 | Semantic Orchestration | pending | 3-5d | [phase-04](phase-04-semantic-orchestration.md) |
| 5 | Polish | pending | 1-2d | [phase-05](phase-05-polish.md) |

## Architecture Overview

```
USER MESSAGE
     |
     v
COMPLEXITY DETECTOR (fast LLM) --> SIMPLE --> Direct LLM Response
     |
     v
  COMPLEX
     |
     v
ORCHESTRATOR (multi-skill)
     |
     +-- "Using: planning..." --> Result
     +-- "Using: code-review..." --> Result
     v
SYNTHESIZED RESPONSE
```

## Key Files to Modify

- `main.py` - Commands, webhook handler
- `firebase.py` - Auth tokens, tier storage
- `orchestrator.py` - Progress callbacks
- `state.py` - User tier caching

## Success Criteria

1. All API features accessible via Telegram
2. Tier-based access control working
3. Admin can view traces/circuits via Telegram
4. Complexity detector routes appropriately
5. Orchestrated tasks show progress messages

## Dependencies

- Claude Haiku (already available) for complexity classifier
- Firebase composite index for reminders

## Risks

| Risk | Mitigation |
|------|------------|
| Classifier inaccuracy | Explicit `/mode` fallback |
| Message flood | Throttle, batch small results |
| Unauthorized access | Telegram ID allowlist + tier system |

## Validation Summary

**Validated:** 2025-12-29
**Questions asked:** 6

### Confirmed Decisions

1. **Guest tier access:** Rate-limited (not blocked) - guests can use basic skills with lower limits
2. **Complexity classifier:** Use Claude Haiku (already integrated) instead of Groq - no new secret needed
3. **Progress UX:** Sequential messages (as planned)
4. **Auth mechanism:** Telegram ID allowlist in Firebase instead of one-time tokens - simpler approach
5. **Orchestrator trigger:** Auto-detect for mode=auto users (as planned)
6. **Phase order:** Sequential as planned

### Action Items (Plan Revisions Completed)

- [x] Phase 1: Change from token-based auth to Telegram ID allowlist in Firebase
- [x] Phase 1: Add rate limits for guest tier (5 req/min) vs authenticated tiers
- [x] Phase 3: Change from Groq to Claude Haiku for complexity detection
- [x] Remove GROQ_API_KEY dependency
