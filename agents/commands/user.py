"""User commands: general chat interactions and account management."""
from commands.router import command_router


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
        set_onboarding_step,
        OnboardingStep,
        build_welcome_message,
        build_welcome_keyboard,
        build_returning_message,
    )
    import sys

    name = user.get("first_name", "there")
    user_id = user.get("id")

    # Check if first-time user
    if await is_first_time_user(user_id):
        # Show interactive welcome with keyboard
        await set_onboarding_step(user_id, OnboardingStep.WELCOME)

        # Get send_telegram_keyboard from main module
        main = sys.modules.get("main")
        if main and hasattr(main, "send_telegram_keyboard"):
            await main.send_telegram_keyboard(
                chat_id,
                build_welcome_message(name),
                build_welcome_keyboard()
            )
            return None  # Message sent with keyboard

        # Fallback to text-only
        return build_welcome_message(name)

    # Returning user - brief welcome
    return build_returning_message(name)


@command_router.command(
    name="/help",
    description="Show available commands for your tier",
    permission="guest",
    category="general"
)
async def help_command(args: str, user: dict, chat_id: int) -> str:
    """Show help text based on user tier."""
    from src.core.state import get_state_manager
    state = get_state_manager()
    tier = await state.get_user_tier_cached(user.get("id"))
    return command_router.get_help_text(tier)


@command_router.command(
    name="/status",
    description="Show bot status, your tier, and circuit health",
    permission="guest",
    category="general"
)
async def status_command(args: str, user: dict, chat_id: int) -> str:
    """Show current bot status and user info."""
    from src.core.state import get_state_manager
    from src.core.resilience import get_circuit_status

    state = get_state_manager()
    tier = await state.get_user_tier_cached(user.get("id"))
    mode = await state.get_user_mode(user.get("id"))

    circuits = get_circuit_status()
    circuit_summary = ", ".join(f"{k}:{v}" for k, v in circuits.items())

    return f"""<b>Bot Status</b>

<b>User:</b> {user.get("first_name")}
<b>Tier:</b> {tier}
<b>Mode:</b> {mode}
<b>Circuits:</b> {circuit_summary}"""


@command_router.command(
    name="/tier",
    description="Check your current access tier and limits",
    permission="guest",
    category="general"
)
async def tier_command(args: str, user: dict, chat_id: int) -> str:
    """Show user's current tier and limits."""
    from src.core.state import get_state_manager
    from src.services.firebase import get_rate_limit

    state = get_state_manager()
    tier = await state.get_user_tier_cached(user.get("id"))
    limit = get_rate_limit(tier)

    tier_info = {
        "guest": "Basic access, rate limited",
        "user": "Standard access, more requests",
        "developer": "Full access, traces, circuits",
        "admin": "Admin access, all features"
    }

    return f"""<b>Your Tier:</b> {tier}

<b>Description:</b> {tier_info.get(tier, 'Unknown tier')}
<b>Rate Limit:</b> {limit} requests/min

Use /help to see available commands for your tier."""


@command_router.command(
    name="/forget",
    description="Delete all your personal data (GDPR compliance)",
    permission="guest",
    category="general"
)
async def forget_command(args: str, user: dict, chat_id: int) -> str:
    """Delete user's personal data with confirmation keyboard."""
    # Import here to avoid circular dependency
    from src.services.telegram import send_telegram_keyboard

    keyboard = [
        [
            {"text": "✅ Yes, delete everything", "callback_data": f"forget_confirm:{user.get('id')}"},
            {"text": "❌ Cancel", "callback_data": "forget_cancel"}
        ]
    ]

    await send_telegram_keyboard(
        chat_id,
        "⚠️ <b>Delete All Personal Data?</b>\n\n"
        "This will permanently delete:\n"
        "• Your profile and preferences\n"
        "• Work context\n"
        "• All macros\n"
        "• Activity history\n"
        "• Conversation memory\n\n"
        "<b>This cannot be undone.</b>",
        keyboard
    )
    return None  # Message sent with keyboard


@command_router.command(
    name="/clear",
    description="Clear conversation history",
    permission="user",
    category="general"
)
async def clear_command(args: str, user: dict, chat_id: int) -> str:
    """Clear user's conversation history."""
    from src.core.state import get_state_manager
    state = get_state_manager()
    await state.clear_conversation(user.get("id"))
    return "✓ Conversation history cleared."


@command_router.command(
    name="/cancel",
    description="Cancel pending operation",
    permission="user",
    category="general"
)
async def cancel_command(args: str, user: dict, chat_id: int) -> str:
    """Cancel any pending skill execution."""
    from src.core.state import get_state_manager
    state = get_state_manager()
    await state.clear_pending_skill(user.get("id"))
    return "✓ Operation cancelled."
