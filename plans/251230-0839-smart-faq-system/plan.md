---
title: "Smart FAQ System"
description: "Hybrid keyword+semantic FAQ system to handle common questions without LLM"
status: pending
priority: P1
effort: 3h
branch: main
tags: [faq, optimization, identity, telegram]
created: 2025-12-30
---

# Smart FAQ System

## Overview

Implement hybrid FAQ system that handles common questions (identity, capabilities, commands) without LLM calls. Fixes Claude identity leak and reduces latency/cost.

## Problem

1. Claude model leaks "I'm Claude made by Anthropic" despite system prompts
2. Simple questions waste LLM tokens and add 2-5s latency
3. No guarantee of consistent branded responses

## Solution

```
Message → Keyword Check (~5ms)
    ↓ no match
Qdrant Semantic Search (~50ms, threshold=0.9)
    ↓ no match
Normal LLM Flow
```

## Phases

| Phase | Description | Effort | Status |
|-------|-------------|--------|--------|
| [Phase 1](./phase-01-faq-core.md) | Firebase schema + FAQ matcher | 45min | pending |
| [Phase 2](./phase-02-qdrant-collection.md) | Qdrant FAQ collection | 30min | pending |
| [Phase 3](./phase-03-integration.md) | Integrate into message flow | 30min | pending |
| [Phase 4](./phase-04-admin-commands.md) | Admin /faq commands | 30min | pending |
| [Phase 5](./phase-05-seed-data.md) | Seed initial FAQ entries | 30min | pending |

## Success Criteria

- 100% identity questions answered correctly
- <50ms keyword matches, <100ms semantic matches
- Zero LLM tokens for FAQ hits
- Runtime editable by admin

## Dependencies

- Firebase (existing)
- Qdrant (existing)
- Embedding model (existing)

## References

- [Brainstorm Report](../reports/brainstorm-251230-0839-smart-faq-system.md)
- [Codebase Summary](../../docs/codebase-summary.md)
