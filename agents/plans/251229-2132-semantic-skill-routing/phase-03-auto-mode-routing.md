# Phase 3: Auto Mode Routing Update

## Context

- Parent: [plan.md](plan.md)
- Depends on: Phase 1 (intent.py), Phase 2 (explicit detection)
- Target: `main.py:1550-1580` - current auto mode logic

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-29 |
| Priority | P1 |
| Effort | 1h |
| Status | pending |
| Review | pending |

Update `process_message()` auto mode to use new intent classification and explicit skill detection.

## Key Insights

- Current auto mode only does simple/complex routing
- Need to add SKILL intent that triggers SkillRouter
- Explicit skill commands bypass all classification
- Keep existing _run_simple, _run_routed, _run_orchestrated functions

## Requirements

1. Check explicit skill first (/skill, @skill)
2. If explicit → execute skill directly via execute_skill_simple()
3. Else classify intent (CHAT/SKILL/ORCHESTRATE)
4. Route based on intent

## Architecture

```python
# In main.py process_message(), around line 1550

if mode == "auto":
    from src.core.intent import classify_intent
    from src.core.router import SkillRouter, parse_explicit_skill

    # Check explicit skill first
    explicit = parse_explicit_skill(text, get_registry())
    if explicit:
        skill_name, remaining_text = explicit
        await edit_progress_message(chat_id, progress_msg_id, f"🎯 <i>{skill_name}</i>")
        result = await execute_skill_simple(skill_name, remaining_text, {"user": user})
        from src.services.telegram import format_skill_result
        response = format_skill_result(skill_name, result, 0)
    else:
        # Intent classification
        await edit_progress_message(chat_id, progress_msg_id, "🧠 <i>Analyzing...</i>")
        intent = await classify_intent(text)
        logger.info("intent_detected", intent=intent, mode=mode)

        if intent == "orchestrate":
            await edit_progress_message(chat_id, progress_msg_id, "🔧 <i>Orchestrating...</i>")
            response = await _run_orchestrated(text, user, chat_id, progress_msg_id)
        elif intent == "skill":
            await edit_progress_message(chat_id, progress_msg_id, "🔍 <i>Finding skill...</i>")
            router = SkillRouter()
            skill = await router.route_single(text)
            if skill:
                await edit_progress_message(chat_id, progress_msg_id, f"🎯 <i>{skill.name}</i>")
                result = await execute_skill_simple(skill.name, text, {"user": user})
                response = format_skill_result(skill.name, result, 0)
            else:
                # No skill found, fall back to chat
                response = await _run_simple(text, user, chat_id, progress_msg_id, update_progress, model="kiro-claude-haiku-4-5-agentic")
        else:
            # CHAT intent
            response = await _run_simple(text, user, chat_id, progress_msg_id, update_progress, model="kiro-claude-haiku-4-5-agentic")
```

## Related Code Files

- `main.py:1550-1580` - Current routing logic
- `src/core/intent.py` - New intent classifier (Phase 1)
- `src/core/router.py` - SkillRouter + explicit parsing (Phase 2)
- `src/skills/registry.py` - get_registry()

## Implementation Steps

1. Import new modules at top of auto mode block
2. Add explicit skill check before intent classification
3. If explicit, execute skill directly
4. Else call classify_intent()
5. Route based on intent: CHAT → _run_simple, SKILL → SkillRouter, ORCHESTRATE → _run_orchestrated
6. Add progress messages for each path
7. Handle skill not found fallback

## Todo List

- [ ] Add explicit skill check
- [ ] Replace complexity with intent classification
- [ ] Add SKILL intent → SkillRouter flow
- [ ] Add progress messages
- [ ] Handle fallback cases

## Success Criteria

- [ ] `/research quantum` executes gemini-deep-research
- [ ] "research quantum computing" auto-routes to research skill
- [ ] "hello" stays on CHAT → Haiku
- [ ] "build me an API" goes to ORCHESTRATE

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing flow | High | Test thoroughly before deploy |
| Skill not found | Medium | Graceful fallback to chat |
| Wrong skill matched | Medium | Show skill name in progress |

## Security Considerations

- Maintain tier checks for skill execution
- No new permissions needed

## Next Steps

After Phase 3 complete → Phase 4: Testing & Deployment
