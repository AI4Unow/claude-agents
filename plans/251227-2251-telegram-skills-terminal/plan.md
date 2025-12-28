---
title: "Telegram Bot as Skills Terminal"
description: "Enable all II Framework skills to be invoked and managed via Telegram bot interface"
status: completed
completed: 2025-12-28
priority: P1
effort: 6h
branch: main
tags: [telegram, skills, ii-framework, terminal]
created: 2025-12-27
reviewed: 2025-12-27
---

# Telegram Skills Terminal Implementation Plan

## Overview

Transform Telegram bot into unified terminal for all II Framework skills. Users invoke any skill via `/skill <name> <task>`, browse with `/skills`, and interact via inline keyboards.

## Current State

- **Telegram handler**: Webhook at `/webhook/telegram` (main.py:55-91)
- **Commands**: `/start`, `/help`, `/status`, `/translate`, `/summarize`, `/rewrite`
- **Skill API**: `/api/skill` endpoint with 5 modes (main.py:142-204)
- **Registry**: `SkillRegistry.discover()` returns 24+ skills with name, description, category

## Target State

- `/skill <name> <task>` - Direct skill execution
- `/skills` - Interactive skill menu (inline keyboard)
- `/mode <simple|routed|evaluated>` - Set default execution mode
- Callback queries for button interactions
- HTML/MarkdownV2 formatting with code blocks
- Long output chunking (4096 char limit)
- Error handling with suggestions

## Architecture

```
Telegram Update
     │
     ├─ /skill cmd ──► execute_skill_simple() ──► Response
     │
     ├─ /skills cmd ──► send_skills_menu() ──► Inline Keyboard
     │
     ├─ callback_query ──► handle_callback() ──► Skill execution
     │
     └─ message ──► process_message() ──► Agentic loop
```

## Phases

| Phase | Focus | Effort | Files Modified |
|-------|-------|--------|----------------|
| 01 | Skill commands (`/skill`, `/skills`) | 1.5h | main.py |
| 02 | Inline keyboards | 1.5h | main.py |
| 03 | Output formatting | 1.5h | main.py, telegram.py (new) |
| 04 | Callback handlers | 1.5h | main.py |

## Dependencies

- Existing `SkillRegistry` (src/skills/registry.py)
- Existing skill execution functions (main.py:226-299)
- Telegram Bot API (already configured)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Long skill outputs exceed 4096 char limit | Medium | Chunk messages, file attachment fallback |
| Callback data 64 byte limit | Low | Use compact encoding (skill name + mode) |
| MarkdownV2 escaping errors | Medium | Use HTML mode for dynamic content |
| Concurrent skill executions | Low | Modal handles concurrency |

## Success Criteria

1. `/skill planning "Create auth system"` executes and returns result
2. `/skills` shows categorized inline keyboard menu
3. Button clicks trigger skill selection and task prompt
4. Long outputs split correctly without breaking formatting
5. Errors show suggestions (e.g., "Did you mean: planning?")

## Phase Files

- [Phase 1: Skill Commands](./phase-01-skill-commands.md)
- [Phase 2: Inline Keyboards](./phase-02-inline-keyboards.md)
- [Phase 3: Output Formatting](./phase-03-output-formatting.md)
- [Phase 4: Callback Handlers](./phase-04-callback-handlers.md)

## Validation Summary

**Validated:** 2025-12-27
**Questions asked:** 7

### Confirmed Decisions

| Decision | Choice | Notes |
|----------|--------|-------|
| Execution mode management | Global user preference | Store in Firebase per user, persists across sessions |
| Message formatting | HTML mode | Easier escaping, recommended for dynamic content |
| Long output handling | Split into multiple messages | Keep response in chat, easier to read |
| Access control | Open access | Anyone can use all skills (current behavior) |
| Skill categories source | From skill registry | Use existing category from skill info.md frontmatter |
| Non-command messages | Agentic loop | Keep current behavior with tools |
| Session state storage | Firebase Firestore | Use existing Firebase integration |

### Action Items

- [x] Update Phase 2: Use `SkillRegistry.discover()` categories instead of hardcoded SKILL_CATEGORIES
- [x] Phase 1 /mode command: Store preference in Firebase `telegram_sessions/{user_id}/mode`
- [ ] Confirm all skill info.md files have valid category frontmatter

## Code Review Findings (2025-12-27)

**Report**: `/Users/nad/Library/CloudStorage/OneDrive-Personal/Agents/plans/reports/code-reviewer-251227-2315-telegram-skills-terminal.md`

### Critical Issues (Must Fix Before Deploy)

- [x] Add error handling to Firebase session functions → Now uses StateManager with error handling
- [x] Validate user_id before Firebase operations → StateManager checks `if not user_id`
- [x] Escape HTML in all message formatting → Using `escape_html()` in `handle_skill_select()`

### High Priority

- [ ] Validate callback_data length (64 byte limit)
- [ ] Implement rate limiting for skill execution
- [ ] Add execution timeout for skills (45s max)

### Medium Priority

- [ ] Fix HTML tag splitting in message chunking
- [ ] Improve skill suggestions with fuzzy matching
- [ ] Add callback execution logging

### Status

**Implementation**: COMPLETE (all phases done)
**Review**: COMPLETE - Critical issues fixed 2025-12-28
**Next**: Deploy to production
