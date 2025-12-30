# Telegram Bot Personalization Implementation Plan

**Created:** 2025-12-30
**Branch:** feature/telegram-personalization
**Brainstorm:** plans/reports/brainstorm-251230-0822-telegram-personalization.md
**Status:** Ready for Implementation

## Overview

Implement a 4-pillar personalization system for the Telegram bot:
1. **User Profiles** - Tone, domain, tech stack preferences
2. **Work Context** - Current project, task, session facts
3. **Personal Macros** - NLU-triggered shortcuts
4. **Activity Learning** - Patterns, predictions, suggestions

## Architecture Summary

```
User Message → PersonalContextLoader → Macro Detection → Personalized Prompt → Execute + Learn
                    │                       │
                    ├─ Firebase: profiles   ├─ Exact match
                    ├─ Firebase: contexts   └─ Semantic similarity
                    ├─ Firebase: macros
                    └─ Qdrant: memories
```

## Implementation Phases

| Phase | Name | Duration | Files |
|-------|------|----------|-------|
| 1 | Core Infrastructure | 3-4 days | personalization.py, models.py |
| 2 | Profile & Context | 2-3 days | user_profile.py, user_context.py |
| 3 | Macros & NLU | 2-3 days | user_macros.py, macro_executor.py |
| 4 | Activity Learning | 2-3 days | activity.py, suggestions.py |

**Total estimated:** 10-13 days

## Success Criteria

- [ ] Profile onboarding works for new users
- [ ] Work context auto-updates from activity
- [ ] Macros trigger via natural language
- [ ] Proactive suggestions based on patterns
- [ ] Latency impact < 100ms per request

## Phase Details

See individual phase files:
- `phase-01-core-infrastructure.md`
- `phase-02-profile-context.md`
- `phase-03-macros-nlu.md`
- `phase-04-activity-learning.md`

## Critical Integration Points

### 1. main.py:process_message() Modification

```python
# Current flow (line 1514-1666):
async def process_message(text, user, chat_id, message_id):
    tier = await state.get_user_tier_cached(user_id)
    # ... routing logic ...

# New flow:
async def process_message(text, user, chat_id, message_id):
    # Load personalization FIRST (parallel)
    personal_ctx = await load_personal_context(user.get("id"))

    # Check macro BEFORE any routing
    macro = await detect_macro(user.get("id"), text)
    if macro:
        return await execute_macro(macro, user, chat_id)

    # Build personalized system prompt
    personalized_system = build_personalized_prompt(personal_ctx)

    # Existing routing with personalized context
    # ...

    # Post-execution: Learn
    await log_activity(user.get("id"), ...)
    await update_work_context(user.get("id"), text, skill_used)
```

### 2. New Firebase Collections

```
user_profiles/{telegram_id}     # Static preferences
user_contexts/{telegram_id}     # Session/work state
user_macros/{telegram_id}       # Personal shortcuts (subcollection: /macros)
user_activities/{telegram_id}   # For Firebase-based patterns
```

### 3. New Qdrant Collection

```python
# Add to qdrant.py COLLECTIONS dict
"user_activities": "User activity patterns for learning"
```

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Prompt bloat | Token budget per layer (profile: 100, context: 150, memories: 200) |
| Firebase reads | L1 cache TTL 5min for profile/context |
| NLU accuracy | Fallback to exact match, threshold 0.85 |
| Context staleness | 2h session timeout auto-clear |

## New Commands (Phase 2-4)

| Command | Phase | Description |
|---------|-------|-------------|
| `/profile` | 2 | View/edit preferences |
| `/context` | 2 | View/clear work context |
| `/macro add` | 3 | Create macro |
| `/macro list` | 3 | List macros |
| `/macro remove` | 3 | Delete macro |
| `/activity` | 4 | View recent activity |
| `/suggest` | 4 | Get proactive suggestion |
| `/forget` | 4 | Delete all personal data |

## File Structure

```
agents/src/
├── services/
│   ├── personalization.py    # PersonalContextLoader, PromptBuilder
│   ├── user_profile.py       # Profile CRUD + onboarding
│   ├── user_context.py       # Work context management
│   ├── user_macros.py        # Macro CRUD + NLU matching
│   └── activity.py           # Activity logging & patterns
├── core/
│   ├── macro_executor.py     # Macro execution (command/skill/sequence)
│   └── suggestions.py        # Proactive suggestion engine
└── models/
    └── personalization.py    # Dataclasses: UserProfile, WorkContext, Macro
```

## Testing Strategy

1. **Unit tests:** Profile/context CRUD, macro detection
2. **Integration tests:** Full personalization flow
3. **Manual testing:** Telegram bot onboarding, macro triggers
