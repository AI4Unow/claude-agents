"""First-time user onboarding experience.

Provides interactive welcome flow with demo capabilities.
Detects first-time users and guides them through bot features.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class OnboardingStep(Enum):
    """Onboarding progress states."""
    NEW = "new"           # Never seen before
    WELCOME = "welcome"   # Saw welcome message
    DEMO = "demo"         # Tried a demo
    COMPLETE = "complete" # Onboarding finished


@dataclass
class OnboardingState:
    """User's onboarding progress."""
    step: OnboardingStep = OnboardingStep.NEW
    demos_tried: List[str] = field(default_factory=list)


async def is_first_time_user(user_id: int) -> bool:
    """Check if user has never used the bot.

    Args:
        user_id: Telegram user ID

    Returns:
        True if user has no history or onboarding state
    """
    from src.core.state import get_state_manager
    state = get_state_manager()

    # Check if user has any conversation history
    history = await state.get_conversation(str(user_id))
    if history and len(history) > 0:
        return False

    # Check onboarding state
    onboarding = await state.get("onboarding", str(user_id))
    return onboarding is None


async def get_onboarding_state(user_id: int) -> OnboardingState:
    """Get user's onboarding state.

    Args:
        user_id: Telegram user ID

    Returns:
        OnboardingState with current step and demos tried
    """
    from src.core.state import get_state_manager
    state = get_state_manager()

    data = await state.get("onboarding", str(user_id))
    if not data:
        return OnboardingState()

    return OnboardingState(
        step=OnboardingStep(data.get("step", "new")),
        demos_tried=data.get("demos_tried", [])
    )


async def set_onboarding_step(user_id: int, step: OnboardingStep) -> None:
    """Update onboarding step.

    Args:
        user_id: Telegram user ID
        step: New onboarding step
    """
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


async def mark_demo_tried(user_id: int, demo_type: str) -> None:
    """Mark that user tried a demo.

    Args:
        user_id: Telegram user ID
        demo_type: Type of demo tried (research, code, design)
    """
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
    """Build welcome message for new users.

    Args:
        name: User's first name

    Returns:
        Formatted welcome message HTML
    """
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
    """Build inline keyboard for welcome demos.

    Returns:
        Inline keyboard layout for Telegram
    """
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
    """Build message for returning users.

    Args:
        name: User's first name

    Returns:
        Formatted welcome back message HTML
    """
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
    """Get demo prompt for a category.

    Args:
        demo_type: Type of demo (research, code, design)

    Returns:
        Demo prompt string or None
    """
    return DEMO_PROMPTS.get(demo_type)
