# Phase 01: Status Messages

**Priority:** P0 (Quick Win)
**Effort:** Low
**Impact:** High - Users see activity during processing

---

## Objective

Show real-time status updates during message processing to eliminate "dead air" feeling.

## Current State

- `send_progress_message()` exists but limited
- `edit_progress_message()` exists
- `typing_indicator()` runs in background
- No contextual status (skill name, action type)

## Target State

```
User sends: "Research AI trends"
Bot shows: 🔄 Processing...
Bot updates: 🔍 Running gemini-deep-research...
Bot updates: 📝 Generating report...
Bot shows: ✅ Complete
Bot sends: [Research result]
```

## Implementation

### Task 1: Create status message utilities

**File:** `agents/src/core/status_messages.py` (NEW)

```python
"""Status message utilities for Telegram.

Provides contextual status updates during processing.
"""
from typing import Optional, Callable, Awaitable
from enum import Enum

class ProcessingStatus(Enum):
    PROCESSING = "🔄 Processing..."
    DETECTING_INTENT = "🧠 Understanding request..."
    ROUTING_SKILL = "🔍 Finding best skill..."
    RUNNING_SKILL = "⚡ Running {skill_name}..."
    SEARCHING = "🔎 Searching..."
    THINKING = "💭 Thinking..."
    GENERATING = "📝 Generating response..."
    COMPLETE = "✅ Complete"
    ERROR = "❌ Error occurred"

STATUS_TEMPLATES = {
    "chat": ["🧠 Thinking...", "📝 Responding..."],
    "skill": ["🔍 Routing to skill...", "⚡ Running {skill}...", "📝 Finalizing..."],
    "orchestrate": ["🧠 Planning approach...", "🔧 Executing steps...", "📝 Compiling result..."],
    "research": ["🔍 Searching...", "📚 Analyzing sources...", "📝 Writing report..."],
}

class StatusUpdater:
    """Manages status message updates for a processing session."""

    def __init__(
        self,
        chat_id: int,
        message_id: int,
        edit_fn: Callable[[int, int, str], Awaitable[bool]]
    ):
        self.chat_id = chat_id
        self.message_id = message_id
        self.edit_fn = edit_fn
        self.current_status: Optional[str] = None

    async def update(self, status: str, **kwargs):
        """Update status message."""
        formatted = status.format(**kwargs) if kwargs else status
        if formatted != self.current_status:
            self.current_status = formatted
            await self.edit_fn(self.chat_id, self.message_id, f"<i>{formatted}</i>")

    async def complete(self):
        """Mark processing complete."""
        await self.update(ProcessingStatus.COMPLETE.value)

    async def error(self, msg: str = None):
        """Mark processing failed."""
        status = f"❌ {msg}" if msg else ProcessingStatus.ERROR.value
        await self.update(status)


def get_skill_status_sequence(skill_name: str) -> list:
    """Get status messages for skill execution."""
    base = [
        f"🔍 Running {skill_name}...",
    ]

    # Skill-specific additions
    if "research" in skill_name:
        base.extend(["📚 Analyzing sources...", "📝 Writing report..."])
    elif "code" in skill_name:
        base.extend(["💻 Reviewing code...", "📝 Formatting output..."])
    elif "design" in skill_name:
        base.extend(["🎨 Creating design...", "📝 Finalizing..."])
    else:
        base.append("📝 Generating response...")

    return base
```

### Task 2: Integrate status updates in process_message

**File:** `agents/main.py`
**Function:** `process_message()`

**Changes:**

1. Create StatusUpdater after progress message
2. Update status based on intent detection result
3. Update status when running skill
4. Call `complete()` on success

```python
# After line 654 (send_progress_message)
from src.core.status_messages import StatusUpdater

status_updater = StatusUpdater(
    chat_id=chat_id,
    message_id=progress_msg_id,
    edit_fn=edit_progress_message
)

# After intent detection (around line 692)
await status_updater.update("🧠 Understanding request...")

# When skill is detected
if explicit or (mode == "routed"):
    await status_updater.update(f"⚡ Running {skill_name}...")

# After execution
await status_updater.complete()
```

### Task 3: Add typing action helper

**File:** `agents/main.py`

```python
async def send_chat_action(chat_id: int, action: str = "typing"):
    """Send chat action (typing indicator)."""
    import httpx
    import os

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{bot_token}/sendChatAction"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json={
                "chat_id": chat_id,
                "action": action  # typing, upload_photo, record_video, etc.
            })
    except Exception:
        pass  # Non-blocking
```

## Testing

```python
# tests/test_status_messages.py
import pytest
from src.core.status_messages import StatusUpdater, get_skill_status_sequence

def test_skill_status_sequence_research():
    seq = get_skill_status_sequence("gemini-deep-research")
    assert "📚 Analyzing sources" in seq[1]

def test_skill_status_sequence_code():
    seq = get_skill_status_sequence("code-review")
    assert "💻 Reviewing code" in seq[1]

@pytest.mark.asyncio
async def test_status_updater():
    updates = []
    async def mock_edit(chat_id, msg_id, text):
        updates.append(text)
        return True

    updater = StatusUpdater(123, 456, mock_edit)
    await updater.update("Processing...")
    await updater.complete()

    assert len(updates) == 2
    assert "Complete" in updates[-1]
```

## Acceptance Criteria

- [ ] Status message shows immediately after user sends message
- [ ] Status updates reflect current processing stage
- [ ] Skill name shown when running skill
- [ ] "Complete" shown before final response
- [ ] No rate limit errors (max 30 edits/min)
- [ ] Error status shown on failures

## Rollback

Remove StatusUpdater instantiation and calls in `process_message()`. No database changes.
