---
title: "Agents Enhancement: Skill Categorization & Self-Improvement"
description: "Add skill categorization for local/remote deployment and implement human-in-the-loop self-improvement loop"
status: completed
priority: P1
effort: 16h
branch: main
tags: [agents, ii-framework, self-improvement, skills]
created: 2025-12-28
---

# Agents Enhancement Plan

## Overview

Enhance the Modal.com II Framework Agents with two key features:
1. **Skill Categorization** - Filter local-only skills from Modal deployment
2. **Self-Improvement Loop** - Real-time error detection with human approval via Telegram

## Context

- Brainstorm: `plans/reports/brainstorm-251228-0736-agents-enhancement-integration.md`
- Current: Deployed MVP with 25+ skills, 5 tools, Telegram chat agent
- Gap: No skill filtering, self-improvement architecture exists but not active

## Phases

| # | Phase | Status | Effort | Link |
|---|-------|--------|--------|------|
| 1 | Skill Categorization Schema | ✅ Done | 2h | [phase-01](./phase-01-skill-categorization-schema.md) |
| 2 | Skill Sync Filter | ✅ Done | 2h | [phase-02](./phase-02-skill-sync-filter.md) |
| 3 | ImprovementService Core | ✅ Done | 4h | [phase-03](./phase-03-improvement-service.md) |
| 4 | Telegram Admin Notifications | ✅ Done | 3h | [phase-04](./phase-04-telegram-notifications.md) |
| 5 | Integration & Testing | ✅ Done | 3h | [phase-05](./phase-05-integration-testing.md) |
| 6 | Deploy & Monitor | 🔄 Ready | 2h | [phase-06](./phase-06-deploy-monitor.md) |

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                     SKILL CATEGORIZATION                              │
├──────────────────────────────────────────────────────────────────────┤
│  LOCAL-ONLY (Claude Code)              REMOTE (Modal)                │
│  • tiktok, facebook, youtube           • planning, research          │
│  • linkedin, instagram                 • backend-development         │
│  • Requires consumer IP/browser        • API-based, cloud-safe       │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                     SELF-IMPROVEMENT LOOP                            │
├──────────────────────────────────────────────────────────────────────┤
│  1. Error Detection (agentic.py)                                     │
│  2. LLM Reflection → ImprovementProposal                             │
│  3. Store in Firebase (skill_improvements collection)                │
│  4. Telegram Notification to Admin (full diff inline)                │
│  5. [Approve] → Write to info.md → Volume commit                     │
│     [Reject] → Mark rejected, log reason                             │
└──────────────────────────────────────────────────────────────────────┘
```

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Improvement trigger | Real-time per-error | Immediate contextual learning |
| Validation | Human-in-the-loop | Safety, controlled changes |
| Admin access | Single Telegram ID | Simplicity, via env var |
| Diff display | Full inline | Immediate visibility |
| Skill sync | CC → Modal one-way | Source of truth in CC |
| Skill filter | deployment field | YAML frontmatter in info.md |

## Dependencies

- Modal Volume commit access
- Firebase Firestore (skill_improvements collection)
- Telegram Bot API (inline keyboards)
- ADMIN_TELEGRAM_ID environment variable

## Success Criteria

- [ ] Local-only skills NOT deployed to Modal Volume
- [ ] Errors trigger improvement proposals
- [ ] Admin receives Telegram notification with diff
- [ ] Approve/reject buttons work correctly
- [ ] Approved changes persist to info.md
- [ ] Volume commits succeed without errors
