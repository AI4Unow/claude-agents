# Phase 2: Agent Coordination

## Context

Define coordination patterns between local Claude Code agents and remote Modal agents. Enable seamless task delegation and skill sharing.

## Overview

Hybrid agent system with two execution contexts:
- **Local:** Claude Code CLI with chrome-dev/chrome skills for browser automation
- **Remote:** Modal serverless agents for API-based operations

Firebase acts as coordination layer enabling async task delegation.

## Key Insights

- Local agents need consumer IP for social platforms (anti-bot detection)
- Remote agents can scale on-demand (pay-per-use)
- Coordination must be async and resilient
- Skills categorized by deployment target

## Local Agents (Claude Code)

### Capabilities

| Capability | Tool/Skill | Use Case |
|------------|-----------|----------|
| Browser automation | chrome-dev, chrome | Social media posting |
| File system | Read, Write, Edit | Document processing |
| Code execution | Bash, local Python | Build, test, deploy |
| MCP servers | perplexity, etc. | Extended capabilities |

### Local-Only Skills

Skills requiring consumer IP or browser automation:

```yaml
# Skill info.md frontmatter
---
name: tiktok
deployment: local  # NOT deployed to Modal
requires:
  - chrome-dev skill
  - consumer IP
---
```

| Skill | Reason |
|-------|--------|
| tiktok | Anti-bot detection, browser required |
| facebook | Consumer IP, login session |
| youtube | Upload requires browser auth |
| linkedin | Rate limits on datacenter IPs |
| instagram | Similar to facebook |

### Triggering Local Skills from Modal

```
Modal Agent → Firebase Task Queue → Polling → Local Agent → Execute
```

**Task Schema:**
```javascript
// Firebase: tasks/{taskId}
{
  "id": "task_abc123",
  "type": "local_skill",
  "skill": "tiktok",
  "payload": {
    "action": "post_video",
    "file_path": "gs://bucket/video.mp4",
    "caption": "..."
  },
  "status": "pending",  // pending → processing → done → failed
  "created_at": timestamp,
  "assigned_to": null,  // local agent ID when claimed
  "result": null        // populated on completion
}
```

## Remote Agents (Modal)

### Agent Inventory

| Agent | Trigger | Purpose | min_containers |
|-------|---------|---------|----------------|
| TelegramChatAgent | Webhook (always-on) | User chat | 1 |
| GitHubAgent | Cron (hourly) + webhook | Repo automation | 0 |
| DataAgent | Cron (1 AM UTC) | Daily summaries | 0 |
| ContentAgent | API call | Content generation | 0 |

### Remote Skills (Modal Volume)

Skills safe for cloud execution:

| Category | Skills |
|----------|--------|
| Development | planning, research, debugging, code-review |
| Backend | backend-development, frontend-development |
| Design | ui-ux-pro-max, canvas-design, ui-styling |
| Documents | pdf, docx, pptx, xlsx |
| Media | ai-multimodal, media-processing, ai-artist |

## Coordination Patterns

### Pattern 1: Direct API (Sync)

For immediate responses within Telegram timeout.

```
User → Telegram → Modal Webhook → Agentic Loop → Response → User
                                      ↓
                              (tools: web_search, etc.)
```

### Pattern 2: Task Queue (Async)

For long-running or local-only operations.

```
┌─────────────────────────────────────────────────────────────────┐
│                    ASYNC TASK DELEGATION                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Modal Agent detects local-only task                         │
│     ┌────────────────┐                                          │
│     │ "Post to TikTok│                                          │
│     │  this video"   │                                          │
│     └───────┬────────┘                                          │
│             │                                                    │
│  2. Create task in Firebase                                     │
│             ▼                                                    │
│     ┌──────────────────────────────────────────────┐            │
│     │ Firebase: tasks/task_xyz                      │            │
│     │ {type: "local_skill", skill: "tiktok", ...}  │            │
│     └──────────────────────────────────────────────┘            │
│             │                                                    │
│  3. Reply to user with task ID                                  │
│             ▼                                                    │
│     "Task queued. ID: task_xyz. I'll notify when done."        │
│                                                                  │
│  4. Local agent polls/watches Firebase                          │
│     ┌────────────────┐                                          │
│     │ Claude Code    │◄─── Polls every 30s or uses listener    │
│     │ + chrome skill │                                          │
│     └───────┬────────┘                                          │
│             │                                                    │
│  5. Claims and executes task                                    │
│             ▼                                                    │
│     Update: status=processing, assigned_to=local_1              │
│     Execute: chrome-dev → TikTok upload                         │
│     Update: status=done, result={...}                           │
│                                                                  │
│  6. Modal agent notifies user (via Telegram)                    │
│     "Task task_xyz complete! Video posted."                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Pattern 3: Skill Chaining (Mixed)

Combine remote and local skills in sequence.

```
User: "Research TikTok trends and post a summary video"

Chain:
1. [Remote] research skill → trending topics
2. [Remote] content skill → video script
3. [Local] media-processing → generate video
4. [Local] tiktok skill → post video
```

## Skill Categorization Schema

Add `deployment` field to skill info.md frontmatter:

```yaml
---
name: planning
description: Create implementation plans
deployment: remote  # remote | local | both
category: development
---
```

| deployment | Meaning |
|------------|---------|
| remote | Deploy to Modal Volume |
| local | Keep in Claude Code only |
| both | Sync to both environments |

## Implementation Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    COORDINATION LAYER                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────┐              │
│  │ Modal Agent      │         │ Local Agent      │              │
│  │ (TelegramChat)   │         │ (Claude Code)    │              │
│  └────────┬─────────┘         └────────┬─────────┘              │
│           │                            │                         │
│           │ create_task()              │ poll_tasks()            │
│           │ get_task_result()          │ claim_task()            │
│           │ notify_user()              │ complete_task()         │
│           │                            │                         │
│           └──────────┬─────────────────┘                         │
│                      ▼                                           │
│           ┌────────────────────────────┐                         │
│           │ Firebase: tasks collection │                         │
│           │ ├── pending tasks          │                         │
│           │ ├── processing tasks       │                         │
│           │ └── completed tasks        │                         │
│           └────────────────────────────┘                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Steps

1. [ ] Add `deployment` field to skill info.md files
2. [ ] Create TaskService in src/services/tasks.py
3. [ ] Implement task creation in agentic.py for local skills
4. [ ] Create local agent poller script (Python or Claude hook)
5. [ ] Add task status notifications to Telegram
6. [ ] Implement skill chaining with mixed deployment

## Todo List

- [ ] Define task state machine
- [ ] Add task TTL and cleanup
- [ ] Implement task claiming with locking
- [ ] Create local agent daemon script
- [ ] Add retry logic for failed tasks

## Success Criteria

- [ ] Local/remote skills properly categorized
- [ ] Task queue operational in Firebase
- [ ] Local agent can claim and execute tasks
- [ ] Users receive completion notifications
- [ ] Mixed chains execute correctly
