---
phase: 4
title: "Reactions & Progress Updates"
parent: plan.md
status: pending
effort: 2h
---

# Phase 4: Reactions & Progress Updates

## Context

- Parent: [plan.md](./plan.md)
- Depends on: [Phase 3](./phase-03-image-document-handling.md)
- Code: `agents/main.py`, `agents/src/services/agentic.py`

## Overview

Add emoji reactions to acknowledge messages and provide real-time progress updates during long operations.

## Requirements

1. React to user message immediately (👀 or ⏳)
2. Update reaction as processing progresses
3. Show tool execution progress in real-time
4. Final reaction on completion (✅ or ❌)

## Architecture

```
User Message → React "👀" → Process → React "✅"
                              ↓
                    Tool 1 → Edit message "Running web_search..."
                              ↓
                    Tool 2 → Edit message "Running run_python..."
                              ↓
                    Final → Send response
```

## Related Code Files

- `agents/main.py:191-238` - telegram_webhook
- `agents/src/services/agentic.py` - agentic loop

## Implementation Steps

### Step 1: Add setMessageReaction helper

```python
async def set_message_reaction(chat_id: int, message_id: int, emoji: str = "👀"):
    """Set reaction emoji on a message."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    # Available emojis: 👍👎❤️🔥🎉🤔👏🥳😢😡🤯
    # Custom emojis require premium

    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/setMessageReaction",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "reaction": [{"type": "emoji", "emoji": emoji}],
                "is_big": False
            }
        )
```

### Step 2: Add progress message helper

```python
async def send_progress_message(chat_id: int, text: str) -> int:
    """Send progress message and return message_id for editing."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
        )
        result = resp.json()
        return result.get("result", {}).get("message_id")


async def edit_progress_message(chat_id: int, message_id: int, text: str):
    """Edit progress message with new status."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "HTML"
            }
        )


async def delete_message(chat_id: int, message_id: int):
    """Delete a message."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/deleteMessage",
            json={"chat_id": chat_id, "message_id": message_id}
        )
```

### Step 3: Add progress callback to agentic loop

```python
# In src/services/agentic.py, modify run_agentic_loop:

async def run_agentic_loop(
    user_message: str,
    system: str,
    user_id: int = None,
    skill: str = None,
    progress_callback: Callable = None  # NEW
) -> str:
    ...
    for iteration in range(max_iterations):
        ...
        # On tool use
        if stop_reason == "tool_use":
            for tool_call in tool_calls:
                tool_name = tool_call["name"]

                # Report progress if callback provided
                if progress_callback:
                    await progress_callback(f"🔧 Running <code>{tool_name}</code>...")

                result = await execute_tool(tool_call)
                ...
```

### Step 4: Update process_message with reactions

```python
async def process_message(text: str, user: dict, chat_id: int) -> str:
    # Get message_id from update (need to pass through)
    user_message_id = ...  # Pass from webhook

    # React to acknowledge
    await set_message_reaction(chat_id, user_message_id, "👀")

    # Send initial progress message
    progress_msg_id = await send_progress_message(chat_id, "⏳ <i>Processing...</i>")

    async def update_progress(status: str):
        await edit_progress_message(chat_id, progress_msg_id, status)

    try:
        response = await run_agentic_loop(
            user_message=text,
            system=system_prompt,
            user_id=user.get("id"),
            progress_callback=update_progress
        )

        # Success reaction
        await set_message_reaction(chat_id, user_message_id, "✅")

        # Delete progress message
        await delete_message(chat_id, progress_msg_id)

        return response

    except Exception as e:
        # Error reaction
        await set_message_reaction(chat_id, user_message_id, "❌")
        await edit_progress_message(chat_id, progress_msg_id, f"❌ Error: {str(e)[:100]}")
        raise
```

### Step 5: Pass message_id through webhook

```python
# In telegram_webhook, pass message_id to process_message:
message_id = message.get("message_id")
response = await process_message(text, user, chat_id, message_id)
```

## Todo List

- [ ] Add set_message_reaction helper
- [ ] Add send_progress_message helper
- [ ] Add edit_progress_message helper
- [ ] Add delete_message helper
- [ ] Add progress_callback to agentic loop
- [ ] Update process_message with reactions
- [ ] Pass message_id through webhook
- [ ] Test reaction flow

## Success Criteria

- [ ] 👀 reaction on message receipt
- [ ] Progress updates during tool execution
- [ ] ✅ reaction on success
- [ ] ❌ reaction on error
- [ ] Progress message deleted after completion

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Reaction API failure | Low | Non-blocking, ignore errors |
| Message edit flood | Low | Rate limit edits (1/sec) |
| Progress message stuck | Low | Cleanup on error |

## Next Steps

After completion, proceed to [Phase 5](./phase-05-proactive-notifications.md).
