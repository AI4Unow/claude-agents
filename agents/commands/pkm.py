"""PKM (Personal Knowledge Management) commands."""
from commands.router import command_router
from src.services import pkm
from src.services.firebase.pkm import get_inbox, get_tasks, update_item, list_items
from datetime import datetime
import structlog

logger = structlog.get_logger()

# Emoji mapping for item types
TYPE_EMOJI = {
    "note": "📝",
    "task": "☐",
    "idea": "💡",
    "link": "🔗",
    "quote": "💬"
}


@command_router.command(
    name="/save",
    description="Quick capture any content (note, task, idea, link, quote)",
    usage="/save <content>",
    permission="user",
    category="pkm"
)
async def save_command(args: str, user: dict, chat_id: int) -> str:
    """Save content to PKM inbox with auto-classification."""
    if not args.strip():
        return "📝 Usage: /save <content>\n\nExample: /save Review Q1 metrics tomorrow"

    user_id = user.get("id")

    try:
        # Save and classify item
        item = await pkm.save_item(user_id, args.strip(), source="telegram")

        # Format response with type emoji
        emoji = TYPE_EMOJI.get(item.type, "📝")
        tags_str = f" #{' #'.join(item.tags)}" if item.tags else ""

        return (
            f"✓ Saved to inbox\n\n"
            f"{emoji} Type: {item.type}\n"
            f"📋 ID: `{item.id[:8]}`{tags_str}"
        )

    except Exception as e:
        logger.error("save_command_error", error=str(e), user_id=user_id)
        return f"❌ Failed to save: {str(e)[:100]}"


@command_router.command(
    name="/inbox",
    description="Show inbox items needing processing",
    usage="/inbox [limit]",
    permission="user",
    category="pkm"
)
async def inbox_command(args: str, user: dict, chat_id: int) -> str:
    """Show inbox items with preview."""
    user_id = user.get("id")

    # Parse limit
    limit = 5
    if args.strip().isdigit():
        limit = min(int(args.strip()), 20)

    try:
        items = await get_inbox(user_id, limit=limit)

        if not items:
            return "📭 Inbox is empty!\n\nUse /save to capture new items."

        # Format as numbered list
        lines = [f"📥 <b>Inbox ({len(items)} items)</b>\n"]

        for i, item in enumerate(items, 1):
            emoji = TYPE_EMOJI.get(item.type, "📝")
            preview = item.content[:60] + "..." if len(item.content) > 60 else item.content
            item_id = item.id[:8]
            lines.append(f"{i}. {emoji} `{item_id}` {preview}")

        lines.append("\nUse /outcome <id> <text> to record outcome")

        return "\n".join(lines)

    except Exception as e:
        logger.error("inbox_command_error", error=str(e), user_id=user_id)
        return f"❌ Error: {str(e)[:100]}"


@command_router.command(
    name="/tasks",
    description="Show active tasks (☐ active, ☑ done)",
    usage="/tasks [all|done]",
    permission="user",
    category="pkm"
)
async def tasks_command(args: str, user: dict, chat_id: int) -> str:
    """Show task list with status indicators."""
    user_id = user.get("id")

    # Parse filter
    show_mode = args.strip().lower()
    include_done = show_mode in ["all", "done"]
    only_done = show_mode == "done"

    try:
        tasks = await get_tasks(user_id, include_done=include_done)

        if not tasks:
            return "✓ No tasks found!\n\nUse /save to capture new tasks."

        # Filter if only showing done
        if only_done:
            tasks = [t for t in tasks if t.status == "done"]

        # Format task list
        lines = [f"☑ <b>Tasks ({len(tasks)})</b>\n"]

        for task in tasks:
            # Status indicator
            if task.status == "done":
                checkbox = "☑"
            else:
                checkbox = "☐"

            # Format task line
            preview = task.content[:60] + "..." if len(task.content) > 60 else task.content
            item_id = task.id[:8]

            # Add priority indicator
            priority_mark = ""
            if task.priority == "high":
                priority_mark = "⚠️ "
            elif task.priority == "medium":
                priority_mark = "⚡ "

            lines.append(f"{checkbox} {priority_mark}`{item_id}` {preview}")

        lines.append("\nUse /outcome <id> <text> to mark done")

        return "\n".join(lines)

    except Exception as e:
        logger.error("tasks_command_error", error=str(e), user_id=user_id)
        return f"❌ Error: {str(e)[:100]}"


@command_router.command(
    name="/find",
    description="Semantic search across all items",
    usage="/find <query>",
    permission="user",
    category="pkm"
)
async def find_command(args: str, user: dict, chat_id: int) -> str:
    """Find items using semantic search."""
    if not args.strip():
        return "🔍 Usage: /find <query>\n\nExample: /find project ideas from last week"

    user_id = user.get("id")
    query = args.strip()

    try:
        results = await pkm.find_items(user_id, query, limit=5)

        if not results:
            return f"🔍 No results for: {query[:50]}\n\nTry different keywords or check /inbox"

        # Format results
        lines = [f"🔍 <b>Results for:</b> {query[:50]}\n"]

        for i, item in enumerate(results, 1):
            emoji = TYPE_EMOJI.get(item.type, "📝")
            preview = item.content[:60] + "..." if len(item.content) > 60 else item.content
            item_id = item.id[:8]

            # Format date
            date_str = ""
            if item.created_at:
                date_str = item.created_at.strftime("%b %d")

            lines.append(f"{i}. {emoji} `{item_id}` {preview} ({date_str})")

        return "\n".join(lines)

    except Exception as e:
        logger.error("find_command_error", error=str(e), user_id=user_id)
        return f"❌ Error: {str(e)[:100]}"


@command_router.command(
    name="/outcome",
    description="Record outcome for item and mark done",
    usage="/outcome <item_id> <outcome_text>",
    permission="user",
    category="pkm"
)
async def outcome_command(args: str, user: dict, chat_id: int) -> str:
    """Record outcome and mark task done."""
    if not args.strip():
        return "✓ Usage: /outcome <id> <outcome>\n\nExample: /outcome abc123 Completed review, approved for production"

    user_id = user.get("id")

    # Parse item_id and outcome
    parts = args.strip().split(maxsplit=1)
    if len(parts) < 2:
        return "❌ Please provide both item ID and outcome text"

    item_id_prefix = parts[0]
    outcome_text = parts[1]

    try:
        # Find full item ID by prefix match
        items = await list_items(user_id, limit=100)
        matching_items = [i for i in items if i.id.startswith(item_id_prefix)]

        if not matching_items:
            return f"❌ No item found with ID starting with: `{item_id_prefix}`"

        if len(matching_items) > 1:
            return f"❌ Multiple items match `{item_id_prefix}`. Use more characters."

        item = matching_items[0]

        # Update with outcome and mark done
        updated = await update_item(
            user_id,
            item.id,
            outcome=outcome_text,
            status="done"
        )

        if not updated:
            return f"❌ Failed to update item `{item_id_prefix}`"

        emoji = TYPE_EMOJI.get(updated.type, "📝")
        return (
            f"✓ Outcome recorded\n\n"
            f"{emoji} `{item.id[:8]}` → Done\n"
            f"📋 {outcome_text[:100]}"
        )

    except Exception as e:
        logger.error("outcome_command_error", error=str(e), user_id=user_id)
        return f"❌ Error: {str(e)[:100]}"


@command_router.command(
    name="/review",
    description="Weekly review summary (items, inbox, tasks)",
    usage="/review",
    permission="user",
    category="pkm"
)
async def review_command(args: str, user: dict, chat_id: int) -> str:
    """Generate weekly review summary."""
    user_id = user.get("id")

    try:
        # Get inbox and tasks
        inbox_items = await get_inbox(user_id, limit=100)
        all_tasks = await get_tasks(user_id, include_done=True)

        # Calculate stats
        inbox_count = len(inbox_items)
        active_tasks = [t for t in all_tasks if t.status != "done"]
        done_tasks = [t for t in all_tasks if t.status == "done"]

        # Count items created this week
        now = datetime.utcnow()
        week_ago = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = week_ago.replace(day=week_ago.day - 7)

        recent_items = await list_items(user_id, limit=100)
        items_this_week = [
            i for i in recent_items
            if i.created_at and i.created_at >= week_ago
        ]

        # Format summary
        lines = [
            "📊 <b>Weekly Review</b>\n",
            f"📥 Inbox: {inbox_count} items",
            f"☐ Active tasks: {len(active_tasks)}",
            f"☑ Completed: {len(done_tasks)}",
            f"📝 New items this week: {len(items_this_week)}\n"
        ]

        # Add suggestions
        if inbox_count > 10:
            lines.append("💡 Tip: Process inbox items with /inbox")
        elif len(active_tasks) > 15:
            lines.append("💡 Tip: Focus on high-priority tasks")
        elif len(done_tasks) > 0:
            lines.append(f"✨ Great work! {len(done_tasks)} tasks completed")

        return "\n".join(lines)

    except Exception as e:
        logger.error("review_command_error", error=str(e), user_id=user_id)
        return f"❌ Error: {str(e)[:100]}"
