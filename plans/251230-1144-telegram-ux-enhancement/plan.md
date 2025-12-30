# Implementation Plan: Telegram UX Enhancement

**Date:** Dec 30, 2025
**Target:** Casual users with conversational UX
**Priority:** Intelligence first (intent detection, FSM, suggestions, personalization)
**Brainstorm:** `plans/reports/brainstorm-251230-1144-telegram-ux-enhancement.md`

---

## Overview

Enhance Telegram bot UX for casual users through:
1. **P0:** Status messages + Smart onboarding (quick wins)
2. **P1:** Conversation FSM + Enhanced intent detection (intelligence layer)
3. **P2:** Quick replies + Proactive suggestions (engagement)

## Phases

| Phase | Description | Files | Effort |
|-------|-------------|-------|--------|
| [Phase 01](phase-01-status-messages.md) | Status messages during processing | 2 files | Low |
| [Phase 02](phase-02-smart-onboarding.md) | First-time user experience | 3 files | Low |
| [Phase 03](phase-03-conversation-fsm.md) | Conversation state machine | 3 files | Medium |
| [Phase 04](phase-04-enhanced-intent.md) | Intent + skill + params detection | 2 files | Medium |
| [Phase 05](phase-05-quick-replies.md) | Contextual follow-up buttons | 2 files | Low |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     TELEGRAM WEBHOOK                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ FSM Manager  │───►│ Intent Layer │───►│ Skill Router │      │
│  │ (NEW Phase3) │    │ (ENH Phase4) │    │ (existing)   │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ Status Msgs  │    │ Onboarding   │    │ Quick Reply  │      │
│  │ (NEW Phase1) │    │ (NEW Phase2) │    │ (NEW Phase5) │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    StateManager                           │  │
│  │    L1 Cache (volatile) + L2 Firebase (persistent)         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## File Changes Summary

### New Files
| File | Purpose |
|------|---------|
| `src/core/conversation_fsm.py` | Conversation state machine |
| `src/core/onboarding.py` | First-time user experience |
| `src/core/status_messages.py` | Progress/status message utilities |
| `src/core/quick_replies.py` | Contextual follow-up buttons |

### Modified Files
| File | Changes |
|------|---------|
| `src/core/intent.py` | Add `detect_intent_with_params()` |
| `src/core/state.py` | FSM state storage methods |
| `src/services/telegram.py` | Quick reply keyboard builders |
| `api/routes/telegram.py` | FSM integration in webhook |
| `main.py` | `process_message()` with status updates |
| `commands/user.py` | Enhanced `/start` with onboarding |

## Integration Points

1. **telegram.py webhook** - Entry point, FSM check
2. **process_message()** - Status updates, intent detection
3. **StateManager** - FSM persistence
4. **commands/user.py** - Onboarding flow

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| First-message success | Unknown | >80% |
| Command usage | High | <20% |
| User retention (7-day) | Unknown | >40% |

## Dependencies

- Existing: StateManager, intent.py, router.py, telegram.py
- No new external dependencies

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Status msg rate limits | Telegram 30 edits/min, batch updates |
| FSM complexity | 5 states only, thorough testing |
| LLM cost | Semantic first, LLM only <70% confidence |

## Implementation Order

1. **Phase 01** (P0) - Status messages: Quick win, immediate UX improvement
2. **Phase 02** (P0) - Onboarding: Better first impression
3. **Phase 03** (P1) - FSM: Foundation for intelligent routing
4. **Phase 04** (P1) - Intent: Smarter skill detection
5. **Phase 05** (P2) - Quick replies: Engagement boost

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| FSM persistence | L1 + L2 Firebase (reliable) |
| Intent confidence threshold | 0.7 for LLM fallback |
| Hint frequency | Max 1 per session type |
| Quick reply expiry | No expiry, buttons persist |
