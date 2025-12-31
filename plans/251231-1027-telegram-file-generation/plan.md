# Telegram File Generation - Implementation Plan

**Date:** 2025-12-31
**Status:** Ready for Implementation
**Effort:** 1-2 days
**Brainstorm:** [brainstorm-251231-1027-telegram-ux-enhancements.md](../reports/brainstorm-251231-1027-telegram-ux-enhancements.md)

## Overview

Add file export capabilities to AI4U.now Telegram bot:
- Send documents (CSV, JSON) via Telegram API
- `/export` command with wizard flow
- Conversation history export
- Usage stats export

## Phases

| Phase | Description | Effort |
|-------|-------------|--------|
| 01 | Add `send_telegram_document()` function | 30 min |
| 02 | Create export wizard infrastructure | 1 hour |
| 03 | Implement conversation export | 1 hour |
| 04 | Implement activity stats export | 30 min |

---

## Phase 01: send_telegram_document()

**File:** `agents/main.py` (after `delete_telegram_message`)

### Implementation

```python
async def send_telegram_document(
    chat_id: int,
    file_bytes: bytes,
    filename: str,
    caption: str = None
) -> bool:
    """Send document file via Telegram API.

    Args:
        chat_id: Telegram chat ID
        file_bytes: File content as bytes
        filename: Filename with extension (e.g., "export.csv")
        caption: Optional caption for the file

    Returns:
        True if sent successfully
    """
    import httpx
    import structlog

    logger = structlog.get_logger()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    if not token:
        logger.error("telegram_no_token")
        return False

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Use multipart form for file upload
            files = {"document": (filename, file_bytes)}
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption[:1024]  # Telegram limit
                data["parse_mode"] = "HTML"

            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                files=files,
                data=data
            )
            result = response.json()

            if not result.get("ok"):
                logger.error("telegram_document_failed", error=result.get("description"))
                return False

            logger.info("telegram_document_sent", filename=filename, chat_id=chat_id)
            return True

    except Exception as e:
        logger.error("telegram_document_error", error=str(e)[:100])
        return False
```

### Location

Insert after `delete_telegram_message()` function (~line 1048).

---

## Phase 02: Export Wizard Infrastructure

**Files:**
- `agents/commands/user.py` - Add `/export` command
- `agents/src/core/state.py` - Add wizard state management

### 2.1 Wizard State (state.py)

Add to `StateManager` class:

```python
# Wizard state constants
COLLECTION_WIZARD = "wizard_state"

async def get_wizard_state(self, user_id: int) -> Optional[Dict]:
    """Get current wizard state for user."""
    data = await self.get(self.COLLECTION_WIZARD, str(user_id), ttl_seconds=300)
    return data

async def set_wizard_state(self, user_id: int, wizard_type: str, step: str, data: Dict = None):
    """Set wizard state for multi-step flows."""
    await self.set(
        self.COLLECTION_WIZARD,
        str(user_id),
        {
            "wizard": wizard_type,
            "step": step,
            "data": data or {},
            "updated_at": time.time()
        },
        ttl_seconds=300  # 5 min timeout
    )

async def clear_wizard_state(self, user_id: int):
    """Clear wizard state."""
    await self._invalidate_cache(self.COLLECTION_WIZARD, str(user_id))
```

### 2.2 Export Command (user.py)

```python
@command_router.command(
    name="/export",
    description="Export your data (conversations, stats)",
    permission="user",
    category="account"
)
async def export_command(args: str, user: dict, chat_id: int) -> str:
    """Start export wizard."""
    import sys

    main = sys.modules.get("main")
    if not main:
        return "Export unavailable."

    keyboard = [
        [
            {"text": "💬 Conversations", "callback_data": "export:type:conversations"},
            {"text": "📊 Usage Stats", "callback_data": "export:type:stats"}
        ],
        [
            {"text": "🗂️ PKM Notes", "callback_data": "export:type:pkm"},
            {"text": "❌ Cancel", "callback_data": "export:cancel"}
        ]
    ]

    await main.send_telegram_keyboard(
        chat_id,
        "<b>📤 Export Data</b>\n\nWhat would you like to export?",
        keyboard
    )

    # Set wizard state
    from src.core.state import get_state_manager
    state = get_state_manager()
    await state.set_wizard_state(user.get("id"), "export", "select_type")

    return None  # Message sent via keyboard
```

### 2.3 Callback Handler (main.py)

Add to `handle_callback()` function export handlers:

```python
# Export wizard callbacks
if callback_data.startswith("export:"):
    return await handle_export_callback(callback_data, user, chat_id, message_id)
```

### 2.4 Export Callback Handler (main.py)

```python
async def handle_export_callback(
    callback_data: str,
    user: dict,
    chat_id: int,
    message_id: int
) -> dict:
    """Handle export wizard callbacks."""
    import structlog
    from src.core.state import get_state_manager

    logger = structlog.get_logger()
    user_id = user.get("id")
    state = get_state_manager()
    parts = callback_data.split(":")

    if len(parts) < 2:
        return {"ok": True}

    action = parts[1]
    value = parts[2] if len(parts) > 2 else None

    if action == "cancel":
        await state.clear_wizard_state(user_id)
        await edit_progress_message(chat_id, message_id, "Export cancelled.")
        return {"ok": True}

    if action == "type":
        # User selected export type
        await state.set_wizard_state(user_id, "export", "select_format", {"type": value})

        keyboard = [
            [
                {"text": "📄 CSV", "callback_data": f"export:format:csv"},
                {"text": "📋 JSON", "callback_data": f"export:format:json"}
            ],
            [
                {"text": "❌ Cancel", "callback_data": "export:cancel"}
            ]
        ]

        await send_telegram_keyboard(
            chat_id,
            f"<b>📤 Export {value.title()}</b>\n\nSelect format:",
            keyboard
        )
        # Delete old message
        await delete_telegram_message(chat_id, message_id)
        return {"ok": True}

    if action == "format":
        # User selected format, execute export
        wizard_state = await state.get_wizard_state(user_id)
        if not wizard_state:
            await send_telegram_message(chat_id, "Export session expired. Use /export again.")
            return {"ok": True}

        export_type = wizard_state.get("data", {}).get("type", "conversations")
        export_format = value  # csv or json

        await edit_progress_message(chat_id, message_id, "⏳ <i>Generating export...</i>")

        # Execute export
        success = await execute_export(user_id, chat_id, export_type, export_format)

        await state.clear_wizard_state(user_id)

        if success:
            await delete_telegram_message(chat_id, message_id)
        else:
            await edit_progress_message(chat_id, message_id, "❌ Export failed. Try again later.")

        return {"ok": True}

    return {"ok": True}
```

---

## Phase 03: Conversation Export

**File:** `agents/main.py`

```python
async def execute_export(
    user_id: int,
    chat_id: int,
    export_type: str,
    export_format: str
) -> bool:
    """Execute data export and send file."""
    import json
    import csv
    import io
    from datetime import datetime

    try:
        if export_type == "conversations":
            data = await export_conversations(user_id)
        elif export_type == "stats":
            data = await export_activity_stats(user_id)
        elif export_type == "pkm":
            data = await export_pkm_notes(user_id)
        else:
            return False

        if not data:
            await send_telegram_message(chat_id, "No data to export.")
            return True

        # Generate file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")

        if export_format == "json":
            file_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
            filename = f"{export_type}_{timestamp}.json"
        else:  # csv
            file_bytes = convert_to_csv(data, export_type)
            filename = f"{export_type}_{timestamp}.csv"

        # Send file
        return await send_telegram_document(
            chat_id,
            file_bytes,
            filename,
            caption=f"📤 <b>{export_type.title()}</b> export\n{len(data) if isinstance(data, list) else 1} items"
        )

    except Exception as e:
        import structlog
        structlog.get_logger().error("export_error", error=str(e)[:100])
        return False


async def export_conversations(user_id: int) -> List[Dict]:
    """Export user's conversation history."""
    from src.core.state import get_state_manager

    state = get_state_manager()
    messages = await state.get_conversation(user_id)

    # Add metadata
    return [{
        "role": msg.get("role"),
        "content": msg.get("content"),
    } for msg in messages]


def convert_to_csv(data: List[Dict], export_type: str) -> bytes:
    """Convert data to CSV format."""
    import csv
    import io

    if not data:
        return b""

    output = io.StringIO()

    if export_type == "conversations":
        writer = csv.DictWriter(output, fieldnames=["role", "content"])
        writer.writeheader()
        writer.writerows(data)
    elif export_type == "stats":
        # Stats is a dict, convert to rows
        writer = csv.writer(output)
        writer.writerow(["metric", "value"])
        for key, value in data.items():
            if isinstance(value, (list, dict)):
                value = str(value)
            writer.writerow([key, value])
    else:
        # Generic: use first item's keys as headers
        keys = list(data[0].keys()) if data else []
        writer = csv.DictWriter(output, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)

    return output.getvalue().encode("utf-8")
```

---

## Phase 04: Activity Stats Export

**File:** `agents/main.py`

```python
async def export_activity_stats(user_id: int) -> Dict:
    """Export user's activity statistics."""
    from src.services.activity import get_activity_stats, get_recent_activities

    stats = await get_activity_stats(user_id)
    recent = await get_recent_activities(user_id, limit=100)

    return {
        "summary": stats,
        "recent_activities": [
            {
                "action_type": a.get("action_type"),
                "skill": a.get("skill"),
                "summary": a.get("summary"),
                "timestamp": a.get("timestamp")
            }
            for a in recent
        ]
    }


async def export_pkm_notes(user_id: int) -> List[Dict]:
    """Export user's PKM notes."""
    from src.services.firebase.pkm import get_user_notes

    notes = await get_user_notes(user_id, limit=500)
    return notes
```

---

## File Changes Summary

| File | Changes |
|------|---------|
| `main.py` | Add `send_telegram_document()`, export handlers, export functions |
| `src/core/state.py` | Add wizard state methods |
| `commands/user.py` | Add `/export` command |

---

## Testing Checklist

- [ ] `/export` shows keyboard with options
- [ ] Selecting "Conversations" → "CSV" generates file
- [ ] Selecting "Conversations" → "JSON" generates file
- [ ] Selecting "Usage Stats" → "CSV" generates file
- [ ] Cancel button clears wizard state
- [ ] Wizard timeout (5 min) works correctly
- [ ] Empty data shows appropriate message
- [ ] Large exports (>50MB) fail gracefully with message

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| File size >50MB | Check size before sending, split or compress |
| Timeout during export | Use progress messages, async processing |
| Memory usage for large exports | Stream CSV instead of building in memory |

---

## Future Enhancements

- PDF export with formatting (Phase 2)
- Date range filter in wizard
- Email delivery option for large exports
- Scheduled exports (daily/weekly)
