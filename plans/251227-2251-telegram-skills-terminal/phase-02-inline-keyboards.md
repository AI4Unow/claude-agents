---
phase: 2
title: "Inline Keyboards"
status: pending
effort: 1.5h
---

# Phase 2: Inline Keyboards

## Objective

Replace text-based `/skills` list with interactive inline keyboard menu organized by category.

## Implementation Steps

### 1. Define skill categories

Group skills by category for menu display:

```python
SKILL_CATEGORIES = {
    "development": ["planning", "code-review", "debugging", "backend-development", "frontend-development", "mobile-development"],
    "design": ["ui-styling", "ui-ux-pro-max", "canvas-design"],
    "media": ["ai-artist", "ai-multimodal", "image-enhancer", "media-processing", "video-downloader"],
    "document": ["pdf", "docx", "pptx", "xlsx"],
    "content": ["content", "research"],
    "automation": ["github", "data", "telegram-chat"],
}
```

### 2. Add send_telegram_keyboard() function

**New function** in main.py (after send_telegram_message):

```python
async def send_telegram_keyboard(chat_id: int, text: str, keyboard: list):
    """Send message with inline keyboard."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    reply_markup = {"inline_keyboard": keyboard}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
                "parse_mode": "HTML"
            }
        )
        return response.json()
```

### 3. Build skills menu keyboard

**Function** to generate category-based keyboard:

```python
def build_skills_keyboard(category: str = None) -> list:
    """Build inline keyboard for skill selection."""
    if category is None:
        # Show category buttons
        return [
            [{"text": "Development", "callback_data": "cat:development"}],
            [{"text": "Design", "callback_data": "cat:design"}],
            [{"text": "Media", "callback_data": "cat:media"}],
            [{"text": "Document", "callback_data": "cat:document"}],
            [{"text": "Content", "callback_data": "cat:content"}],
            [{"text": "Automation", "callback_data": "cat:automation"}],
        ]

    # Show skills in category (3 per row)
    skills = SKILL_CATEGORIES.get(category, [])
    keyboard = []
    row = []

    for skill in skills:
        row.append({"text": skill, "callback_data": f"skill:{skill}"})
        if len(row) == 3:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    # Back button
    keyboard.append([{"text": "Back to Categories", "callback_data": "cat:main"}])

    return keyboard
```

### 4. Update /skills command

Replace text list with keyboard menu:

```python
elif cmd == "/skills":
    keyboard = build_skills_keyboard()
    await send_telegram_keyboard(
        chat_id,
        "Select a skill category:",
        keyboard
    )
    return None  # Message already sent
```

### 5. Handle callback_query in webhook

**Update** telegram_webhook to detect callback queries:

```python
@web_app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    update = await request.json()

    # Check for callback query (button press)
    callback = update.get("callback_query")
    if callback:
        return await handle_callback(callback)

    # Existing message handling...
    message = update.get("message", {})
    # ...
```

## Callback Data Format

| Action | Format | Example |
|--------|--------|---------|
| Category select | `cat:<category>` | `cat:development` |
| Skill select | `skill:<name>` | `skill:planning` |
| Mode select | `mode:<mode>` | `mode:simple` |
| Back | `cat:main` | - |

**Note**: Telegram limits callback_data to 64 bytes. Our format fits within limit.

## Code Changes Summary

| File | Section | Change |
|------|---------|--------|
| main.py | constants | Add SKILL_CATEGORIES |
| main.py | functions | Add send_telegram_keyboard(), build_skills_keyboard() |
| main.py | /skills handler | Use keyboard instead of text |
| main.py | webhook | Add callback_query detection |

## Testing

1. `/skills` - Shows category buttons
2. Click "Development" - Shows planning, debugging, etc.
3. Click "Back to Categories" - Returns to main menu

## Success Criteria

- [ ] `/skills` displays category buttons
- [ ] Category click shows skills in that category
- [ ] Back button returns to categories
- [ ] Buttons fit within 64-byte callback_data limit

## Risks

| Risk | Mitigation |
|------|------------|
| Too many skills per category | Limit to 9 per category (3 rows) |
| Category doesn't exist | Fallback to "Other" category |
