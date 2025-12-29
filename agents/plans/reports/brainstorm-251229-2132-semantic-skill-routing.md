# Brainstorm: Semantic Skill Routing for Telegram Bot

**Date:** 2025-12-29
**Status:** Agreed
**Priority:** High

## Problem Statement

Current Telegram bot has limited skill routing:
- `simple` mode → Haiku direct response
- `routed` mode → Qdrant skill search (explicit mode only)
- `auto` mode → Complexity detection only (chat vs orchestrator)

**Gap:** Auto mode doesn't semantically detect when user wants a specific skill like `gemini-deep-research`, `canvas-design`, etc.

## Requirements

1. **Automatic skill detection** from natural language ("do deep research on X" → gemini-deep-research)
2. **Explicit invocation** via `/skill_name` or `@skill_name` syntax
3. **All 53 skills** should be semantically invocable
4. **Hybrid approach:** Intent classifier + Vector search

## Evaluated Approaches

### Option A: Single-Stage Intent Classifier
- Modify `classify_complexity()` → `classify_intent()`
- Return: `chat`, `skill:{name}`, or `orchestrate`
- **Pros:** Single LLM call
- **Cons:** LLM can't know all 53 skills reliably

### Option B: Two-Stage Classification ✅ SELECTED
- Stage 1: Intent classifier (Haiku) → `chat` | `skill` | `orchestrate`
- Stage 2: If `skill`, Qdrant vector search for best match
- **Pros:** Best accuracy, uses existing Qdrant infrastructure
- **Cons:** Extra latency for skill detection (~100ms)

### Option C: Pure Vector Search
- Always run Qdrant, use confidence thresholds
- **Pros:** No extra LLM call
- **Cons:** May miss nuanced intent, false positives

## Final Solution: Two-Stage Semantic Router

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MESSAGE RECEIVED                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  EXPLICIT CHECK: /skill or @skill prefix?                   │
│  Yes → Extract skill name → Qdrant search → Execute         │
│  No  → Continue to intent classification                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  INTENT CLASSIFIER (Haiku, ~50ms)                           │
│  Analyze message → Return intent type                       │
│                                                              │
│  CHAT      → Simple greeting, quick question                │
│  SKILL     → User wants specific capability                 │
│  ORCHESTRATE → Complex multi-step task                      │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌─────────┐    ┌─────────────┐  ┌─────────────┐
        │  CHAT   │    │   SKILL     │  │ ORCHESTRATE │
        │ Haiku   │    │ Qdrant →    │  │ Full        │
        │ direct  │    │ Execute     │  │ Orchestrator│
        └─────────┘    └─────────────┘  └─────────────┘
```

### Intent Classifier Prompt

```python
INTENT_PROMPT = """Classify this message into ONE of three categories:

CHAT: greeting, simple question, casual conversation, quick lookup
SKILL: user wants a specific capability (research, code, design, image, translate, summarize)
ORCHESTRATE: complex multi-step task, planning, building something

Message: {message}

Reply with only: CHAT, SKILL, or ORCHESTRATE"""
```

### Skill Categories for Intent Hints

| Trigger Keywords | Skill Category |
|-----------------|----------------|
| research, investigate, deep dive | gemini-deep-research |
| design, create visual, poster | canvas-design |
| code, implement, debug, fix | backend-development, frontend-development |
| translate, convert language | telegram-chat (built-in) |
| summarize, tldr | content, ai-multimodal |
| image, photo, picture | image-enhancer, ai-artist |
| video, download | video-downloader |

### Explicit Invocation Patterns

```
/research topic        → gemini-deep-research
@research topic        → gemini-deep-research
/code write a function → backend-development
@design create poster  → canvas-design
```

## Implementation Plan

### Phase 1: Intent Classifier (1h)
- Create `src/core/intent.py` with `classify_intent()`
- Three-way classification: CHAT, SKILL, ORCHESTRATE
- Use Haiku for speed (~50ms)

### Phase 2: Explicit Skill Detection (30min)
- Add regex detection for `/skill_name` and `@skill_name`
- Extract skill name → fuzzy match against registry
- Bypass intent classifier for explicit invocations

### Phase 3: Update Auto Mode Routing (1h)
- Modify `process_message()` in main.py
- Intent → Router → Execute flow
- Integrate with existing SkillRouter + Qdrant

### Phase 4: Skill Description Enhancement (30min)
- Ensure all 53 skills have good descriptions for vector matching
- Add trigger keywords to skill metadata

## Files to Modify

| File | Changes |
|------|---------|
| `src/core/intent.py` | NEW - Intent classifier |
| `src/core/complexity.py` | Update or deprecate |
| `main.py:1550-1580` | Update auto mode routing |
| `src/core/router.py` | Add explicit skill parsing |

## Success Metrics

1. **Accuracy:** >90% correct skill detection for explicit intents
2. **Latency:** <200ms total intent + routing time
3. **Coverage:** All 53 skills semantically accessible
4. **Fallback:** Graceful degradation to chat if no skill match

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| False positive skill matches | Confidence threshold (>0.7) |
| Slow intent classification | Use Haiku, cache common patterns |
| Qdrant unavailable | Fallback to keyword matching |
| User expects wrong skill | Show skill name before execution |

## Next Steps

1. Create implementation plan with `/plan`
2. Implement Phase 1-4 sequentially
3. Test with diverse message samples
4. Deploy and monitor

## Unresolved Questions

1. Should we show "Using skill: X" before execution for transparency?
2. Minimum confidence score for auto skill selection (0.7? 0.8?)?
3. Should explicit `/skill` commands skip confirmation?
