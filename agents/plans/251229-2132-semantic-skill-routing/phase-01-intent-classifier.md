# Phase 1: Intent Classifier

## Context

- Parent: [plan.md](plan.md)
- Pattern: [complexity.py](../../src/core/complexity.py) - follow same structure
- Brainstorm: [brainstorm-251229-2132-semantic-skill-routing.md](../reports/brainstorm-251229-2132-semantic-skill-routing.md)

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-29 |
| Priority | P1 |
| Effort | 1h |
| Status | pending |
| Review | pending |

Create `src/core/intent.py` with three-way intent classification: CHAT, SKILL, ORCHESTRATE.

## Key Insights

- Follow complexity.py pattern: fast keyword check → LLM fallback
- Use Haiku for speed (~50ms)
- SKILL intent = user wants specific capability (research, design, code)
- CHAT intent = greeting, simple question, casual conversation
- ORCHESTRATE intent = multi-step task, building something

## Requirements

1. `IntentType = Literal["chat", "skill", "orchestrate"]`
2. `classify_intent(message: str) -> IntentType`
3. Fast keyword patterns before LLM call
4. Async wrapper for main.py integration

## Architecture

```python
# Fast path keywords
SKILL_KEYWORDS = {"research", "design", "code", "generate", "create image", "summarize", "translate"}
ORCHESTRATE_KEYWORDS = {"build", "plan", "develop", "architect", "implement system"}
CHAT_PATTERNS = [r"^(hi|hello|hey)...", r"^what is ", ...]

def fast_intent_check(msg) -> IntentType | None:
    # Check patterns first
    # Return None if needs LLM

def classify_intent_sync(msg) -> IntentType:
    fast = fast_intent_check(msg)
    if fast: return fast
    # LLM classification with Haiku

async def classify_intent(msg) -> IntentType:
    return await asyncio.to_thread(classify_intent_sync, msg)
```

## Related Code Files

- `src/core/complexity.py` - Pattern to follow
- `src/services/llm.py` - LLM client usage
- `src/core/resilience.py` - Circuit breaker check

## Implementation Steps

1. Create `src/core/intent.py` file
2. Define IntentType literal type
3. Define SKILL_KEYWORDS, ORCHESTRATE_KEYWORDS sets
4. Define CHAT_PATTERNS list (regex)
5. Implement `fast_intent_check()` function
6. Define INTENT_PROMPT for LLM classification
7. Implement `classify_intent_sync()` with Haiku call
8. Implement async `classify_intent()` wrapper
9. Add logging for intent classification

## Todo List

- [ ] Create intent.py with type definitions
- [ ] Add fast keyword/pattern checks
- [ ] Implement LLM classification with Haiku
- [ ] Add async wrapper
- [ ] Add logging

## Success Criteria

- [ ] Fast path works for obvious intents (<1ms)
- [ ] LLM path works for ambiguous messages (~50ms)
- [ ] Returns correct intent for test messages
- [ ] Graceful fallback to CHAT on error

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM misclassifies | Medium | Conservative defaults, tune prompt |
| Circuit open | Low | Default to CHAT |
| Latency spike | Medium | Fast path for common patterns |

## Security Considerations

- No user data persisted in classification
- Truncate message to 500 chars for LLM

## Next Steps

After Phase 1 complete → Phase 2: Explicit Skill Detection
