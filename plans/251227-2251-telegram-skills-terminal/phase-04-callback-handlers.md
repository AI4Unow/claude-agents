---
phase: 4
title: "Callback Handlers"
status: pending
effort: 1.5h
---

# Phase 4: Callback Handlers

## Objective

Handle inline keyboard button clicks for skill selection and execution flow.

## Implementation Steps

### 1. Add handle_callback() function

**New function** in main.py:

```python
async def handle_callback(callback: dict) -> dict:
    """Handle inline keyboard button press."""
    import structlog
    logger = structlog.get_logger()

    callback_id = callback.get("id")
    data = callback.get("data", "")
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    message_id = callback.get("message", {}).get("message_id")
    user = callback.get("from", {})

    logger.info("callback_received", data=data, chat_id=chat_id)

    # Parse callback data
    action, value = data.split(":", 1) if ":" in data else (data, "")

    # Answer callback to remove loading state
    await answer_callback(callback_id)

    if action == "cat":
        # Category selected - show skills
        await handle_category_select(chat_id, message_id, value)

    elif action == "skill":
        # Skill selected - prompt for task
        await handle_skill_select(chat_id, value, user)

    elif action == "mode":
        # Mode selected - execute pending skill
        await handle_mode_select(chat_id, value, user)

    elif action == "exec":
        # Direct execution with stored task
        skill, task_id = value.split("|")
        await handle_skill_execute(chat_id, skill, task_id, user)

    return {"ok": True}
```

### 2. Add answer_callback() function

Required to dismiss loading indicator:

```python
async def answer_callback(callback_id: str, text: str = None):
    """Answer callback query to dismiss loading state."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            json={
                "callback_query_id": callback_id,
                "text": text  # Optional toast message
            }
        )
```

### 3. Add handler functions

**Category selection** - update keyboard:

```python
async def handle_category_select(chat_id: int, message_id: int, category: str):
    """Handle category button press - update message with skills."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    if category == "main":
        keyboard = build_skills_keyboard()
        text = "Select a skill category:"
    else:
        keyboard = build_skills_keyboard(category)
        text = f"<b>{category.title()}</b> skills:\nSelect one to use:"

    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": {"inline_keyboard": keyboard},
                "parse_mode": "HTML"
            }
        )
```

**Skill selection** - prompt for task:

```python
async def handle_skill_select(chat_id: int, skill_name: str, user: dict):
    """Handle skill button press - prompt for task."""
    from src.skills.registry import get_registry

    registry = get_registry()
    skill = registry.get_full(skill_name)

    if not skill:
        await send_telegram_message(chat_id, f"Skill '{skill_name}' not found.")
        return

    # Store pending skill in user session (Firebase)
    await store_pending_skill(user.get("id"), skill_name)

    message = (
        f"<b>{skill_name}</b>\n"
        f"{skill.description[:100]}\n\n"
        "Send your task now (or /cancel to exit):"
    )

    await send_telegram_message(chat_id, message)
```

### 4. Add session state management

Store pending skill selection in Firebase:

```python
async def store_pending_skill(user_id: int, skill_name: str):
    """Store user's pending skill selection."""
    from src.services.firebase import init_firebase
    from datetime import datetime

    db = init_firebase()
    db.collection("telegram_sessions").document(str(user_id)).set({
        "pending_skill": skill_name,
        "timestamp": datetime.utcnow(),
    }, merge=True)


async def get_pending_skill(user_id: int) -> str:
    """Get user's pending skill selection."""
    from src.services.firebase import init_firebase

    db = init_firebase()
    doc = db.collection("telegram_sessions").document(str(user_id)).get()

    if doc.exists:
        data = doc.to_dict()
        return data.get("pending_skill")
    return None


async def clear_pending_skill(user_id: int):
    """Clear user's pending skill."""
    from src.services.firebase import init_firebase

    db = init_firebase()
    db.collection("telegram_sessions").document(str(user_id)).update({
        "pending_skill": None
    })
```

### 5. Update process_message() to check pending skill

**Modify** process_message() in main.py:

```python
async def process_message(text: str, user: dict, chat_id: int) -> str:
    """Process a regular message."""

    # Check for pending skill
    pending_skill = await get_pending_skill(user.get("id"))

    if pending_skill:
        # Execute pending skill with this message as task
        await clear_pending_skill(user.get("id"))

        import time
        start = time.time()
        result = await execute_skill_simple(pending_skill, text, {"user": user})
        duration_ms = int((time.time() - start) * 1000)

        from src.services.telegram import format_skill_result
        return format_skill_result(pending_skill, result, duration_ms)

    # Normal agentic loop...
    from src.services.agentic import run_agentic_loop
    # ...existing code...
```

### 6. Add /cancel command

**Add** to handle_command():

```python
elif cmd == "/cancel":
    await clear_pending_skill(user.get("id"))
    return "Operation cancelled."
```

## Code Changes Summary

| File | Section | Change |
|------|---------|--------|
| main.py | telegram_webhook | Add callback_query handling |
| main.py | functions | Add handle_callback(), answer_callback() |
| main.py | functions | Add category/skill handlers |
| main.py | functions | Add session state functions |
| main.py | process_message | Check pending skill |
| main.py | handle_command | Add /cancel |

## Flow Diagram

```
/skills → [Categories] → [Skills] → "Send task"
                                       ↓
                              User types task
                                       ↓
                              execute_skill()
                                       ↓
                              Format & send result
```

## Testing

1. `/skills` → Click "Development" → Click "planning" → Type task → Get result
2. `/skills` → Click "planning" → `/cancel` → Should clear state
3. Two users simultaneously → Should maintain separate states

## Success Criteria

- [ ] Category buttons update message with skill list
- [ ] Skill buttons prompt for task input
- [ ] Next message executes skill with task
- [ ] /cancel clears pending state
- [ ] Multiple users don't interfere

## Risks

| Risk | Mitigation |
|------|------------|
| Firebase latency | Use merge=True for fast writes |
| State left orphaned | Add TTL cleanup (cron job) |
| Callback timeout (30s) | Answer immediately, process async |

## Unresolved Questions

1. Should mode selection be per-skill or global preference?
2. Add inline mode for searching skills by typing @bot skill_name?
