---
title: "Telegram Chatbot Enhancements"
description: "Enhance Telegram bot with voice/image support, typing indicators, reactions, and Mini Apps"
status: completed
priority: P1
effort: 12h
branch: main
tags: [telegram, chatbot, media, voice, mini-apps]
created: 2025-12-28
completed: 2025-12-28
---

# Telegram Chatbot Enhancements

## Overview

Enhance the Telegram chatbot with advanced features to improve UX, add media capabilities, and implement modern Telegram Bot API features (API 9.0+).

## Current State

- Basic text messaging with agentic loop
- Inline keyboards for skill selection
- HTML formatting and message chunking
- Callback query handling for improvements
- Commands: /start, /help, /status, /skills, /skill, /mode, /clear, /translate, /summarize, /rewrite

## Problem

1. No media handling (images, voice, documents)
2. No typing indicators (user doesn't know bot is processing)
3. No reactions or interactive feedback
4. Limited error recovery UX
5. No proactive notifications or scheduled messages

## Phases

| # | Phase | Effort | Status | Link |
|---|-------|--------|--------|------|
| 1 | Typing Indicators & UX Polish | 2h | completed | [phase-01](./phase-01-typing-indicators-ux.md) |
| 2 | Voice Message Support | 3h | completed | [phase-02](./phase-02-voice-support.md) |
| 3 | Image & Document Handling | 3h | completed | [phase-03](./phase-03-image-document-handling.md) |
| 4 | Reactions & Progress Updates | 2h | completed | [phase-04](./phase-04-reactions-progress.md) |
| 5 | Proactive Notifications | 2h | completed | [phase-05](./phase-05-proactive-notifications.md) |

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Voice transcription | Whisper API (OpenAI) | Best accuracy, Modal integration |
| Image analysis | Claude Vision | Already integrated, multi-modal |
| File storage | Firebase Storage | Free tier, existing integration |
| Typing simulation | Chat action API | Native, no state needed |

## Success Criteria

- [ ] Typing indicator shows during processing
- [ ] Voice messages transcribed and processed
- [ ] Images analyzed with Claude Vision
- [ ] Documents stored and referenced
- [ ] Reactions used for quick feedback
- [ ] Scheduled reminders working

## Dependencies

- Existing: `main.py`, `src/services/telegram.py`, `src/services/agentic.py`
- New: Groq API secret for Whisper transcription
- New: Modal Volume for document storage

## Validation Summary

**Validated:** 2025-12-28
**Questions asked:** 7

### Confirmed Decisions

| Decision | User Choice |
|----------|-------------|
| Voice transcription | Groq Whisper (free, fast) |
| Document storage | Modal Volume (persist for skill access) |
| TTS reply | Add in Phase 6 (future) |
| Progress message | Keep as history (don't delete) |
| Voice duration limit | 60 seconds max |
| Reminder access | Admin only (ADMIN_TELEGRAM_ID) |
| Image resolution | Large (1280px) for Claude Vision |

### Action Items

- [ ] Update Phase 2: Replace OpenAI Whisper with Groq Whisper
- [ ] Update Phase 3: Store documents in Modal Volume instead of Firebase Storage
- [ ] Update Phase 4: Keep progress message instead of deleting
- [ ] Update Phase 5: Restrict /remind to admin only
- [ ] Create Phase 6: TTS voice replies (future)
