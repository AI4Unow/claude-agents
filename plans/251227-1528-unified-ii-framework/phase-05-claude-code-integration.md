---
phase: 5
title: "Claude Code Integration"
status: pending
effort: 2h
priority: P1
dependencies: [phase-04]
---

# Phase 5: Claude Code Integration

## Context

- Parent: [Unified II Framework](./plan.md)
- Depends on: [Phase 4 - Media & Procaffe](./phase-04-media-procaffe-scripts.md)

## Overview

Create Claude Code skill to invoke Modal skills. Enable bidirectional memory sync.

## Key Insights

- Claude Code can invoke HTTP endpoints via WebFetch
- Modal skills accessible via webhook or function call
- Memory sync: Local → Modal (push) and Modal → Local (pull)
- Use Qdrant as bridge for cross-environment learning

## Requirements

1. Create `modal-invoke` Claude Code skill
2. Add webhook endpoints for skill invocation
3. Implement bidirectional memory sync
4. End-to-end testing across environments

## Architecture

### Claude Code → Modal Flow

```
Claude Code Session
      │
      ▼
┌─────────────────┐
│ /modal-invoke   │ ◄── Claude Code skill
│ planning        │
└────────┬────────┘
         │
         ▼ HTTP POST
┌─────────────────┐
│ Modal Webhook   │
│ /api/skill      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Modal Skill     │
│ planning/       │
│ info.md         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Response        │ ───► Claude Code
└─────────────────┘
```

### Bidirectional Memory Sync

```
Local (SKILL.md)                 Modal (info.md)
     │                                │
     │      Git Push Trigger          │
     │ ─────────────────────────────► │
     │      Rebuild info.md           │
     │                                │
     │      Memory Export             │
     │ ◄───────────────────────────── │
     │      (via Qdrant KB)           │
     │                                │
     ▼                                ▼
┌─────────┐                    ┌─────────┐
│ Qdrant  │ ◄───────────────── │ Qdrant  │
│ Cloud   │   Shared KB        │ Cloud   │
└─────────┘                    └─────────┘
```

## Related Code Files

| File | Purpose |
|------|---------|
| `agents/main.py` | Add /api/skill endpoint |
| `~/.claude/skills/` | Local skills directory |
| `agents/src/services/qdrant.py` | Qdrant client |

## Implementation Steps

- [ ] Create `modal-invoke` skill in ~/.claude/skills/
- [ ] Add /api/skill webhook to main.py
- [ ] Create skill dispatcher function
- [ ] Implement memory export to Qdrant
- [ ] Add memory import from Qdrant to local
- [ ] Create sync trigger (cron or on-demand)
- [ ] End-to-end test: local → modal → local
- [ ] Document usage patterns

## New Skill: modal-invoke

```markdown
# modal-invoke

## When to Use
Invoke Modal-deployed skills from Claude Code when:
- Task needs cloud resources (GPU, memory)
- Running long-duration operations
- Accessing Modal-specific integrations

## Usage
/modal-invoke <skill-name> <task-description>

## Examples
/modal-invoke planning "Create auth system plan"
/modal-invoke media-processing "Convert video to MP4"
```

## Todo List

- [ ] Create modal-invoke SKILL.md
- [ ] Add /api/skill endpoint
- [ ] Skill dispatcher implementation
- [ ] Memory export function
- [ ] Memory import function
- [ ] Sync trigger mechanism
- [ ] E2E tests
- [ ] Documentation

## Success Criteria

1. modal-invoke skill works from Claude Code
2. Modal skills respond correctly
3. Memory syncs bidirectionally
4. Same results local and cloud

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Latency | Medium | Async execution option |
| Auth | High | Secure webhook tokens |
| Memory conflicts | Medium | Conflict resolution strategy |

## Security Considerations

- Webhook authentication with secret token
- Rate limiting on /api/skill endpoint
- Sanitize skill names to prevent injection

## Unresolved Questions

1. How to handle long-running Modal tasks?
2. Conflict resolution for memory writes?
3. Should sync be push, pull, or both?

## Next Steps

→ Production deployment and monitoring
