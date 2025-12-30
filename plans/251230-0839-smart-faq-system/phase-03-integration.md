# Phase 3: Integration

## Context
- Parent: [plan.md](./plan.md)
- Depends on: [Phase 1](./phase-01-faq-core.md), [Phase 2](./phase-02-qdrant-collection.md)

## Overview
- **Date:** 2025-12-30
- **Description:** Integrate FAQ matcher into message processing flow
- **Priority:** P1
- **Implementation Status:** pending
- **Review Status:** pending

## Key Insights
- FAQ check MUST happen BEFORE intent classification
- FAQ match = instant return (no LLM)
- Log FAQ hits for analytics/monitoring

## Requirements
1. Check FAQ before intent classification
2. Return FAQ answer directly if match
3. Log hits for monitoring

## Architecture

```
process_message()
    ↓
FAQ Check (get_faq_matcher().match())
    ↓ match found
Return FAQ answer immediately
    ↓ no match
Intent Classification (existing flow)
    ↓
Skill/Chat/Orchestrate
```

## Related Code Files
- `main.py` - Modify process_message() function

## Implementation Steps

### 1. Locate Integration Point (main.py)
```python
# In process_message() - around line 1550
# BEFORE intent classification, add:

async def process_message(text: str, user: dict, chat_id: int) -> str:
    """Process incoming message."""
    from src.core.faq import get_faq_matcher

    # 1. Check FAQ first (fastest path)
    faq_matcher = get_faq_matcher()
    faq_answer = await faq_matcher.match(text)
    if faq_answer:
        logger.info("faq_response", user_id=user.get("id"))
        return faq_answer

    # 2. Existing flow: mode check, intent classification, etc.
    mode = await state.get_user_mode(user.get("id"))
    ...
```

### 2. Add Logging/Analytics
```python
# In faq.py match() method
async def match(self, message: str) -> Optional[str]:
    """Hybrid match with logging."""
    start = time.time()

    # Keyword match
    answer = await self.match_keyword(message)
    if answer:
        duration_ms = int((time.time() - start) * 1000)
        logger.info("faq_hit",
            match_type="keyword",
            duration_ms=duration_ms,
            message_preview=message[:50]
        )
        return answer

    # Semantic match
    answer = await self.match_semantic(message)
    if answer:
        duration_ms = int((time.time() - start) * 1000)
        logger.info("faq_hit",
            match_type="semantic",
            duration_ms=duration_ms,
            message_preview=message[:50]
        )
        return answer

    return None
```

### 3. Handle Edge Cases
```python
# Skip FAQ for:
# - Commands (start with /)
# - Very long messages (>200 chars likely not FAQ)
# - Messages with attachments

async def process_message(text: str, user: dict, chat_id: int) -> str:
    # Skip FAQ for commands
    if text.startswith('/'):
        return await handle_command(text, user, chat_id)

    # Skip FAQ for long messages
    if len(text) <= 200:
        faq_answer = await get_faq_matcher().match(text)
        if faq_answer:
            return faq_answer

    # Normal flow
    ...
```

## Todo List
- [ ] Add FAQ check at start of process_message()
- [ ] Skip FAQ for commands and long messages
- [ ] Add timing logs for FAQ hits
- [ ] Test integration with sample queries
- [ ] Verify FAQ bypass for /commands

## Success Criteria
- "who are you" returns FAQ answer (no LLM)
- /start still works (FAQ skipped)
- Long questions go to LLM
- Logs show FAQ hits with timing

## Risk Assessment
- **FAQ error:** Try/except with fallback to LLM
- **Performance regression:** FAQ adds <5ms if no match

## Security Considerations
- No new security concerns
- FAQ answers are public

## Next Steps
→ [Phase 4: Admin Commands](./phase-04-admin-commands.md)
