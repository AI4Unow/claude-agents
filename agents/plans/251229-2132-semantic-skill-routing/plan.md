---
title: "Semantic Skill Routing for Telegram Bot"
description: "Enable automatic skill detection from natural language with explicit /skill and @skill invocation"
status: complete
priority: P1
effort: 3h
branch: main
tags: [telegram, routing, skills, intent, qdrant]
created: 2025-12-29
---

# Semantic Skill Routing

## Overview

Upgrade Telegram bot's auto mode to semantically detect user intent and route to appropriate skills. Currently auto mode only distinguishes simple/complex. Goal: detect when user wants specific skill (research, design, code) and route accordingly.

## Architecture

```
Message → Explicit check (/skill, @skill)?
    ↓ no
classify_intent() [Haiku ~50ms]
    ↓
CHAT → _run_simple(haiku)
SKILL → SkillRouter.route_single() → execute_skill_simple()
ORCHESTRATE → _run_orchestrated()
```

## Phases

| Phase | Description | Status | Link |
|-------|-------------|--------|------|
| 1 | Intent Classifier | ✅ complete | [phase-01-intent-classifier.md](phase-01-intent-classifier.md) |
| 2 | Explicit Skill Detection | ✅ complete | [phase-02-explicit-skill-detection.md](phase-02-explicit-skill-detection.md) |
| 3 | Auto Mode Routing Update | ✅ complete | [phase-03-auto-mode-routing.md](phase-03-auto-mode-routing.md) |
| 4 | Testing & Deployment | ✅ complete | [phase-04-testing-deployment.md](phase-04-testing-deployment.md) |

## Key Files

| File | Action |
|------|--------|
| `src/core/intent.py` | CREATE - Three-way intent classifier |
| `main.py:1550-1580` | MODIFY - New routing logic |
| `src/core/router.py` | EXTEND - Add explicit skill parsing |

## Success Criteria

1. `/research topic` and `@research topic` work
2. "research X" auto-routes to gemini-deep-research
3. "design X" auto-routes to canvas-design
4. Simple questions stay on Haiku (fast)
5. <200ms routing overhead

## Dependencies

- Existing: SkillRouter, SkillRegistry, Qdrant, Haiku
- No new dependencies

## Brainstorm

See [brainstorm-251229-2132-semantic-skill-routing.md](../reports/brainstorm-251229-2132-semantic-skill-routing.md)
