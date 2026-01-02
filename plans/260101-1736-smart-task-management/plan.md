---
title: "Smart Task Management System"
description: "Unified task system with Claude Agents SDK, NLP parsing, calendar sync, and React dashboard"
status: completed
priority: P1
effort: 51h
branch: main
tags: [task-management, nlp, calendar, dashboard, agent-autonomy, claude-agents-sdk]
created: 2026-01-01
updated: 2026-01-02
completed: 2026-01-02
---

# Smart Task Management System

## Overview

Unified task management integrating PKM + Reminders with Claude Agents SDK for agent autonomy, hybrid NLP parsing, calendar sync, and React dashboard.

## Architecture Summary

```
User Input → Claude Agents SDK → SmartTask (Firebase) → SDK Tools
                   │
                   ├── hooks.py (trust rules via PreToolUse)
                   ├── tools/*.py (task/calendar/nlp)
                   └── Native checkpointing (undo capability)
                                        │
               ┌────────────────────────┼────────────────────────┐
               ▼                        ▼                        ▼
        Google Calendar          Google Tasks           Apple CalDAV
        (time-blocked)           (date-only)            (full sync)
               │
               ▼
        React Dashboard (agents/dashboard/)
        - List / Kanban / Calendar / Timeline views
        - Real-time Firebase sync
        - Telegram Login auth
```

## Phases

| Phase | Description | Effort | Status |
|-------|-------------|--------|--------|
| [Phase 0](phase-00-sdk-foundation.md) | SDK Foundation (full migration: all agents, tools, hooks) | 18h | completed |
| [Phase 1](phase-01-core-foundation.md) | Core Foundation (SmartTask, NLP) | 7h | completed |
| [Phase 2](phase-02-smart-features.md) | Smart Features (Timing, Extraction, Auto-reschedule) | 8h | completed |
| [Phase 3](phase-03-calendar-sync.md) | Calendar Sync (Google + Apple) | 10h | completed |
| [Phase 4](phase-04-web-dashboard.md) | Web Dashboard (React SPA) | 8h | completed |

## Key Decisions

1. **Claude Agents SDK**: Full migration of ALL agents from agentic.py/llm.py to SDK
2. **Big Bang Migration**: Replace all at once (not gradual), aggressive approach
3. **SDK within Modal**: Keep Modal infrastructure, use SDK as library
4. **Native Trust Rules**: SDK Hooks (PreToolUse) replace custom trust_rules.py
5. **Native Undo**: SDK Checkpointing replaces L1/L2 undo queue
6. **Unified Model**: Merge `reminders.py` → `pkm.py` with `SmartTask` dataclass
7. **NLP Strategy**: LLM for intent + `dateparser` for temporal (skip spaCy for MVP)
8. **Calendar Sync**: Firebase as source of truth, Python libraries (not MCP)
9. **Dashboard Auth**: Telegram Login Widget → Firebase Custom Token

## Dependencies

- Google Cloud project (Calendar + Tasks API enabled)
- Apple app-specific password for CalDAV
- Vercel account for dashboard hosting
- Firebase Firestore (already configured)

## Research Reports

- [NLP Parsing Research](research/researcher-nlp-parsing.md)
- [Calendar APIs Research](research/researcher-calendar-apis.md)

## Success Metrics

| Metric | Target |
|--------|--------|
| Task capture time | < 3 seconds |
| NLP parsing accuracy | > 90% common patterns |
| Calendar sync latency | < 30 seconds |
| Dashboard load time | < 2 seconds |

## Validation Summary

**Validated:** 2026-01-01
**Questions asked:** 7

### Confirmed Decisions

| Decision | User Choice | Impact |
|----------|-------------|--------|
| Reminders migration | Hard cutover | Delete `reminders.py` completely, no backward compat |
| Task extraction scope | All groups | Extract tasks from group chats (high noise risk) |
| Recurrence complexity | Full RRULE | Implement `dateutil.rrule` for complex patterns |
| Dashboard location | Monorepo subfolder | Create `agents/dashboard/` |
| Undo queue storage | Hybrid L1/L2 | Memory for speed, Firebase for durability |
| Timeline view | Include in MVP | Add Gantt-style timeline to Phase 4 |
| Apple CalDAV auth | Research first | Research OAuth alternatives before implementing |

### Action Items (Plan Updates Needed)

- [x] Phase 1: Remove backward compatibility code for reminders.py
- [x] Phase 2: Add group chat extraction with noise filtering
- [ ] Phase 3: Expand RRULE implementation, add research task for Apple auth
- [ ] Phase 4: Keep Timeline view in MVP scope, update path to `agents/dashboard/`
- [x] All phases: Replace "Clawdis" branding with "ai4u.now"
- [x] Create Phase 0: SDK Foundation

## Unresolved Questions

1. ~~Apple credentials: App-specific passwords vs OAuth?~~ → Research first
2. ~~Dashboard domain: Subdomain or separate?~~ → Monorepo subfolder
3. Offline support: Service workers for dashboard?
4. Mobile app: React Native in scope for future?
5. Group chat noise: How to filter actionable items from casual conversation?
