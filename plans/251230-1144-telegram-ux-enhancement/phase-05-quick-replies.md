# Phase 05: Quick Replies

**Priority:** P2 (Engagement)
**Effort:** Low
**Impact:** Medium - Better follow-up experience

---

## Objective

Add contextual quick reply buttons after responses to guide users toward relevant next actions.

## Current State

- Inline keyboards only for `/skills` menu
- No post-response buttons
- Users must know what to ask next

## Target State

```
After research result:
├── [📥 Download PDF]
├── [🔄 Dig Deeper]
└── [📧 Share]

After code review:
├── [🔧 Apply Fixes]
└── [📝 Explain More]

After any response:
├── [🔍 Search More]
└── [📚 Related Topics]
```

## Implementation

### Task 1: Create quick replies module

**File:** `agents/src/core/quick_replies.py` (NEW)

```python
"""Quick reply buttons for contextual follow-up actions.

Provides inline keyboard buttons based on response context.
"""
from typing import Dict, List, Optional

from src.utils.logging import get_logger

logger = get_logger()


# Quick reply configurations per context
QUICK_REPLIES = {
    # Research skills
    "gemini-deep-research": [
        {"text": "📥 Download PDF", "action": "download_report"},
        {"text": "🔄 Dig Deeper", "action": "research_more"},
        {"text": "📤 Share", "action": "share_report"},
    ],
    "gemini-grounding": [
        {"text": "🔍 More Details", "action": "expand"},
        {"text": "📚 Sources", "action": "show_sources"},
    ],

    # Code skills
    "code-review": [
        {"text": "🔧 Apply Fixes", "action": "apply_fixes"},
        {"text": "📝 Explain", "action": "explain_code"},
    ],
    "debugging": [
        {"text": "🔧 Fix It", "action": "fix_issue"},
        {"text": "🔍 Root Cause", "action": "root_cause"},
    ],

    # Design skills
    "canvas-design": [
        {"text": "🎨 Variations", "action": "design_variations"},
        {"text": "📐 Resize", "action": "resize"},
    ],
    "ui-ux-pro-max": [
        {"text": "💻 Code It", "action": "generate_code"},
        {"text": "🎨 More Options", "action": "more_designs"},
    ],

    # Document skills
    "pdf": [
        {"text": "📄 Summary", "action": "summarize"},
        {"text": "🔍 Find Text", "action": "search_doc"},
    ],

    # Default for any skill
    "_default": [
        {"text": "🔍 More Info", "action": "expand"},
        {"text": "🔄 Try Again", "action": "retry"},
    ],

    # Chat responses (no skill)
    "_chat": [
        {"text": "🔍 Search Web", "action": "web_search"},
        {"text": "📚 Learn More", "action": "learn_more"},
    ],
}


def build_quick_replies(
    context: Dict,
    max_buttons: int = 3
) -> List[List[Dict]]:
    """Build inline keyboard for quick replies.

    Args:
        context: Response context with skill, type, etc.
        max_buttons: Maximum buttons to show

    Returns:
        Inline keyboard rows for Telegram
    """
    skill = context.get("skill")
    response_type = context.get("type", "chat")

    # Get reply config
    if skill and skill in QUICK_REPLIES:
        replies = QUICK_REPLIES[skill]
    elif skill:
        replies = QUICK_REPLIES["_default"]
    elif response_type == "chat":
        replies = QUICK_REPLIES["_chat"]
    else:
        return []

    # Build keyboard (limit to max_buttons)
    buttons = []
    for reply in replies[:max_buttons]:
        callback_data = f"qr:{reply['action']}"
        # Include context for action
        if skill:
            callback_data += f":{skill}"

        buttons.append({
            "text": reply["text"],
            "callback_data": callback_data
        })

    # Return as single row or split into 2-button rows
    if len(buttons) <= 2:
        return [buttons]
    else:
        rows = []
        for i in range(0, len(buttons), 2):
            rows.append(buttons[i:i+2])
        return rows


def get_action_prompt(action: str, original_context: Dict) -> Optional[str]:
    """Get prompt for quick reply action.

    Args:
        action: Action identifier
        original_context: Context from original request

    Returns:
        Prompt to execute for the action
    """
    skill = original_context.get("skill", "")
    original_query = original_context.get("query", "")

    ACTION_PROMPTS = {
        # Research actions
        "download_report": None,  # Special: trigger download
        "research_more": f"Provide more in-depth research on: {original_query}",
        "share_report": None,  # Special: trigger share flow
        "expand": f"Expand on this with more details: {original_query}",
        "show_sources": "List all sources used in the previous response with links",

        # Code actions
        "apply_fixes": "Apply the suggested fixes to the code",
        "explain_code": "Explain the code in more detail, step by step",
        "fix_issue": "Fix the identified issue",
        "root_cause": "Explain the root cause of this issue in detail",

        # Design actions
        "design_variations": "Create 3 variations of this design",
        "resize": "What size would you like? (e.g., 1080x1920 for Instagram)",
        "generate_code": "Generate the code for this design",
        "more_designs": "Show me 3 alternative design options",

        # Document actions
        "summarize": "Provide a brief summary of this document",
        "search_doc": "What would you like to find in this document?",

        # General actions
        "web_search": f"Search the web for: {original_query}",
        "learn_more": f"Tell me more about: {original_query}",
        "retry": f"Try again: {original_query}",
    }

    return ACTION_PROMPTS.get(action)


def is_special_action(action: str) -> bool:
    """Check if action requires special handling (not a prompt)."""
    return action in ("download_report", "share_report", "resize")
```

### Task 2: Add quick reply callback handler

**File:** `agents/main.py`

Add to `handle_callback()`:

```python
async def handle_callback(callback: dict) -> dict:
    """Handle inline keyboard button press."""
    data = callback.get("data", "")

    # ... existing handlers ...

    # Handle quick reply callbacks
    if data.startswith("qr:"):
        return await handle_quick_reply_callback(callback)

    # ... rest of handlers ...


async def handle_quick_reply_callback(callback: dict) -> dict:
    """Handle quick reply button press."""
    from src.core.quick_replies import get_action_prompt, is_special_action
    from src.core.state import get_state_manager

    data = callback.get("data", "")
    user = callback.get("from", {})
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    callback_id = callback.get("id")

    # Parse callback data: qr:action:skill
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    skill = parts[2] if len(parts) > 2 else ""

    # Answer callback
    await answer_callback_query(callback_id, f"Processing {action}...")

    # Get original context from state
    state = get_state_manager()
    context = await state.get("quick_reply_context", str(user.get("id")))
    if not context:
        context = {"skill": skill, "query": ""}

    # Special actions
    if is_special_action(action):
        return await handle_special_action(action, context, user, chat_id)

    # Get action prompt
    prompt = get_action_prompt(action, context)
    if not prompt:
        await send_telegram_message(chat_id, "Action not available.")
        return {"ok": True}

    # If action requires user input
    if "?" in prompt:
        # Ask user for input
        await send_telegram_message(chat_id, prompt)
        # Set pending action
        from src.core.conversation_fsm import get_fsm
        fsm = await get_fsm(user.get("id"))
        fsm.set_pending_action(action)
        await fsm.transition("ask_user")
        await fsm.save()
        return {"ok": True}

    # Execute prompt
    response = await process_message(prompt, user, chat_id)
    if response:
        await send_telegram_message(chat_id, response)

    return {"ok": True}


async def handle_special_action(
    action: str,
    context: dict,
    user: dict,
    chat_id: int
) -> dict:
    """Handle special quick reply actions."""
    if action == "download_report":
        # Get latest report for user
        from src.services.firebase.storage import get_latest_report_url
        url = await get_latest_report_url(user.get("id"))
        if url:
            await send_telegram_message(
                chat_id,
                f"📥 <a href=\"{url}\">Download your report</a>"
            )
        else:
            await send_telegram_message(chat_id, "No report found.")

    elif action == "share_report":
        await send_telegram_message(
            chat_id,
            "📤 Share options:\n"
            "• Forward this message to share\n"
            "• Use /report to get shareable link"
        )

    return {"ok": True}
```

### Task 3: Store context for quick replies

**File:** `agents/main.py`

After sending response, store context:

```python
# At end of process_message, before return
async def process_message(...):
    # ... existing code ...

    # Store context for quick replies
    if intent_result and intent_result.is_skill:
        await state.set(
            "quick_reply_context",
            str(user_id),
            {
                "skill": intent_result.skill,
                "query": text[:200],
                "params": intent_result.params,
            },
            ttl_seconds=3600  # 1 hour
        )

    return result
```

### Task 4: Add quick replies to response

**File:** `agents/main.py`

Modify response sending to include quick replies:

```python
# Create helper function
async def send_response_with_quick_replies(
    chat_id: int,
    response: str,
    context: dict
) -> None:
    """Send response with quick reply buttons."""
    from src.core.quick_replies import build_quick_replies

    keyboard = build_quick_replies(context)

    if keyboard:
        await send_telegram_keyboard(chat_id, response, keyboard)
    else:
        await send_telegram_message(chat_id, response)


# Use in process_message
if response:
    await send_response_with_quick_replies(
        chat_id,
        response,
        {"skill": intent_result.skill if intent_result else None}
    )
```

## Testing

```python
# tests/test_quick_replies.py
import pytest
from src.core.quick_replies import (
    build_quick_replies,
    get_action_prompt,
    is_special_action,
)

def test_research_skill_replies():
    context = {"skill": "gemini-deep-research"}
    kb = build_quick_replies(context)

    assert len(kb) >= 1
    assert any("Download" in btn["text"] for row in kb for btn in row)

def test_code_skill_replies():
    context = {"skill": "code-review"}
    kb = build_quick_replies(context)

    assert any("Fix" in btn["text"] for row in kb for btn in row)

def test_default_replies():
    context = {"skill": "unknown-skill"}
    kb = build_quick_replies(context)

    assert len(kb) >= 1  # Gets default replies

def test_chat_replies():
    context = {"type": "chat"}
    kb = build_quick_replies(context)

    assert any("Search" in btn["text"] for row in kb for btn in row)

def test_action_prompt():
    context = {"query": "AI trends"}
    prompt = get_action_prompt("research_more", context)

    assert "AI trends" in prompt

def test_special_actions():
    assert is_special_action("download_report")
    assert is_special_action("share_report")
    assert not is_special_action("expand")
```

## Acceptance Criteria

- [ ] Quick reply buttons appear after skill responses
- [ ] Buttons are contextual to skill type
- [ ] Clicking button triggers appropriate action
- [ ] Special actions (download, share) work
- [ ] Context persists for action execution
- [ ] Max 3 buttons per response (not cluttered)

## Rollback

Remove quick reply keyboard from response sending. Keep module (no harm if unused).
