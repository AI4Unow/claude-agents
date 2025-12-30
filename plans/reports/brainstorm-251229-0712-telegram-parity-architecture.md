# Brainstorm: Telegram Parity Architecture

**Date:** Dec 29, 2025
**Goal:** Telegram parity with API - full skill execution, orchestration, monitoring via Telegram

## Problem Statement

Current Telegram bot has basic commands but lacks:
- Chained/orchestrated skill execution
- Admin monitoring (traces, circuits)
- Token-based authentication tiers
- Semantic auto-orchestration (like Claude Code)

**Target:** Power users can do everything via Telegram that API supports.

## Requirements Gathered

| Aspect | Decision |
|--------|----------|
| Scope | Telegram parity with API |
| Users | End users, developers, admin |
| Priority | Power user features first |
| UX Pattern | Hybrid: Menu for discovery, commands for power users |
| Orchestration | Semantic auto-detect (like Claude Code) |
| Auth | One-time token link to Telegram ID |
| Progress | Sequential messages, verbose skill visibility |

## Evaluated Approaches

### Approach 1: Command-Heavy
**Description:** Add more commands for each feature.

**Pros:**
- Simple to implement
- Fast for experienced users
- No state management complexity

**Cons:**
- Verbose, hard to discover
- Not intuitive for new users
- Doesn't leverage Telegram's rich UI

**Verdict:** ❌ Rejected - too verbose

### Approach 2: Menu-Driven UI
**Description:** Extensive use of inline keyboards and state machine.

**Pros:**
- Rich, discoverable UX
- Visual workflow
- Good for complex flows

**Cons:**
- 64-byte callback limit forces Firebase state
- Complex implementation
- Slower for power users

**Verdict:** ⚠️ Partial - good for discovery, not power users

### Approach 3: Hybrid (Selected)
**Description:** Menu for discovery/browsing + commands for power users + semantic orchestration.

**Pros:**
- Best of both worlds
- Progressive complexity
- Matches Claude Code UX philosophy

**Cons:**
- More code to maintain
- Need complexity detector

**Verdict:** ✅ Selected

## Final Architecture

### Core: Intelligent Telegram Agent

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    INTELLIGENT TELEGRAM INTERFACE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  USER MESSAGE                                                                │
│       │                                                                      │
│       ▼                                                                      │
│  ┌──────────────────────┐                                                    │
│  │ COMPLEXITY DETECTOR  │ ← LLM classifies: simple chat vs complex task     │
│  │ (fast, cheap model)  │                                                    │
│  └──────────┬───────────┘                                                    │
│             │                                                                │
│    ┌────────┴────────┐                                                       │
│    ▼                 ▼                                                       │
│  Simple             Complex                                                  │
│    │                   │                                                     │
│    ▼                   ▼                                                     │
│  Direct LLM         Orchestrator                                             │
│  Response           (multi-skill)                                            │
│    │                   │                                                     │
│    │                   ├── 🔧 Using: planning...                             │
│    │                   ├── 📝 Result: [plan]                                 │
│    │                   ├── 🔧 Using: code-review...                          │
│    │                   ├── 📝 Result: [review]                               │
│    ▼                   ▼                                                     │
│  Single Message     Sequential Messages                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Command Structure

| Command | Purpose | Tier |
|---------|---------|------|
| `/auth <token>` | Link Telegram ID to tier | guest |
| `/skill <name> <task>` | Direct skill execution | user |
| `/skills` | Browse skills (menu) | user |
| `/mode <simple\|routed\|auto>` | Set default mode | user |
| `/traces [limit]` | View execution traces | developer |
| `/trace <id>` | Trace details | developer |
| `/circuits` | Circuit breaker status | developer |
| `/task <id>` | Local task status | user |
| `/admin reset <circuit>` | Reset circuit | admin |

### Auth Tiers

| Tier | Access | How to Get |
|------|--------|------------|
| `guest` | Chat only, no skills | Default |
| `user` | Skills, auto-orchestration | Token from admin |
| `developer` | + traces, circuits, task status | Token from admin |
| `admin` | + reset circuits, system control | ADMIN_TELEGRAM_ID env |

### Firebase Schema Additions

```javascript
user_tiers/{telegram_id}: {
  tier: "developer",
  auth_token_hash: "sha256...",  // Never store raw token
  linked_at: timestamp,
  last_active: timestamp
}

auth_tokens/{token_hash}: {
  tier: "developer",
  created_by: admin_id,
  created_at: timestamp,
  used: false,
  used_by: null
}
```

### Complexity Detector

Fast classification using small model (e.g., haiku or groq/llama):

```python
COMPLEXITY_PROMPT = """
Classify this message as SIMPLE or COMPLEX:
- SIMPLE: greeting, question, quick info, single action
- COMPLEX: multi-step task, planning needed, code/analysis required

Message: {message}
Classification:
"""
```

### Progress Messages Format

```
🔧 Using: planning
━━━━━━━━━━━━━━━━━━━

📝 Plan: Authentication System
1. Design user model
2. Implement JWT tokens
3. Add middleware
...

🔧 Using: code-review
━━━━━━━━━━━━━━━━━━━

📝 Review: Looks good, consider:
- Add rate limiting
- Use bcrypt for passwords

✅ Task Complete (3 skills, 12.4s)
```

## Implementation Phases

### Phase 1: Auth System (1-2 days)
- `/auth <token>` command
- Firebase token/tier storage
- Tier-based command filtering

### Phase 2: Admin Commands (1-2 days)
- `/traces`, `/trace <id>` for developers
- `/circuits`, `/admin reset` for admins
- `/task <id>` for all users

### Phase 3: Complexity Detector (2-3 days)
- Implement fast classifier
- Add `/mode auto` command
- Route to orchestrator vs direct response

### Phase 4: Semantic Orchestration (3-5 days)
- Modify orchestrator for Telegram output
- Sequential message emission
- Verbose skill visibility

### Phase 5: Polish (1-2 days)
- Error handling
- Rate limiting per tier
- Help text updates

**Total: ~10-15 days**

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Complexity detector inaccurate | Poor UX | Explicit `/auto` fallback |
| Token leakage | Security breach | Hash tokens, no logs |
| Message flood from orchestrator | Telegram rate limit | Throttle, batch small results |
| Firebase state complexity | Bugs | Clear state machine, tests |

## Success Metrics

1. **Parity:** All API features accessible via Telegram
2. **Adoption:** 80%+ of API usage shifts to Telegram within 1 month
3. **UX:** <3 steps to execute any skill
4. **Performance:** Complex tasks complete within 60s

## Next Steps

1. Create detailed implementation plan
2. Start with Phase 1 (Auth System)
3. Progressive rollout with testing

---

## Unresolved Questions

None - all requirements clarified during brainstorm.
