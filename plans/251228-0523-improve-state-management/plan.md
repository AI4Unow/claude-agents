---
title: "Improve State Management"
description: "Unified StateManager with TTL caching, async Firebase, conversation persistence"
status: completed
completed: 2025-12-28
priority: P1
effort: 6h
branch: main
tags: [state, caching, firebase, async, modal]
created: 2025-12-28
---

# Improve State Management

## Problem Summary

Current state is fragmented across 4 locations with inconsistent patterns:
1. Telegram sessions - Direct Firebase, no caching, sync ops in async
2. SkillRegistry - In-memory only, lost on restart
3. Web search cache - Module-level global, TTL works but lost on restart
4. Agentic loop - No conversation persistence

## Solution Overview

Create unified `StateManager` class (`src/core/state.py`) providing:
- **L1 Cache**: In-memory with TTL (hot data)
- **L2 Store**: Firebase Firestore (cold persistence)
- **Async wrapping**: All Firebase ops via `asyncio.to_thread()`
- **Conversation store**: Persist agentic messages per user

## Phases

| Phase | Focus | Effort | File |
|-------|-------|--------|------|
| 01 | StateManager core + TTL cache | 1.5h | phase-01-state-manager-core.md |
| 02 | Migrate Telegram session functions | 1.5h | phase-02-migrate-telegram-sessions.md |
| 03 | Add conversation persistence | 1.5h | phase-03-conversation-persistence.md |
| 04 | Warm caches on startup | 1.5h | phase-04-cache-warming.md |

## Architecture

```
StateManager
├── _l1_cache: Dict[str, CacheEntry]  # TTL-based in-memory
├── _firebase: Firestore client
└── Methods:
    ├── get(key) -> async read L1, fallback L2
    ├── set(key, val, ttl) -> write L1 + L2
    ├── get_session(user_id) -> Telegram session
    ├── get_conversation(user_id) -> message history
    └── warm() -> preload hot data on startup
```

## Key Decisions

1. **Single module** - All state in `src/core/state.py`, not scattered
2. **TTL defaults** - Sessions: 1hr, Conversations: 24hr, Skills: 5min
3. **Async-first** - Wrap sync Firebase with `asyncio.to_thread()`
4. **No Redis** - YAGNI; in-memory + Firebase sufficient for current scale

## Success Criteria

- [ ] Session reads hit cache >80% of time
- [ ] No sync Firebase calls in async functions
- [ ] Conversations persist across container restarts
- [ ] Skill cache warms on container start

## Risks

| Risk | Mitigation |
|------|------------|
| Multi-container stale cache | Accept eventual consistency; TTL keeps fresh |
| Cold start latency | Cache warming in container `@enter` hook |

## Validation Summary

**Validated:** 2025-12-28
**Questions asked:** 4

### Confirmed Decisions

| Decision | Choice |
|----------|--------|
| TTL defaults | Yes, use defaults (1hr sessions, 24hr conversations, 5min cache) |
| Conversation persistence | Yes, add persistence (last 20 messages per user) |
| Cache warming approach | @enter hook (requires @app.cls refactor) |
| Migration strategy | Replace immediately (remove old session functions) |

### Action Items

- [ ] Phase 04: Use Modal @enter hook instead of FastAPI startup event
- [ ] Refactor `telegram_chat_agent()` function to `TelegramChatAgentCls` class with @app.cls
