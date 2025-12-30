# Phase 02: Smart Onboarding

**Priority:** P0 (Quick Win)
**Effort:** Low
**Impact:** High - Better first impression for new users

---

## Objective

Create an interactive welcome experience for first-time users that showcases capabilities without overwhelming.

## Current State

```python
# commands/user.py - Basic text welcome
@command_router.command(name="/start", ...)
async def start_command(args, user, chat_id):
    return f"""Hello {name}!
    I'm AI4U.now Bot...
    • Just send any message...
    • Use /help...
    """
```

## Target State

```
First-time user sends /start:
├── Bot detects first-time user
├── Shows interactive welcome with demo buttons
├── Tracks onboarding state
└── After demo, shows "You're ready!"

Returning user sends /start:
└── Shows brief welcome, no demo
```

## Implementation

### Task 1: Create onboarding module

**File:** `agents/src/core/onboarding.py` (NEW)

```python
"""First-time user onboarding experience.

Provides interactive welcome flow with demo capabilities.
"""
from typing import Optional
from dataclasses import dataclass
from enum import Enum


class OnboardingStep(Enum):
    NEW = "new"           # Never seen before
    WELCOME = "welcome"   # Saw welcome message
    DEMO = "demo"         # Tried a demo
    COMPLETE = "complete" # Onboarding finished


@dataclass
class OnboardingState:
    step: OnboardingStep
    demos_tried: list  # ["research", "code", ...]


async def is_first_time_user(user_id: int) -> bool:
    """Check if user has never used the bot."""
    from src.core.state import get_state_manager
    state = get_state_manager()

    # Check if user has any conversation history
    history = await state.get_conversation(str(user_id))
    if history and len(history) > 0:
        return False

    # Check onboarding state
    onboarding = await state.get(
        "onboarding",
        str(user_id)
    )
    return onboarding is None


async def get_onboarding_state(user_id: int) -> OnboardingState:
    """Get user's onboarding state."""
    from src.core.state import get_state_manager
    state = get_state_manager()

    data = await state.get("onboarding", str(user_id))
    if not data:
        return OnboardingState(step=OnboardingStep.NEW, demos_tried=[])

    return OnboardingState(
        step=OnboardingStep(data.get("step", "new")),
        demos_tried=data.get("demos_tried", [])
    )


async def set_onboarding_step(user_id: int, step: OnboardingStep):
    """Update onboarding step."""
    from src.core.state import get_state_manager
    state = get_state_manager()

    current = await get_onboarding_state(user_id)
    await state.set(
        "onboarding",
        str(user_id),
        {
            "step": step.value,
            "demos_tried": current.demos_tried,
        },
        ttl_seconds=86400 * 30  # 30 days
    )


async def mark_demo_tried(user_id: int, demo_type: str):
    """Mark that user tried a demo."""
    from src.core.state import get_state_manager
    state = get_state_manager()

    current = await get_onboarding_state(user_id)
    if demo_type not in current.demos_tried:
        current.demos_tried.append(demo_type)

    await state.set(
        "onboarding",
        str(user_id),
        {
            "step": OnboardingStep.DEMO.value,
            "demos_tried": current.demos_tried,
        },
        ttl_seconds=86400 * 30
    )


def build_welcome_message(name: str) -> str:
    """Build welcome message for new users."""
    return f"""👋 Welcome, {name}!

I'm your AI assistant with <b>55+ skills</b>.

<b>What I can do:</b>
• 🔍 <b>Research</b> any topic in depth
• 💻 <b>Code</b> review, write, debug
• 🎨 <b>Design</b> posters, images
• 📄 <b>Documents</b> (PDF, DOCX, PPTX)
• 🌐 <b>Web</b> search and analysis

<b>Just chat naturally!</b> No commands needed.

<i>Try a demo below, or just ask me anything:</i>"""


def build_welcome_keyboard() -> list:
    """Build inline keyboard for welcome demos."""
    return [
        [
            {"text": "🔍 Try Research", "callback_data": "demo:research"},
            {"text": "💻 Try Coding", "callback_data": "demo:code"},
        ],
        [
            {"text": "🎨 Try Design", "callback_data": "demo:design"},
            {"text": "📖 All Skills", "callback_data": "cat:main"},
        ],
        [
            {"text": "✓ Skip, I'm ready!", "callback_data": "demo:skip"},
        ],
    ]


def build_returning_message(name: str) -> str:
    """Build message for returning users."""
    return f"""Welcome back, {name}! 👋

<b>Quick tips:</b>
• Just chat naturally - no commands needed
• Use /skills to browse all capabilities
• Use /help for command reference

What can I help you with?"""


# Demo prompts for each category
DEMO_PROMPTS = {
    "research": "What are the latest trends in AI assistants for 2025?",
    "code": "Write a Python function to calculate fibonacci numbers efficiently",
    "design": "Create a modern poster design for a tech conference",
}


def get_demo_prompt(demo_type: str) -> Optional[str]:
    """Get demo prompt for a category."""
    return DEMO_PROMPTS.get(demo_type)
```

### Task 2: Update /start command

**File:** `agents/commands/user.py`

```python
@command_router.command(
    name="/start",
    description="Welcome message and quick start guide",
    permission="guest",
    category="general"
)
async def start_command(args: str, user: dict, chat_id: int) -> str:
    """Welcome message with onboarding for new users."""
    from src.core.onboarding import (
        is_first_time_user,
        get_onboarding_state,
        set_onboarding_step,
        OnboardingStep,
        build_welcome_message,
        build_welcome_keyboard,
        build_returning_message,
    )
    # Import send_telegram_keyboard from main (avoid circular)
    import sys
    main = sys.modules.get("main")
    send_keyboard = main.send_telegram_keyboard if main else None

    name = user.get("first_name", "there")
    user_id = user.get("id")

    # Check if first-time user
    if await is_first_time_user(user_id):
        # Show interactive welcome
        await set_onboarding_step(user_id, OnboardingStep.WELCOME)

        if send_keyboard:
            await send_keyboard(
                chat_id,
                build_welcome_message(name),
                build_welcome_keyboard()
            )
            return None  # Message sent with keyboard

        # Fallback to text-only
        return build_welcome_message(name)

    # Returning user - brief welcome
    return build_returning_message(name)
```

### Task 3: Add demo callback handler

**File:** `agents/main.py`
**Function:** Add to `handle_callback()`

```python
# In handle_callback(), add case for demo:* callbacks
async def handle_callback(callback: dict) -> dict:
    # ... existing code ...

    data = callback.get("data", "")

    # Handle demo callbacks
    if data.startswith("demo:"):
        demo_type = data.split(":")[1]
        return await handle_demo_callback(callback, demo_type)

    # ... rest of existing handlers ...


async def handle_demo_callback(callback: dict, demo_type: str) -> dict:
    """Handle demo button press from onboarding."""
    from src.core.onboarding import (
        mark_demo_tried,
        get_demo_prompt,
        set_onboarding_step,
        OnboardingStep,
    )

    user = callback.get("from", {})
    user_id = user.get("id")
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    callback_id = callback.get("id")

    # Answer callback to remove loading state
    await answer_callback_query(callback_id, "Starting demo...")

    if demo_type == "skip":
        # User skipped onboarding
        await set_onboarding_step(user_id, OnboardingStep.COMPLETE)
        await send_telegram_message(
            chat_id,
            "✨ You're all set! Just send any message to get started."
        )
        return {"ok": True}

    # Get demo prompt
    prompt = get_demo_prompt(demo_type)
    if not prompt:
        return {"ok": True}

    # Mark demo tried
    await mark_demo_tried(user_id, demo_type)

    # Show demo prompt
    await send_telegram_message(
        chat_id,
        f"<i>Demo: {demo_type.title()}</i>\n\n<b>Trying:</b> {prompt}"
    )

    # Execute demo (reuse process_message)
    response = await process_message(prompt, user, chat_id)
    if response:
        await send_telegram_message(chat_id, response)

    # Show completion message
    await send_telegram_message(
        chat_id,
        "✨ <b>Great!</b> You've seen what I can do. Try another demo or just ask me anything!"
    )

    return {"ok": True}
```

### Task 4: Add StateManager methods for onboarding

**File:** `agents/src/core/state.py`

Already supports generic `get()` and `set()` with TTL. No changes needed - onboarding module uses existing API.

## Testing

```python
# tests/test_onboarding.py
import pytest
from src.core.onboarding import (
    is_first_time_user,
    build_welcome_message,
    build_welcome_keyboard,
    OnboardingStep,
)

def test_welcome_message_contains_key_elements():
    msg = build_welcome_message("John")
    assert "John" in msg
    assert "55+ skills" in msg
    assert "Research" in msg
    assert "Code" in msg

def test_welcome_keyboard_has_demos():
    kb = build_welcome_keyboard()
    assert len(kb) == 3  # 3 rows
    assert any("Research" in btn["text"] for row in kb for btn in row)

@pytest.mark.asyncio
async def test_first_time_user_detection():
    # Mock state manager
    # Test that user with no history is first-time
    pass
```

## Acceptance Criteria

- [ ] First-time user sees interactive welcome with buttons
- [ ] Demo buttons trigger example prompts
- [ ] "Skip" button completes onboarding immediately
- [ ] Returning user sees brief welcome (no buttons)
- [ ] Onboarding state persists across sessions
- [ ] Demo execution shows actual skill results

## Rollback

Remove onboarding.py and revert start_command to original. No database changes needed (onboarding collection is optional).
