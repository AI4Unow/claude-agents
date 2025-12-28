---
phase: 1
title: "Typing Indicators & UX Polish"
parent: plan.md
status: pending
effort: 2h
---

# Phase 1: Typing Indicators & UX Polish

## Context

- Parent: [plan.md](./plan.md)
- Code: `agents/main.py`

## Overview

Add typing indicators and improve UX feedback during message processing.

## Requirements

1. Send "typing" action when processing starts
2. Continue sending during long operations
3. Add processing time estimates
4. Better error messages with retry suggestions

## Architecture

```
User Message → Send "typing" → Process → Response
                   ↓
              (every 4s)
                   ↓
         sendChatAction("typing")
```

## Related Code Files

- `agents/main.py:619-665` - process_message function
- `agents/main.py:191-238` - telegram_webhook handler
- `agents/src/services/agentic.py` - agentic loop

## Implementation Steps

### Step 1: Add send_typing_action helper

```python
async def send_typing_action(chat_id: int):
    """Send typing indicator to show bot is processing."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"}
        )
```

### Step 2: Add continuous typing during processing

```python
import asyncio

async def typing_indicator(chat_id: int, cancel_event: asyncio.Event):
    """Send typing indicator every 4 seconds until cancelled."""
    while not cancel_event.is_set():
        await send_typing_action(chat_id)
        try:
            await asyncio.wait_for(cancel_event.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            continue
```

### Step 3: Wrap process_message with typing

Modify `process_message`:
```python
async def process_message(text: str, user: dict, chat_id: int) -> str:
    cancel_event = asyncio.Event()
    typing_task = asyncio.create_task(typing_indicator(chat_id, cancel_event))

    try:
        # existing processing logic
        response = await run_agentic_loop(...)
        return response
    finally:
        cancel_event.set()
        typing_task.cancel()
```

### Step 4: Add error recovery suggestions

```python
ERROR_SUGGESTIONS = {
    "timeout": "Try again or simplify your request.",
    "circuit_open": "Service temporarily unavailable. Try in 30 seconds.",
    "rate_limit": "Too many requests. Please wait a moment.",
}

def format_error_message(error: str) -> str:
    for key, suggestion in ERROR_SUGGESTIONS.items():
        if key in error.lower():
            return f"❌ {error}\n\n💡 {suggestion}"
    return f"❌ Sorry, something went wrong. Please try again."
```

## Todo List

- [ ] Add send_typing_action helper function
- [ ] Add typing_indicator background task
- [ ] Wrap process_message with typing indicator
- [ ] Add handle_command typing for long commands
- [ ] Add error recovery suggestions
- [ ] Test with various message types

## Success Criteria

- [ ] Typing indicator shows within 500ms of message receipt
- [ ] Typing continues during multi-tool agentic loops
- [ ] Errors show helpful retry suggestions
- [ ] No typing indicator left "stuck"

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Typing task not cancelled | Low | Use try/finally, cancel on error |
| Rate limiting | Low | 4s interval is safe |
| Timeout on typing API | Low | Non-blocking, ignore failures |

## Next Steps

After completion, proceed to [Phase 2](./phase-02-voice-support.md).
