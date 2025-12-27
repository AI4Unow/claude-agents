---
title: "Modal.com Self-Improving Agents (II Framework)"
description: "Deploy self-improving AI agents on Modal using the Information & Implementation framework"
status: pending
priority: P1
effort: 20h
issue: null
branch: main
tags: [ai-agents, modal, ii-framework, self-improving, telegram, firebase]
created: 2025-12-26
updated: 2025-12-26
---

# Modal.com Self-Improving Agents

## Overview

Multi-agent system using the **II Framework (Information & Implementation)** deployed on Modal.com. Agents are self-improving: they read instructions from Modal Volume, execute tasks, and rewrite their own instructions based on experience.

**Key Pattern:** Each skill = `.md` (Information) + `.py` (Implementation)
- `.md` → Modal Volume (mutable, self-improving)
- `.py` → Modal Server (immutable after deploy)

## The II Framework

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SKILL = Information (.md) + Implementation (.py)          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐         │
│  │  INFORMATION (.md)          │    │  IMPLEMENTATION (.py)        │         │
│  │  ─────────────────          │    │  ──────────────────          │         │
│  │  • Instructions             │    │  • Python execution code     │         │
│  │  • Memory of past runs      │    │  • Tool functions            │         │
│  │  • Learned improvements     │    │  • LLM API calls             │         │
│  │  • Error history            │    │  • External integrations     │         │
│  │  • Context & plans          │    │                              │         │
│  │                             │    │                              │         │
│  │  MUTABLE at runtime         │    │  IMMUTABLE after deploy      │         │
│  │  → Stored in Modal Volume   │    │  → Deployed to Modal Server  │         │
│  └─────────────────────────────┘    └─────────────────────────────┘         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Architecture

```
LOCAL DEVELOPMENT                         MODAL CLOUD
─────────────────                         ───────────

┌─────────────────┐                      ┌─────────────────────────────────────┐
│ Your Computer   │                      │            MODAL SERVER             │
│                 │                      │                                     │
│ skills/         │    modal deploy      │  ┌─────────────────────────────────┐│
│ ├── telegram/   │ ──────────────────► │  │  telegram_chat.py               ││
│ │   ├── info.md │                      │  │  github_agent.py                ││
│ │   └── agent.py│                      │  │  data_agent.py                  ││
│ ├── github/     │                      │  │  content_agent.py               ││
│ │   ├── info.md │                      │  │                                 ││
│ │   └── agent.py│                      │  │  Runs on cron schedule          ││
│ └── ...         │                      │  │  Up to 60 min per execution     ││
│                 │                      │  └─────────────────────────────────┘│
│ .env (secrets)  │    modal secrets     │                                     │
│                 │ ──────────────────► │  ┌─────────────────────────────────┐│
└─────────────────┘                      │  │  MODAL VOLUME (/skills/)        ││
                                         │  │                                 ││
                                         │  │  telegram-chat/info.md (mutable)   ││
                                         │  │  github/info.md     (mutable)   ││
                                         │  │  data/info.md       (mutable)   ││
                                         │  │  content/info.md    (mutable)   ││
                                         │  │                                 ││
                                         │  │  Agents READ and WRITE here     ││
                                         │  │  Self-improvement persists      ││
                                         │  └─────────────────────────────────┘│
                                         └─────────────────────────────────────┘
                                                          │
                    ┌─────────────────────────────────────┼─────────────────┐
                    ▼                                     ▼                 ▼
          ┌─────────────────┐                   ┌─────────────┐   ┌─────────────┐
          │  VERCEL EDGE    │                   │   FIREBASE  │   │QDRANT CLOUD │
          │  (Webhooks)     │                   │  (State)    │   │  (Memory)   │
          └─────────────────┘                   └─────────────┘   └─────────────┘
```

## Self-Improvement Loop

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENT EXECUTION CYCLE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. WAKE UP (Cron or webhook trigger)                                       │
│     │                                                                        │
│  2. READ info.md from Modal Volume                                          │
│     │  - Current instructions                                               │
│     │  - Memory of past runs                                                │
│     │  - Learned improvements                                               │
│     │                                                                        │
│  3. EXECUTE task using agent.py + LLM API                                   │
│     │                                                                        │
│  4. EVALUATE results                                                        │
│     │                                                                        │
│     ├── Success → Append to memory section in info.md                       │
│     │                                                                        │
│     └── Error → SELF-IMPROVE                                                │
│           │                                                                  │
│           ├── LLM analyzes what went wrong                                  │
│           ├── LLM rewrites info.md with fix                                 │
│           ├── Commit changes to Modal Volume                                │
│           └── Retry (recursive until success or timeout)                    │
│                                                                              │
│  5. COMPLETE - Sleep until next trigger                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Phases

| # | Phase | Status | Effort | Description |
|---|-------|--------|--------|-------------|
| 1 | Modal Setup & II Framework | Pending | 3h | Project structure, Volume, base agent |
| 2 | Firebase Integration | Pending | 2h | State management, task queue |
| 3 | Qdrant Cloud Setup | Pending | 2h | Vector memory (Asia region) |
| 4 | Vercel Edge Webhooks | Pending | 2h | Telegram/GitHub webhook handlers |
| 5 | Telegram Chat Agent | Pending | 3h | Primary interface with self-improvement |
| 6 | GitHub Agent | Pending | 3h | Repo automation with self-improvement |
| 7 | Data & Content Agents | Pending | 3h | Analytics and content generation |
| 8 | Testing & Deployment | Pending | 2h | E2E testing, production deploy |

## Skill Structure

Each skill follows the II Framework pattern:

```
skills/
├── telegram-chat/
│   ├── info.md              # Information: instructions, memory, plans
│   └── agent.py             # Implementation: execution code
│
├── github-automation/
│   ├── info.md
│   └── agent.py
│
├── data-processing/
│   ├── info.md
│   └── agent.py
│
└── content-writing/
    ├── info.md
    └── agent.py
```

### info.md Template

```markdown
# [Skill Name] Agent

## Instructions
[What this agent does and how]

## Tools Available
[List of functions the agent can call]

## Memory
[Accumulated learnings from past runs]

## Error History
[Past errors and how they were resolved]

## Current Plan
[Active goals and next steps]
```

### agent.py Template

```python
import modal
from pathlib import Path

app = modal.App("skill-name")
volume = modal.Volume.from_name("skills-volume")

@app.function(
    volumes={"/skills": volume},
    secrets=[modal.Secret.from_name("api-keys")],
    schedule=modal.Cron("0 9 * * *"),  # Daily at 9 AM
    timeout=3600,  # 60 minutes max
)
async def run():
    # 1. Read information
    info = Path("/skills/skill-name/info.md").read_text()

    # 2. Execute with LLM
    result = await execute_with_llm(info, task)

    # 3. Self-improve if needed
    if result.needs_improvement:
        improved_info = await improve_instructions(info, result.error)
        Path("/skills/skill-name/info.md").write_text(improved_info)
        volume.commit()

    return result
```

## Dependencies

- Modal.com account ($5 free credits)
- Vercel account (free tier)
- Firebase project (free tier)
- Qdrant Cloud (Asia region)
- Telegram Bot (via BotFather)
- LLM API keys (Anthropic, OpenAI, or other)

## Cost Estimate

| Component | Monthly Cost |
|-----------|-------------|
| Modal compute | ~$5-15 (pay per use) |
| Vercel Edge | $0 (free tier) |
| LLM API calls | ~$10-20 |
| Firebase | $0 (free tier) |
| Qdrant Cloud | ~$25 |
| **Total** | **~$40-60** |

## Success Criteria

- [ ] Skills deploy with one command (`modal deploy`)
- [ ] Agents read/write info.md from Volume
- [ ] Self-improvement loop works
- [ ] Telegram webhook responds <2 seconds
- [ ] Agents communicate via Firebase
- [ ] Vector memory persists in Qdrant

## Related Files

- Brainstorm: `../reports/brainstorm-251226-1500-modal-claude-agents-architecture.md`
- II Framework Research: `../reports/brainstorm-251226-2118-ii-framework-modal-agents.md`
