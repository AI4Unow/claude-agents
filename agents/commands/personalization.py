"""Personalization commands: profile, context, macros, and activity."""
from commands.router import command_router


@command_router.command(
    name="/profile",
    description="View or configure your profile preferences",
    usage="/profile [tone|length|emoji] [value]",
    permission="user",
    category="personalization"
)
async def profile_command(args: str, user: dict, chat_id: int) -> str:
    """View or configure user profile."""
    from src.services.user_profile import (
        get_profile, create_profile, set_tone, set_response_length,
        toggle_emoji, format_profile_display
    )

    user_id = user.get("id")
    args_lower = args.lower().strip() if args else ""

    # Parse subcommands
    if args_lower.startswith("tone "):
        tone = args_lower.split(" ", 1)[1].strip()
        if tone in ["concise", "detailed", "casual", "formal"]:
            await set_tone(user_id, tone)
            return f"✓ Tone set to: <b>{tone}</b>"
        return "❌ Valid tones: concise, detailed, casual, formal"

    elif args_lower.startswith("length "):
        length = args_lower.split(" ", 1)[1].strip()
        if length in ["short", "medium", "long"]:
            await set_response_length(user_id, length)
            return f"✓ Response length set to: <b>{length}</b>"
        return "❌ Valid lengths: short, medium, long"

    elif args_lower == "emoji on":
        await toggle_emoji(user_id, True)
        return "✓ Emoji enabled in responses. 😊"

    elif args_lower == "emoji off":
        await toggle_emoji(user_id, False)
        return "✓ Emoji disabled in responses."

    else:
        # Show profile
        profile = await get_profile(user_id)
        if not profile:
            profile = await create_profile(user_id, user.get("first_name"))
        return format_profile_display(profile)


@command_router.command(
    name="/context",
    description="View or clear your work context",
    usage="/context [clear]",
    permission="user",
    category="personalization"
)
async def context_command(args: str, user: dict, chat_id: int) -> str:
    """View or clear work context."""
    from src.services.user_context import (
        get_context, clear_context, format_context_display
    )

    user_id = user.get("id")
    args_lower = args.lower().strip() if args else ""

    if args_lower == "clear":
        await clear_context(user_id)
        return "✓ Work context cleared."

    context = await get_context(user_id)
    if context:
        return format_context_display(context)
    return "<i>No work context captured yet. Keep chatting to build context!</i>"


@command_router.command(
    name="/macro",
    description="Manage your custom macros (shortcuts)",
    usage="/macro [list|show|add|remove] [args]",
    permission="user",
    category="personalization"
)
async def macro_command(args: str, user: dict, chat_id: int) -> str:
    """Manage user macros."""
    from src.services.user_macros import (
        get_macros, get_macro, create_macro, delete_macro,
        format_macros_list, format_macro_display
    )

    user_id = user.get("id")
    parts = args.split(maxsplit=1) if args else []
    subcmd = parts[0].lower() if parts else ""

    if not subcmd or subcmd == "list":
        macros = await get_macros(user_id)
        return format_macros_list(macros)

    elif subcmd == "show" and len(parts) > 1:
        macro_id = parts[1].strip()
        macro = await get_macro(user_id, macro_id)
        if macro:
            return format_macro_display(macro)
        return f"❌ Macro <code>{macro_id}</code> not found."

    elif subcmd == "add":
        # Format: /macro add "trigger" -> action
        if len(parts) < 2 or "->" not in parts[1]:
            return (
                "<b>Usage:</b> /macro add \"trigger phrase\" -> action\n\n"
                "<b>Examples:</b>\n"
                '/macro add "deploy" -> skill:planning Deploy to prod\n'
                '/macro add "status" -> command:modal app logs\n'
                '/macro add "morning" -> skill:summarize Daily standup'
            )

        content = parts[1]
        arrow_idx = content.index("->")
        trigger_part = content[:arrow_idx].strip()
        action_part = content[arrow_idx + 2:].strip()

        # Extract trigger (with or without quotes)
        trigger = trigger_part.strip('"').strip("'")

        # Determine action type
        if action_part.startswith("skill:"):
            action_type = "skill"
            action = action_part[6:].strip()
        elif action_part.startswith("command:"):
            action_type = "command"
            action = action_part[8:].strip()
        else:
            action_type = "skill"
            action = action_part

        macro = await create_macro(
            user_id=user_id,
            trigger_phrases=[trigger],
            action_type=action_type,
            action=action,
            description=f"Macro: {trigger}"
        )

        if macro:
            return f"✓ Created macro <code>{macro.macro_id}</code>\nTrigger: \"{trigger}\"\nAction: {action_type}:{action}"
        return "❌ Failed to create macro. Limit reached or duplicate trigger."

    elif subcmd == "remove" and len(parts) > 1:
        macro_id = parts[1].strip()
        success = await delete_macro(user_id, macro_id)
        if success:
            return f"✓ Deleted macro <code>{macro_id}</code>"
        return f"❌ Macro <code>{macro_id}</code> not found."

    else:
        return (
            "<b>Macro Commands:</b>\n\n"
            "/macro - List your macros\n"
            "/macro show <id> - Show macro details\n"
            "/macro add \"trigger\" -> action - Create macro\n"
            "/macro remove <id> - Delete macro"
        )


@command_router.command(
    name="/macros",
    description="Alias for /macro list",
    permission="user",
    category="personalization"
)
async def macros_command(args: str, user: dict, chat_id: int) -> str:
    """List all user macros (alias for /macro list)."""
    return await macro_command("list", user, chat_id)


@command_router.command(
    name="/activity",
    description="View your activity history and stats",
    usage="/activity [stats]",
    permission="user",
    category="personalization"
)
async def activity_command(args: str, user: dict, chat_id: int) -> str:
    """View activity history and statistics."""
    from src.services.activity import (
        get_recent_activities, get_activity_stats,
        format_activity_display, format_stats_display
    )

    user_id = user.get("id")
    args_lower = args.lower().strip() if args else ""

    if args_lower == "stats":
        stats = await get_activity_stats(user_id)
        return format_stats_display(stats)

    # Default: show recent activity
    activities = await get_recent_activities(user_id)
    return format_activity_display(activities)
