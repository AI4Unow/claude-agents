# Telegram Bot Personalization Architecture

**Type:** Brainstorm Report
**Date:** 2025-12-30
**Status:** Ready for Implementation

## Problem Statement

Make the Telegram bot UI/UX more personal to each user with:
- Tone & style adaptation
- Context memory across sessions
- Proactive features & suggestions
- Custom workflows/macros

## Current State

| Component | Status | Gap |
|-----------|--------|-----|
| User tiers | `user_tiers/{id}` | Only tier, no profile |
| Conversations | Qdrant `conversations` | Not injected into prompts |
| Mode preference | `state.get_user_mode()` | Just mode selection |
| Memory search | Tool available | Not auto-retrieved |

## Requirements Gathered

- **Profile setup:** Hybrid (auto-detect + manual override)
- **Data storage:** Full history (user trusts platform)
- **Macro trigger:** NLU-based natural language ("deploy as usual")
- **Effort level:** Full system (1-2 week investment)

---

## Solution: Multi-Layer Context System

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Request Flow                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  User Message                                            │
│       │                                                  │
│       ▼                                                  │
│  ┌─────────────────┐                                     │
│  │ PersonalContext │ ◀── Firebase + Qdrant              │
│  │    Loader       │     (parallel fetch)               │
│  └────────┬────────┘                                     │
│           │                                              │
│           ├── user_profiles/{id}  → Preferences         │
│           ├── user_contexts/{id}  → Work state          │
│           ├── user_macros/{id}    → Personal shortcuts  │
│           └── Qdrant memories     → Past interactions   │
│           │                                              │
│           ▼                                              │
│  ┌─────────────────┐                                     │
│  │  Macro Detector │ ◀── NLU intent match               │
│  └────────┬────────┘                                     │
│           │                                              │
│     ┌─────┴─────┐                                        │
│     │           │                                        │
│   Macro?     Normal?                                     │
│     │           │                                        │
│     ▼           ▼                                        │
│  Execute    ┌─────────────┐                              │
│  stored     │ Personalized │                             │
│  action     │ System Prompt│                             │
│             └──────┬──────┘                              │
│                    │                                     │
│                    ▼                                     │
│             ┌─────────────┐                              │
│             │   Execute   │                              │
│             │  + Learn    │                              │
│             └─────────────┘                              │
│                    │                                     │
│                    ▼                                     │
│             Update activity patterns                     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Data Models

#### 1. User Profile (`user_profiles/{telegram_id}`)

```python
{
    "name": "Nad",
    "timezone": "Asia/Ho_Chi_Minh",
    "language": "en",
    "tone": "concise",           # concise | detailed | casual | formal
    "domain": ["fintech", "saas"],
    "tech_stack": ["python", "typescript", "modal.com"],
    "communication": {
        "use_emoji": false,
        "markdown_preference": true,
        "response_length": "short"  # short | medium | long
    },
    "onboarded": true,
    "onboarded_at": "2025-12-30T08:00:00Z",
    "updated_at": "2025-12-30T08:00:00Z"
}
```

#### 2. Work Context (`user_contexts/{telegram_id}`)

```python
{
    "current_project": "claude-agents",
    "current_task": "telegram personalization",
    "active_branch": "feature/personalization",
    "recent_skills": ["planning", "research", "debugging"],
    "session_facts": [
        "working on Modal.com deployment",
        "using Firebase for persistence"
    ],
    "last_active": "2025-12-30T08:00:00Z",
    "session_start": "2025-12-30T07:30:00Z"
}
```

#### 3. Personal Macros (`user_macros/{telegram_id}/macros/{macro_id}`)

```python
{
    "trigger_phrases": ["deploy", "deploy as usual", "ship it"],
    "action_type": "command",          # command | skill | sequence
    "action": "modal deploy agents/main.py",
    "description": "Deploy to Modal.com production",
    "created_at": "2025-12-30T08:00:00Z",
    "use_count": 42
}
```

Macro types:
- `command`: Execute bash command
- `skill`: Invoke specific skill with params
- `sequence`: Run multiple actions in order

#### 4. Activity Patterns (`user_activities` Qdrant collection)

```python
{
    "user_id": telegram_id,
    "action_type": "skill_invoke",
    "skill": "research",
    "request_summary": "research payment providers",
    "timestamp": "2025-12-30T08:00:00Z",
    "hour_of_day": 8,
    "day_of_week": 1,
    "duration_ms": 5000,
    "followed_by": ["planning", "code-review"]  # sequence tracking
}
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (3-4 days)

**Files to create:**
- `src/services/personalization.py` - PersonalContextLoader
- `src/services/user_profile.py` - Profile CRUD + onboarding
- `src/services/user_context.py` - Work context management
- `src/services/user_macros.py` - Macro CRUD + NLU matching

**Key functions:**
```python
# personalization.py
async def load_personal_context(user_id: int) -> PersonalContext:
    """Parallel load all personalization data."""
    profile, context, macros, memories = await asyncio.gather(
        get_user_profile(user_id),
        get_user_context(user_id),
        get_user_macros(user_id),
        search_relevant_memories(user_id, limit=3)
    )
    return PersonalContext(profile, context, macros, memories)

async def build_personalized_prompt(
    base_prompt: str,
    personal_ctx: PersonalContext
) -> str:
    """Inject personalization into system prompt."""
    sections = [base_prompt]

    if personal_ctx.profile:
        sections.append(format_profile_context(personal_ctx.profile))

    if personal_ctx.work_context:
        sections.append(format_work_context(personal_ctx.work_context))

    if personal_ctx.memories:
        sections.append(format_memory_context(personal_ctx.memories))

    return "\n\n".join(sections)
```

### Phase 2: Profile & Context (2-3 days)

**User profile onboarding flow:**
```
First message from new user:
  └── Auto-detect language from message
  └── Ask: "Quick question: How should I respond?
           [Concise] [Detailed] [Casual] [Formal]"
  └── Store preference, mark onboarded

/profile command:
  └── Show current settings
  └── Inline keyboard to modify each setting
```

**Work context detection:**
```python
async def update_work_context(user_id: int, message: str, skill_used: str):
    """Auto-update context from user activity."""
    # Extract project/task mentions
    if "working on" in message.lower():
        project = extract_project_name(message)
        await update_current_project(user_id, project)

    # Track recent skills
    await append_recent_skill(user_id, skill_used)

    # Extract facts using LLM
    facts = await extract_session_facts(message)
    await update_session_facts(user_id, facts)
```

### Phase 3: Macros & NLU (2-3 days)

**Macro management commands:**
- `/macro add "deploy" -> modal deploy agents/main.py`
- `/macro list` - Show all macros
- `/macro remove deploy`
- `/macro edit deploy`

**NLU macro detection:**
```python
async def detect_macro(user_id: int, message: str) -> Optional[Macro]:
    """Detect if message triggers a personal macro."""
    macros = await get_user_macros(user_id)

    if not macros:
        return None

    # Build trigger phrase list
    triggers = {phrase: macro for macro in macros
                for phrase in macro.trigger_phrases}

    # Exact match first
    lower_msg = message.lower().strip()
    if lower_msg in triggers:
        return triggers[lower_msg]

    # Semantic match via embedding similarity
    for phrase, macro in triggers.items():
        if semantic_similarity(lower_msg, phrase) > 0.85:
            return macro

    return None
```

### Phase 4: Activity Learning (2-3 days)

**Store activity patterns:**
```python
async def log_activity(user_id: int, activity: dict):
    """Log user activity to Qdrant for pattern analysis."""
    embedding = get_embedding(activity["request_summary"])

    await store_activity(
        user_id=user_id,
        action_type=activity["action_type"],
        skill=activity.get("skill"),
        summary=activity["request_summary"],
        embedding=embedding,
        timestamp=datetime.utcnow()
    )
```

**Proactive suggestions:**
```python
async def get_proactive_suggestion(user_id: int) -> Optional[str]:
    """Suggest based on patterns and pending items."""
    # Check pending reminders
    reminders = await get_due_reminders(user_id)
    if reminders:
        return f"Reminder: {reminders[0]['message']}"

    # Pattern-based: same time yesterday
    yesterday_activity = await get_activity_at_time(
        user_id,
        time=datetime.utcnow() - timedelta(days=1)
    )
    if yesterday_activity:
        return f"Yesterday you were working on: {yesterday_activity['summary']}"

    # Sequence prediction
    last_skill = await get_last_skill(user_id)
    if last_skill:
        common_next = await predict_next_skill(user_id, last_skill)
        if common_next:
            return f"Need {common_next}? You often use it after {last_skill}."

    return None
```

---

## Integration Points

### Modify `main.py:process_message()`

```python
async def process_message(text: str, user: dict, chat_id: int, message_id: int = None):
    # Load personalization FIRST
    personal_ctx = await load_personal_context(user.get("id"))

    # Check for macro trigger
    macro = await detect_macro(user.get("id"), text)
    if macro:
        return await execute_macro(macro, user, chat_id)

    # Personalized system prompt
    base_system = get_base_system_prompt()
    personalized_system = await build_personalized_prompt(base_system, personal_ctx)

    # Run agentic loop with personalized context
    response = await run_agentic_loop(
        user_message=text,
        system=personalized_system,
        user_id=user.get("id"),
        ...
    )

    # Learn from interaction
    await log_activity(user.get("id"), {
        "action_type": "chat",
        "request_summary": text[:100],
        "skill": detected_skill
    })

    # Update work context
    await update_work_context(user.get("id"), text, detected_skill)

    return response
```

### New Commands

| Command | Description |
|---------|-------------|
| `/profile` | View/edit personal preferences |
| `/profile reset` | Reset to defaults |
| `/context` | View current work context |
| `/context clear` | Clear session context |
| `/macro add` | Create personal macro |
| `/macro list` | List all macros |
| `/macro remove` | Delete macro |
| `/activity` | View recent activity |
| `/suggest` | Get proactive suggestion |
| `/forget` | Data deletion (GDPR) |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Response relevance | +30% | User feedback rating |
| Macro usage | 20% of requests | Activity logs |
| Context accuracy | 90%+ | Manual review |
| Latency impact | <100ms | Trace timing |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Prompt bloat | Token budget per layer, summarize long contexts |
| Firebase read cost | L1 cache (TTL 5min) for profile, context |
| Privacy concerns | `/forget` command, clear data controls |
| Macro abuse | Rate limit macros, admin approval for dangerous actions |
| Context drift | Session timeout (2h inactivity clears context) |

---

## File Structure

```
agents/src/
├── services/
│   ├── personalization.py    # PersonalContextLoader
│   ├── user_profile.py       # Profile CRUD
│   ├── user_context.py       # Work context
│   └── user_macros.py        # Macro management
├── core/
│   └── macro_executor.py     # Macro execution logic
└── tools/
    └── personal_memory.py    # User-scoped memory search
```

---

## Next Steps

1. **Create implementation plan** with phase breakdown
2. **Review Firebase schema** for cost optimization
3. **Design onboarding UX** (inline keyboards vs. conversation)
4. **Implement Phase 1** core infrastructure

---

## Unresolved Questions

1. Should macros be shared/copied between users? (template macros)
2. Max macros per user? (suggest 20)
3. Session timeout for work context? (suggest 2 hours)
4. Store raw messages or only summaries in activity log?
