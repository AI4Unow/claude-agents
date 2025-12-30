"""Reminders commands: create and list reminders."""
from commands.router import command_router


def parse_reminder_time(time_str: str):
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


@command_router.command(
    name="/remind",
    description="Create a reminder (admin only)",
    usage="/remind <time> <message>",
    permission="admin",
    category="reminders"
)
async def remind_command(args: str, user: dict, chat_id: int) -> str:
    """Create a reminder."""
    if not args:
        return (
            "Usage: /remind <time> <message>\n\n"
            "Examples:\n"
            "  /remind 1h Check the deployment\n"
            "  /remind 30m Call mom\n"
            "  /remind 2d Review code"
        )

    # Parse time and message
    remind_parts = args.split(maxsplit=1)
    if len(remind_parts) < 2:
        return "❌ Please provide both time and message."

    time_str, message = remind_parts
    due_at = parse_reminder_time(time_str)

    if not due_at:
        return f"❌ Invalid time format: {time_str}\nUse: 30m, 2h, 1d"

    # Store reminder
    from src.services.firebase import create_reminder

    reminder_id = await create_reminder(
        user_id=user.get("id"),
        chat_id=chat_id,
        message=message,
        due_at=due_at
    )

    return f"⏰ Reminder set for {due_at.strftime('%Y-%m-%d %H:%M UTC')}\nID: {reminder_id[:8]}..."


@command_router.command(
    name="/reminders",
    description="List your pending reminders (admin only)",
    permission="admin",
    category="reminders"
)
async def reminders_command(args: str, user: dict, chat_id: int) -> str:
    """List user's pending reminders."""
    from src.services.firebase import get_user_reminders

    reminders = await get_user_reminders(user.get("id"), limit=10)

    if not reminders:
        return "No pending reminders. Use /remind to create one."

    lines = ["<b>Your Reminders:</b>\n"]
    for r in reminders:
        due = r.get("due_at")
        if hasattr(due, "strftime"):
            due_str = due.strftime("%m/%d %H:%M")
        else:
            due_str = str(due)[:16]
        msg = r.get("message", "")[:30]
        lines.append(f"• {due_str} - {msg}...")

    return "\n".join(lines)
