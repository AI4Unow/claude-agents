---
title: "Skills Deployment Audit"
description: "Audit and deploy missing agents as Modal functions with corresponding skills"
status: completed
priority: P1
effort: 3h
branch: main
tags: [modal, skills, agents, deployment]
created: 2025-12-27
completed: 2025-12-27
---

# Skills Deployment Audit

## Overview

Audit local modules vs Modal deployment to identify and deploy missing components.

## Current State Analysis

### Deployed on Modal

| Function | Type | Status |
|----------|------|--------|
| `telegram_chat_agent` | ASGI App | ✅ Running |
| `sync_skills_from_github` | Function | ✅ Available |
| `init_skills` | Function | ✅ Available |
| `test_*` (5 functions) | Test | ✅ Available |

### Local Modules (Not Deployed)

| Agent | File | Purpose | Modal Status |
|-------|------|---------|--------------|
| GitHubAgent | `github_automation.py` | Repo automation | ❌ Missing |
| DataAgent | `data_processor.py` | Analytics/reports | ❌ Missing |
| ContentAgent | `content_generator.py` | Content generation | ❌ Missing |

### Skills Directory

| Skill | Local | Modal Volume |
|-------|-------|--------------|
| telegram-chat | ✅ | ✅ |
| github | ❌ | ❌ |
| data | ❌ | ❌ |
| content | ❌ | ❌ |

## Phases

| Phase | Description | Effort | Status |
|-------|-------------|--------|--------|
| 1 | [GitHub Agent Deployment](./phase-01-github-agent-deployment.md) | 1h | ✅ completed |
| 2 | [Data Agent Deployment](./phase-02-data-agent-deployment.md) | 0.5h | ✅ completed |
| 3 | [Content Agent Deployment](./phase-03-content-agent-deployment.md) | 0.5h | ✅ completed |
| 4 | [Skills Volume Sync](./phase-04-skills-volume-sync.md) | 1h | ✅ completed |

## Architecture

```
main.py (Modal App)
├── telegram_chat_agent()     ✅ Deployed
├── github_agent()            ❌ NEW - Phase 1
├── data_agent()              ❌ NEW - Phase 2
├── content_agent()           ❌ NEW - Phase 3
└── sync_skills_from_github() ✅ Deployed

skills/
├── telegram-chat/info.md     ✅ Exists
├── github/info.md            ❌ NEW - Phase 1
├── data/info.md              ❌ NEW - Phase 2
└── content/info.md           ❌ NEW - Phase 3
```

## Success Criteria

1. All 4 agents deployed as Modal functions
2. All 4 skills initialized in Modal Volume
3. Each agent reads its skill info.md for instructions
4. Agents accessible via webhooks or scheduled triggers

## Dependencies

- Modal.com account configured
- Secrets: anthropic-credentials, firebase-credentials, telegram-credentials, qdrant-credentials, exa-credentials, tavily-credentials
- GitHub token (for github agent)

## Validation Summary

**Validated:** 2025-12-27
**Questions asked:** 4

### Confirmed Decisions
- GitHub Agent triggers: **Both webhook + cron** (handle events + periodic monitoring)
- Daily summary schedule: **8 AM local (1 AM UTC)** - adjusted for ICT timezone
- Content Agent access: **All three** (Telegram commands + HTTP API + Internal)
- GitHub credentials: **Separate github-credentials secret**

### Action Items
- [ ] Phase 1: Add both webhook endpoint AND cron schedule for GitHub Agent
- [ ] Phase 2: Change cron to `0 1 * * *` (1 AM UTC = 8 AM ICT)
- [ ] Phase 3: Add HTTP API endpoint `/api/content` in addition to Telegram commands
- [ ] Create Modal secret `github-credentials` with GITHUB_TOKEN

## Related Docs

- [System Architecture](../../docs/system-architecture.md)
- [Codebase Summary](../../docs/codebase-summary.md)
