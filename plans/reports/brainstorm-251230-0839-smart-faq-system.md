# Brainstorm: Smart FAQ System

**Date:** 2025-12-30
**Status:** Agreed

## Problem Statement

Current issues:
1. Claude model leaks "I'm Claude made by Anthropic" identity despite system prompts
2. Simple questions (who are you, what can you do) waste LLM tokens and add latency
3. No guarantee of consistent branded responses

## Requirements

- Handle identity, capabilities, troubleshooting, onboarding questions
- Sub-100ms response time for FAQ matches
- Zero LLM cost for matched questions
- Runtime editable by admin
- Graceful fallback to LLM if no match

## Evaluated Approaches

### Option 1: Keyword/Regex Only
**Pros:** Fastest (~5ms), deterministic, easy to debug
**Cons:** Limited flexibility, requires exact patterns, maintenance burden

### Option 2: Semantic Embedding Only
**Pros:** Natural language understanding, handles variations
**Cons:** Slower (~50-100ms), requires Qdrant call, potential false positives

### Option 3: Hybrid (Keyword → Embedding) ✅ SELECTED
**Pros:** Best of both worlds - fast for exact matches, flexible fallback
**Cons:** Slightly more complex, two matching stages

## Final Solution

### Architecture
```
Message → Keyword/Regex Check (~5ms)
    ↓ no match
Qdrant FAQ Collection Search (~50ms, threshold=0.9)
    ↓ no match
Normal LLM Flow (intent classification → skill/chat)
```

### Storage: Firebase
- Collection: `faq_entries`
- Fields: `id`, `patterns[]`, `answer`, `embedding[]`, `category`, `enabled`, `updated_at`
- Indexed by patterns for O(1) lookup
- Embeddings synced to Qdrant for semantic search

### FAQ Categories
1. **Identity:** who are you, who made you, what are you
2. **Capabilities:** what can you do, list skills, features
3. **Commands:** how to use /skill, /translate, /summarize
4. **Troubleshooting:** error handling, rate limits, timeouts
5. **Onboarding:** getting started, first steps

### Example FAQ Entry
```json
{
  "id": "identity-who-are-you",
  "patterns": ["who are you", "what are you", "introduce yourself"],
  "answer": "I'm AI4U.now Bot, a unified AI assistant created by the AI4U.now team. I provide access to multiple AI models (Gemini, Claude, GPT) through a single Telegram interface with 50+ specialized skills.",
  "category": "identity",
  "enabled": true
}
```

### Matching Logic
1. Normalize input: lowercase, strip punctuation
2. Check exact keyword matches in Firebase cache
3. If no match: Qdrant similarity search (threshold 0.9)
4. If match found: return FAQ answer directly (no LLM)
5. If no match: proceed to normal flow

### Implementation Components
1. `src/core/faq.py` - FAQ matcher class
2. Firebase collection + cache layer
3. Qdrant FAQ collection for embeddings
4. Admin commands: `/faq add`, `/faq edit`, `/faq list`

## Success Metrics
- 100% identity questions answered correctly (no Claude leaks)
- <50ms average response time for FAQ hits
- >80% of simple questions handled by FAQ
- Zero LLM tokens spent on FAQ matches

## Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| False positive matches | Strict 0.9 threshold, keyword priority |
| Stale FAQs | Admin review, usage analytics |
| Cache invalidation | Firebase real-time listener |

## Next Steps
1. Create Firebase `faq_entries` collection schema
2. Implement `src/core/faq.py` matcher
3. Integrate into `process_message()` before intent classification
4. Seed initial FAQ entries (identity, capabilities, commands)
5. Add admin commands for FAQ management
6. Monitor and tune threshold based on usage

## Dependencies
- Firebase (existing)
- Qdrant (existing)
- Embedding model (existing)
