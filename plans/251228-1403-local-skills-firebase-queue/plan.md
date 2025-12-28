---
title: "Local Skills via Firebase Task Queue"
description: "Enable local skill execution through Firebase task queue with Claude Code polling"
status: completed
priority: P1
effort: 4h
branch: main
tags: [firebase, skills, local-execution, task-queue]
created: 2025-12-28
---

# Local Skills via Firebase Task Queue

## Overview

Enable 8 local-only skills (pdf, docx, xlsx, pptx, media-processing, canvas-design, image-enhancer, video-downloader) to be invoked from Modal.com via Firebase task queue, with Claude Code polling and executing locally.

## Problem

Skills marked `deployment: local` exist in the codebase but have no invocation mechanism. Users cannot trigger local skills from Telegram or the API.

## Solution

```
Modal.com                                Claude Code (Local)
─────────                                ───────────────────

1. Request arrives
   (Telegram/API)
        │
2. Detect skill is local
   (frontmatter.deployment == "local")
        │
3. Queue task to Firebase ──────────────► 4. Poll Firebase (30s)
   task_queue/{id}                           or manual trigger
   {skill, task, user_id, status}
                                          5. Execute skill locally
                                             (browser, desktop apps)
        │                                         │
        ◄──────────────────────────────── 6. Write result to Firebase
7. Notify user via Telegram                  {status: completed, result}
```

## Phases

| # | Phase | Effort | Status | Link |
|---|-------|--------|--------|------|
| 1 | Firebase Task Queue Schema | 1h | completed | [phase-01](./phase-01-firebase-task-queue.md) |
| 2 | Modal Detection & Queueing | 1.5h | completed | [phase-02](./phase-02-modal-detection-queueing.md) |
| 3 | Claude Code Local Executor | 1.5h | completed | [phase-03](./phase-03-local-executor.md) |

## Key Decisions (Validated)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Queue mechanism | Firebase Firestore | Already integrated, free tier |
| Polling interval | 30 seconds | Balance responsiveness vs cost |
| Retry strategy | 3 retries with backoff | Handle transient failures |
| Notifications | Both queued + result | Full visibility for user |
| Execution mode | LLM agentic loop | Consistent with Modal execution |
| Task retention | 7 days | Auto-cleanup old tasks |
| Executor | Claude Code script | Reuse existing patterns |

## Success Criteria

- [x] Local skills detectable via `deployment` field
- [x] Tasks queued to Firebase from Modal
- [x] Claude Code can poll and execute tasks
- [x] Results returned to user via Telegram
- [x] Error handling with retry logic

## Dependencies

- Existing: `src/services/firebase.py`
- Existing: `src/skills/registry.py`
- Existing: `src/core/state.py`
