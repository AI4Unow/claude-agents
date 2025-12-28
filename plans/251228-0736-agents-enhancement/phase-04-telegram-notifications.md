# Phase 4: Telegram Admin Notifications

## Context

- Plan: `./plan.md`
- Depends on: Phase 3 (ImprovementService)

## Overview

- **Priority:** P1
- **Status:** Pending
- **Effort:** 3h

Send improvement proposals to admin via Telegram with full diff and approve/reject buttons.

## Key Insights

- Existing: `send_telegram_keyboard()` in main.py for inline keyboards
- Existing: `handle_callback()` handles button presses
- Need: ADMIN_TELEGRAM_ID environment variable
- Need: Diff formatting for Telegram HTML
- Telegram message limit: 4096 characters

## Requirements

### Functional
- Send improvement proposal to admin Telegram chat
- Show full diff (before/after) inline
- Include [✅ Approve] and [❌ Reject] buttons
- Handle button callbacks for approve/reject
- Confirm action success to admin
- Notify admin of Volume commit

### Non-Functional
- Message chunking if diff > 4096 chars
- HTML escaping for code/markdown content
- Graceful handling if admin ID not configured

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                     TELEGRAM NOTIFICATION FLOW                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ImprovementService.store_proposal()                                 │
│       │                                                              │
│       └──► send_improvement_notification(proposal)                   │
│                │                                                     │
│                ▼                                                     │
│  ┌────────────────────────────────────────────────────────┐         │
│  │ 🔧 Improvement Proposal                                 │         │
│  │                                                         │         │
│  │ <b>Skill:</b> telegram-chat                            │         │
│  │ <b>Error:</b> Tool web_search failed: API timeout      │         │
│  │                                                         │         │
│  │ <b>Proposed Memory Addition:</b>                       │         │
│  │ <pre>When web search times out, retry once...</pre>    │         │
│  │                                                         │         │
│  │ <b>Error History Entry:</b>                            │         │
│  │ <pre>2025-12-28: web_search timeout - retry</pre>      │         │
│  │                                                         │         │
│  │ [✅ Approve]  [❌ Reject]                               │         │
│  └────────────────────────────────────────────────────────┘         │
│                │                                                     │
│                ▼                                                     │
│  User clicks button → handle_callback()                              │
│       │                                                              │
│       ├── action == "improve_approve"                                │
│       │       └── ImprovementService.apply_proposal()                │
│       │       └── Send confirmation + Volume commit                  │
│       │                                                              │
│       └── action == "improve_reject"                                 │
│               └── ImprovementService.reject_proposal()               │
│               └── Send confirmation                                  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Related Code Files

### Modify
- `agents/main.py` - Add notification function and callback handlers
- `agents/src/services/telegram.py` - Add diff formatting utilities

### Secrets
- `admin-credentials` Modal secret - Add ADMIN_TELEGRAM_ID

## Implementation Steps

1. Add ADMIN_TELEGRAM_ID to Modal secrets
2. Create diff formatting utilities in telegram.py
3. Create send_improvement_notification() function
4. Extend handle_callback() for improve_approve/improve_reject
5. Add confirmation messages
6. Test full flow with sample proposal

## Code Changes

### telegram.py additions

```python
# In agents/src/services/telegram.py

def format_improvement_proposal(proposal: dict) -> str:
    """Format improvement proposal for Telegram HTML."""
    skill = escape_html(proposal.get("skill_name", "unknown"))
    error = escape_html(proposal.get("error_summary", "")[:300])
    memory = escape_html(proposal.get("proposed_memory_addition", "")[:500])
    error_entry = escape_html(proposal.get("proposed_error_entry", "")[:200])

    return f"""🔧 <b>Improvement Proposal</b>

<b>Skill:</b> {skill}

<b>Error:</b>
<pre>{error}</pre>

<b>Proposed Memory Addition:</b>
<pre>{memory}</pre>

<b>Error History Entry:</b>
<pre>{error_entry}</pre>

<i>Proposal ID: {proposal.get("id", "?")[:8]}...</i>"""


def build_improvement_keyboard(proposal_id: str) -> list:
    """Build inline keyboard for approve/reject."""
    return [
        [
            {"text": "✅ Approve", "callback_data": f"improve_approve:{proposal_id}"},
            {"text": "❌ Reject", "callback_data": f"improve_reject:{proposal_id}"},
        ]
    ]
```

### main.py additions

```python
# In agents/main.py

async def send_improvement_notification(proposal: dict):
    """Send improvement proposal to admin for approval."""
    import structlog
    from src.services.telegram import format_improvement_proposal, build_improvement_keyboard

    logger = structlog.get_logger()

    admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
    if not admin_id:
        logger.warning("admin_telegram_id_not_configured")
        return False

    try:
        admin_id = int(admin_id)
    except ValueError:
        logger.error("invalid_admin_telegram_id")
        return False

    message = format_improvement_proposal(proposal)
    keyboard = build_improvement_keyboard(proposal["id"])

    return await send_telegram_keyboard(admin_id, message, keyboard)


# Extend handle_callback() in main.py

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

    # Existing handlers...
    if action == "cat":
        await handle_category_select(chat_id, message_id, value)

    elif action == "skill":
        await handle_skill_select(chat_id, value, user)

    elif action == "mode":
        from src.core.state import get_state_manager
        state = get_state_manager()
        await state.set_user_mode(user.get("id"), value)
        await send_telegram_message(chat_id, f"Mode set to: <b>{value}</b>")

    # NEW: Improvement approval handlers
    elif action == "improve_approve":
        await handle_improvement_approve(chat_id, value, user)

    elif action == "improve_reject":
        await handle_improvement_reject(chat_id, value, user)

    return {"ok": True}


async def handle_improvement_approve(chat_id: int, proposal_id: str, user: dict):
    """Handle improvement approval."""
    import structlog
    from src.core.improvement import get_improvement_service

    logger = structlog.get_logger()

    # Verify admin
    admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
    if str(user.get("id")) != admin_id:
        await send_telegram_message(chat_id, "⛔ Only admin can approve proposals.")
        return

    service = get_improvement_service()
    success = await service.apply_proposal(proposal_id, user.get("id"))

    if success:
        # Commit to Modal Volume
        try:
            skills_volume.commit()
            await send_telegram_message(
                chat_id,
                f"✅ <b>Proposal approved!</b>\n\n"
                f"Skill info.md updated.\n"
                f"Modal Volume committed.\n"
                f"<i>ID: {proposal_id[:8]}...</i>"
            )
            logger.info("proposal_approved", id=proposal_id)
        except Exception as e:
            await send_telegram_message(
                chat_id,
                f"⚠️ Proposal applied but Volume commit failed:\n<pre>{str(e)[:100]}</pre>"
            )
    else:
        await send_telegram_message(chat_id, "❌ Failed to apply proposal. Check logs.")


async def handle_improvement_reject(chat_id: int, proposal_id: str, user: dict):
    """Handle improvement rejection."""
    import structlog
    from src.core.improvement import get_improvement_service

    logger = structlog.get_logger()

    # Verify admin
    admin_id = os.environ.get("ADMIN_TELEGRAM_ID")
    if str(user.get("id")) != admin_id:
        await send_telegram_message(chat_id, "⛔ Only admin can reject proposals.")
        return

    service = get_improvement_service()
    success = await service.reject_proposal(proposal_id, user.get("id"), "Rejected by admin")

    if success:
        await send_telegram_message(
            chat_id,
            f"❌ <b>Proposal rejected.</b>\n<i>ID: {proposal_id[:8]}...</i>"
        )
        logger.info("proposal_rejected", id=proposal_id)
    else:
        await send_telegram_message(chat_id, "❌ Failed to reject proposal. Check logs.")
```

## Todo List

- [ ] Add ADMIN_TELEGRAM_ID to admin-credentials Modal secret
- [ ] Add format_improvement_proposal() to telegram.py
- [ ] Add build_improvement_keyboard() to telegram.py
- [ ] Add send_improvement_notification() to main.py
- [ ] Add handle_improvement_approve() to main.py
- [ ] Add handle_improvement_reject() to main.py
- [ ] Extend handle_callback() with new actions
- [ ] Test notification flow
- [ ] Test approve flow with Volume commit
- [ ] Test reject flow

## Success Criteria

- Admin receives Telegram notification with proposal
- Full diff displayed inline (memory addition + error entry)
- Approve button triggers apply_proposal() and Volume commit
- Reject button triggers reject_proposal()
- Confirmation messages sent after action
- Non-admin users cannot approve/reject

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Admin ID not configured | High | Log warning, skip notification |
| Message too long | Medium | Truncate fields, chunk if needed |
| Volume commit fails | Medium | Show error, proposal still marked approved |
| Non-admin tries to approve | Medium | Check admin ID, reject action |

## Security Considerations

- Verify user.id matches ADMIN_TELEGRAM_ID before approve/reject
- Don't expose full proposal ID in messages (show truncated)
- Rate limit notifications to prevent spam

## Next Steps

After this phase, proceed to Phase 5: Integration & Testing
