---
phase: 5
title: "Proactive Notifications"
parent: plan.md
status: pending
effort: 2h
---

# Phase 5: Proactive Notifications

## Context

- Parent: [plan.md](./plan.md)
- Depends on: [Phase 4](./phase-04-reactions-progress.md)
- Code: `agents/main.py`, `agents/src/services/firebase.py`

## Overview

Enable scheduled reminders and proactive notifications to users.

## Requirements

1. /remind command for scheduling messages
2. Store reminders in Firebase
3. Cron job to check and send due reminders
4. Daily summary notification (optional)
5. Notification preferences per user

## Architecture

```
/remind 2h Check the deploy → Store in Firebase
                                    ↓
                          reminders/{id}
                          {user_id, chat_id, message, due_at}
                                    ↓
Cron (every 5 min) → Query due → Send notification → Mark sent
```

## Related Code Files

- `agents/main.py` - commands, cron jobs
- `agents/src/services/firebase.py` - reminder storage

## Implementation Steps

### Step 1: Add /remind command

```python
elif cmd == "/remind":
    if not args:
        return (
            "Usage: /remind <time> <message>\n"
            "Examples:\n"
            "  /remind 1h Check the deployment\n"
            "  /remind 30m Call mom\n"
            "  /remind 2d Review code"
        )

    # Parse time and message
    parts = args.split(maxsplit=1)
    if len(parts) < 2:
        return "Please provide both time and message."

    time_str, message = parts
    due_at = parse_reminder_time(time_str)

    if not due_at:
        return f"Invalid time format: {time_str}. Use: 30m, 2h, 1d"

    # Store reminder
    from src.services.firebase import create_reminder
    reminder_id = await create_reminder(
        user_id=user.get("id"),
        chat_id=chat_id,
        message=message,
        due_at=due_at
    )

    return f"⏰ Reminder set for {due_at.strftime('%Y-%m-%d %H:%M UTC')}\nID: {reminder_id[:8]}..."
```

### Step 2: Add time parser

```python
def parse_reminder_time(time_str: str) -> datetime:
    """Parse relative time string like '30m', '2h', '1d'."""
    import re
    from datetime import datetime, timedelta, timezone

    match = re.match(r"(\d+)([mhd])", time_str.lower())
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)

    now = datetime.now(timezone.utc)

    if unit == "m":
        return now + timedelta(minutes=amount)
    elif unit == "h":
        return now + timedelta(hours=amount)
    elif unit == "d":
        return now + timedelta(days=amount)

    return None
```

### Step 3: Add Firebase reminder functions

```python
# In src/services/firebase.py:

async def create_reminder(
    user_id: int,
    chat_id: int,
    message: str,
    due_at: datetime
) -> str:
    """Create a reminder. Returns reminder ID."""
    db = get_db()
    doc_ref = db.collection("reminders").document()
    doc_ref.set({
        "user_id": user_id,
        "chat_id": chat_id,
        "message": message,
        "due_at": due_at,
        "sent": False,
        "created_at": firestore.SERVER_TIMESTAMP
    })
    return doc_ref.id


async def get_due_reminders(limit: int = 50) -> List[Dict]:
    """Get reminders that are due and not sent."""
    from datetime import datetime, timezone

    db = get_db()
    now = datetime.now(timezone.utc)

    query = (
        db.collection("reminders")
        .where("sent", "==", False)
        .where("due_at", "<=", now)
        .limit(limit)
    )

    return [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]


async def mark_reminder_sent(reminder_id: str):
    """Mark reminder as sent."""
    db = get_db()
    db.collection("reminders").document(reminder_id).update({
        "sent": True,
        "sent_at": firestore.SERVER_TIMESTAMP
    })
```

### Step 4: Add reminder cron job

```python
@app.function(
    image=image,
    secrets=secrets,
    schedule=modal.Cron("*/5 * * * *"),  # Every 5 minutes
)
async def send_due_reminders():
    """Check for due reminders and send them."""
    import structlog
    from src.services.firebase import init_firebase, get_due_reminders, mark_reminder_sent

    logger = structlog.get_logger()
    init_firebase()

    try:
        reminders = await get_due_reminders()
        logger.info("checking_reminders", count=len(reminders))

        for reminder in reminders:
            chat_id = reminder.get("chat_id")
            message = reminder.get("message")
            reminder_id = reminder.get("id")

            # Send notification
            await send_telegram_message(
                chat_id,
                f"⏰ <b>Reminder</b>\n\n{message}"
            )

            # Mark as sent
            await mark_reminder_sent(reminder_id)
            logger.info("reminder_sent", id=reminder_id)

    except Exception as e:
        logger.error("reminder_error", error=str(e))
```

### Step 5: Add /reminders command to list

```python
elif cmd == "/reminders":
    from src.services.firebase import get_user_reminders

    reminders = await get_user_reminders(user.get("id"), limit=10)

    if not reminders:
        return "No pending reminders. Use /remind to create one."

    lines = ["<b>Your Reminders:</b>\n"]
    for r in reminders:
        due = r.get("due_at").strftime("%m/%d %H:%M")
        msg = r.get("message")[:30]
        lines.append(f"• {due} - {msg}...")

    return "\n".join(lines)
```

## Todo List

- [ ] Add /remind command handler
- [ ] Add parse_reminder_time function
- [ ] Add Firebase reminder functions
- [ ] Add reminder cron job (every 5 min)
- [ ] Add /reminders list command
- [ ] Add /cancelremind command
- [ ] Test reminder flow

## Success Criteria

- [ ] Reminders created and stored
- [ ] Cron sends due reminders
- [ ] User can list pending reminders
- [ ] Reminders marked as sent
- [ ] Time parsing works (m, h, d)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Cron missed | Low | 5min interval catches up |
| Duplicate sends | Medium | Mark sent atomically |
| Timezone confusion | Medium | Always use UTC |

## Security Considerations

- Validate chat_id matches user_id
- Rate limit reminder creation
- Max 50 reminders per user
- Don't expose reminder IDs

## Next Steps

After all phases complete:
1. Deploy to Modal
2. Test end-to-end flow
3. Monitor performance
4. Gather user feedback
